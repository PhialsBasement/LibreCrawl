"""Site-wide crawl analysis.

Most checks look at one page at a time and run as each page is crawled. The
ones here need the whole crawl (who links to a page, which other pages share
its title, whether its canonical target is itself indexable), so they run
once when the crawl finishes, like Screaming Frog's "Crawl Analysis".

Everything is a single pass over the rows and a single pass over the links,
with dict lookups, so the cost grows linearly with the crawl. The one
iterative step, Link Score (internal PageRank), runs at most
LINK_SCORE_ITERATIONS rounds over the link graph and stops early on
convergence or after LINK_SCORE_TIME_BUDGET_SECONDS.
"""
import math
import time
from collections import defaultdict
from urllib.parse import urljoin

from .link_manager import normalize_url

INDEXABLE = 'Indexable'
NON_INDEXABLE = 'Non-Indexable'

LINK_SCORE_DAMPING = 0.85
LINK_SCORE_ITERATIONS = 40
LINK_SCORE_TIME_BUDGET_SECONDS = 30
MAX_REDIRECT_HOPS = 10
EXAMPLES_PER_ISSUE = 3

# Issues produced by the site-wide pass. A resumed crawl recomputes them at
# the end, so these are dropped when a crawl is resumed rather than repeated.
ANALYSIS_ISSUES = frozenset({
    'Duplicate Title',
    'Duplicate Meta Description',
    'Duplicate H1',
    'Broken Internal Links',
    'Broken External Links',
    'Internal Links to Redirects',
    'Redirect Chain',
    'Redirect Loop',
    'Redirect to Broken URL',
    'Canonical Points to Non-Indexable URL',
    'Canonical Chain',
    'Orphan Page (Sitemap Only)',
    'Non-Indexable URL in Sitemap',
    'Indexable Page Not in Sitemap',
})

# Fields the analysis writes onto each row
ANALYSIS_FIELDS = ('indexability', 'indexability_status', 'inlinks', 'outlinks',
                   'link_score', 'in_sitemap')


def _safe_normalize(url, base=None):
    """normalize_url(urljoin(base, url)), or '' for anything unparseable
    (a malformed href or header must never abort the whole analysis)."""
    if not url or not isinstance(url, str):
        return ''
    try:
        return normalize_url(urljoin(base, url) if base else url)
    except (ValueError, TypeError):
        return ''


def is_html(row):
    return 'html' in (row.get('content_type') or '').lower()


def final_url(row):
    """Where the row's content actually lives after any redirects."""
    return row.get('redirected_to') or row.get('url', '')


def _resolve_canonical(row, href):
    if not isinstance(href, str):
        return ''
    target = _safe_normalize(href.strip(), final_url(row))
    # A javascript:/mailto:/data: "canonical" names no page; treat it as
    # absent rather than as pointing the page somewhere else
    return target if target.startswith(('http://', 'https://')) else ''


def canonical_targets(row):
    """Distinct pages the row's canonical declarations (HTML tags and Link
    headers) point at, normalised, in declaration order."""
    declared = row.get('canonicals') or [row.get('canonical_url')]
    targets = []
    for href in declared:
        target = _resolve_canonical(row, href)
        if target and target not in targets:
            targets.append(target)
    return targets


def has_conflicting_canonicals(row):
    return (row.get('canonical_count') or 0) > 1 and len(canonical_targets(row)) > 1


def canonical_target(row):
    """The row's canonical as a normalised absolute URL, or ''.

    Conflicting canonicals give '': search engines ignore every canonical
    on a page whose declarations disagree.
    """
    if (row.get('canonical_count') or 0) > 1:
        # Several declarations: usable only when they agree (junk ones,
        # e.g. an empty href, are ignored rather than counted as dissent)
        targets = canonical_targets(row)
        return targets[0] if len(targets) == 1 else ''
    return _resolve_canonical(row, row.get('canonical_url'))


def is_canonicalised(row):
    """True when the canonical points at a different URL than the page."""
    target = canonical_target(row)
    if not target:
        return False
    here = _safe_normalize(final_url(row))
    return bool(here) and target != here


