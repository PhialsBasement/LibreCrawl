"""SEO issue detection and reporting"""
import threading
from fnmatch import fnmatch
from urllib.parse import urlparse
from difflib import SequenceMatcher


class IssueDetector:
    """Detects SEO and technical issues in crawled pages"""

    def __init__(self, exclusion_patterns=None, js_wait_time=0):
        self.exclusion_patterns = exclusion_patterns or []
        self.detected_issues = []
        self.issues_lock = threading.Lock()
        self.js_wait_time = js_wait_time

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
        self._check_broken_image_issues(result, issues)
        self._check_security_headers(result, issues)

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

        # No HTTP response at all (DNS failure, connection refused, timeout, etc.)
        if status_code == 0:
            error_type = result.get('error_type')
            error_label_map = {
                'dns_not_found': ('DNS Not Found',
                                  'Domain does not resolve. The site may be expired or misconfigured.'),
                'connection_refused': ('Connection Refused',
                                       'Server actively refused the connection.'),
                'timeout': ('Request Timeout',
                            'Server did not respond before the request timed out.'),
                'ssl_error': ('SSL/TLS Error',
                              'Could not establish a secure connection (certificate or TLS issue).'),
                'connection_error': ('Connection Error',
                                     'Could not connect to the server.'),
            }
            if error_type and error_type != 'file_too_large':
                title, default_details = error_label_map.get(
                    error_type, ('No Response', 'No HTTP response received.')
                )
                issues.append({
                    'url': url,
                    'type': 'error',
                    'category': 'Technical',
                    'issue': title,
                    'details': result.get('error') or default_details
                })

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

        # Subtract JS wait time if page was rendered with JavaScript
        is_js = result.get('javascript_rendered', False)
        js_wait = result.get('js_wait_time')
        if js_wait is None:
            js_wait = self.js_wait_time

        # Check if the response_time has already been pre-adjusted by the crawler
        raw_response_time = result.get('raw_response_time')
        if raw_response_time is not None:
            adjusted_response_time = response_time
        else:
            # Fallback for historical data/other paths
            raw_response_time = response_time
            adjusted_response_time = response_time
            if is_js and js_wait > 0:
                adjusted_response_time = max(0.0, response_time - (js_wait * 1000))

        if adjusted_response_time > 3000:
            details = f'Page took {raw_response_time}ms to respond'
            if is_js and js_wait > 0:
                details += f' (adjusted: {adjusted_response_time:.2f}ms excluding {js_wait}s JS wait time)'
            details += ' (recommended: <3000ms)'
            issues.append({
                'url': url,
                'type': 'error',
                'category': 'Performance',
                'issue': 'Slow Response Time',
                'details': details
            })
        elif adjusted_response_time > 1000:
            details = f'Page took {raw_response_time}ms to respond'
            if is_js and js_wait > 0:
                details += f' (adjusted: {adjusted_response_time:.2f}ms excluding {js_wait}s JS wait time)'
            details += ' (recommended: <1000ms)'
            issues.append({
                'url': url,
                'type': 'warning',
                'category': 'Performance',
                'issue': 'Moderate Response Time',
                'details': details
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

    def _check_broken_image_issues(self, result, issues):
        """Check for broken image URLs on the page"""
        url = result.get('url', '')
        broken_images = result.get('broken_images', [])
        for img in broken_images:
            status = img.get('status', 0)
            img_url = img.get('url', '')
            if status == 0:
                issues.append({
                    'url': url,
                    'type': 'error',
                    'category': 'Content',
                    'issue': 'Broken Image (No Response)',
                    'details': f'Image does not respond: {img_url}'
                })
            elif status >= 400:
                issues.append({
                    'url': url,
                    'type': 'error',
                    'category': 'Content',
                    'issue': f'Broken Image ({status})',
                    'details': f'Image returned {status}: {img_url}'
                })

    def detect_duplication_issues(self, all_results, similarity_threshold=0.85):
        """
        Detect content duplication across all crawled pages.

        Args:
            all_results: List of all crawled result dictionaries
            similarity_threshold: Minimum similarity ratio to flag as duplicate (0.0-1.0)
        """
        issues = []
        processed_pairs = set()

        # Compare each result with all others
        for i, result1 in enumerate(all_results):
            url1 = result1.get('url', '')

            # Skip if URL should be excluded
            if self._should_exclude(url1):
                continue

            for j, result2 in enumerate(all_results):
                # Skip same URL or already processed pairs
                if i >= j:
                    continue

                url2 = result2.get('url', '')

                # Skip if URL should be excluded
                if self._should_exclude(url2):
                    continue

                # Create unique pair identifier
                pair_key = tuple(sorted([url1, url2]))
                if pair_key in processed_pairs:
                    continue

                processed_pairs.add(pair_key)

                # Calculate similarity
                similarity = self._calculate_content_similarity(result1, result2)

                # Flag as duplicate if above threshold
                if similarity >= similarity_threshold:
                    # Add issue for both URLs
                    issues.append({
                        'url': url1,
                        'type': 'warning',
                        'category': 'Duplication',
                        'issue': 'Duplicate Content Detected',
                        'details': f'Content is {similarity*100:.1f}% similar to {url2}'
                    })
                    issues.append({
                        'url': url2,
                        'type': 'warning',
                        'category': 'Duplication',
                        'issue': 'Duplicate Content Detected',
                        'details': f'Content is {similarity*100:.1f}% similar to {url1}'
                    })

        # Add all detected duplication issues
        with self.issues_lock:
            self.detected_issues.extend(issues)

    def _calculate_content_similarity(self, result1, result2):
        """
        Calculate similarity between two page results.

        Compares title, meta description, h1, and content length.
        Returns a similarity ratio between 0.0 and 1.0.
        """
        # Extract content fields
        title1 = result1.get('title', '').lower().strip()
        title2 = result2.get('title', '').lower().strip()

        desc1 = result1.get('meta_description', '').lower().strip()
        desc2 = result2.get('meta_description', '').lower().strip()

        h1_1 = result1.get('h1', '').lower().strip()
        h1_2 = result2.get('h1', '').lower().strip()

        word_count1 = result1.get('word_count', 0)
        word_count2 = result2.get('word_count', 0)

        # Calculate individual similarities
        title_sim = self._text_similarity(title1, title2) if title1 and title2 else 0
        desc_sim = self._text_similarity(desc1, desc2) if desc1 and desc2 else 0
        h1_sim = self._text_similarity(h1_1, h1_2) if h1_1 and h1_2 else 0

        # Word count similarity (1.0 if within 10% of each other)
        if word_count1 and word_count2:
            max_count = max(word_count1, word_count2)
            min_count = min(word_count1, word_count2)
            word_count_sim = min_count / max_count if max_count > 0 else 0
        else:
            word_count_sim = 0

        # Weighted average (title and description are most important)
        weights = {
            'title': 0.35,
            'desc': 0.35,
            'h1': 0.20,
            'word_count': 0.10
        }

        overall_similarity = (
            title_sim * weights['title'] +
            desc_sim * weights['desc'] +
            h1_sim * weights['h1'] +
            word_count_sim * weights['word_count']
        )

        return overall_similarity

    def _text_similarity(self, text1, text2):
        """Calculate similarity ratio between two text strings using SequenceMatcher"""
        if not text1 or not text2:
            return 0.0
        return SequenceMatcher(None, text1, text2).ratio()

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

    def _check_security_headers(self, result, issues):
        """Check for security-related HTTP headers"""
        url = result.get('url', '')
        # Only check successful or redirected pages, skip pages that failed to load completely
        status_code = result.get('status_code', 0)
        if status_code == 0 or status_code >= 400:
            return

        headers = result.get('headers', {})
        if not isinstance(headers, dict):
            headers = {}

        # Content-Security-Policy (CSP)
        csp = headers.get('content-security-policy', '')
        if not csp:
            issues.append({
                'url': url,
                'type': 'error',
                'category': 'Security',
                'issue': 'Missing Content-Security-Policy',
                'details': 'Content-Security-Policy (CSP) header is not set. This exposes the site to Cross-Site Scripting (XSS) and code injection attacks.'
            })
        else:
            # Check for unsafe directives in CSP
            csp_lower = csp.lower()
            unsafe_checks = []
            if "'unsafe-inline'" in csp_lower:
                unsafe_checks.append("'unsafe-inline'")
            if "'unsafe-eval'" in csp_lower:
                unsafe_checks.append("'unsafe-eval'")
            if "script-src *" in csp_lower or "default-src *" in csp_lower:
                unsafe_checks.append("wildcard '*' sources")

            if unsafe_checks:
                issues.append({
                    'url': url,
                    'type': 'warning',
                    'category': 'Security',
                    'issue': 'Insecure Content-Security-Policy',
                    'details': f"CSP contains potentially insecure sources: {', '.join(unsafe_checks)}. Consider using nonces or hashes instead."
                })

        # Strict-Transport-Security (HSTS)
        # HSTS is only valid for HTTPS sites
        if url.startswith('https://'):
            hsts = headers.get('strict-transport-security', '')
            if not hsts:
                issues.append({
                    'url': url,
                    'type': 'error',
                    'category': 'Security',
                    'issue': 'Missing Strict-Transport-Security',
                    'details': 'HSTS header is missing. Secure connections are not enforced, making the site vulnerable to SSL stripping attacks.'
                })
            else:
                hsts_lower = hsts.lower()
                # Parse max-age
                import re
                max_age_match = re.search(r'max-age\s*=\s*(\d+)', hsts_lower)
                if max_age_match:
                    max_age = int(max_age_match.group(1))
                    if max_age < 31536000:  # 1 year
                        issues.append({
                            'url': url,
                            'type': 'warning',
                            'category': 'Security',
                            'issue': 'Low HSTS Max-Age',
                            'details': f"HSTS max-age is set to {max_age} seconds. A minimum of 31536000 seconds (1 year) is recommended for production."
                        })
                else:
                    issues.append({
                        'url': url,
                        'type': 'warning',
                        'category': 'Security',
                        'issue': 'Invalid HSTS Header',
                        'details': f"HSTS header does not specify a valid max-age directive: '{hsts}'."
                    })

                if 'includesubdomains' not in hsts_lower:
                    issues.append({
                        'url': url,
                        'type': 'warning',
                        'category': 'Security',
                        'issue': 'HSTS Subdomains Not Protected',
                        'details': "HSTS header is missing 'includeSubDomains', leaving subdomains vulnerable to SSL stripping."
                    })

        # X-Frame-Options
        xfo = headers.get('x-frame-options', '')
        # Check if CSP has frame-ancestors, if so X-Frame-Options is optional
        has_frame_ancestors = 'frame-ancestors' in csp.lower() if csp else False

        if not xfo and not has_frame_ancestors:
            issues.append({
                'url': url,
                'type': 'error',
                'category': 'Security',
                'issue': 'Missing Clickjacking Protection',
                'details': 'Neither X-Frame-Options nor CSP frame-ancestors is set. The site is vulnerable to clickjacking attacks.'
            })
        elif xfo:
            xfo_lower = xfo.lower().strip()
            if xfo_lower not in ['deny', 'sameorigin']:
                issues.append({
                    'url': url,
                    'type': 'warning',
                    'category': 'Security',
                    'issue': 'Insecure X-Frame-Options',
                    'details': f"X-Frame-Options is set to '{xfo}', which is deprecated or insecure. Use 'DENY' or 'SAMEORIGIN'."
                })

        # X-Content-Type-Options
        xcto = headers.get('x-content-type-options', '')
        if not xcto:
            issues.append({
                'url': url,
                'type': 'error',
                'category': 'Security',
                'issue': 'Missing X-Content-Type-Options',
                'details': 'X-Content-Type-Options header is missing. This allows browsers to MIME-sniff response content, opening vectors for XSS.'
            })
        elif xcto.lower().strip() != 'nosniff':
            issues.append({
                'url': url,
                'type': 'warning',
                'category': 'Security',
                'issue': 'Insecure X-Content-Type-Options',
                'details': f"X-Content-Type-Options is set to '{xcto}' instead of 'nosniff'."
            })

        # Referrer-Policy
        rp = headers.get('referrer-policy', '')
        if not rp:
            issues.append({
                'url': url,
                'type': 'warning',
                'category': 'Security',
                'issue': 'Missing Referrer-Policy',
                'details': "Referrer-Policy header is missing. The browser's default policy will be used, which might leak sensitive URL data."
            })
        else:
            rp_lower = rp.lower().strip()
            if 'unsafe-url' in rp_lower:
                issues.append({
                    'url': url,
                    'type': 'warning',
                    'category': 'Security',
                    'issue': 'Insecure Referrer-Policy',
                    'details': f"Referrer-Policy is set to '{rp}', which leaks full URL path and query parameters to untrusted sites."
                })

        # Permissions-Policy
        pp = headers.get('permissions-policy', '')
        if not pp:
            issues.append({
                'url': url,
                'type': 'info',
                'category': 'Security',
                'issue': 'Missing Permissions-Policy',
                'details': 'Permissions-Policy header is missing. Restricting browser capabilities (like camera, microphone, geolocation) is recommended.'
            })

        # Information Disclosure (Server / X-Powered-By / X-AspNet-Version)
        server = headers.get('server', '')
        if server:
            # Check if server header contains version numbers (e.g., Apache/2.4.41 or nginx/1.18.0)
            import re
            if re.search(r'/\d', server):
                issues.append({
                    'url': url,
                    'type': 'info',
                    'category': 'Security',
                    'issue': 'Server Version Disclosure',
                    'details': f"Server header discloses software version information: '{server}'. This can help attackers identify known vulnerabilities."
                })

        x_powered_by = headers.get('x-powered-by', '')
        if x_powered_by:
            issues.append({
                'url': url,
                'type': 'info',
                'category': 'Security',
                'issue': 'Technology Stack Disclosure',
                'details': f"X-Powered-By header is present: '{x_powered_by}'. This discloses server technology details (e.g. PHP, ASP.NET)."
            })

        x_aspnet = headers.get('x-aspnet-version', '')
        if x_aspnet:
            issues.append({
                'url': url,
                'type': 'info',
                'category': 'Security',
                'issue': 'ASP.NET Version Disclosure',
                'details': f"X-AspNet-Version header is present: '{x_aspnet}'."
            })

    def get_issues(self):
        """Get all detected issues"""
        with self.issues_lock:
            return self.detected_issues.copy()

    def reset(self):
        """Reset detected issues"""
        with self.issues_lock:
            self.detected_issues.clear()
