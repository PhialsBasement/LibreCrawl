"""Link management and extraction"""
import threading
from urllib.parse import urljoin, urlparse
from collections import deque


class LinkManager:
    """Manages link discovery, tracking, and extraction"""

    def __init__(self, base_domain):
        self.base_domain = base_domain
        self.visited_urls = set()
        self.discovered_urls = deque()
        self.all_discovered_urls = set()
        self.all_links = []
        self.links_set = set()

        self.urls_lock = threading.Lock()
        self.links_lock = threading.Lock()

    def extract_links(self, soup, current_url, depth, should_crawl_callback):
        """Extract links from HTML and add to discovery queue"""
        links = soup.find_all('a', href=True)

        for link in links:
            href = link['href'].strip()
            if not href or href.startswith('#') or href.startswith('mailto:') or href.startswith('tel:'):
                continue

            # Convert relative URLs to absolute
            absolute_url = urljoin(current_url, href)

            # Clean URL (remove fragment)
            parsed = urlparse(absolute_url)
            clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            if parsed.query:
                clean_url += f"?{parsed.query}"

            # Thread-safe checking and adding
            with self.urls_lock:
                if (clean_url not in self.visited_urls and
                    clean_url not in self.all_discovered_urls and
                    clean_url != current_url):

                    # Check if this URL should be crawled
                    if should_crawl_callback(clean_url):
                        self.all_discovered_urls.add(clean_url)
                        self.discovered_urls.append((clean_url, depth))

    def collect_all_links(self, soup, source_url, crawl_results):
        """Collect all links for the Links tab display"""
        links = soup.find_all('a', href=True)

        for link in links:
            href = link['href'].strip()
            if not href or href.startswith('#'):
                continue

            # Get anchor text
            anchor_text = link.get_text().strip()[:100]

            # Handle special link types
            if href.startswith('mailto:') or href.startswith('tel:'):
                continue

            # Convert relative URLs to absolute
            try:
                absolute_url = urljoin(source_url, href)
                parsed_target = urlparse(absolute_url)

                # Clean URL (remove fragment)
                clean_url = f"{parsed_target.scheme}://{parsed_target.netloc}{parsed_target.path}"
                if parsed_target.query:
                    clean_url += f"?{parsed_target.query}"

                # Determine if link is internal or external
                target_domain_clean = parsed_target.netloc.replace('www.', '', 1)
                base_domain_clean = self.base_domain.replace('www.', '', 1)
                is_internal = target_domain_clean == base_domain_clean

                # Find the status of the target URL if we've crawled it
                target_status = None
                for result in crawl_results:
                    if result['url'] == clean_url:
                        target_status = result['status_code']
                        break

                link_data = {
                    'source_url': source_url,
                    'target_url': clean_url,
                    'anchor_text': anchor_text or '(no text)',
                    'is_internal': is_internal,
                    'target_domain': parsed_target.netloc,
                    'target_status': target_status
                }

                # Thread-safe adding to links collection with duplicate checking
                with self.links_lock:
                    link_key = f"{link_data['source_url']}|{link_data['target_url']}"

                    if link_key not in self.links_set:
                        self.links_set.add(link_key)
                        self.all_links.append(link_data)

            except Exception:
                continue

    def is_internal(self, url):
        """Check if URL is internal to the base domain"""
        parsed_url = urlparse(url)
        url_domain_clean = parsed_url.netloc.replace('www.', '', 1)
        base_domain_clean = self.base_domain.replace('www.', '', 1)
        return url_domain_clean == base_domain_clean

    def add_url(self, url, depth):
        """Add a URL to the discovery queue"""
        with self.urls_lock:
            if url not in self.all_discovered_urls and url not in self.visited_urls:
                self.all_discovered_urls.add(url)
                self.discovered_urls.append((url, depth))

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
        """Update target_status for all links based on crawl results"""
        # Build a fast lookup dict
        status_lookup = {result['url']: result['status_code'] for result in crawl_results}

        with self.links_lock:
            for link in self.all_links:
                target_url = link['target_url']
                if target_url in status_lookup:
                    link['target_status'] = status_lookup[target_url]

    def reset(self):
        """Reset all state"""
        with self.urls_lock:
            self.visited_urls.clear()
            self.discovered_urls.clear()
            self.all_discovered_urls.clear()

        with self.links_lock:
            self.all_links.clear()
            self.links_set.clear()
