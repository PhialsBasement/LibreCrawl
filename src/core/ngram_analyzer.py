"""N-gram analysis over crawled page text and inlinks."""
import re
from collections import Counter

_EXCLUDED_TAGS = ('script', 'style', 'noscript', 'nav', 'footer')
_WORD_RE = re.compile(r'[^\s]+')
_STRIP_CHARS = '.,;:!?()[]{}<>\"\'“”’'


def visible_text(soup):
    """Return body text without script/style/nav/footer markup."""
    root = soup.find('body') or soup
    parts = []
    for node in root.find_all(string=True):
        parent = node.parent
        if parent is None:
            continue
        blocked = False
        for ancestor in [parent] + list(parent.parents):
            if ancestor.name in _EXCLUDED_TAGS:
                blocked = True
                break
        if not blocked:
            text = node.strip()
            if text:
                parts.append(text)
    return ' '.join(parts)


def heading_texts(soup):
    """Collect the text of every heading from h1 through h6."""
    texts = []
    for level in range(1, 7):
        for tag in soup.find_all(f'h{level}'):
            text = tag.get_text(' ', strip=True)
            if text:
                texts.append(text)
    return texts


def tokenize(text):
    if not text:
        return []
    tokens = []
    for token in _WORD_RE.findall(text.lower()):
        token = token.strip(_STRIP_CHARS)
        if token and re.search(r'\w', token):
            tokens.append(token)
    return tokens


def count_ngrams(tokens, n):
    return Counter(tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1))


class NgramAnalyzer:
    def aggregate(self, urls, links, selected_urls=None, n=1):
        """Aggregate n-grams across selected URLs, including inlinks."""
        n = max(1, min(6, int(n)))
        selected = set(selected_urls) if selected_urls is not None else {u.get('url') for u in urls}

        body_counts = Counter()
        unlinked_counts = Counter()
        heading_counts = Counter()
        title_counts = Counter()
        inlink_counts = Counter()
        alt_counts = Counter()
        body_total = 0
        url_presence = {}

        anchors_by_target = {}
        alts_by_target = {}
        for link in links:
            target = link.get('target_url')
            if target not in selected:
                continue
            anchor = link.get('anchor_text') or ''
            alt = link.get('anchor_alt') or ''
            if anchor:
                anchors_by_target.setdefault(target, []).append(anchor)
            if alt:
                alts_by_target.setdefault(target, []).append(alt)

        for u in urls:
            url = u.get('url')
            if url not in selected:
                continue

            tokens = tokenize(u.get('body_text') or '')
            counts = count_ngrams(tokens, n)
            body_counts.update(counts)
            body_total += sum(counts.values())

            anchor_counts = count_ngrams(tokenize(' '.join(anchors_by_target.get(url, []))), n)
            alt_counts.update(count_ngrams(tokenize(' '.join(alts_by_target.get(url, []))), n))
            for gram, count in counts.items():
                unlinked_counts[gram] += max(0, count - anchor_counts.get(gram, 0))

            heading_counts.update(count_ngrams(tokenize(' '.join(u.get('heading_texts') or [])), n))
            title_counts.update(count_ngrams(tokenize(u.get('title') or ''), n))
            inlink_counts.update(anchor_counts)

            for gram in set(counts):
                url_presence.setdefault(gram, set()).add(url)

        rows = []
        grams = set(body_counts) | set(heading_counts) | set(title_counts) | set(inlink_counts) | set(alt_counts)
        for gram in grams:
            body = body_counts.get(gram, 0)
            density = (body / body_total * 100) if body_total else 0.0
            total = body + title_counts.get(gram, 0) + inlink_counts.get(gram, 0) + alt_counts.get(gram, 0)
            rows.append({
                'gram': ' '.join(gram),
                'body': body,
                'density': round(density, 2),
                'body_unlinked': unlinked_counts.get(gram, 0),
                'headings': heading_counts.get(gram, 0),
                'title': title_counts.get(gram, 0),
                'inlinks_anchor': inlink_counts.get(gram, 0),
                'inlinks_alt': alt_counts.get(gram, 0),
                'total': total,
                'url_count': len(url_presence.get(gram, set()))
            })

        rows.sort(key=lambda r: (-r['total'], r['gram']))
        return rows
