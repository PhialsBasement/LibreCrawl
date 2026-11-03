"""Custom extraction: pull user-defined values out of each page.

Each rule names a column and selects nodes with a CSS selector or an
XPath expression, then reads one of: the visible text, the inner HTML,
the outer HTML, or an attribute. Results land on the page result as
``custom_extraction = {rule name: [values]}``.
"""
import re

import soupsieve
from lxml import etree, html as lxml_html

SELECTOR_TYPES = ('css', 'xpath')
EXTRACT_MODES = ('text', 'inner_html', 'outer_html', 'attribute')

MAX_RULES = 30
MAX_MATCHES_PER_RULE = 50
MAX_VALUE_CHARS = 2000

_WHITESPACE = re.compile(r'\s+')


def _clean_text(text):
    return _WHITESPACE.sub(' ', text or '').strip()


def normalize_rules(raw_rules):
    """Validate rules and return (rules, errors).

    Rules missing a name or selector are dropped silently: those are
    blank rows left in the settings editor. Rules with a selector that
    fails to compile are reported in ``errors``.
    """
    rules, errors, seen = [], [], set()
    if not isinstance(raw_rules, list):
        return [], ['Custom extraction rules must be a list']

    for raw in raw_rules:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get('name') or '').strip()
        selector = str(raw.get('selector') or '').strip()
        if not (name and selector):
            continue

        sel_type = str(raw.get('type') or 'css').lower()
        mode = str(raw.get('mode') or 'text').lower()
        attribute = str(raw.get('attribute') or '').strip()

        if name in seen:
            errors.append(f'"{name}": duplicate extractor name')
            continue
        if sel_type not in SELECTOR_TYPES:
            errors.append(f'"{name}": unknown selector type {sel_type}')
            continue
        if mode not in EXTRACT_MODES:
            errors.append(f'"{name}": unknown extract mode {mode}')
            continue
        if mode == 'attribute' and not attribute:
            errors.append(f'"{name}": attribute mode needs an attribute name')
            continue

        try:
            if sel_type == 'css':
                compiled = soupsieve.compile(selector)
            else:
                compiled = etree.XPath(selector)
        except Exception as exc:
            reason = (str(exc).splitlines() or ['syntax error'])[0]
            label = 'XPath' if sel_type == 'xpath' else 'CSS selector'
            errors.append(f'"{name}": invalid {label} ({reason})')
            continue

        seen.add(name)
        rules.append({
            'name': name, 'type': sel_type, 'selector': selector,
            'mode': mode, 'attribute': attribute, '_compiled': compiled,
        })

    if len(rules) > MAX_RULES:
        errors.append(f'At most {MAX_RULES} extractors are allowed')
        rules = rules[:MAX_RULES]
    return rules, errors


class CustomExtractor:
    """Applies a fixed set of extraction rules to page HTML."""

    def __init__(self, raw_rules):
        self.rules, self.errors = normalize_rules(raw_rules)
        self._needs_lxml = any(r['type'] == 'xpath' for r in self.rules)

    def __bool__(self):
        return bool(self.rules)

    def extract(self, soup, raw_html):
        """Return {rule name: [values]} for one page.

        ``soup`` is the BeautifulSoup tree the crawler already built.
        ``raw_html`` (str or bytes) feeds lxml for XPath rules.
        """
        tree = self._lxml_tree(raw_html) if self._needs_lxml else None
        out = {}
        for rule in self.rules:
            try:
                if rule['type'] == 'css':
                    values = self._css(rule, soup)
                elif tree is not None:
                    values = self._xpath(rule, tree)
                else:
                    values = []
            except Exception as exc:
                values = [f'[extraction error: {exc}]']
            out[rule['name']] = [v[:MAX_VALUE_CHARS] for v in values]
        return out

    @staticmethod
    def _lxml_tree(raw_html):
        if not raw_html:
            return None
        if isinstance(raw_html, str):
            raw_html = raw_html.encode('utf-8')
        try:
            return lxml_html.document_fromstring(raw_html)
        except (etree.ParserError, ValueError):
            return None

    @staticmethod
    def _css(rule, soup):
        values = []
        for el in rule['_compiled'].select(soup, limit=MAX_MATCHES_PER_RULE):
            mode = rule['mode']
            if mode == 'text':
                value = _clean_text(el.get_text(' '))
            elif mode == 'inner_html':
                value = el.decode_contents().strip()
            elif mode == 'outer_html':
                value = str(el).strip()
            else:
                value = el.get(rule['attribute'])
                if isinstance(value, list):
                    value = ' '.join(value)
            if value:
                values.append(value)
        return values

    @staticmethod
    def _xpath(rule, tree):
        result = rule['_compiled'](tree)
        # count(), boolean() and string() return scalars
        if isinstance(result, bool):
            return ['true' if result else 'false']
        if isinstance(result, float):
            return [str(int(result)) if result.is_integer() else str(result)]
        if isinstance(result, str):
            text = _clean_text(result)
            return [text] if text else []

        values = []
        for node in result[:MAX_MATCHES_PER_RULE]:
            if isinstance(node, str):
                value = _clean_text(node)
            elif not isinstance(node.tag, str):
                continue  # comments and processing instructions
            elif rule['mode'] == 'text':
                value = _clean_text(node.text_content())
            elif rule['mode'] == 'inner_html':
                value = ((node.text or '') + ''.join(
                    etree.tostring(child, encoding='unicode', method='html')
                    for child in node)).strip()
            elif rule['mode'] == 'outer_html':
                value = etree.tostring(node, encoding='unicode', method='html',
                                       with_tail=False).strip()
            else:
                value = node.get(rule['attribute'])
            if value:
                values.append(value)
        return values
