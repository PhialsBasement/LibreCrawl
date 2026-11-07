"""Link management and extraction"""
import threading
from urllib.parse import urljoin, urlparse
from collections import deque


def normalize_url(url):
    """Normalize a URL for deduplication: strip fragments and give bare domains a '/' path
    so e.g. https://example.com and https://example.com/ dedupe to one URL"""
    parsed = urlparse(url)
    clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path or '/'}"
    if parsed.query:
        clean_url += f"?{parsed.query}"
    return clean_url


class LinkManager:
    """Manages link discovery, tracking, and extraction"""

    def __init__(self, base_domain, event_log=None):
        self.base_domain = base_domain
        # Journal for incremental UI sync. Links are emitted while links_lock
        # is held so a status backfill can never be announced before the link
        # it refers to.
        self.event_log = event_log
        self.visited_urls = set()
        self.discovered_urls = deque()
        self.all_discovered_urls = set()
        self.all_links = []
        self.links_set = set()
        # target_url -> {source_url: None}, an ordered set
        self.source_pages = {}

        # Incremental indexes for target status backfill, so each
        # result and each link is processed once (see _sync_statuses)
        self._status = {}
        self._status_src = None
        self._status_len = 0
        self._by_target = {}
        self._indexed_links = None
        self._indexed_len = 0

        self.urls_lock = threading.Lock()
        self.links_lock = threading.Lock()

    def _add_source(self, target_url, source_url):
        """Record a source page for target_url. Caller holds urls_lock."""
        sources = self.source_pages.get(target_url)
        if sources is None:
            sources = self.source_pages[target_url] = {}
        sources[source_url] = None

    def extract_links(self, soup, current_url, depth, should_crawl_callback, include_images=False, base_url=None):
        """Extract links from HTML and add to discovery queue.

        base_url overrides the URL relative hrefs resolve against — required
        when the page was reached via redirect, because its content lives at
        a different URL than the one that was requested.
        """
        resolve_base = base_url or current_url
        links = soup.find_all('a', href=True)

        for link in links:
            href = link['href'].strip()
            if not href or href.startswith('#') or href.startswith('mailto:') or href.startswith('tel:'):
                continue

            # Convert relative URLs to absolute and drop the fragment. One
            # malformed href (e.g. "http://[bad/") is skipped; it must not
            # take the rest of the page's links down with it.
            try:
                clean_url = normalize_url(urljoin(resolve_base, href))
            except ValueError:
                continue

            # Thread-safe checking and adding
            with self.urls_lock:
                self._add_source(clean_url, current_url)

                if (clean_url not in self.visited_urls and
                    clean_url not in self.all_discovered_urls and
                    clean_url != current_url):

                    # Check if this URL should be crawled
                    if should_crawl_callback(clean_url):
                        self.all_discovered_urls.add(clean_url)
                        self.discovered_urls.append((clean_url, depth))

        # Optionally queue images as crawl targets (full download)
        if not include_images:
            return

        imgs = soup.find_all('img', src=True)
        for img in imgs:
            src = img.get('src', '').strip()
            if not src or src.startswith('data:'):
                continue

            try:
                absolute_url = urljoin(resolve_base, src)
                parsed = urlparse(absolute_url)

                if parsed.scheme not in ('http', 'https'):
                    continue

                clean_url = normalize_url(absolute_url)

                with self.urls_lock:
                    self._add_source(clean_url, current_url)

                    if (clean_url not in self.visited_urls and
                        clean_url not in self.all_discovered_urls and
                        clean_url != current_url):

                        if should_crawl_callback(clean_url):
                            self.all_discovered_urls.add(clean_url)
                            self.discovered_urls.append((clean_url, depth))
            except Exception:
                continue

    def collect_all_links(self, soup, source_url, crawl_results, base_url=None):
        """Collect all links for the Links tab display.

        base_url overrides the URL relative hrefs resolve against (for pages
        reached via redirect); source_url stays the requested URL so link
        attribution matches the results table.

        Returns the links newly added by this call, so callers don't have to
        diff all_links by index (which is racy with concurrent workers).
        """
        candidates = []
        resolve_base = base_url or source_url
        links = soup.find_all('a', href=True)

        for link in links:
            href = link['href'].strip()
            if not href or href.startswith('#'):
                continue

            # Get anchor text
            anchor_text = link.get_text().strip()[:100]

            # Image-only anchors carry their alt text as the inlink label
            anchor_alt = ''
            img = link.find('img')
            if img and img.get('alt'):
                anchor_alt = img.get('alt').strip()[:100]

            # Handle special link types
            if href.startswith('mailto:') or href.startswith('tel:'):
                continue

            # Convert relative URLs to absolute
            try:
                absolute_url = urljoin(resolve_base, href)
                parsed_target = urlparse(absolute_url)

                # Clean URL (remove fragment)
                clean_url = normalize_url(absolute_url)

                # Determine if link is internal or external
                target_domain_clean = parsed_target.netloc.replace('www.', '', 1)
                base_domain_clean = self.base_domain.replace('www.', '', 1)
                is_internal = target_domain_clean == base_domain_clean

                # Determine placement (navigation, footer, body)
                placement = self._detect_link_placement(link)

                link_data = {
                    'source_url': source_url,
                    'target_url': clean_url,
                    'anchor_text': anchor_text or '(no text)',
                    'anchor_alt': anchor_alt,
                    'is_internal': is_internal,
                    'target_domain': parsed_target.netloc,
                    'target_status': None,  # filled in by _commit_links
                    'placement': placement
                }

                # Track source page for this URL (for "Linked From" feature)
                with self.urls_lock:
                    self._add_source(clean_url, source_url)

                candidates.append(link_data)

            except Exception:
                continue

        # Also collect <img src> as links so broken images are discoverable
        imgs = soup.find_all('img', src=True)
        for img in imgs:
            src = img.get('src', '').strip()
            if not src or src.startswith('data:'):
                continue

            # keep "decorative" apart from "no attribute" (issue #95)
            raw_alt = img.get('alt')
            alt_text = (raw_alt or '').strip()[:100]
            if not alt_text:
                alt_text = '(decorative)' if raw_alt is not None else '(no alt attribute)'

            try:
                absolute_url = urljoin(resolve_base, src)
                parsed_target = urlparse(absolute_url)

                # Only HTTP(S) images
                if parsed_target.scheme not in ('http', 'https'):
                    continue

                clean_url = normalize_url(absolute_url)

                target_domain_clean = parsed_target.netloc.replace('www.', '', 1)
                base_domain_clean = self.base_domain.replace('www.', '', 1)
                is_internal = target_domain_clean == base_domain_clean

                link_data = {
                    'source_url': source_url,
                    'target_url': clean_url,
                    'anchor_text': alt_text,
                    'is_internal': is_internal,
                    'target_domain': parsed_target.netloc,
                    'target_status': None,
                    'placement': 'image'
                }

                candidates.append(link_data)

            except Exception:
                continue

        return self._commit_links(candidates, crawl_results)

    def _commit_links(self, candidates, crawl_results):
        """Append new links and journal them in one locked step.

        Emitting inside links_lock is what keeps update_link_statuses from
        announcing a status backfill for a link the UI has not received yet.
        """
        new_links = []
        with self.links_lock:
            # Backfills for links already sent, and fresh statuses
            # for the new ones before they are sent
            changed = self._sync_statuses(crawl_results)
            for link_data in candidates:
                link_key = f"{link_data['source_url']}|{link_data['target_url']}"
                if link_key not in self.links_set:
                    self.links_set.add(link_key)
                    target = link_data['target_url']
                    if target in self._status:
                        link_data['target_status'] = self._status[target]
                    self.all_links.append(link_data)
                    new_links.append(link_data)

            if self.event_log:
                if changed:
                    self.event_log.emit_many('link_update', changed)
                if new_links:
                    self.event_log.emit_many('link', new_links)

        return new_links

    def _sync_statuses(self, crawl_results):
        """Apply results and links added since the last call.

        Caller holds links_lock. Returns the links whose
        target_status changed. Falls back to a full pass when
        either list was replaced or cleared.
        """
        full = False
        links = self.all_links
        if links is not self._indexed_links or len(links) < self._indexed_len:
            self._by_target = {}
            self._indexed_links = links
            self._indexed_len = 0
            full = True
        if crawl_results is not self._status_src or len(crawl_results) < self._status_len:
            self._status = {}
            self._status_src = crawl_results
            self._status_len = 0
            full = True

        new_results = crawl_results[self._status_len:]
        self._status_len += len(new_results)
        for result in new_results:
            self._status[result['url']] = result['status_code']

        new_links = links[self._indexed_len:]
        self._indexed_len += len(new_links)
        for link in new_links:
            self._by_target.setdefault(link['target_url'], []).append(link)

        if full:
            candidates = links
        else:
            candidates = list(new_links)
            for result in new_results:
                candidates.extend(self._by_target.get(result['url'], ()))

        changed = []
        for link in candidates:
            target = link['target_url']
            if target in self._status and link['target_status'] != self._status[target]:
                link['target_status'] = self._status[target]
                changed.append(link)
        return changed

    def _detect_link_placement(self, link_element):
        """Detect where on the page a link is placed"""
        # Check parent elements up the tree
        current = link_element.parent

        while current and current.name:
            # Check for footer
            if current.name == 'footer':
                return 'footer'

            # Check for footer by class/id
            classes = current.get('class', [])
            element_id = current.get('id', '')
            classes_str = ' '.join(classes).lower() if classes else ''

            if 'footer' in classes_str or 'footer' in element_id.lower():
                return 'footer'

            # Check for navigation
            if current.name in ['nav', 'header']:
                return 'navigation'

            # Check for navigation by class/id
            if any(keyword in classes_str or keyword in element_id.lower()
                   for keyword in ['nav', 'menu', 'header']):
                return 'navigation'

            current = current.parent

        # Default to body if not in nav or footer
        return 'body'

    def is_internal(self, url):
        """Check if URL is internal to the base domain"""
        parsed_url = urlparse(url)
        url_domain_clean = parsed_url.netloc.replace('www.', '', 1)
        base_domain_clean = self.base_domain.replace('www.', '', 1)
        return url_domain_clean == base_domain_clean

    def add_url(self, url, depth):
        """Add a URL to the discovery queue"""
        url = normalize_url(url)
        with self.urls_lock:
            if url not in self.all_discovered_urls and url not in self.visited_urls:
                self.all_discovered_urls.add(url)
                self.discovered_urls.append((url, depth))

    def mark_discovered(self, url):
        """Count a URL as discovered without queueing it.

        Image rows synthesized from HEAD checks are real results but were never
        queued, so without this the "URLs Discovered" counter sits at the HTML
        page count while the crawled count climbs past it.
        """
        with self.urls_lock:
            self.all_discovered_urls.add(normalize_url(url))

    def mark_visited(self, url):
        """Mark a URL as visited"""
        with self.urls_lock:
            self.visited_urls.add(url)

    def get_next_url(self):
        """Get the next URL to crawl"""
        with self.urls_lock:
            if self.discovered_urls:
                return self.discovered_urls.popleft()
        return None

    def get_stats(self):
        """Get current statistics"""
        with self.urls_lock:
            return {
                'discovered': len(self.all_discovered_urls),
                'visited': len(self.visited_urls),
                'pending': len(self.discovered_urls)
            }

    def update_link_statuses(self, crawl_results):
        """Update target_status for all links based on crawl results.

        Returns the links whose status actually changed, so callers can
        emit update events for just those.
        """
        with self.links_lock:
            changed = self._sync_statuses(crawl_results)

            # Inside the lock: a link is only ever updated after its own
            # 'link' event has been journalled
            if changed and self.event_log:
                self.event_log.emit_many('link_update', changed)
        return changed

    def get_source_pages(self, url):
        """Get list of source pages that link to this URL"""
        with self.urls_lock:
            return list(self.source_pages.get(url, ()))

    def reset(self):
        """Reset all state"""
        with self.urls_lock:
            self.visited_urls.clear()
            self.discovered_urls.clear()
            self.all_discovered_urls.clear()
            self.source_pages.clear()

        with self.links_lock:
            self.all_links.clear()
            self.links_set.clear()
