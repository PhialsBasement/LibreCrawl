"""Compare two crawls of a site: what was added, removed, or changed.

Rows are matched by URL. The comparison reads only a handful of columns per
crawl (see crawl_db.load_compare_rows) and is one pass over each crawl with
dict lookups, so it is linear in the crawl size.
"""
from collections import Counter

# Change kinds, in the order the UI lists them
CHANGE_KINDS = (
    ('added', 'New URL'),
    ('removed', 'Removed URL'),
    ('status', 'Status code changed'),
    ('indexability', 'Indexability changed'),
    ('title', 'Title changed'),
    ('meta_description', 'Meta description changed'),
    ('h1', 'H1 changed'),
    ('canonical', 'Canonical changed'),
    ('word_count', 'Word count changed'),
    ('new_issue', 'New issue'),
    ('resolved_issue', 'Resolved issue'),
)

# A word-count change smaller than this share of the old count is noise
WORD_COUNT_CHANGE_RATIO = 0.2

_TEXT_FIELDS = (
    ('title', 'title'),
    ('meta_description', 'meta_description'),
    ('h1', 'h1'),
    ('canonical', 'canonical_url'),
)


def _clean(value):
    if value is None:
        return ''
    return ' '.join(str(value).split())


def _index_label(row):
    label = row.get('indexability') or ''
    reason = row.get('indexability_status') or ''
    return f'{label} ({reason})' if reason else label


def _status_label(row):
    status = row.get('status_code')
    if not status:
        return row.get('error_type') or 'no response'
    return str(status)


def compare_crawls(previous_rows, current_rows, previous_issues, current_issues):
    """Diff two crawls.

    previous_rows/current_rows: dicts from load_compare_rows.
    previous_issues/current_issues: (url, issue, type) tuples.

    Returns {'summary': {...}, 'issue_changes': [...], 'changes': [...]},
    where each change is {'url', 'change', 'previous', 'current'}.
    """
    prev = {r['url']: r for r in previous_rows if r.get('url') and not r.get('link_check_only')}
    cur = {r['url']: r for r in current_rows if r.get('url') and not r.get('link_check_only')}

    # Issue rows come straight from SQLite, where the columns are nullable
    previous_issues = [(url, str(issue), kind or '') for url, issue, kind in previous_issues
                       if url and issue]
    current_issues = [(url, str(issue), kind or '') for url, issue, kind in current_issues
                      if url and issue]

    changes = []
    for url, row in cur.items():
        old = prev.get(url)
        if old is None:
            changes.append({'url': url, 'change': 'added', 'previous': '',
                            'current': _status_label(row)})
            continue

        if (old.get('status_code') or 0) != (row.get('status_code') or 0):
            changes.append({'url': url, 'change': 'status',
                            'previous': _status_label(old), 'current': _status_label(row)})

        # Indexability is only compared when both crawls recorded it
        # (crawls saved before it existed have none)
        if old.get('indexability') and row.get('indexability'):
            before, after = _index_label(old), _index_label(row)
            if before != after:
                changes.append({'url': url, 'change': 'indexability',
                                'previous': before, 'current': after})

        for kind, field in _TEXT_FIELDS:
            before, after = _clean(old.get(field)), _clean(row.get(field))
            if before != after:
                changes.append({'url': url, 'change': kind, 'previous': before, 'current': after})

        before, after = old.get('word_count') or 0, row.get('word_count') or 0
        if before != after and abs(after - before) >= max(1, before) * WORD_COUNT_CHANGE_RATIO:
            changes.append({'url': url, 'change': 'word_count',
                            'previous': str(before), 'current': str(after)})

    for url, row in prev.items():
        if url not in cur:
            changes.append({'url': url, 'change': 'removed',
                            'previous': _status_label(row), 'current': ''})

    # Issues: per URL, which issue names appeared or went away. A URL that
    # is only in one crawl is already reported as added/removed, so its
    # issues are not listed again one by one.
    prev_by_url, cur_by_url = {}, {}
    for url, issue, _ in previous_issues:
        prev_by_url.setdefault(url, set()).add(issue)
    for url, issue, _ in current_issues:
        cur_by_url.setdefault(url, set()).add(issue)

    for url, names in cur_by_url.items():
        if url not in prev:
            continue
        for name in sorted(names - prev_by_url.get(url, set())):
            changes.append({'url': url, 'change': 'new_issue', 'previous': '', 'current': name})
    for url, names in prev_by_url.items():
        if url not in cur:
            continue
        for name in sorted(names - cur_by_url.get(url, set())):
            changes.append({'url': url, 'change': 'resolved_issue', 'previous': name, 'current': ''})

    # Totals per issue name, for the summary table
    prev_counts = Counter(issue for _, issue, _ in previous_issues)
    cur_counts = Counter(issue for _, issue, _ in current_issues)
    issue_types = {}
    for _, issue, kind in previous_issues:
        issue_types[issue] = kind
    for _, issue, kind in current_issues:
        issue_types[issue] = kind
    issue_changes = sorted(
        ({'issue': name, 'type': issue_types.get(name, ''),
          'previous': prev_counts.get(name, 0), 'current': cur_counts.get(name, 0),
          'delta': cur_counts.get(name, 0) - prev_counts.get(name, 0)}
         for name in set(prev_counts) | set(cur_counts)),
        key=lambda c: (-abs(c['delta']), c['issue']))

    order = {kind: i for i, (kind, _) in enumerate(CHANGE_KINDS)}
    changes.sort(key=lambda c: (order.get(c['change'], 99), c['url']))

    by_kind = Counter(c['change'] for c in changes)
    summary = {
        'previous_urls': len(prev),
        'current_urls': len(cur),
        'previous_issues': len(previous_issues),
        'current_issues': len(current_issues),
        'changes': {kind: by_kind.get(kind, 0) for kind, _ in CHANGE_KINDS},
    }
    return {'summary': summary, 'issue_changes': issue_changes, 'changes': changes}
