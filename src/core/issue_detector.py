"""SEO issue detection and reporting"""
import threading
from fnmatch import fnmatch
from urllib.parse import urlparse


class IssueDetector:
    """Detects SEO and technical issues in crawled pages"""

    def __init__(self, exclusion_patterns=None):
        self.exclusion_patterns = exclusion_patterns or []
        self.detected_issues = []
        self.issues_lock = threading.Lock()

    def detect_issues(self, result):
        """Detect SEO issues for a crawled URL"""
        url = result.get('url', '')
        issues = []

        # Skip if URL matches exclusion patterns
        if self._should_exclude(url):
            return

        # Critical SEO Issues
        self._check_title_issues(result, issues)
        self._check_meta_description_issues(result, issues)
        self._check_heading_issues(result, issues)
        self._check_content_issues(result, issues)
        self._check_technical_issues(result, issues)
        self._check_mobile_issues(result, issues)
        self._check_accessibility_issues(result, issues)
        self._check_social_media_issues(result, issues)
        self._check_structured_data_issues(result, issues)
        self._check_performance_issues(result, issues)
        self._check_indexability_issues(result, issues)

        # Add all detected issues
        with self.issues_lock:
            self.detected_issues.extend(issues)

    def _check_title_issues(self, result, issues):
        """Check for title-related issues"""
        url = result.get('url', '')
        title = result.get('title', '')

        if not title:
            issues.append({
                'url': url,
                'type': 'error',
                'category': 'SEO',
                'issue': 'Missing Title Tag',
                'details': 'Page has no title tag'
            })
        elif len(title) > 60:
            issues.append({
                'url': url,
                'type': 'warning',
                'category': 'SEO',
                'issue': 'Title Too Long',
                'details': f"Title is {len(title)} characters (recommended: ≤60)"
            })
        elif len(title) < 30:
            issues.append({
                'url': url,
                'type': 'warning',
                'category': 'SEO',
                'issue': 'Title Too Short',
                'details': f"Title is {len(title)} characters (recommended: 30-60)"
            })

    def _check_meta_description_issues(self, result, issues):
        """Check for meta description issues"""
        url = result.get('url', '')
        meta_desc = result.get('meta_description', '')

        if not meta_desc:
            issues.append({
                'url': url,
                'type': 'error',
                'category': 'SEO',
                'issue': 'Missing Meta Description',
                'details': 'Page has no meta description'
            })
        elif len(meta_desc) > 160:
            issues.append({
                'url': url,
                'type': 'warning',
                'category': 'SEO',
                'issue': 'Meta Description Too Long',
                'details': f"Description is {len(meta_desc)} characters (recommended: ≤160)"
            })
        elif len(meta_desc) < 120:
            issues.append({
                'url': url,
                'type': 'warning',
                'category': 'SEO',
                'issue': 'Meta Description Too Short',
                'details': f"Description is {len(meta_desc)} characters (recommended: 120-160)"
            })

    def _check_heading_issues(self, result, issues):
        """Check for heading-related issues"""
        url = result.get('url', '')

        if not result.get('h1'):
            issues.append({
                'url': url,
                'type': 'error',
                'category': 'SEO',
                'issue': 'Missing H1 Tag',
                'details': 'Page has no H1 heading'
            })

    def _check_content_issues(self, result, issues):
        """Check for content-related issues"""
        url = result.get('url', '')
        word_count = result.get('word_count', 0)

        if word_count < 300:
            issues.append({
                'url': url,
                'type': 'warning',
                'category': 'Content',
                'issue': 'Thin Content',
                'details': f'Page has only {word_count} words (recommended: ≥300)'
            })

    def _check_technical_issues(self, result, issues):
        """Check for technical SEO issues"""
        url = result.get('url', '')
        status_code = result.get('status_code', 0)

        if status_code >= 400 and status_code < 500:
            issues.append({
                'url': url,
                'type': 'error',
                'category': 'Technical',
                'issue': f'{status_code} Client Error',
                'details': self._get_status_code_message(status_code)
            })
        elif status_code >= 500:
            issues.append({
                'url': url,
                'type': 'error',
                'category': 'Technical',
                'issue': f'{status_code} Server Error',
                'details': self._get_status_code_message(status_code)
            })
        elif status_code >= 300 and status_code < 400:
            issues.append({
                'url': url,
                'type': 'info',
                'category': 'Technical',
                'issue': f'{status_code} Redirect',
                'details': 'URL redirects to another location'
            })

        # Canonical URL checks
        canonical_url = result.get('canonical_url', '')
        if not canonical_url:
            issues.append({
                'url': url,
                'type': 'warning',
                'category': 'Technical',
                'issue': 'Missing Canonical URL',
                'details': 'Page has no canonical URL specified'
            })
        elif canonical_url != url:
            issues.append({
                'url': url,
                'type': 'warning',
                'category': 'Technical',
                'issue': 'Canonical URL Different',
                'details': f"Canonical points to: {canonical_url}"
            })

    def _check_mobile_issues(self, result, issues):
        """Check for mobile optimization issues"""
        url = result.get('url', '')

        if not result.get('viewport'):
            issues.append({
                'url': url,
                'type': 'error',
                'category': 'Mobile',
                'issue': 'Missing Viewport Meta Tag',
                'details': 'Page is not mobile-optimized'
            })

    def _check_accessibility_issues(self, result, issues):
        """Check for accessibility issues"""
        url = result.get('url', '')

        if not result.get('lang'):
            issues.append({
                'url': url,
                'type': 'warning',
                'category': 'Accessibility',
                'issue': 'Missing Language Attribute',
                'details': 'HTML tag has no lang attribute'
            })

        # Image alt text
        images = result.get('images', [])
        images_without_alt = [img for img in images if not img.get('alt')]
        if images_without_alt:
            issues.append({
                'url': url,
                'type': 'warning',
                'category': 'Accessibility',
                'issue': 'Images Without Alt Text',
                'details': f'{len(images_without_alt)} of {len(images)} images lack alt text'
            })

    def _check_social_media_issues(self, result, issues):
        """Check for social media optimization issues"""
        url = result.get('url', '')

        if not result.get('og_tags'):
            issues.append({
                'url': url,
                'type': 'warning',
                'category': 'Social',
                'issue': 'Missing OpenGraph Tags',
                'details': 'Page has no OpenGraph tags for social sharing'
            })

        if not result.get('twitter_tags'):
            issues.append({
                'url': url,
                'type': 'warning',
                'category': 'Social',
                'issue': 'Missing Twitter Card Tags',
                'details': 'Page has no Twitter Card tags'
            })

    def _check_structured_data_issues(self, result, issues):
        """Check for structured data issues"""
        url = result.get('url', '')

        if not result.get('json_ld') and not result.get('schema_org'):
            issues.append({
                'url': url,
                'type': 'error',
                'category': 'Structured Data',
                'issue': 'No Structured Data',
                'details': 'Page has no JSON-LD or Schema.org markup'
            })

    def _check_performance_issues(self, result, issues):
        """Check for performance issues"""
        url = result.get('url', '')
        response_time = result.get('response_time', 0)
        page_size = result.get('size', 0)

        if response_time > 3000:
            issues.append({
                'url': url,
                'type': 'error',
                'category': 'Performance',
                'issue': 'Slow Response Time',
                'details': f'Page took {response_time}ms to respond (recommended: <3000ms)'
            })
        elif response_time > 1000:
            issues.append({
                'url': url,
                'type': 'warning',
                'category': 'Performance',
                'issue': 'Moderate Response Time',
                'details': f'Page took {response_time}ms to respond (recommended: <1000ms)'
            })

        if page_size > 3 * 1024 * 1024:
            issues.append({
                'url': url,
                'type': 'error',
                'category': 'Performance',
                'issue': 'Large Page Size',
                'details': f'Page size is {page_size / 1024 / 1024:.1f}MB (recommended: <3MB)'
            })
        elif page_size > 1 * 1024 * 1024:
            issues.append({
                'url': url,
                'type': 'warning',
                'category': 'Performance',
                'issue': 'Moderate Page Size',
                'details': f'Page size is {page_size / 1024 / 1024:.1f}MB (recommended: <1MB)'
            })

    def _check_indexability_issues(self, result, issues):
        """Check for indexability issues"""
        url = result.get('url', '')
        robots = result.get('robots', '').lower()

        if 'noindex' in robots:
            issues.append({
                'url': url,
                'type': 'error',
                'category': 'Indexability',
                'issue': 'Noindex Tag Present',
                'details': 'Page is BLOCKED from search engines - has noindex directive'
            })

        if 'nofollow' in robots:
            issues.append({
                'url': url,
                'type': 'error',
                'category': 'Indexability',
                'issue': 'Nofollow Tag Present',
                'details': 'Links on this page are NOT followed by search engines - has nofollow directive'
            })

    def _should_exclude(self, url):
        """Check if URL should be excluded from issue detection"""
        parsed = urlparse(url)
        path = parsed.path

        for pattern in self.exclusion_patterns:
            if '*' in pattern:
                if fnmatch(path, pattern):
                    return True
            elif path == pattern or path.startswith(pattern.rstrip('*')):
                return True

        return False

    def _get_status_code_message(self, status_code):
        """Get descriptive message for HTTP status codes"""
        messages = {
            400: 'Bad Request',
            401: 'Unauthorized',
            403: 'Forbidden',
            404: 'Not Found',
            405: 'Method Not Allowed',
            406: 'Not Acceptable',
            408: 'Request Timeout',
            410: 'Gone',
            429: 'Too Many Requests',
            500: 'Internal Server Error',
            501: 'Not Implemented',
            502: 'Bad Gateway',
            503: 'Service Unavailable',
            504: 'Gateway Timeout',
            505: 'HTTP Version Not Supported'
        }
        return messages.get(status_code, f'HTTP {status_code} Error')

    def get_issues(self):
        """Get all detected issues"""
        with self.issues_lock:
            return self.detected_issues.copy()

    def reset(self):
        """Reset detected issues"""
        with self.issues_lock:
            self.detected_issues.clear()