def _robots_tokens(value):
    """Directives in a robots meta or X-Robots-Tag value.

    X-Robots-Tag may name a crawler ("googlebot: noindex") and several headers
    arrive joined with commas, so split on both and drop the crawler prefix.
    """
    tokens = set()
    for part in (value or '').lower().replace(';', ',').split(','):
        part = part.strip()
        if ':' in part:
            part = part.split(':', 1)[1].strip()
        if part:
            tokens.add(part)
    return tokens


def noindex_source(row):
    """'meta', 'header', or '' depending on where a noindex came from."""
    meta = _robots_tokens(row.get('robots'))
    if 'noindex' in meta or 'none' in meta:
        return 'meta'
    header = _robots_tokens(row.get('x_robots_tag'))
    if 'noindex' in header or 'none' in header:
        return 'header'
    return ''


def nofollow_source(row):
    meta = _robots_tokens(row.get('robots'))
    if 'nofollow' in meta or 'none' in meta:
        return 'meta'
    header = _robots_tokens(row.get('x_robots_tag'))
    if 'nofollow' in header or 'none' in header:
        return 'header'
    return ''


def indexability(row):
    """(Indexable | Non-Indexable, reason) for one crawled row.

    Reasons, in the order they are checked: No Response, Blocked by
    robots.txt, Redirected, Client Error, Server Error, noindex,
    Canonicalised. The first that applies wins, so a 404 with a noindex
    reads "Client Error".
    """
    status = row.get('status_code') or 0
    if row.get('error_type') == 'blocked_by_robots':
        return NON_INDEXABLE, 'Blocked by robots.txt'
    if status == 0:
        return NON_INDEXABLE, 'No Response'
    if row.get('redirects') or 300 <= status < 400:
        return NON_INDEXABLE, 'Redirected'
    if 400 <= status < 500:
        return NON_INDEXABLE, 'Client Error'
    if status >= 500:
        return NON_INDEXABLE, 'Server Error'
    if status != 200:
        # 204 No Content, 206 etc.: nothing a search engine would index
        return NON_INDEXABLE, f'Non-200 Status ({status})'
    source = noindex_source(row)
    if source == 'header':
        return NON_INDEXABLE, 'noindex (X-Robots-Tag)'
    if source:
        return NON_INDEXABLE, 'noindex'
    if is_html(row) and is_canonicalised(row):
        return NON_INDEXABLE, 'Canonicalised'
    return INDEXABLE, ''


def apply_indexability(row):
    """Set the indexability fields on a row (cheap; used while crawling)."""
    label, reason = indexability(row)
    row['indexability'] = label
    row['indexability_status'] = reason
    return row


def _is_broken(status):
    return status is not None and (status == 0 or status >= 400)


def _examples(urls, exclude=None):
    """The first few of `urls` (skipping `exclude`, which callers pass only
    when it is in the list) and how many more there are.

    Stops scanning after EXAMPLES_PER_ISSUE: it runs once per page of a
    duplicate group, so walking the whole group each time would make a
    group of 20,000 identical meta descriptions quadratic.
    """
    shown = []
    for url in urls:
        if url != exclude:
            shown.append(url)
            if len(shown) == EXAMPLES_PER_ISSUE:
                break
    total = len(urls) - (1 if exclude is not None else 0)
    more = total - len(shown)
    return ', '.join(shown) + (f' (+{more} more)' if more > 0 else '')


def _normalise_text(value):
    if isinstance(value, list):
        value = next((v for v in value if isinstance(v, str) and v.strip()), '')
    if not isinstance(value, str):
        return ''
    return ' '.join(value.lower().split())


