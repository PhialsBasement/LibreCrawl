"""SEO data extraction from HTML content"""
import re
import json
from urllib.parse import urljoin, urlparse


class SEOExtractor:
    """Extracts SEO-related data from HTML content"""

    @staticmethod
    def extract_basic_seo_data(soup, result):
        """Extract basic SEO data (title, headings, meta description, etc.)"""
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
        result['h2'] = [h2.get_text().strip() for h2 in h2_tags[:10]]

        h3_tags = soup.find_all('h3')
        result['h3'] = [h3.get_text().strip() for h3 in h3_tags[:10]]

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

    @staticmethod
    def extract_meta_tags(soup, result):
        """Extract all meta tags"""
        meta_tags = soup.find_all('meta')

        for meta in meta_tags:
            name = meta.get('name', '').lower()
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

    @staticmethod
    def extract_opengraph_tags(soup, result):
        """Extract OpenGraph meta tags"""
        og_metas = soup.find_all('meta', attrs={'property': re.compile(r'^og:')})

        for meta in og_metas:
            property_name = meta.get('property', '')
            content = meta.get('content', '')
            if property_name:
                key = property_name.replace('og:', '')
                result['og_tags'][key] = content

    @staticmethod
    def extract_twitter_tags(soup, result):
        """Extract Twitter Card meta tags"""
        twitter_metas = soup.find_all('meta', attrs={'name': re.compile(r'^twitter:')})

        for meta in twitter_metas:
            name = meta.get('name', '')
            content = meta.get('content', '')
            if name:
                key = name.replace('twitter:', '')
                result['twitter_tags'][key] = content

    @staticmethod
    def extract_json_ld(soup, result):
        """Extract JSON-LD structured data"""
        json_ld_scripts = soup.find_all('script', attrs={'type': 'application/ld+json'})

        for script in json_ld_scripts:
            try:
                json_data = json.loads(script.string)
                result['json_ld'].append(json_data)
            except (json.JSONDecodeError, AttributeError, TypeError):
                continue

    @staticmethod
    def extract_analytics_tracking(soup, html_content, result):
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

    @staticmethod
    def extract_images(soup, base_url, result):
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

    @staticmethod
    def extract_link_counts(soup, result, base_domain):
        """Count internal vs external links"""
        links = soup.find_all('a', href=True)

        for link in links:
            href = link.get('href', '')
            if href and not href.startswith(('#', 'mailto:', 'tel:', 'javascript:')):
                absolute_url = urljoin(result['url'], href)
                parsed_url = urlparse(absolute_url)

                # Handle www vs non-www domains
                url_domain_clean = parsed_url.netloc.replace('www.', '', 1)
                base_domain_clean = base_domain.replace('www.', '', 1)

                if url_domain_clean == base_domain_clean:
                    result['internal_links'] += 1
                else:
                    result['external_links'] += 1

    @staticmethod
    def extract_hreflang(soup, result):
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

    @staticmethod
    def extract_schema_org(soup, result):
        """Extract Schema.org microdata"""
        schema_items = soup.find_all(attrs={'itemtype': True})

        for item in schema_items:
            itemtype = item.get('itemtype', '')
            if itemtype:
                result['schema_org'].append({
                    'type': itemtype,
                    'properties': SEOExtractor._extract_microdata_properties(item)
                })

    @staticmethod
    def _extract_microdata_properties(element):
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

    @staticmethod
    def create_empty_result(url, depth, status_code=0, error=None):
        """Create an empty result structure"""
        return {
            'url': url,
            'status_code': status_code,
            'content_type': '',
            'size': 0,
            'is_internal': False,
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
            'schema_org': [],
            'error': error
        }
