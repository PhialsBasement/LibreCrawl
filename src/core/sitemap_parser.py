"""Sitemap discovery and parsing"""
import gzip
import xml.etree.ElementTree as ET
from urllib.parse import urlparse


class SitemapParser:
    """Discovers and parses sitemap.xml files"""

    def __init__(self, session, base_domain, timeout=10):
        self.session = session
        self.base_domain = base_domain
        self.timeout = timeout

    def discover_sitemaps(self, base_url):
        """
        Discover and parse sitemap.xml files

        Returns:
            list: List of URLs found in sitemaps
        """
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

        all_urls = []
        for sitemap_url in sitemap_urls:
            try:
                urls = self._parse_sitemap(sitemap_url, depth=1)
                all_urls.extend(urls)
            except Exception as e:
                print(f"Failed to parse sitemap {sitemap_url}: {e}")

        return all_urls

    def _get_sitemaps_from_robots(self, base_domain):
        """Extract sitemap URLs from robots.txt"""
        sitemaps = []
        try:
            robots_url = f"{base_domain}/robots.txt"
            response = self.session.get(robots_url, timeout=self.timeout)

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
        """
        Parse a sitemap.xml file and extract URLs

        Returns:
            list: List of URLs found in the sitemap
        """
        if depth > max_depth:
            return []

        try:
            print(f"Parsing sitemap: {sitemap_url}")
            response = self.session.get(sitemap_url, timeout=self.timeout)

            if response.status_code != 200:
                return []

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
                return []

            # Remove namespace prefixes for easier parsing
            for elem in root.iter():
                if '}' in elem.tag:
                    elem.tag = elem.tag.split('}')[1]

            all_urls = []

            # Check if this is a sitemap index (contains other sitemaps)
            sitemaps = root.findall('.//sitemap')
            if sitemaps:
                print(f"Found sitemap index with {len(sitemaps)} nested sitemaps")
                for sitemap in sitemaps:
                    loc_elem = sitemap.find('loc')
                    if loc_elem is not None and loc_elem.text:
                        nested_url = loc_elem.text.strip()
                        nested_urls = self._parse_sitemap(nested_url, depth + 1, max_depth)
                        all_urls.extend(nested_urls)

            # Extract URLs from sitemap
            urls = root.findall('.//url')
            if urls:
                print(f"Found {len(urls)} URLs in sitemap")
                for url_elem in urls:
                    loc_elem = url_elem.find('loc')
                    if loc_elem is not None and loc_elem.text:
                        url = loc_elem.text.strip()
                        all_urls.append(url)

            return all_urls

        except Exception as e:
            print(f"Error parsing sitemap {sitemap_url}: {e}")
            return []