class CrawlAnalyzer:
    """Runs the site-wide checks over a finished crawl.

    analyze() returns (patches, issues): patches maps each row's URL to the
    analysis fields that changed, and issues are new issue dicts. Rows are
    updated in place as well, so callers only journal the patches.
    """

    def __init__(self, should_exclude=None):
        self.should_exclude = should_exclude or (lambda url: False)
        self.link_score_truncated = False

    def analyze(self, rows, links, sitemap_urls=None, start_url=None):
        started = time.monotonic()
        rows = [r for r in rows if r.get('url') and not r.get('link_check_only')]
        by_url = {r['url']: r for r in rows}

        # Redirected rows are also reachable by their destination, so a
        # canonical naming the destination still finds the crawled content
        by_final = dict(by_url)
        for r in rows:
            dest = r.get('redirected_to')
            if dest:
                try:
                    by_final.setdefault(normalize_url(dest), r)
                except ValueError:
                    pass

        before = {r['url']: tuple(r.get(f) for f in ANALYSIS_FIELDS) for r in rows}
        issues = []

        for r in rows:
            apply_indexability(r)

        inlinks, outlinks = self._link_counts(rows, by_url, links, issues)
        for r in rows:
            if r.get('is_internal'):
                r['inlinks'] = inlinks.get(r['url'], 0)
                r['outlinks'] = outlinks.get(r['url'], 0)

        self._link_score(rows, by_url, links, started)
        self._duplicates(rows, issues)
        self._redirect_graph(rows, by_url, issues)
        self._canonicals(rows, by_final, issues)
        self._sitemap(rows, sitemap_urls, start_url, issues)

        patches = {}
        for r in rows:
            after = tuple(r.get(f) for f in ANALYSIS_FIELDS)
            if after != before[r['url']]:
                patches[r['url']] = {f: r.get(f) for f in ANALYSIS_FIELDS}

        issues = [i for i in issues if not self.should_exclude(i['url'])]
        return patches, issues

    # ------------------------------------------------------------------
    # Links: inlinks/outlinks plus the per-page broken/redirect link report
    # ------------------------------------------------------------------
    def _link_counts(self, rows, by_url, links, issues):
        inlinks = defaultdict(int)
        outlinks = defaultdict(int)
        broken_internal = defaultdict(list)
        broken_external = defaultdict(list)
        to_redirects = defaultdict(list)

        for link in links:
            if link.get('placement') == 'image':
                continue
            source = link.get('source_url')
            target = link.get('target_url')
            if not source or not target or source == target:
                continue
            source_row = by_url.get(source)
            # A redirecting URL's row holds its destination's HTML; those
            # links belong to the destination, not to the redirect
            if source_row is None or source_row.get('redirects'):
                continue
            target_row = by_url.get(target)

            if link.get('is_internal'):
                # (links are stored once per source/target pair, so these
                # are unique inlinks, as Screaming Frog's "Unique Inlinks")
                inlinks[target] += 1
                outlinks[source] += 1
                if target_row is not None:
                    status = target_row.get('status_code')
                    if target_row.get('error_type') == 'blocked_by_robots':
                        continue
                    if _is_broken(status):
                        broken_internal[source].append(f'{target} ({status or "no response"})')
                    elif target_row.get('redirects') or (status and 300 <= status < 400):
                        to_redirects[source].append(target)
                elif _is_broken(link.get('target_status')):
                    broken_internal[source].append(
                        f'{target} ({link.get("target_status") or "no response"})')
            elif _is_broken(link.get('target_status')):
                status = link.get('target_status')
                broken_external[source].append(f'{target} ({status or "no response"})')

        for source, targets in broken_internal.items():
            issues.append({
                'url': source, 'type': 'error', 'category': 'Links',
                'issue': 'Broken Internal Links',
                'details': f"{len(targets)} link{'s' if len(targets) != 1 else ''} "
                           f"to broken internal URLs: {_examples(targets)}"
            })
        for source, targets in broken_external.items():
            issues.append({
                'url': source, 'type': 'warning', 'category': 'Links',
                'issue': 'Broken External Links',
                'details': f"{len(targets)} link{'s' if len(targets) != 1 else ''} "
                           f"to broken external URLs: {_examples(targets)}"
            })
        for source, targets in to_redirects.items():
            issues.append({
                'url': source, 'type': 'warning', 'category': 'Links',
                'issue': 'Internal Links to Redirects',
                'details': f"{len(targets)} link{'s' if len(targets) != 1 else ''} "
                           f"to redirecting URLs (link to the destination instead): "
                           f"{_examples(targets)}"
            })
        return inlinks, outlinks

    # ------------------------------------------------------------------
    # Link Score: PageRank over the internal link graph, scaled to 0-100
    # ------------------------------------------------------------------
    def _link_score(self, rows, by_url, links, started):
        self.link_score_truncated = False
        nodes = [r for r in rows if r.get('is_internal')]
        count = len(nodes)
        if count == 0:
            return
        index = {r['url']: i for i, r in enumerate(nodes)}
        # Redirect rows pass nothing on through links (see _link_counts)
        redirecting = {i for i, r in enumerate(nodes) if r.get('redirects')}

        # Links are unique per source/target pair already (the link
        # manager dedupes them), so no edge set is needed here
        incoming = [[] for _ in range(count)]
        outdegree = [0] * count
        for link in links:
            if not link.get('is_internal') or link.get('placement') == 'image':
                continue
            s = index.get(link.get('source_url'))
            d = index.get(link.get('target_url'))
            if s is None or d is None or s == d or s in redirecting:
                continue
            incoming[d].append(s)
            outdegree[s] += 1

        rank = [1.0 / count] * count
        teleport = (1.0 - LINK_SCORE_DAMPING) / count
        dangling = [i for i in range(count) if outdegree[i] == 0]
        for _ in range(LINK_SCORE_ITERATIONS):
            if time.monotonic() - started > LINK_SCORE_TIME_BUDGET_SECONDS:
                self.link_score_truncated = True
                print('Link Score stopped at its time budget; scores are approximate')
                break
            share = [rank[i] * LINK_SCORE_DAMPING / outdegree[i] if outdegree[i] else 0.0
                     for i in range(count)]
            dangling_share = LINK_SCORE_DAMPING * sum(rank[i] for i in dangling) / count
            base = teleport + dangling_share
            new_rank = [base + sum(map(share.__getitem__, srcs)) if srcs else base
                        for srcs in incoming]
            delta = sum(abs(a - b) for a, b in zip(new_rank, rank))
            rank = new_rank
            if delta < 1e-9 * count:
                break

        # Log scale, so the homepage reads 100 and deep pages are told apart
        low, high = min(rank), max(rank)
        # Ranks equal up to float noise (a cycle, a fully interlinked site)
        # must score equally; scaling last-bit differences onto 0-100
        # would invent a spread that is not there
        if high <= low * (1 + 1e-6):
            has_links = any(outdegree)
            for r in nodes:
                r['link_score'] = 100 if (has_links or count == 1) else 0
            return
        span = math.log(high / low)
        for r, value in zip(nodes, rank):
            score = round(100 * math.log(value / low) / span)
            # Values within the noise band of the minimum read as 0
            r['link_score'] = max(0, min(100, score))

    # ------------------------------------------------------------------
    # Duplicate titles, meta descriptions and H1s across indexable pages
    # ------------------------------------------------------------------
    def _duplicates(self, rows, issues):
        pages = [r for r in rows
                 if r.get('is_internal') and is_html(r)
                 and r.get('indexability') == INDEXABLE]
        for field, issue_name, label in (
                ('title', 'Duplicate Title', 'title'),
                ('meta_description', 'Duplicate Meta Description', 'meta description'),
                ('h1', 'Duplicate H1', 'H1')):
            groups = defaultdict(list)
            for r in pages:
                value = _normalise_text(r.get(field))
                if value:
                    groups[value].append(r['url'])
            for urls in groups.values():
                if len(urls) < 2:
                    continue
                others = len(urls) - 1
                for url in urls:
                    issues.append({
                        'url': url, 'type': 'warning', 'category': 'Duplication',
                        'issue': issue_name,
                        'details': f"Same {label} as {others} other indexable "
                                   f"page{'s' if others != 1 else ''}: {_examples(urls, url)}"
                    })

    # ------------------------------------------------------------------
    # Redirect chains, loops and redirects that end in an error
    # ------------------------------------------------------------------
    def _redirect_graph(self, rows, by_url, issues):
        # Followed redirects: the fetch recorded every hop itself
        for r in rows:
            if r.get('error_type') == 'redirect_loop':
                issues.append({
                    'url': r['url'], 'type': 'error', 'category': 'Redirects',
                    'issue': 'Redirect Loop',
                    'details': r.get('error') or 'Too many redirects (redirect loop)'
                })
                continue
            history = r.get('redirects') or []
            if not history:
                continue
            path = [str((h or {}).get('url') or '?') for h in history] + [r.get('redirected_to') or '?']
            status = r.get('status_code')
            if len(history) >= 2:
                issues.append({
                    'url': r['url'], 'type': 'warning', 'category': 'Redirects',
                    'issue': 'Redirect Chain',
                    'details': f'{len(history)} hops: ' + ' → '.join(path)
                               + (f' ({status})' if status else '')
                })
            if _is_broken(status):
                issues.append({
                    'url': r['url'], 'type': 'error', 'category': 'Redirects',
                    'issue': 'Redirect to Broken URL',
                    'details': f'Redirects to {path[-1]}, which returned {status or "no response"}'
                })

        # Redirects not followed: walk 3xx rows through their Location
        hops = {}
        for r in rows:
            status = r.get('status_code') or 0
            target = r.get('redirect_target')
            if 300 <= status < 400 and target:
                try:
                    hops[r['url']] = normalize_url(urljoin(r['url'], target))
                except ValueError:
                    pass

        for start in hops:
            path = [start]
            seen = {start}
            current = start
            loop = False
            while current in hops and len(path) <= MAX_REDIRECT_HOPS:
                current = hops[current]
                if current in seen:
                    loop = True
                    path.append(current)
                    break
                seen.add(current)
                path.append(current)

            if loop:
                issues.append({
                    'url': start, 'type': 'error', 'category': 'Redirects',
                    'issue': 'Redirect Loop',
                    'details': 'Redirects back on itself: ' + ' → '.join(path)
                })
            else:
                final_row = by_url.get(path[-1])
                final_status = final_row.get('status_code') if final_row else None
                if len(path) > 2:
                    issues.append({
                        'url': start, 'type': 'warning', 'category': 'Redirects',
                        'issue': 'Redirect Chain',
                        'details': f'{len(path) - 1} hops: ' + ' → '.join(path)
                                   + (f' ({final_status})' if final_status else '')
                    })
                if final_row is not None and _is_broken(final_status):
                    issues.append({
                        'url': start, 'type': 'error', 'category': 'Redirects',
                        'issue': 'Redirect to Broken URL',
                        'details': f'Redirects to {path[-1]}, which returned '
                                   f'{final_status or "no response"}'
                    })

    # ------------------------------------------------------------------
    # Canonicals pointing at non-indexable pages, or at another canonical
    # ------------------------------------------------------------------
    def _canonicals(self, rows, by_final, issues):
        for r in rows:
            if not is_html(r) or not r.get('is_internal'):
                continue
            if r.get('indexability_status') != 'Canonicalised':
                continue
            target = canonical_target(r)
            target_row = by_final.get(target)
            if target_row is None or target_row is r:
                continue
            label, reason = target_row.get('indexability'), target_row.get('indexability_status')
            if label == NON_INDEXABLE and reason == 'Canonicalised':
                issues.append({
                    'url': r['url'], 'type': 'warning', 'category': 'Canonicals',
                    'issue': 'Canonical Chain',
                    'details': f'Canonical {target} is itself canonicalised to '
                               f'{canonical_target(target_row)}'
                })
            elif label == NON_INDEXABLE:
                issues.append({
                    'url': r['url'], 'type': 'error', 'category': 'Canonicals',
                    'issue': 'Canonical Points to Non-Indexable URL',
                    'details': f'Canonical {target} is non-indexable ({reason})'
                })

    # ------------------------------------------------------------------
    # Sitemap audit
    # ------------------------------------------------------------------
    def _sitemap(self, rows, sitemap_urls, start_url, issues):
        if not sitemap_urls:
            for r in rows:
                r['in_sitemap'] = None
            return
        start = _safe_normalize(start_url) if start_url else None

        for r in rows:
            in_map = r['url'] in sitemap_urls
            r['in_sitemap'] = in_map
            if not r.get('is_internal'):
                continue
            label, reason = r.get('indexability'), r.get('indexability_status')

            if in_map and label == NON_INDEXABLE:
                issues.append({
                    'url': r['url'], 'type': 'warning', 'category': 'Sitemaps',
                    'issue': 'Non-Indexable URL in Sitemap',
                    'details': f'Listed in the XML sitemap but non-indexable ({reason}). '
                               f'Sitemaps should list only indexable canonical URLs.'
                })

            if not is_html(r) or label != INDEXABLE:
                continue
            if in_map and not r.get('inlinks') and r['url'] != start:
                issues.append({
                    'url': r['url'], 'type': 'warning', 'category': 'Sitemaps',
                    'issue': 'Orphan Page (Sitemap Only)',
                    'details': 'In the XML sitemap but no crawled page links to it'
                })
            elif not in_map:
                issues.append({
                    'url': r['url'], 'type': 'info', 'category': 'Sitemaps',
                    'issue': 'Indexable Page Not in Sitemap',
                    'details': 'Indexable page found by crawling that the XML sitemap does not list'
                })
