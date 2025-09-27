import requests
import threading
import time
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from collections import deque
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import queue
import xml.etree.ElementTree as ET
import gzip
from datetime import datetime

class WebCrawler:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'LibreCrawl/1.0 (Web Crawler)'
        })

        self.base_url = None
        self.base_domain = None
        self.visited_urls = set()
        self.discovered_urls = deque()
        self.crawl_results = []
        self.all_links = []  # Store all links found during crawling
        self.links_set = set()  # Track unique link combinations for faster duplicate checking
        self.results_lock = threading.Lock()
        self.urls_lock = threading.Lock()
        self.links_lock = threading.Lock()

        self.is_running = False
        self.is_paused = False
        self.is_running_pagespeed = False

        # Default configuration
        self.config = {
            'max_depth': 3,
            'max_urls': 1000,
            'delay': 1.0,
            'follow_redirects': True,
            'crawl_external': False,
            'user_agent': 'LibreCrawl/1.0 (Web Crawler)',
            'timeout': 10,
            'retries': 3,
            'accept_language': 'en-US,en;q=0.9',
            'respect_robots': True,
            'allow_cookies': True,
            'include_extensions': ['html', 'htm', 'php', 'asp', 'aspx', 'jsp'],
            'exclude_extensions': ['pdf', 'doc', 'docx', 'zip', 'exe', 'dmg'],
            'include_patterns': [],
            'exclude_patterns': [],
            'max_file_size': 50 * 1024 * 1024,  # 50MB
            'concurrency': 5,
            'memory_limit': 512 * 1024 * 1024,  # 512MB
            'log_level': 'INFO',
            'enable_proxy': False,
            'proxy_url': None,
            'custom_headers': {},
            'discover_sitemaps': True,
            'enable_pagespeed': False
        }

        self.stats = {
            'discovered': 0,
            'crawled': 0,
            'depth': 0,
            'speed': 0.0,
            'start_time': None
        }

        self.crawl_thread = None

    def start_crawl(self, url):
        """Start crawling from the given URL"""
        if self.is_running:
            return False, "Crawl already in progress"

        try:
            # Validate and normalize URL
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url

            parsed = urlparse(url)
            self.base_url = f"{parsed.scheme}://{parsed.netloc}"
            self.base_domain = parsed.netloc

            # Reset state
            self.visited_urls.clear()
            self.discovered_urls.clear()
            self.crawl_results.clear()
            self.all_links.clear()
            self.links_set.clear()
            self._all_discovered_urls = set()

            self.stats = {
                'discovered': 0,  # Start at 0, will be incremented
                'crawled': 0,
                'depth': 0,
                'speed': 0.0,
                'start_time': time.time()
            }

            # Add initial URL
            self.discovered_urls.append((url, 0))
            self._all_discovered_urls.add(url)
            self.stats['discovered'] = 1

            # Discover sitemaps if enabled
            if self.config.get('discover_sitemaps', True):
                print(f"Starting sitemap discovery for {url}")
                self._discover_sitemaps(url)
                print(f"Sitemap discovery completed. Total discovered URLs: {self.stats['discovered']}")
                print(f"URLs in queue: {len(self.discovered_urls)}")

            # Start crawling in separate thread
            self.is_running = True
            self.crawl_thread = threading.Thread(target=self._crawl_worker)
            self.crawl_thread.start()

            return True, "Crawl started successfully"

        except Exception as e:
            return False, f"Error starting crawl: {str(e)}"

    def stop_crawl(self):
        """Stop the current crawl"""
        self.is_running = False
        self.is_paused = False
        if self.crawl_thread and self.crawl_thread.is_alive():
            self.crawl_thread.join(timeout=5)
        return True, "Crawl stopped"

    def pause_crawl(self):
        """Pause the current crawl"""
        if not self.is_running:
            return False, "No crawl in progress"
        self.is_paused = True
        return True, "Crawl paused"

    def resume_crawl(self):
        """Resume the paused crawl"""
        if not self.is_running:
            return False, "No crawl in progress"
        if not self.is_paused:
            return False, "Crawl is not paused"
        self.is_paused = False
        return True, "Crawl resumed"

    def get_status(self):
        """Get current crawl status and results"""
        status = 'completed' if not self.is_running and self.stats['crawled'] > 0 else 'running'
        if not self.is_running and self.stats['crawled'] == 0:
            status = 'idle'

        # Calculate speed
        if self.stats['start_time']:
            elapsed = time.time() - self.stats['start_time']
            self.stats['speed'] = round(self.stats['crawled'] / max(elapsed, 1), 2)

        return {
            'status': status,
            'stats': self.stats.copy(),
            'urls': self.crawl_results.copy(),
            'links': self.all_links.copy(),
            'progress': min(100, (self.stats['crawled'] / max(self.stats['discovered'], 1)) * 100),
            'is_running_pagespeed': self.is_running_pagespeed
        }

    def _crawl_worker(self):
        """Main crawling worker thread with concurrent execution"""
        max_workers = self.config.get('concurrency', 5)
        consecutive_empty_iterations = 0
        max_empty_iterations = 3
        last_crawled_count = 0
        no_progress_iterations = 0
        max_no_progress = 10  # Force stop after 10 iterations with no progress

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            active_futures = set()

            while self.is_running:
                try:
                    # Check if crawl is paused
                    if self.is_paused:
                        time.sleep(1)
                        continue

                    # Submit new tasks if we have space and URLs
                    while (len(active_futures) < max_workers and
                           self.discovered_urls and
                           self.is_running and
                           self.stats['crawled'] < self.config['max_urls']):

                        with self.urls_lock:
                            if not self.discovered_urls:
                                break
                            current_url, depth = self.discovered_urls.popleft()

                        # Skip if already visited or depth exceeded
                        if current_url in self.visited_urls or depth > self.config['max_depth']:
                            continue

                        # Mark as visited immediately to prevent duplicates
                        with self.urls_lock:
                            self.visited_urls.add(current_url)

                        # Submit crawl task
                        future = executor.submit(self._crawl_url_with_delay, current_url, depth)
                        active_futures.add(future)
                        consecutive_empty_iterations = 0

                    # Process completed tasks
                    if active_futures:
                        completed_futures = set()
                        try:
                            # Use timeout to avoid blocking forever
                            for future in as_completed(active_futures, timeout=1):
                                completed_futures.add(future)
                                try:
                                    result = future.result()
                                    if result:
                                        with self.results_lock:
                                            self.crawl_results.append(result)
                                            self.stats['crawled'] += 1
                                            self.stats['depth'] = max(self.stats['depth'], result.get('depth', 0))
                                except Exception as e:
                                    print(f"Error in crawl task: {e}")
                        except:
                            # Timeout occurred, no completed futures
                            pass

                        # Remove completed futures
                        active_futures -= completed_futures

                    # Check for completion conditions
                    if not self.discovered_urls and not active_futures:
                        consecutive_empty_iterations += 1
                        if consecutive_empty_iterations >= max_empty_iterations:
                            print("No more URLs to crawl, stopping...")
                            break
                        time.sleep(1)
                    else:
                        consecutive_empty_iterations = 0

                    if self.stats['crawled'] >= self.config['max_urls']:
                        print(f"Reached maximum URLs limit ({self.config['max_urls']}), stopping...")
                        break

                    # Force stop if not running (user stopped)
                    if not self.is_running:
                        print("Crawl stopped by user")
                        break

                    # Check for no progress (safety mechanism)
                    if self.stats['crawled'] == last_crawled_count:
                        no_progress_iterations += 1
                        if no_progress_iterations >= max_no_progress:
                            print(f"No progress for {max_no_progress} iterations, forcing stop...")
                            break
                    else:
                        no_progress_iterations = 0
                        last_crawled_count = self.stats['crawled']

                    # Small delay to prevent tight loop
                    time.sleep(0.1)

                except Exception as e:
                    print(f"Error in crawl worker: {e}")
                    time.sleep(1)

        # Run PageSpeed analysis if enabled
        if self.config.get('enable_pagespeed', False):
            print("Running PageSpeed analysis...")
            self.is_running_pagespeed = True
            self._run_pagespeed_analysis()
            self.is_running_pagespeed = False

        # Mark crawl as complete
        self.is_running = False
        print(f"Crawl completed. Discovered: {self.stats['discovered']}, Crawled: {self.stats['crawled']}")

    def _crawl_url_with_delay(self, url, depth):
        """Wrapper for _crawl_url with delay handling"""
        result = self._crawl_url(url, depth)

        # Apply delay after crawling if configured
        if self.config['delay'] > 0:
            time.sleep(self.config['delay'])

        return result

    def update_config(self, new_config):
        """Update crawler configuration"""
        self.config.update(new_config)

        # Update session headers
        self.session.headers.update({
            'User-Agent': self.config['user_agent'],
            'Accept-Language': self.config['accept_language']
        })

        # Add custom headers
        if self.config['custom_headers']:
            self.session.headers.update(self.config['custom_headers'])

        # Configure proxy if enabled
        if self.config['enable_proxy'] and self.config['proxy_url']:
            self.session.proxies = {
                'http': self.config['proxy_url'],
                'https': self.config['proxy_url']
            }
        else:
            self.session.proxies = {}

    def _crawl_url(self, url, depth):
        """Crawl a single URL and extract information"""
        retries = self.config.get('retries', 3)
        last_exception = None

        try:
            for attempt in range(retries + 1):
                try:
                    # First, do a HEAD request to check file size if configured
                    if self.config.get('max_file_size', 0) > 0:
                        head_response = self.session.head(
                            url,
                            timeout=self.config['timeout'],
                            allow_redirects=self.config['follow_redirects']
                        )
                        content_length = head_response.headers.get('content-length')
                        if content_length and int(content_length) > self.config['max_file_size']:
                            return {
                                'url': url,
                                'status_code': 0,
                                'content_type': '',
                                'size': 0,
                                'is_internal': False,
                                'depth': depth,
                                'title': '',
                                'meta_description': '',
                                'h1': '',
                                'word_count': 0,
                                'error': f'File too large: {content_length} bytes (limit: {self.config["max_file_size"]})'
                            }

                    response = self.session.get(
                        url,
                        timeout=self.config['timeout'],
                        allow_redirects=self.config['follow_redirects']
                    )
                    break  # Success, exit retry loop

                except Exception as e:
                    last_exception = e
                    if attempt < retries:
                        time.sleep(1)  # Wait before retry
                        continue
                    else:
                        # All retries exhausted
                        raise e

            # Determine if URL is internal
            parsed_url = urlparse(url)
            # Handle www vs non-www domains
            url_domain_clean = parsed_url.netloc.replace('www.', '', 1)
            base_domain_clean = self.base_domain.replace('www.', '', 1)
            is_internal = url_domain_clean == base_domain_clean

            result = {
                'url': url,
                'status_code': response.status_code,
                'content_type': response.headers.get('content-type', '').split(';')[0],
                'size': len(response.content),
                'is_internal': is_internal,
                'depth': depth,
                'title': '',
                'meta_description': '',
                'h1': '',
                'h2': [],
                'h3': [],
                'word_count': 0,
                'meta_tags': {},
                'og_tags': {},
                'twitter_tags': {},
                'canonical_url': '',
                'lang': '',
                'charset': '',
                'viewport': '',
                'robots': '',
                'author': '',
                'keywords': '',
                'generator': '',
                'theme_color': '',
                'json_ld': [],
                'analytics': {
                    'google_analytics': False,
                    'gtag': False,
                    'ga4_id': '',
                    'gtm_id': '',
                    'facebook_pixel': False,
                    'hotjar': False,
                    'mixpanel': False
                },
                'images': [],
                'external_links': 0,
                'internal_links': 0,
                'response_time': 0,
                'redirects': [],
                'hreflang': [],
                'schema_org': []
            }

            # Track response time
            start_time = time.time()

            # Only parse HTML content
            if 'text/html' in response.headers.get('content-type', ''):
                soup = BeautifulSoup(response.content, 'html.parser')

                # Extract comprehensive data
                self._extract_basic_seo_data(soup, result)
                self._extract_meta_tags(soup, result)
                self._extract_opengraph_tags(soup, result)
                self._extract_twitter_tags(soup, result)
                self._extract_json_ld(soup, result)
                self._extract_analytics_tracking(soup, response.text, result)
                self._extract_images(soup, url, result)
                self._extract_link_counts(soup, result)
                self._extract_hreflang(soup, result)
                self._extract_schema_org(soup, result)

            result['response_time'] = round((time.time() - start_time) * 1000, 2)  # ms

            # Extract and store all links for the Links tab
            self._collect_all_links(soup, url)

            # Extract links for further crawling
            # Only for internal pages, unless external crawling is enabled
            should_extract_links = (
                (is_internal and depth < self.config['max_depth']) or
                (self.config['crawl_external'] and depth < self.config['max_depth'])
            )

            if should_extract_links:
                self._extract_links(soup, url, depth + 1)

            return result

        except Exception as e:
            return {
                'url': url,
                'status_code': 0,
                'content_type': '',
                'size': 0,
                'is_internal': False,
                'depth': depth,
                'title': '',
                'meta_description': '',
                'h1': '',
                'word_count': 0,
                'error': str(e)
            }

    def _extract_links(self, soup, current_url, depth):
        """Extract links from HTML and add to discovery queue"""
        links = soup.find_all('a', href=True)

        # Keep track of URLs we've already queued in this session
        if not hasattr(self, '_all_discovered_urls'):
            self._all_discovered_urls = set()

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
                # Skip if already discovered, visited, or queued
                if (clean_url not in self.visited_urls and
                    clean_url not in self._all_discovered_urls and
                    clean_url != current_url):

                    # Check if this URL should be crawled based on settings
                    if self._should_crawl_url(clean_url):
                        # Add to our tracking set
                        self._all_discovered_urls.add(clean_url)

                        # Add to queue
                        self.discovered_urls.append((clean_url, depth))
                        self.stats['discovered'] += 1

    def _collect_all_links(self, soup, source_url):
        """Collect all links for the Links tab display"""
        links = soup.find_all('a', href=True)

        for link in links:
            href = link['href'].strip()
            if not href or href.startswith('#'):
                continue

            # Get anchor text
            anchor_text = link.get_text().strip()[:100]  # Limit length

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
                for result in self.crawl_results:
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
                    # Create unique key for source+target combination
                    link_key = f"{link_data['source_url']}|{link_data['target_url']}"

                    # Only add if not already seen
                    if link_key not in self.links_set:
                        self.links_set.add(link_key)
                        self.all_links.append(link_data)

            except Exception as e:
                # Skip malformed URLs
                continue

    def _should_crawl_url(self, url):
        """Check if URL should be crawled based on current settings"""
        parsed = urlparse(url)

        # Check external domain policy
        if not self.config['crawl_external']:
            # Handle www vs non-www domains
            url_domain = parsed.netloc
            base_domain = self.base_domain

            # Normalize domains by removing www prefix
            url_domain_clean = url_domain.replace('www.', '', 1)
            base_domain_clean = base_domain.replace('www.', '', 1)

            if url_domain_clean != base_domain_clean:
                return False

        # Check robots.txt if enabled
        if self.config['respect_robots']:
            if not self._check_robots_txt(url):
                return False

        # Check file extensions
        path = parsed.path.lower()
        if '.' in path:
            extension = path.split('.')[-1]

            # Check excluded extensions
            if extension in self.config['exclude_extensions']:
                return False

            # Check included extensions (if specified)
            if self.config['include_extensions'] and extension not in self.config['include_extensions']:
                return False

        # Check URL patterns
        if self.config['exclude_patterns']:
            for pattern in self.config['exclude_patterns']:
                if pattern and re.search(pattern, url):
                    return False

        if self.config['include_patterns']:
            pattern_match = False
            for pattern in self.config['include_patterns']:
                if pattern and re.search(pattern, url):
                    pattern_match = True
                    break
            if not pattern_match:
                return False

        return True

    def _check_robots_txt(self, url):
        """Check if URL is allowed by robots.txt"""
        try:
            from urllib.robotparser import RobotFileParser

            parsed = urlparse(url)
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

            # Cache robots.txt parsers
            if not hasattr(self, '_robots_cache'):
                self._robots_cache = {}

            if robots_url not in self._robots_cache:
                rp = RobotFileParser()
                rp.set_url(robots_url)
                try:
                    rp.read()
                    self._robots_cache[robots_url] = rp
                except:
                    # If robots.txt can't be fetched, allow crawling
                    return True

            rp = self._robots_cache[robots_url]
            user_agent = self.config.get('user_agent', '*')
            return rp.can_fetch(user_agent, url)

        except Exception:
            # If robots.txt checking fails, allow crawling
            return True

    def _extract_basic_seo_data(self, soup, result):
        """Extract basic SEO data (title, h1-h3, meta description, etc.)"""
        # Extract title
        title_tag = soup.find('title')
        result['title'] = title_tag.get_text().strip() if title_tag else ''

        # Extract meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        result['meta_description'] = meta_desc.get('content', '').strip() if meta_desc else ''

        # Extract headings
        h1_tag = soup.find('h1')
        result['h1'] = h1_tag.get_text().strip() if h1_tag else ''

        h2_tags = soup.find_all('h2')
        result['h2'] = [h2.get_text().strip() for h2 in h2_tags[:10]]  # Limit to first 10

        h3_tags = soup.find_all('h3')
        result['h3'] = [h3.get_text().strip() for h3 in h3_tags[:10]]  # Limit to first 10

        # Count words
        text_content = soup.get_text()
        words = re.findall(r'\b\w+\b', text_content)
        result['word_count'] = len(words)

        # Extract language
        html_tag = soup.find('html')
        result['lang'] = html_tag.get('lang', '') if html_tag else ''

        # Extract charset
        charset_meta = soup.find('meta', attrs={'charset': True})
        if charset_meta:
            result['charset'] = charset_meta.get('charset', '')
        else:
            content_type_meta = soup.find('meta', attrs={'http-equiv': 'Content-Type'})
            if content_type_meta:
                content = content_type_meta.get('content', '')
                charset_match = re.search(r'charset=([^;]+)', content)
                result['charset'] = charset_match.group(1) if charset_match else ''

    def _extract_meta_tags(self, soup, result):
        """Extract all meta tags"""
        meta_tags = soup.find_all('meta')

        for meta in meta_tags:
            name = meta.get('name', '').lower()
            property_attr = meta.get('property', '').lower()
            content = meta.get('content', '')

            if name:
                result['meta_tags'][name] = content

                # Extract specific important meta tags
                if name == 'viewport':
                    result['viewport'] = content
                elif name == 'robots':
                    result['robots'] = content
                elif name == 'author':
                    result['author'] = content
                elif name == 'keywords':
                    result['keywords'] = content
                elif name == 'generator':
                    result['generator'] = content
                elif name == 'theme-color':
                    result['theme_color'] = content

        # Extract canonical URL
        canonical = soup.find('link', attrs={'rel': 'canonical'})
        result['canonical_url'] = canonical.get('href', '') if canonical else ''

    def _extract_opengraph_tags(self, soup, result):
        """Extract OpenGraph meta tags"""
        og_metas = soup.find_all('meta', attrs={'property': re.compile(r'^og:')})

        for meta in og_metas:
            property_name = meta.get('property', '')
            content = meta.get('content', '')
            if property_name:
                # Remove 'og:' prefix for cleaner keys
                key = property_name.replace('og:', '')
                result['og_tags'][key] = content

    def _extract_twitter_tags(self, soup, result):
        """Extract Twitter Card meta tags"""
        twitter_metas = soup.find_all('meta', attrs={'name': re.compile(r'^twitter:')})

        for meta in twitter_metas:
            name = meta.get('name', '')
            content = meta.get('content', '')
            if name:
                # Remove 'twitter:' prefix for cleaner keys
                key = name.replace('twitter:', '')
                result['twitter_tags'][key] = content

    def _extract_json_ld(self, soup, result):
        """Extract JSON-LD structured data"""
        import json

        json_ld_scripts = soup.find_all('script', attrs={'type': 'application/ld+json'})

        for script in json_ld_scripts:
            try:
                json_data = json.loads(script.string)
                result['json_ld'].append(json_data)
            except (json.JSONDecodeError, AttributeError):
                continue

    def _extract_analytics_tracking(self, soup, html_content, result):
        """Detect analytics and tracking scripts"""
        # Google Analytics patterns
        ga_patterns = [
            r'gtag\(',
            r'ga\(',
            r'GoogleAnalyticsObject',
            r'google-analytics\.com',
            r'googletagmanager\.com'
        ]

        # GA4 ID pattern
        ga4_match = re.search(r'G-[A-Z0-9]{10}', html_content)
        if ga4_match:
            result['analytics']['ga4_id'] = ga4_match.group()
            result['analytics']['gtag'] = True

        # GTM ID pattern
        gtm_match = re.search(r'GTM-[A-Z0-9]+', html_content)
        if gtm_match:
            result['analytics']['gtm_id'] = gtm_match.group()

        # Check for various analytics
        for pattern in ga_patterns:
            if re.search(pattern, html_content, re.IGNORECASE):
                result['analytics']['google_analytics'] = True
                break

        # Facebook Pixel
        if re.search(r'fbq\(|facebook\.com/tr', html_content, re.IGNORECASE):
            result['analytics']['facebook_pixel'] = True

        # Hotjar
        if re.search(r'hotjar\.com|hj\(', html_content, re.IGNORECASE):
            result['analytics']['hotjar'] = True

        # Mixpanel
        if re.search(r'mixpanel\.com|mixpanel\.track', html_content, re.IGNORECASE):
            result['analytics']['mixpanel'] = True

    def _extract_images(self, soup, base_url, result):
        """Extract image information"""
        images = soup.find_all('img')

        for img in images[:20]:  # Limit to first 20 images
            src = img.get('src', '')
            alt = img.get('alt', '')

            if src:
                # Convert relative URLs to absolute
                if src.startswith('//'):
                    src = 'https:' + src
                elif src.startswith('/'):
                    parsed_base = urlparse(base_url)
                    src = f"{parsed_base.scheme}://{parsed_base.netloc}{src}"
                elif not src.startswith(('http://', 'https://')):
                    src = urljoin(base_url, src)

                result['images'].append({
                    'src': src,
                    'alt': alt,
                    'width': img.get('width', ''),
                    'height': img.get('height', '')
                })

    def _extract_link_counts(self, soup, result):
        """Count internal vs external links"""
        links = soup.find_all('a', href=True)

        for link in links:
            href = link.get('href', '')
            if href and not href.startswith(('#', 'mailto:', 'tel:', 'javascript:')):
                absolute_url = urljoin(result['url'], href)
                parsed_url = urlparse(absolute_url)

                # Handle www vs non-www domains
                url_domain_clean = parsed_url.netloc.replace('www.', '', 1)
                base_domain_clean = self.base_domain.replace('www.', '', 1)

                if url_domain_clean == base_domain_clean:
                    result['internal_links'] += 1
                else:
                    result['external_links'] += 1

    def _extract_hreflang(self, soup, result):
        """Extract hreflang links"""
        hreflang_links = soup.find_all('link', attrs={'rel': 'alternate', 'hreflang': True})

        for link in hreflang_links:
            hreflang = link.get('hreflang', '')
            href = link.get('href', '')
            if hreflang and href:
                result['hreflang'].append({
                    'lang': hreflang,
                    'url': href
                })

    def _extract_schema_org(self, soup, result):
        """Extract Schema.org microdata"""
        schema_items = soup.find_all(attrs={'itemtype': True})

        for item in schema_items:
            itemtype = item.get('itemtype', '')
            if itemtype:
                result['schema_org'].append({
                    'type': itemtype,
                    'properties': self._extract_microdata_properties(item)
                })

    def _extract_microdata_properties(self, element):
        """Extract microdata properties from an element"""
        properties = {}

        # Find all elements with itemprop
        prop_elements = element.find_all(attrs={'itemprop': True})

        for prop_elem in prop_elements:
            prop_name = prop_elem.get('itemprop', '')

            # Get content based on element type
            if prop_elem.name in ['meta']:
                content = prop_elem.get('content', '')
            elif prop_elem.name in ['img']:
                content = prop_elem.get('src', '')
            elif prop_elem.name in ['a']:
                content = prop_elem.get('href', '')
            else:
                content = prop_elem.get_text().strip()

            if prop_name and content:
                properties[prop_name] = content

        return properties

    def _discover_sitemaps(self, base_url):
        """Discover and parse sitemap.xml files"""
        parsed_base = urlparse(base_url)
        base_domain = f"{parsed_base.scheme}://{parsed_base.netloc}"

        # Common sitemap locations
        sitemap_urls = [
            f"{base_domain}/sitemap.xml",
            f"{base_domain}/sitemap_index.xml",
            f"{base_domain}/sitemaps.xml",
            f"{base_domain}/sitemap/sitemap.xml"
        ]

        # Check robots.txt for sitemap declarations
        robots_sitemaps = self._get_sitemaps_from_robots(base_domain)
        sitemap_urls.extend(robots_sitemaps)

        print(f"Discovering sitemaps for {base_domain}...")

        for sitemap_url in sitemap_urls:
            try:
                self._parse_sitemap(sitemap_url, depth=1)
            except Exception as e:
                print(f"Failed to parse sitemap {sitemap_url}: {e}")

    def _get_sitemaps_from_robots(self, base_domain):
        """Extract sitemap URLs from robots.txt"""
        sitemaps = []
        try:
            robots_url = f"{base_domain}/robots.txt"
            response = self.session.get(robots_url, timeout=self.config['timeout'])

            if response.status_code == 200:
                for line in response.text.split('\n'):
                    line = line.strip()
                    if line.lower().startswith('sitemap:'):
                        sitemap_url = line.split(':', 1)[1].strip()
                        sitemaps.append(sitemap_url)

        except Exception as e:
            print(f"Could not fetch robots.txt: {e}")

        return sitemaps

    def _parse_sitemap(self, sitemap_url, depth=1, max_depth=10):
        """Parse a sitemap.xml file and extract URLs"""
        if depth > max_depth:
            return

        try:
            print(f"Parsing sitemap: {sitemap_url}")
            response = self.session.get(sitemap_url, timeout=self.config['timeout'])

            if response.status_code != 200:
                return

            # Handle compressed sitemaps
            content = response.content
            if sitemap_url.endswith('.gz') or response.headers.get('content-encoding') == 'gzip':
                try:
                    content = gzip.decompress(content)
                except:
                    pass

            # Parse XML
            try:
                root = ET.fromstring(content)
            except ET.ParseError as e:
                print(f"XML parse error for {sitemap_url}: {e}")
                return

            # Remove namespace prefixes for easier parsing
            for elem in root.iter():
                if '}' in elem.tag:
                    elem.tag = elem.tag.split('}')[1]

            # Check if this is a sitemap index (contains other sitemaps)
            sitemaps = root.findall('.//sitemap')
            if sitemaps:
                print(f"Found sitemap index with {len(sitemaps)} nested sitemaps")
                for sitemap in sitemaps:
                    loc_elem = sitemap.find('loc')
                    if loc_elem is not None and loc_elem.text:
                        nested_url = loc_elem.text.strip()
                        self._parse_sitemap(nested_url, depth + 1, max_depth)

            # Extract URLs from sitemap
            urls = root.findall('.//url')
            if urls:
                print(f"Found {len(urls)} URLs in sitemap")
                added_count = 0
                filtered_count = 0
                duplicate_count = 0

                for url_elem in urls:
                    loc_elem = url_elem.find('loc')
                    if loc_elem is not None and loc_elem.text:
                        url = loc_elem.text.strip()

                        # Get additional metadata
                        lastmod_elem = url_elem.find('lastmod')
                        priority_elem = url_elem.find('priority')
                        changefreq_elem = url_elem.find('changefreq')

                        # Add URL to crawl queue if it should be crawled
                        if self._should_crawl_url(url):
                            with self.urls_lock:
                                if (url not in self.visited_urls and
                                    url not in self._all_discovered_urls):

                                    self._all_discovered_urls.add(url)
                                    # Add at depth 0 since sitemaps are considered starting points
                                    self.discovered_urls.append((url, 0))
                                    self.stats['discovered'] += 1
                                    added_count += 1
                                else:
                                    duplicate_count += 1
                        else:
                            filtered_count += 1

                print(f"Sitemap processing: {added_count} added, {filtered_count} filtered, {duplicate_count} duplicates")

        except Exception as e:
            print(f"Error parsing sitemap {sitemap_url}: {e}")

    def _should_crawl_sitemap_url(self, url):
        """Check if a sitemap URL should be crawled (simplified check)"""
        try:
            parsed = urlparse(url)

            # Check if it's an allowed domain
            if not self.config['crawl_external'] and parsed.netloc != self.base_domain:
                return False

            # Basic extension check
            path = parsed.path.lower()
            if path.endswith(('.pdf', '.zip', '.exe', '.dmg', '.doc', '.docx')):
                return False

            return True

        except Exception:
            return False


    def _run_pagespeed_analysis(self):
        """Run PageSpeed analysis on selected pages"""
        try:
            # Select pages for analysis
            selected_pages = self._select_pages_for_pagespeed()

            if not selected_pages:
                print("No suitable pages found for PageSpeed analysis")
                return

            print(f"Running PageSpeed analysis on {len(selected_pages)} pages...")
            print("Note: PageSpeed analysis uses Google's API with rate limits, this may take several minutes...")

            pagespeed_results = []
            for i, page_url in enumerate(selected_pages):
                print(f"Analyzing page {i+1}/{len(selected_pages)}: {page_url}")

                # Run PageSpeed for mobile first
                print(f"  Running mobile analysis...")
                mobile_result = self._call_pagespeed_api(page_url, 'mobile')

                # Wait between mobile and desktop analysis
                print(f"  Waiting 2 seconds before desktop analysis...")
                time.sleep(2)

                # Run PageSpeed for desktop
                print(f"  Running desktop analysis...")
                desktop_result = self._call_pagespeed_api(page_url, 'desktop')

                page_result = {
                    'url': page_url,
                    'mobile': mobile_result,
                    'desktop': desktop_result,
                    'analysis_date': time.strftime('%Y-%m-%d %H:%M:%S')
                }

                pagespeed_results.append(page_result)

                # Add delay between pages to avoid rate limits
                if i < len(selected_pages) - 1:  # Don't wait after the last page
                    print(f"  Waiting 3 seconds before next page...")
                    time.sleep(3)

            # Store results
            self.stats['pagespeed_results'] = pagespeed_results
            print(f"PageSpeed analysis completed for {len(pagespeed_results)} pages")

        except Exception as e:
            print(f"Error running PageSpeed analysis: {e}")

    def _select_pages_for_pagespeed(self):
        """Select homepage and 2 category pages for PageSpeed analysis"""
        selected_pages = []

        # Find homepage (root URL or shortest path)
        homepage = None
        min_path_length = float('inf')

        for result in self.crawl_results:
            if result.get('status_code') == 200 and result.get('is_internal'):
                url = result['url']
                parsed = urlparse(url)
                path = parsed.path.rstrip('/')

                # Consider root path or very short paths as homepage
                if path == '' or path == '/':
                    homepage = url
                    break
                elif len(path) < min_path_length:
                    homepage = url
                    min_path_length = len(path)

        if homepage:
            selected_pages.append(homepage)
            print(f"Selected homepage: {homepage}")

        # Find category pages (URLs with exactly one path segment)
        category_pages = []
        for result in self.crawl_results:
            if result.get('status_code') == 200 and result.get('is_internal'):
                url = result['url']
                parsed = urlparse(url)
                path = parsed.path.strip('/')

                # Category pages typically have one path segment like /category/ or /products/
                if path and '/' not in path and url != homepage:
                    category_pages.append(url)

        # Select up to 2 category pages
        category_pages = category_pages[:2]
        selected_pages.extend(category_pages)

        for cat_page in category_pages:
            print(f"Selected category page: {cat_page}")

        return selected_pages

    def _call_pagespeed_api(self, url, strategy='mobile', retries=3):
        """Call Google PageSpeed Insights API with retry logic for 429 errors"""
        import random

        try:
            api_url = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"

            params = {
                'url': url,
                'strategy': strategy,
                'category': 'performance'
            }

            # Add API key if configured
            if self.config.get('google_api_key'):
                params['key'] = self.config['google_api_key']

            for attempt in range(retries + 1):
                try:
                    response = requests.get(api_url, params=params, timeout=60)

                    if response.status_code == 200:
                        data = response.json()

                        # Extract key metrics
                        lighthouse_result = data.get('lighthouseResult', {})
                        audits = lighthouse_result.get('audits', {})
                        categories = lighthouse_result.get('categories', {})

                        # Performance score
                        performance_score = None
                        if 'performance' in categories:
                            performance_score = categories['performance'].get('score')
                            if performance_score is not None:
                                performance_score = int(performance_score * 100)

                        # Core Web Vitals
                        metrics = {}

                        # First Contentful Paint
                        if 'first-contentful-paint' in audits:
                            fcp = audits['first-contentful-paint'].get('numericValue')
                            metrics['first_contentful_paint'] = round(fcp / 1000, 2) if fcp else None

                        # Largest Contentful Paint
                        if 'largest-contentful-paint' in audits:
                            lcp = audits['largest-contentful-paint'].get('numericValue')
                            metrics['largest_contentful_paint'] = round(lcp / 1000, 2) if lcp else None

                        # Cumulative Layout Shift
                        if 'cumulative-layout-shift' in audits:
                            cls = audits['cumulative-layout-shift'].get('numericValue')
                            metrics['cumulative_layout_shift'] = round(cls, 3) if cls else None

                        # First Input Delay (from field data if available)
                        if 'max-potential-fid' in audits:
                            fid = audits['max-potential-fid'].get('numericValue')
                            metrics['first_input_delay'] = round(fid, 2) if fid else None

                        # Speed Index
                        if 'speed-index' in audits:
                            si = audits['speed-index'].get('numericValue')
                            metrics['speed_index'] = round(si / 1000, 2) if si else None

                        # Time to Interactive
                        if 'interactive' in audits:
                            tti = audits['interactive'].get('numericValue')
                            metrics['time_to_interactive'] = round(tti / 1000, 2) if tti else None

                        return {
                            'success': True,
                            'performance_score': performance_score,
                            'metrics': metrics,
                            'strategy': strategy
                        }

                    elif response.status_code == 429:
                        # Rate limit exceeded, implement exponential backoff
                        if attempt < retries:
                            # Calculate exponential backoff with jitter
                            base_delay = 2 ** attempt  # 2, 4, 8 seconds
                            jitter = random.uniform(0.5, 1.5)  # Add randomness
                            delay = base_delay * jitter

                            print(f"PageSpeed API rate limited (429), retrying in {delay:.1f} seconds... (attempt {attempt + 1}/{retries + 1})")
                            time.sleep(delay)
                            continue
                        else:
                            return {
                                'success': False,
                                'error': f"Rate limit exceeded after {retries + 1} attempts",
                                'strategy': strategy
                            }

                    else:
                        # Other HTTP errors
                        if attempt < retries:
                            delay = 2 + random.uniform(0, 2)  # Wait 2-4 seconds for other errors
                            print(f"PageSpeed API error {response.status_code}, retrying in {delay:.1f} seconds...")
                            time.sleep(delay)
                            continue
                        else:
                            return {
                                'success': False,
                                'error': f"API returned status {response.status_code}",
                                'strategy': strategy
                            }

                except requests.exceptions.RequestException as e:
                    # Network/timeout errors
                    if attempt < retries:
                        delay = 3 + random.uniform(0, 3)  # Wait 3-6 seconds for network errors
                        print(f"PageSpeed API network error: {e}, retrying in {delay:.1f} seconds...")
                        time.sleep(delay)
                        continue
                    else:
                        return {
                            'success': False,
                            'error': f"Network error: {str(e)}",
                            'strategy': strategy
                        }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'strategy': strategy
            }