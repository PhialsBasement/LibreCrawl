"""SEO issue detection and reporting"""
import math
import re
import threading
import time
from collections import defaultdict
from fnmatch import fnmatch
from urllib.parse import urlparse

# Near-duplicate detection is bounded so a large site can never hold a crawl in
# "finishing up" indefinitely: when the budget is exhausted the pass stops with
# a warning and partial results instead of running to completion.
DUPLICATION_TIME_BUDGET_SECONDS = 120
DUPLICATION_EXAMPLES_PER_PAGE = 5

_TOKEN_SPLIT = re.compile(r'[^\w]+')


class IssueDetector:
    """Detects SEO and technical issues in crawled pages"""

    # Weights of the signals that make up the duplicate-content score.
    _DUP_WEIGHTS = {'title': 0.35, 'desc': 0.35, 'h1': 0.20, 'word_count': 0.10}

    def __init__(self, exclusion_patterns=None):
        self.exclusion_patterns = exclusion_patterns or []
        self.detected_issues = []
        self.issues_lock = threading.Lock()
        self.duplication_truncated = False

    def detect_issues(self, result):
        """Detect SEO issues for a crawled URL"""
        url = result.get('url', '')
        issues = []

        # Skip if URL matches exclusion patterns
        if self._should_exclude(url):
            return

        # SEO checks only apply to HTML pages, not images/CSS/JS/etc.
        content_type = result.get('content_type', '')
        if content_type and 'html' not in content_type.lower():
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
        Flag pages whose title, meta description, H1 and length are near-identical
        to other crawled pages.

        Emits at most ONE issue per page — how many near-duplicates it has and
        the closest few — so a site of N templated pages yields N issues, not N².
        (The previous pairwise version produced two issues per matching pair:
        700k rows for a 1,000-page site, which took minutes to compute and
        locked SQLite for over a minute while saving.)

        Only HTML pages that returned 200 and carry a title or description are
        considered. Pages with identical normalised title/description/H1 are
        grouped first; one representative per group is scored and the result
        applies to every member. Candidate pairs between groups come from a
        prefix filter on title tokens: with the default 0.85 threshold a pair
        needs title similarity of at least 0.57, so any qualifying pair must
        share one of each title's rarest few tokens. Sites with distinct titles
        therefore score very few pairs; templated sites score many, but each
        comparison is a handful of set operations, and the whole pass stops
        after DUPLICATION_TIME_BUDGET_SECONDS with partial results rather than
        holding the crawl in "finishing up".

        Args:
            all_results: List of all crawled result dictionaries
            similarity_threshold: Minimum similarity ratio to flag as duplicate (0.0-1.0)
        """
        started = time.monotonic()
        self.duplication_truncated = False

        pages = self._duplication_candidates(all_results)
        if len(pages) < 2:
            return

        # 1. Group pages with identical title / description / H1.
        group_index = {}
        groups = []
        for page in pages:
            signature = (page['title'], page['desc'], page['h1'])
            idx = group_index.get(signature)
            if idx is None:
                idx = group_index[signature] = len(groups)
                groups.append([])
            groups[idx].append(page)
        representatives = [group[0] for group in groups]

        # 2. Score candidate pairs of groups, each pair once.
        similar = defaultdict(list)  # group idx -> [(similarity, other group idx)]
        compared = 0
        for i, j in self._duplication_candidate_pairs(representatives, similarity_threshold):
            compared += 1
            if compared % 2000 == 0 and time.monotonic() - started > DUPLICATION_TIME_BUDGET_SECONDS:
                self.duplication_truncated = True
                print(f"Duplication detection stopped after {DUPLICATION_TIME_BUDGET_SECONDS}s "
                      f"and {compared} comparisons; duplicate results are partial")
                break
            similarity = self._duplication_similarity(
                representatives[i], representatives[j], similarity_threshold)
            if similarity is not None:
                similar[i].append((similarity, j))
                similar[j].append((similarity, i))

        # 3. One issue per page.
        issues = []
        for idx, group in enumerate(groups):
            partners = [(1.0, member['url'], True) for member in group]
            for similarity, j in similar.get(idx, ()):
                partners.extend((similarity, other['url'], False) for other in groups[j])
            if len(partners) < 2:
                continue
            partners.sort(key=lambda p: (-p[0], p[1]))
            total = len(partners) - 1  # everything except the page itself
            for page in group:
                examples = [p for p in partners if p[1] != page['url']][:DUPLICATION_EXAMPLES_PER_PAGE]
                described = '; '.join(
                    f"{url} (identical title, description and H1)" if identical
                    else f"{url} ({similarity * 100:.1f}% similar)"
                    for similarity, url, identical in examples
                )
                more = total - len(examples)
                issues.append({
                    'url': page['url'],
                    'type': 'warning',
                    'category': 'Duplication',
                    'issue': 'Duplicate Content Detected',
                    'details': f"{total} similar page{'s' if total != 1 else ''}: {described}"
                               + (f" (+{more} more)" if more > 0 else '')
                })

        # Add all detected duplication issues
        with self.issues_lock:
            self.detected_issues.extend(issues)

    def _duplication_candidates(self, all_results):
        """Pages eligible for duplicate detection, with normalised fields and token sets."""
        pages = []
        for result in all_results:
            url = result.get('url', '')
            if not url or self._should_exclude(url):
                continue
            status = result.get('status_code')
            if status is not None and status != 200:
                continue
            content_type = (result.get('content_type') or '').lower()
            if content_type and 'html' not in content_type:
                continue
            page = self._duplication_page(result)
            if not page['title'] and not page['desc']:
                continue
            pages.append(page)
        return pages

    def _duplication_page(self, result):
        title = self._normalise_text(result.get('title'))
        desc = self._normalise_text(result.get('meta_description'))
        h1 = self._normalise_text(result.get('h1'))
        return {
            'url': result.get('url', ''),
            'title': title,
            'desc': desc,
            'h1': h1,
            'title_tokens': self._tokens(title),
            'desc_tokens': self._tokens(desc),
            'h1_tokens': self._tokens(h1),
            'word_count': result.get('word_count') or 0,
        }

    @staticmethod
    def _normalise_text(value):
        """Lower-cased, whitespace-collapsed text; H1 may arrive as a list."""
        if isinstance(value, list):
            value = next((v for v in value if isinstance(v, str) and v.strip()), '')
        if not isinstance(value, str):
            return ''
        return ' '.join(value.lower().split())

    @staticmethod
    def _tokens(text):
        return frozenset(t for t in _TOKEN_SPLIT.split(text) if t)

    def _duplication_candidate_pairs(self, representatives, threshold):
        """Yield (i, j) with i < j for the pairs worth scoring.

        Uses a prefix filter on title tokens. The title carries 35% of the
        score, so a pair can only reach `threshold` if the titles' Dice
        similarity is at least (threshold - 0.65) / 0.35. Dice(A, B) >= t
        implies |A ∩ B| >= t·|A| / (2 - t); ordering tokens by global rarity,
        two such sets must share a token within the first
        |A| - need + 1 tokens of each, so indexing those prefixes finds every
        qualifying pair while skipping most pairs of distinct titles.
        """
        weights = self._DUP_WEIGHTS
        min_title = (threshold - (1.0 - weights['title'])) / weights['title']
        count = len(representatives)

        if min_title <= 0:
            # Threshold is too low for the title to prune anything.
            for i in range(count):
                for j in range(i + 1, count):
                    yield i, j
            return

        frequency = defaultdict(int)
        for rep in representatives:
            for token in rep['title_tokens']:
                frequency[token] += 1

        index = defaultdict(list)
        prefixes = []
        for i, rep in enumerate(representatives):
            ordered = sorted(rep['title_tokens'], key=lambda t: (frequency[t], t))
            need = math.ceil(min_title * len(ordered) / (2 - min_title))
            prefix = ordered[:max(1, len(ordered) - need + 1)] if ordered else []
            prefixes.append(prefix)
            for token in prefix:
                index[token].append(i)

        for i, prefix in enumerate(prefixes):
            seen = set()
            for token in prefix:
                for j in index[token]:
                    if j < i and j not in seen:
                        seen.add(j)
                        yield j, i

    def _duplication_similarity(self, a, b, threshold):
        """Weighted similarity of two candidate pages, or None once it is clear
        the score cannot reach `threshold` (so cheap signals short-circuit)."""
        weights = self._DUP_WEIGHTS
        score = self._dice(a['title_tokens'], b['title_tokens']) * weights['title']
        if score + weights['desc'] + weights['h1'] + weights['word_count'] < threshold:
            return None
        score += self._dice(a['desc_tokens'], b['desc_tokens']) * weights['desc']
        if score + weights['h1'] + weights['word_count'] < threshold:
            return None
        score += self._dice(a['h1_tokens'], b['h1_tokens']) * weights['h1']
        if score + weights['word_count'] < threshold:
            return None
        score += self._length_similarity(a['word_count'], b['word_count']) * weights['word_count']
        return score if score >= threshold else None

    @staticmethod
    def _dice(tokens_a, tokens_b):
        """Dice coefficient of two token sets (0.0 when either is empty)."""
        if not tokens_a or not tokens_b:
            return 0.0
        return 2.0 * len(tokens_a & tokens_b) / (len(tokens_a) + len(tokens_b))

    @staticmethod
    def _length_similarity(count_a, count_b):
        if not count_a or not count_b:
            return 0.0
        return min(count_a, count_b) / max(count_a, count_b)

    def _calculate_content_similarity(self, result1, result2):
        """
        Similarity of two page results in [0.0, 1.0]: word-level Dice
        similarity of title (35%), meta description (35%) and H1 (20%), plus
        the ratio of their word counts (10%).
        """
        return self._duplication_similarity(
            self._duplication_page(result1), self._duplication_page(result2), 0.0)

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
