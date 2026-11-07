"""Deterministic crawler tests against local fixture sites.

Runs WebCrawler in-process against tiny HTTP servers started by this script,
so every behaviour is checked without touching a third-party site. No test
framework and no network access required:

    python tests/fixture_tests.py

Each test pins down a bug that reached production once, so a failure here
means a real regression rather than a flaky expectation:

  1. relative links on a page reached through a cross-domain redirect resolve
     against the site that served the content, not the URL that was requested
  2. images hosted off-domain (CDNs) and external links are HEAD-checked and
     listed even while "crawl external links" is off, without crawling
     off-domain pages
  3. sitemap discovery does not block start_crawl, and a crawl does not
     finish while discovery is still feeding the queue
  4. max_urls budgets pages actually fetched, not the rows synthesized from
     image HEAD checks
  5. the event journal never announces an update before the row it refers to,
     and never repeats a row, even while a client polls during the crawl
"""
import http.server
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.crawler import WebCrawler  # noqa: E402

# Fixture servers bind here upward. Override if these clash locally.
BASE_PORT = int(os.environ.get('FIXTURE_BASE_PORT', '8911'))

PASSED, FAILED = [], []


def result(name, ok, detail=''):
    (PASSED if ok else FAILED).append(name)
    print(f"  {'PASS' if ok else 'FAIL'}  {name}{(' - ' + detail) if detail else ''}")


def serve(handler, port):
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', port), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def html(body):
    return f'<html><head><title>t</title></head><body>{body}</body></html>'


def png():
    return b'\x89PNG\r\n\x1a\n' + b'x' * 40


def make_handler(routes, hits=None, slow_paths=(), slow_seconds=0.0):
    """Build a handler serving `routes`: path -> html str, bytes, (code, location),
    or {'body': html str, 'headers': {name: value}} for extra response headers."""

    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def log_message(self, *args):
            pass

        def _send(self, code, body=b'', ctype='text/html'):
            self.send_response(code)
            self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            if body and self.command == 'GET':
                self.wfile.write(body)

        def do_GET(self):
            if hits is not None:
                hits.append(f'{self.command} {self.path}')
            if any(self.path.startswith(p) for p in slow_paths):
                time.sleep(slow_seconds)

            route = routes.get(self.path)
            if route is None:
                self._send(404, b'not found')
            elif isinstance(route, tuple):
                self.send_response(route[0])
                self.send_header('Location', route[1])
                self.send_header('Content-Length', '0')
                self.end_headers()
            elif isinstance(route, bytes):
                ctype = 'image/png' if self.path.endswith('.png') else 'application/octet-stream'
                self._send(200, route, ctype)
            elif isinstance(route, dict):
                body = route['body'].encode()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.send_header('Content-Length', str(len(body)))
                for name, value in route.get('headers', {}).items():
                    self.send_header(name, value)
                self.end_headers()
                if self.command == 'GET':
                    self.wfile.write(body)
            else:
                self._send(200, route.encode())

        do_HEAD = do_GET

    return Handler


def crawl(url, timeout=120, url_list=None, **config):
    """Run a crawl to completion and return the crawler for inspection."""
    crawler = WebCrawler()
    crawler.config.update({
        'delay': 0.02, 'concurrency': 5, 'max_urls': 200, 'max_depth': 4,
        'crawl_external': False, 'crawl_images': False,
        'discover_sitemaps': False, 'respect_robots': False,
    })
    crawler.config.update(config)

    ok, message = crawler.start_crawl(url, url_list=url_list)
    assert ok, message
    deadline = time.time() + timeout
    while crawler.is_running and time.time() < deadline:
        time.sleep(0.1)
    assert not crawler.is_running, 'crawl did not finish within timeout'
    return crawler


def test_cross_domain_redirect():
    """A page that redirects off-domain must not mint internal URLs."""
    site_a, site_b = BASE_PORT, BASE_PORT + 1
    a = serve(make_handler({
        '/': html(f'<a href="/go">offsite</a><a href="/local.html">local</a>'),
        '/local.html': html('<p>local page</p>'),
        '/go': (302, f'http://127.0.0.1:{site_b}/landing'),
    }), site_a)
    b_hits = []
    b = serve(make_handler({
        '/landing': html('<a href="/issues">issues</a><a href="/pulls">pulls</a>'),
    }, hits=b_hits), site_b)
    try:
        crawler = crawl(f'http://127.0.0.1:{site_a}/')
        urls = {r['url'] for r in crawler.crawl_results}
        targets = {l['target_url'] for l in crawler.link_manager.all_links}

        phantoms = [u for u in urls
                    if f':{site_a}' in u and ('/issues' in u or '/pulls' in u)]
        result('redirect: no phantom internal URLs', not phantoms, str(phantoms[:2]))

        go = next(r for r in crawler.crawl_results if r['url'].endswith('/go'))
        result('redirect: chain and destination recorded',
               bool(go.get('redirects'))
               and go.get('redirected_to', '').endswith('/landing'))

        result('redirect: offsite links attributed to the other host',
               f'http://127.0.0.1:{site_b}/issues' in targets)
        # (with crawl_external off, offsite links are HEAD-checked for the
        # External tab, but never fetched)
        result('redirect: offsite content does not enter the queue',
               'GET /issues' not in b_hits, str(b_hits))
    finally:
        a.shutdown()
        b.shutdown()


def test_external_images():
    """With crawl_external off, off-domain images (CDNs) and external links are
    HEAD-checked and listed, but the external site is never crawled."""
    site, other = BASE_PORT + 2, BASE_PORT + 3
    other_hits = []
    off = f'http://127.0.0.1:{other}'
    a = serve(make_handler({
        '/': html(f'<img src="/in.png"><img src="{off}/out.png">'
                  f'<a href="{off}/page">offsite page</a>'
                  f'<a href="{off}/gone">dead link</a>'
                  f'<a href="{off}/no-head">HEAD refused</a>'
                  f'<a href="javascript:void(0)">js</a>'),
        '/in.png': png(),
    }), site)

    class NoHead(make_handler({'/out.png': png(), '/page': html('<a href="/deeper">x</a>'),
                               '/no-head': html('')}, hits=other_hits)):
        def do_HEAD(self):
            if self.path == '/no-head':
                other_hits.append(f'HEAD {self.path}')
                self._send(405)
            else:
                self.do_GET()

    b = serve(NoHead, other)
    try:
        crawler = crawl(f'http://127.0.0.1:{site}/')
        rows = {r['url']: r for r in crawler.crawl_results}
        result('images: offsite image listed as a row', f'{off}/out.png' in rows)
        result('images: offsite image HEAD-checked', 'HEAD /out.png' in other_hits, str(other_hits))
        result('images: same-domain image still listed',
               f'http://127.0.0.1:{site}/in.png' in rows)

        ext = rows.get(f'{off}/page')
        result('external: link listed as an external row',
               ext is not None and ext['is_internal'] is False and ext['status_code'] == 200,
               str(ext and (ext['is_internal'], ext['status_code'])))
        result('external: link HEAD-checked, never fetched',
               'HEAD /page' in other_hits and 'GET /page' not in other_hits
               and not any('/deeper' in h for h in other_hits), str(other_hits))
        result('external: dead link reports 404',
               rows.get(f'{off}/gone', {}).get('status_code') == 404)
        result('external: HEAD 405 falls back to GET',
               rows.get(f'{off}/no-head', {}).get('status_code') == 200, str(other_hits))
        link_statuses = {l['target_url']: l['target_status'] for l in crawler.link_manager.all_links}
        result('external: link status shown in Links tab',
               link_statuses.get(f'{off}/gone') == 404, str(link_statuses))
        result('external: link rows flagged link_check_only (left out of Overview)',
               ext is not None and ext.get('link_check_only') is True)
        result('external: offsite image rows not flagged (stay in Overview)',
               rows.get(f'{off}/out.png', {}).get('link_check_only') is False)
        result('external: crawled pages not flagged',
               not rows[f'http://127.0.0.1:{site}/'].get('link_check_only'))
        result('external: non-http links ignored',
               not any(u.startswith('javascript:') for u in rows))

        other_hits.clear()
        crawler = crawl(f'http://127.0.0.1:{site}/', crawl_external=True)
        result('external: crawled for real when crawl_external is on',
               'GET /page' in other_hits and 'GET /deeper' in other_hits, str(other_hits))
    finally:
        a.shutdown()
        b.shutdown()


def test_sitemap_discovery_is_async():
    """Discovery runs in the background but still gates completion."""
    site = BASE_PORT + 4
    sitemap = ('<?xml version="1.0" encoding="UTF-8"?><urlset>'
               f'<url><loc>http://127.0.0.1:{site}/only-in-sitemap.html</loc></url>'
               '</urlset>')
    a = serve(make_handler({
        '/': html('<p>root</p>'),
        '/only-in-sitemap.html': html('<p>reachable only via sitemap</p>'),
        '/sitemap.xml': sitemap,
    }, slow_paths=('/sitemap',), slow_seconds=2.0), site)
    try:
        crawler = WebCrawler()
        crawler.config.update({'delay': 0.02, 'max_urls': 50, 'max_depth': 3,
                               'respect_robots': False, 'discover_sitemaps': True})
        started = time.time()
        ok, message = crawler.start_crawl(f'http://127.0.0.1:{site}/')
        latency = time.time() - started
        assert ok, message

        deadline = time.time() + 60
        while crawler.is_running and time.time() < deadline:
            time.sleep(0.1)
        urls = {r['url'] for r in crawler.crawl_results}

        result('sitemap: start_crawl returns immediately',
               latency < 0.5, f'{latency * 1000:.0f}ms')
        result('sitemap: crawl waits for slow discovery',
               f'http://127.0.0.1:{site}/only-in-sitemap.html' in urls)
    finally:
        a.shutdown()


def test_max_urls_counts_pages_not_images():
    """Synthesized image rows must not consume the crawl budget."""
    site = BASE_PORT + 5
    routes = {'/': html(''.join(f'<img src="/img{i}.png">' for i in range(30))
                        + ''.join(f'<a href="/p{i}.html">page</a>' for i in range(10)))}
    for i in range(30):
        routes[f'/img{i}.png'] = png()
    for i in range(10):
        routes[f'/p{i}.html'] = html(f'<p>page {i}</p><a href="/">home</a>')

    a = serve(make_handler(routes), site)
    try:
        limit, concurrency = 5, 5
        crawler = crawl(f'http://127.0.0.1:{site}/', max_urls=limit, concurrency=concurrency)
        pages = [r for r in crawler.crawl_results
                 if (r.get('content_type') or '').startswith('text/html')]
        # The submit loop fills every worker slot before rechecking the budget,
        # so a crawl may overshoot by up to `concurrency` pages. What must not
        # happen is image rows eating the budget, which used to leave a single
        # real page crawled no matter how high the limit was.
        result('max_urls: budgets fetched pages, not image rows',
               limit <= len(pages) <= limit + concurrency,
               f'{len(pages)} pages, {len(crawler.crawl_results)} rows total')
        result('max_urls: image rows still captured',
               len(crawler.crawl_results) > len(pages))
    finally:
        a.shutdown()


def test_event_ordering_under_polling():
    """The journal stays consistent while a client polls mid-crawl."""
    site = BASE_PORT + 6
    routes = {'/': html(''.join(f'<a href="/p{i}.html">p</a>' for i in range(40)))}
    for i in range(40):
        routes[f'/p{i}.html'] = html(
            f'<img src="/i{i}.png">'
            f'<a href="/p{(i + 1) % 40}.html">next</a><a href="/">home</a>')
        routes[f'/i{i}.png'] = png()

    a = serve(make_handler(routes), site)
    try:
        crawler = WebCrawler()
        crawler.config.update({'delay': 0.0, 'concurrency': 8, 'max_urls': 40,
                               'max_depth': 3, 'respect_robots': False,
                               'discover_sitemaps': False})
        problems = []
        seen_urls, seen_links = set(), set()
        cursor = {'seq': 0}

        def poll():
            """Mirror what the browser client does on every poll."""
            while crawler.is_running or cursor['seq'] < len(crawler.event_log._events):
                _, events, latest, _ = crawler.event_log.events_since(
                    cursor['seq'], crawler.event_log.epoch)
                cursor['seq'] = latest
                for event in events:
                    kind, data = event['kind'], event['data']
                    if kind == 'url':
                        if data['url'] in seen_urls:
                            problems.append(('duplicate url', data['url']))
                        seen_urls.add(data['url'])
                    elif kind == 'url_update':
                        if data['url'] not in seen_urls:
                            problems.append(('url_update before url', data['url']))
                    elif kind == 'link':
                        key = data['source_url'] + '|' + data['target_url']
                        if key in seen_links:
                            problems.append(('duplicate link', key))
                        seen_links.add(key)
                    elif kind == 'link_update':
                        key = data['source_url'] + '|' + data['target_url']
                        if key not in seen_links:
                            problems.append(('link_update before link', key))
                # this is the call the status route makes, and it emits events
                crawler.get_status_light()
                time.sleep(0.05)

        ok, message = crawler.start_crawl(f'http://127.0.0.1:{site}/')
        assert ok, message
        poller = threading.Thread(target=poll, daemon=True)
        poller.start()

        deadline = time.time() + 90
        while crawler.is_running and time.time() < deadline:
            time.sleep(0.1)
        time.sleep(1.5)  # let the poller drain the tail

        result('events: no ordering violations under concurrent polling',
               not problems, f'{len(problems)} found: {problems[:3]}')
        result('events: replayed client state matches the crawler',
               seen_urls == {r['url'] for r in crawler.crawl_results},
               f'{len(seen_urls)} client rows vs {len(crawler.crawl_results)} crawler rows')
    finally:
        a.shutdown()


def test_discovered_counts_image_rows():
    """Issue #94: the discovered counter ignored synthesized image rows."""
    site = BASE_PORT + 7
    routes = {'/': html(''.join(f'<img src="/i{i}.png">' for i in range(6))
                        + '<a href="/p1.html">p</a>'),
              '/p1.html': html('<p>page</p>')}
    for i in range(6):
        routes[f'/i{i}.png'] = png()

    a = serve(make_handler(routes), site)
    try:
        crawler = crawl(f'http://127.0.0.1:{site}/')
        status = crawler.get_status_light()
        discovered = status['stats']['discovered']
        crawled = status['stats']['crawled']
        rows = len(crawler.crawl_results)

        result('discovered counts every row, images included',
               discovered >= rows,
               f'discovered={discovered} crawled={crawled} rows={rows}')
        result('discovered is never behind crawled',
               discovered >= crawled, f'{discovered} vs {crawled}')
        result('image rows were actually synthesized',
               rows > 2, f'{rows} rows')
    finally:
        a.shutdown()


def test_js_response_time_excludes_render_wait():
    """Issue #93: response_time included js_wait_time, flagging every page."""
    if not _playwright_available():
        result('js response time excludes the render wait', True,
               'skipped, playwright not installed')
        return

    site = BASE_PORT + 8
    a = serve(make_handler({'/': html('<h1>fast</h1>')}), site)
    try:
        wait = 3
        crawler = crawl(f'http://127.0.0.1:{site}/', max_urls=1, enable_javascript=True,
                        js_wait_time=wait, js_max_concurrent_pages=1, timeout=180)
        pages = [r for r in crawler.crawl_results
                 if (r.get('content_type') or '').startswith('text/html')]
        if not pages:
            result('js response time excludes the render wait', False, 'no page crawled')
            return

        page = pages[0]
        response_ms = page.get('response_time') or 0
        render_ms = page.get('render_time') or 0

        result('response_time excludes the render wait',
               response_ms < wait * 1000, f'{response_ms}ms with a {wait}s wait')
        result('response_time stays under the slow threshold for a fast page',
               response_ms < 3000, f'{response_ms}ms')
        result('render_time is reported separately and includes the wait',
               render_ms >= wait * 1000, f'{render_ms}ms')

        from src.core.issue_detector import IssueDetector
        detector = IssueDetector([])
        detector.detect_issues(page)
        slow = [i for i in detector.detected_issues
                if i.get('issue') == 'Slow Response Time']
        result('a fast page is not flagged as slow',
               not slow, str(slow[:1]))
    finally:
        a.shutdown()


def test_duplicate_detection_is_linear():
    """A site of N near-identical pages (suburb "doorway" pages) used to hold
    the crawl in "finishing up" for minutes and produce N² duplicate issues
    (700k rows for 1,000 pages), locking SQLite while they were saved. It must
    finish promptly with exactly one issue per page."""
    from collections import Counter
    from src.core.issue_detector import IssueDetector

    site = BASE_PORT + 9
    count = 60
    routes = {'/': html(''.join(f'<a href="/area-{i}/">{i}</a>' for i in range(count)))}
    for i in range(count):
        routes[f'/area-{i}/'] = (
            f'<html><head><title>Asbestos Removal Area{i} | Get a Free Quote Today!</title>'
            f'<meta name="description" content="Proudly known as the best Asbestos Removal '
            f'experts in Area{i}! Enjoy peace of mind."></head>'
            f'<body><h1>Asbestos Removal Area{i}</h1><p>{"word " * 300}</p></body></html>')
    a = serve(make_handler(routes), site)
    try:
        started = time.time()
        crawler = crawl(f'http://127.0.0.1:{site}/', max_urls=count + 1,
                        enable_duplication_check=True, duplication_threshold=0.85)
        elapsed = time.time() - started
        dupes = [i for i in crawler.issue_detector.get_issues()
                 if i.get('issue') == 'Duplicate Content Detected']
        per_url = Counter(i['url'] for i in dupes)
        result('one duplicate issue per templated page',
               len(dupes) == count and per_url and max(per_url.values()) == 1,
               f'{len(dupes)} issues for {count} pages')
        result('each issue counts the other templated pages',
               bool(dupes) and all(f'{count - 1} similar pages' in i['details'] for i in dupes),
               dupes[0]['details'][:100] if dupes else 'no issues')
        result('the unrelated index page is not flagged',
               f'http://127.0.0.1:{site}/' not in per_url)
        result('crawl finished promptly', elapsed < 60, f'{elapsed:.1f}s')
    finally:
        a.shutdown()

    # Scale check on the detector alone: 1,500 templated pages used to take
    # ~10 minutes of pairwise SequenceMatcher calls.
    pages = [{'url': f'https://x.au/p{i}/', 'status_code': 200, 'content_type': 'text/html',
              'title': f'Asbestos Removal Area{i} | Get a Free Quote Today!',
              'meta_description': f'Proudly known as the best Asbestos Removal experts in Area{i}!',
              'h1': f'Asbestos Removal Area{i}', 'word_count': 1000 + i % 9} for i in range(1500)]
    detector = IssueDetector()
    started = time.time()
    detector.detect_duplication_issues(pages, 0.85)
    elapsed = time.time() - started
    result('1,500 templated pages produce 1,500 issues quickly',
           len(detector.get_issues()) == 1500 and elapsed < 30 and not detector.duplication_truncated,
           f'{len(detector.get_issues())} issues in {elapsed:.1f}s')


def test_export_formats_apply_to_every_data_type():
    """The format picked in Settings must apply to URLs, links AND issues.
    Links/issues used to fall back to CSV for XML, and "Excel (XLSX)" was
    offered in the UI but never implemented, so it silently produced CSV."""
    import base64
    import json
    import types
    import xml.etree.ElementTree as ET
    from io import BytesIO

    os.environ.setdefault('LOCAL_MODE', 'true')
    import main as app_module
    from openpyxl import load_workbook
    from src.core.issue_detector import IssueDetector

    urls = [{'url': 'https://e.au/', 'status_code': 200, 'title': 'Home', 'h2': ['a', 'b']},
            {'url': 'https://e.au/p', 'status_code': 404, 'title': 'Gone', 'h2': []}]
    links = [{'source_url': 'https://e.au/', 'target_url': 'https://e.au/p', 'anchor_text': 'p',
              'is_internal': True, 'target_domain': 'e.au', 'target_status': 404, 'placement': 'body'}]
    issues = [{'url': 'https://e.au/p', 'type': 'error', 'category': 'HTTP', 'issue': 'Not Found',
               'details': '404'}]
    formats = (('csv', 'text/csv'), ('json', 'application/json'),
               ('xml', 'application/xml'), ('xlsx', app_module.XLSX_MIMETYPE))

    def parses(fmt, data, expect_rows):
        if fmt == 'xlsx':
            rows = list(load_workbook(BytesIO(data)).active.iter_rows(values_only=True))
            return len(rows) == expect_rows + 1
        if fmt == 'xml':
            root = ET.fromstring(data)
            return len(root[0]) == expect_rows
        if fmt == 'json':
            return len(json.loads(data)['data']) == expect_rows
        return data.decode().count('\n') == expect_rows + 1

    client = app_module.app.test_client()
    with client.session_transaction() as s:
        s['user_id'] = 1
        s['username'] = 'fixture'
        s['tier'] = 'admin'

    # Streaming endpoint (active or loaded crawl): seed this session's crawler.
    client.get('/api/crawl_status?stats_only=1')
    with client.session_transaction() as s:
        crawler = app_module.crawler_instances[s['session_id']]['crawler']
    crawler.crawl_results = urls
    crawler.issue_detector = IssueDetector()
    crawler.issue_detector.detected_issues = list(issues)
    crawler.link_manager = types.SimpleNamespace(all_links=[dict(l) for l in links])
    for data_type, expect_rows in (('urls', 2), ('links', 1), ('issues', 1)):
        for fmt, mimetype in formats:
            resp = client.get(f'/api/export_stream?format={fmt}&type={data_type}&fields=url,title,h2')
            disposition = resp.headers.get('Content-Disposition', '')
            ok = (resp.status_code == 200 and resp.mimetype == mimetype
                  and disposition.endswith('.' + fmt) and parses(fmt, resp.data, expect_rows))
            result(f'streaming {data_type} export honours {fmt}', ok,
                   f'{resp.status_code} {resp.mimetype} {disposition}')

    # Legacy endpoint (crawl loaded from a file, data lives in the browser).
    for fmt, mimetype in formats:
        resp = client.post('/api/export_data', json={
            'format': fmt, 'fields': ['url', 'title', 'links_detailed', 'issues_detected'],
            'localData': {'urls': urls, 'links': links, 'issues': issues}})
        body = resp.get_json() or {}
        files = body.get('files') or []
        ok = body.get('success') and len(files) == 3 and all(
            f['mimetype'] == mimetype and f['filename'].endswith('.' + fmt) for f in files)
        if ok and fmt == 'xlsx':
            ok = all(f.get('encoding') == 'base64'
                     and parses('xlsx', base64.b64decode(f['content']), 1 if 'export' not in f['filename'] else 2)
                     for f in files)
        result(f'legacy export honours {fmt} for every file', bool(ok),
               ', '.join(f['filename'] for f in files) if files else str(body)[:120])


def test_empty_alt_is_not_missing_alt():
    """Issue #95: alt="" is correct for decorative images, not a defect."""
    site = BASE_PORT + 11
    page = html('<img src="/a.png" alt="A hand holding a crawler report">'
                '<img src="/b.png" alt="">'
                '<img src="/c.png">')
    routes = {'/': page}
    for name in ('a', 'b', 'c'):
        routes[f'/{name}.png'] = png()

    a = serve(make_handler(routes), site)
    try:
        crawler = crawl(f'http://127.0.0.1:{site}/')
        root = next((r for r in crawler.crawl_results
                     if r['url'].rstrip('/').endswith(str(site))), None)
        if root is None:
            root = next(r for r in crawler.crawl_results
                        if (r.get('content_type') or '').startswith('text/html'))

        images = {img['src'].rsplit('/', 1)[-1]: img for img in root.get('images', [])}
        result('alt extraction keeps all three images',
               len(images) == 3, str(sorted(images)))

        result('described image records its alt',
               images['a.png'].get('alt') == 'A hand holding a crawler report'
               and images['a.png'].get('has_alt') is True)
        result('decorative image is marked as having an alt',
               images['b.png'].get('alt') == '' and images['b.png'].get('has_alt') is True)
        result('image with no attribute is marked as missing',
               images['c.png'].get('has_alt') is False)

        from src.core.issue_detector import IssueDetector
        detector = IssueDetector([])
        detector.detect_issues(root)
        alt_issues = [i for i in detector.detected_issues
                      if i.get('issue') == 'Images Without Alt Text']

        result('exactly one image is reported, not two',
               len(alt_issues) == 1 and '1 of 3' in alt_issues[0]['details'],
               alt_issues[0]['details'] if alt_issues else 'no issue raised')
        result('the decorative image is called out as fine',
               bool(alt_issues) and 'decorative' in alt_issues[0]['details'],
               alt_issues[0]['details'] if alt_issues else '')

        # a page where every image is correctly marked must raise nothing
        clean = dict(root)
        clean['images'] = [images['a.png'], images['b.png']]
        detector.detected_issues = []
        detector.detect_issues(clean)
        result('correct markup raises no alt warning at all',
               not [i for i in detector.detected_issues
                    if i.get('issue') == 'Images Without Alt Text'])
    finally:
        a.shutdown()


def test_crawl_delay_is_honoured():
    """The delay setting must space out page fetches without JS too."""
    site = BASE_PORT + 12
    stamps = []
    pages = {'/': html(''.join(f'<a href="/p{i}">p{i}</a>' for i in range(9)))}
    pages.update({f'/p{i}': html('leaf') for i in range(9)})

    class Timed(http.server.BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def log_message(self, *args):
            pass

        def do_GET(self):
            if self.command == 'GET':
                stamps.append(time.time())
            body = pages.get(self.path, 'not found').encode()
            self.send_response(200 if self.path in pages else 404)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            if self.command == 'GET':
                self.wfile.write(body)

        do_HEAD = do_GET

    srv = serve(Timed, site)
    try:
        crawler = crawl(f'http://127.0.0.1:{site}/', delay=0.5, concurrency=5)
        gaps = [b - a for a, b in zip(stamps, stamps[1:])]
        result('delay: every page was fetched', len(crawler.crawl_results) == 10,
               f'{len(crawler.crawl_results)} rows')
        result('delay: fetches spaced by the configured 0.5s', min(gaps) >= 0.45,
               f'smallest gap {min(gaps):.3f}s over {len(stamps)} GETs')
    finally:
        srv.shutdown()


def test_list_mode_fetches_only_the_list():
    """List mode fetches the listed URLs across any number of sites,
    follows no links, skips sitemaps and honours robots.txt."""
    site_a, site_b = BASE_PORT + 13, BASE_PORT + 14
    a_hits, b_hits = [], []
    a = serve(make_handler({
        '/robots.txt': 'User-agent: *\nDisallow: /private\n',
        '/a': html('<a href="/b">b</a><a href="/c">c</a><img src="/i.png">'),
        '/b': html('never listed'),
        '/c': html('<a href="/b">b</a>'),
        '/private': html('secret'),
        '/i.png': png(),
    }, hits=a_hits), site_a)
    b = serve(make_handler({
        '/x': html(f'<a href="http://127.0.0.1:{site_a}/b">b</a>'),
    }, hits=b_hits), site_b)
    base_a, base_b = f'http://127.0.0.1:{site_a}', f'http://127.0.0.1:{site_b}'
    listed = [f'{base_a}/a', f'{base_a}/c', f'{base_b}/x', f'{base_a}/a',
              '', f'{base_a}/private', f'{base_a}/missing']
    try:
        crawler = crawl(listed[0], url_list=listed, respect_robots=True,
                        discover_sitemaps=True, max_depth=4)
        rows = {r['url']: r for r in crawler.crawl_results}
        expected = {f'{base_a}/a', f'{base_a}/c', f'{base_b}/x',
                    f'{base_a}/private', f'{base_a}/missing'}
        result('list: one row per listed URL, duplicates and blanks dropped',
               set(rows) == expected and len(crawler.crawl_results) == 5,
               str(sorted(rows)))
        result('list: links are recorded but never followed',
               'GET /b' not in a_hits
               and any(l['target_url'].endswith('/b') for l in crawler.link_manager.all_links),
               str(a_hits))
        result('list: pages on a second site are crawled too',
               rows.get(f'{base_b}/x', {}).get('status_code') == 200)
        result('list: sitemap discovery is skipped',
               all('sitemap' not in h for h in a_hits + b_hits), str(a_hits))
        private = rows.get(f'{base_a}/private', {})
        result('list: robots.txt disallowed URL is reported, not fetched',
               private.get('error_type') == 'blocked_by_robots'
               and 'GET /private' not in a_hits, str(private.get('error_type')))
        result('list: broken listed URL reports its status',
               rows.get(f'{base_a}/missing', {}).get('status_code') == 404)
        result('list: crawl is flagged as list mode in the config snapshot',
               crawler.config.get('list_mode') is True)

        empty = WebCrawler()
        ok, message = empty.start_crawl('', url_list=['', '   '])
        result('list: an empty list is rejected', not ok, message)
    finally:
        a.shutdown()
        b.shutdown()


def test_custom_extraction():
    """CSS and XPath rules pull values from every page, show up as one
    export column each, and bad selectors are refused when saving."""
    os.environ.setdefault('LOCAL_MODE', 'true')
    import main as app_module
    from src.settings_manager import SettingsManager

    site = BASE_PORT + 15
    product = html(
        '<h1 class="name">Blue <em>Mug</em></h1>'
        '<span class="price" data-currency="EUR"> 9.50 </span>'
        '<ul><li class="tag">kitchen</li><li class="tag">gift</li></ul>'
        '<a href="/other">other</a>')
    srv = serve(make_handler({'/': product, '/other': html('<p>no product</p>')}), site)
    rules = [
        {'name': 'Name', 'type': 'css', 'selector': 'h1.name', 'mode': 'text'},
        {'name': 'Name HTML', 'type': 'css', 'selector': 'h1.name', 'mode': 'inner_html'},
        {'name': 'Currency', 'type': 'xpath', 'mode': 'attribute', 'attribute': 'data-currency',
         'selector': '//span[@class="price"]'},
        {'name': 'Price', 'type': 'xpath', 'selector': 'normalize-space(//span[@class="price"])'},
        {'name': 'Tags', 'type': 'xpath', 'selector': '//li[@class="tag"]/text()'},
        {'name': 'Tag count', 'type': 'xpath', 'selector': 'count(//li[@class="tag"])'},
    ]
    try:
        crawler = crawl(f'http://127.0.0.1:{site}/', custom_extractors=rules)
        rows = {r['url'].rsplit('/', 1)[-1]: r for r in crawler.crawl_results}
        got = rows.get('', {}).get('custom_extraction', {})
        want = {'Name': ['Blue Mug'], 'Name HTML': ['Blue <em>Mug</em>'],
                'Currency': ['EUR'], 'Price': ['9.50'], 'Tags': ['kitchen', 'gift'],
                'Tag count': ['2']}
        result('extract: css and xpath rules return the expected values', got == want, str(got))
        other = rows.get('other', {}).get('custom_extraction', {})
        result('extract: a page without matches gets empty lists, not errors',
               other.get('Name') == [] and other.get('Tag count') == ['0'], str(other))

        flat, fields = app_module.flatten_custom_extraction(
            crawler.crawl_results, ['url', 'custom_extraction', 'title'])
        result('extract: export gets one column per extractor, in rule order',
               fields == ['url', 'extract_name', 'extract_name_html', 'extract_currency',
                          'extract_price', 'extract_tags', 'extract_tag_count', 'title'],
               str(fields))
        home = next(r for r in flat if r['url'].endswith(f'{site}/'))
        result('extract: multiple matches are joined in tabular exports',
               home['extract_tags'] == 'kitchen | gift', home['extract_tags'])

        manager = SettingsManager(tier='admin')
        settings = manager.get_settings()
        settings['customExtractors'] = [{'name': 'Bad', 'type': 'xpath', 'selector': '//div['}]
        ok, message = manager.save_settings(settings)
        result('extract: an invalid XPath is refused with its name',
               not ok and '"Bad"' in message, message)
        settings['customExtractors'] = rules
        ok, message = manager.save_settings(settings)
        result('extract: valid rules save', ok, message)
    finally:
        srv.shutdown()


def test_ngram_analyzer():
    """N-grams count body text, headings, title, inlink anchors and alt text."""
    from src.core.ngram_analyzer import NgramAnalyzer

    urls = [
        {
            'url': 'http://example.com/',
            'body_text': 'broken links are broken links',
            'heading_texts': ['broken links'],
            'title': 'broken links guide',
        },
        {
            'url': 'http://example.com/other',
            'body_text': 'broken link',
            'heading_texts': [],
            'title': 'other',
        },
    ]
    links = [
        {'target_url': 'http://example.com/', 'anchor_text': 'broken links', 'anchor_alt': ''},
        {'target_url': 'http://example.com/', 'anchor_text': '', 'anchor_alt': 'broken links image'},
    ]

    rows = NgramAnalyzer().aggregate(urls, links, ['http://example.com/'], 2)
    row = next(r for r in rows if r['gram'] == 'broken links')
    result('ngrams: body, headings, title, anchor and alt counts',
           row['body'] == 2 and row['headings'] == 1 and row['title'] == 1
           and row['inlinks_anchor'] == 1 and row['inlinks_alt'] == 1,
           str(row))
    result('ngrams: unlinked body occurrences subtract anchor text',
           row['body_unlinked'] == 1, str(row['body_unlinked']))
    result('ngrams: density uses body-text total',
           row['density'] == 50.0, str(row['density']))
    result('ngrams: selected URL changes the result set',
           any(r['gram'] == 'broken link' for r in
               NgramAnalyzer().aggregate(urls, links, ['http://example.com/other'], 2)))


def test_ngram_extraction():
    """The crawler stores body text, headings, and image-anchor alt text."""
    from src.core.ngram_analyzer import NgramAnalyzer

    site = BASE_PORT + 20
    base = f'http://127.0.0.1:{site}'
    srv = serve(make_handler({
        '/': (
            '<html><head><title>Broken links guide</title></head><body>'
            '<h1>Broken links</h1>'
            '<p>broken links are broken links</p>'
            '<a href="/other">other</a>'
            '<a href="/alt">alt</a>'
            '</body></html>'
        ),
        '/other': html('<a href="/">broken links</a>'),
        '/alt': html('<a href="/"><img alt="broken links image" src="/pic.png"></a>'),
        '/pic.png': png(),
    }), site)

    try:
        crawler = crawl(base + '/')
        home = next(r for r in crawler.crawl_results if r['url'] == base + '/')
        result('ngrams: crawler stores body text', 'broken links' in home.get('body_text', ''))
        result('ngrams: crawler stores heading text',
               home.get('heading_texts') == ['Broken links'], str(home.get('heading_texts')))

        alt_link = next(
            l for l in crawler.link_manager.all_links
            if l.get('target_url') == base + '/' and l.get('anchor_alt')
        )
        result('ngrams: image-only anchor records alt text',
               alt_link.get('anchor_alt') == 'broken links image',
               str(alt_link.get('anchor_alt')))

        rows = NgramAnalyzer().aggregate(
            crawler.crawl_results, crawler.link_manager.all_links, [home['url']], 2
        )
        row = next(r for r in rows if r['gram'] == 'broken links')
        result('ngrams: crawler text feeds analyzer counts',
               row['body'] == 3 and row['headings'] == 1 and row['title'] == 1
               and row['inlinks_anchor'] == 1 and row['inlinks_alt'] == 1,
               str(row))
        result('ngrams: crawler unlinked count',
               row['body_unlinked'] == 2, str(row['body_unlinked']))
    finally:
        srv.shutdown()


def test_self_hosted_accounts_without_email():
    """Discussion #100: on a self-hosted server without SMTP, a registered
    account sat unverified on the guest tier forever, with a login message
    telling the owner to wait for an admin that didn't exist."""
    import tempfile
    import manage
    from src import auth_db, crawl_db, email_service

    saved = (auth_db.DB_FILE, crawl_db.DB_FILE, email_service.SMTP_USER, email_service.SMTP_PASSWORD)
    tmp = tempfile.TemporaryDirectory()
    try:
        # Placeholder values from .env.example are "not configured".
        email_service.SMTP_USER, email_service.SMTP_PASSWORD = 'your-email@gmail.com', 'your-app-password'
        placeholders_off = not email_service.is_email_configured()
        email_service.SMTP_USER, email_service.SMTP_PASSWORD = 'me@example.com', 'hunter22'
        real_on = email_service.is_email_configured()
        email_service.SMTP_USER, email_service.SMTP_PASSWORD = '', ''
        result('placeholder SMTP values count as not configured', placeholders_off and real_on)

        def fresh_db(name):
            auth_db.DB_FILE = crawl_db.DB_FILE = os.path.join(tmp.name, name)
            auth_db.init_db()

        def row(username):
            with auth_db.get_db() as conn:
                return conn.execute('SELECT verified, tier FROM users WHERE username = ?',
                                    (username,)).fetchone()

        # A fresh install that once ran in local mode: the synthetic
        # local@localhost admin must not count as "already has an admin".
        fresh_db('fresh.db')
        with auth_db.get_db() as conn:
            conn.execute("INSERT INTO users (username, email, password_hash, verified, tier) "
                         "VALUES ('local', 'local@localhost', 'x', 1, 'admin')")
        ok, _, owner_id = auth_db.create_user('owner', 'owner@example.com', 'password123')
        claimed = ok and auth_db.claim_first_admin(owner_id)
        r = row('owner')
        result('first account becomes a verified admin',
               claimed and r['verified'] == 1 and r['tier'] == 'admin', str(dict(r)))

        ok, msg, user = auth_db.authenticate_user('owner', 'password123', email_configured=False)
        result('first admin can log in', ok and user['tier'] == 'admin', msg)

        _, _, second_id = auth_db.create_user('second', 'second@example.com', 'password123')
        second_claimed = auth_db.claim_first_admin(second_id)
        ok, msg, _ = auth_db.authenticate_user('second', 'password123', email_configured=False)
        result('later accounts are not promoted and get an honest message',
               not second_claimed and not ok and msg == auth_db.UNVERIFIED_NO_EMAIL_MESSAGE
               and 'admin approval' not in msg, msg)

        manage.main(['approve', 'second'])
        ok, msg, user = auth_db.authenticate_user('second', 'password123', email_configured=False)
        result('manage.py approve lets the account log in as tier user',
               ok and user['tier'] == 'user', msg)

        # An install that registered before this fix: the owner's account is
        # unverified with no admin anywhere. Logging in claims admin.
        fresh_db('stuck.db')
        auth_db.create_user('stuck', 'stuck@example.com', 'password123')
        ok, msg, user = auth_db.authenticate_user('stuck', 'password123', email_configured=False)
        r = row('stuck')
        result('existing stuck account claims admin on login',
               ok and user['tier'] == 'admin' and r['verified'] == 1, msg)

        # Servers that verify by email are unaffected.
        fresh_db('smtp.db')
        auth_db.create_user('mailer', 'mailer@example.com', 'password123')
        ok, msg, _ = auth_db.authenticate_user('mailer', 'password123', email_configured=True)
        r = row('mailer')
        result('with SMTP, unverified accounts are told to check email and stay unverified',
               not ok and msg == auth_db.UNVERIFIED_EMAIL_MESSAGE and r['verified'] == 0, msg)

        # Two registrations racing for the empty admin seat: exactly one wins.
        fresh_db('race.db')
        ids = [auth_db.create_user(f'racer{i}', f'racer{i}@example.com', 'password123')[2]
               for i in range(8)]
        wins = []
        threads = [threading.Thread(target=lambda uid=uid: wins.append(auth_db.claim_first_admin(uid)))
                   for uid in ids]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        with auth_db.get_db() as conn:
            admins = conn.execute("SELECT count(*) FROM users WHERE tier = 'admin'").fetchone()[0]
        result('concurrent registrations produce exactly one admin',
               wins.count(True) == 1 and admins == 1, f'{wins.count(True)} claims, {admins} admins')
    finally:
        auth_db.DB_FILE, crawl_db.DB_FILE, email_service.SMTP_USER, email_service.SMTP_PASSWORD = saved
        tmp.cleanup()


def _page(title, body='', head=''):
    return f'<html><head><title>{title}</title>{head}</head><body>{body}</body></html>'


def _analysis_site(port, external_port):
    """Routes for the site-wide analysis fixtures. Returned as a dict so a
    test can change the site between two crawls."""
    links = ''.join(f'<a href="{p}">{p}</a>' for p in (
        '/a', '/b', '/dup1', '/dup2', '/noindex-hdr', '/canon', '/canon2', '/canon-target',
        '/redir1', '/redir-bad', '/loop1', '/broken', '/multi-h1'))
    dup_head = '<meta name="description" content="The same description on two pages">'
    return {
        '/': _page('Home', '<h1>Home</h1>' + links
                   + f'<a href="http://127.0.0.1:{external_port}/gone">gone</a>'),
        '/a': _page('Page A', '<h1>A</h1><a href="/">home</a>'),
        '/b': _page('Page B', '<h1>B</h1><a href="/a">a</a>'),
        '/dup1': _page('Same Title Here', '<h1>Same H1</h1>', dup_head),
        '/dup2': _page('Same Title Here', '<h1>Same H1</h1>', dup_head),
        '/noindex-hdr': {'body': _page('Header Noindex', '<h1>N</h1>'),
                         'headers': {'X-Robots-Tag': 'googlebot: noindex'}},
        '/canon': _page('Canon', '<h1>C</h1>', '<link rel="canonical" href="/canon-target">'),
        '/canon2': _page('Canon Two', '<h1>C2</h1>', '<link rel="canonical" href="/canon">'),
        '/redir1': (301, '/redir2'),
        '/redir2': (301, '/a'),
        '/redir-bad': (301, '/nowhere'),
        '/loop1': (302, '/loop2'),
        '/loop2': (302, '/loop1'),
        '/multi-h1': _page('Multi', '<h1>One</h1><h1>Two</h1>'),
        '/orphan': _page('Orphan', '<h1>O</h1>'),
        '/sitemap.xml': ('<?xml version="1.0" encoding="UTF-8"?>'
                         '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                         + ''.join(f'<url><loc>http://127.0.0.1:{port}{p}</loc></url>'
                                   for p in ('/', '/a', '/orphan', '/noindex-hdr', '/redir1'))
                         + '</urlset>'),
    }


def test_site_wide_analysis():
    """Screaming Frog style crawl analysis: indexability (incl. X-Robots-Tag),
    duplicate title/meta/H1, redirect chains and loops, inlinks and Link
    Score, broken-link sources, canonical and sitemap checks."""
    from collections import Counter

    site, external = BASE_PORT + 16, BASE_PORT + 17
    a = serve(make_handler(_analysis_site(site, external)), site)
    b = serve(make_handler({}), external)
    base = f'http://127.0.0.1:{site}'
    try:
        crawler = crawl(base + '/', discover_sitemaps=True)
        rows = {r['url']: r for r in crawler.crawl_results}
        issues = crawler.issue_detector.get_issues()

        def has(path, name, contains=''):
            return any(i['url'] == base + path and i['issue'] == name and contains in i['details']
                       for i in issues)

        def flagged(name):
            return sorted(i['url'].replace(base, '') for i in issues if i['issue'] == name)

        def index_of(path):
            r = rows.get(base + path, {})
            return r.get('indexability'), r.get('indexability_status')

        result('indexability: plain page is indexable', index_of('/a') == ('Indexable', ''),
               str(index_of('/a')))
        result('indexability: X-Robots-Tag noindex is read',
               index_of('/noindex-hdr') == ('Non-Indexable', 'noindex (X-Robots-Tag)'),
               str(index_of('/noindex-hdr')))
        result('indexability: canonicalised, redirected and 404 pages',
               index_of('/canon')[1] == 'Canonicalised' and index_of('/redir1')[1] == 'Redirected'
               and index_of('/broken')[1] == 'Client Error',
               f"{index_of('/canon')} {index_of('/redir1')} {index_of('/broken')}")
        result('X-Robots-Tag noindex raises the noindex issue',
               has('/noindex-hdr', 'Noindex Tag Present', 'X-Robots-Tag'))

        result('duplicate title: exactly the two pages sharing it',
               flagged('Duplicate Title') == ['/dup1', '/dup2'], str(flagged('Duplicate Title')))
        result('duplicate meta description and H1 are reported too',
               flagged('Duplicate Meta Description') == ['/dup1', '/dup2']
               and flagged('Duplicate H1') == ['/dup1', '/dup2'],
               f"{flagged('Duplicate Meta Description')} {flagged('Duplicate H1')}")
        result('multiple H1 tags', flagged('Multiple H1 Tags') == ['/multi-h1']
               and rows[base + '/multi-h1'].get('h1_count') == 2, str(flagged('Multiple H1 Tags')))

        result('redirect chain of two hops', has('/redir1', 'Redirect Chain', '2 hops'),
               str(flagged('Redirect Chain')))
        result('redirect to a broken URL', flagged('Redirect to Broken URL') == ['/redir-bad'],
               str(flagged('Redirect to Broken URL')))
        result('redirect loop', flagged('Redirect Loop') == ['/loop1'], str(flagged('Redirect Loop')))

        # /canon-target, /broken and /redir-bad end in 404, /loop1 never answers
        result('broken internal links reported on the linking page',
               flagged('Broken Internal Links') == ['/'] and has('/', 'Broken Internal Links', '4 links'),
               next((i['details'] for i in issues if i['issue'] == 'Broken Internal Links'), 'none'))
        result('broken external links reported on the linking page',
               has('/', 'Broken External Links', '/gone'), str(flagged('Broken External Links')))
        result('internal links to redirects reported on the linking page',
               has('/', 'Internal Links to Redirects', '/redir1'))

        result('canonical pointing at a 404', flagged('Canonical Points to Non-Indexable URL') == ['/canon'],
               str(flagged('Canonical Points to Non-Indexable URL')))
        result('canonical chain', flagged('Canonical Chain') == ['/canon2'], str(flagged('Canonical Chain')))

        inlinks_a = rows[base + '/a'].get('inlinks')
        result('unique inlinks counted (redirect rows pass on no links)',
               inlinks_a == 2 and rows[base + '/'].get('inlinks') == 1,
               f"/a={inlinks_a} /={rows[base + '/'].get('inlinks')}")
        scores = [r.get('link_score') for r in rows.values()
                  if r.get('is_internal') and r.get('link_score') is not None]
        result('link score is 0-100 and favours better linked pages',
               scores and max(scores) == 100 and min(scores) >= 0
               and rows[base + '/a']['link_score'] > rows[base + '/multi-h1']['link_score'],
               f"/a={rows[base + '/a'].get('link_score')} /multi-h1={rows[base + '/multi-h1'].get('link_score')}")

        result('sitemap membership recorded',
               rows[base + '/'].get('in_sitemap') is True and rows[base + '/b'].get('in_sitemap') is False)
        result('orphan page found from the sitemap only', flagged('Orphan Page (Sitemap Only)') == ['/orphan'],
               str(flagged('Orphan Page (Sitemap Only)')))
        result('non-indexable URLs in the sitemap',
               flagged('Non-Indexable URL in Sitemap') == ['/noindex-hdr', '/redir1'],
               str(flagged('Non-Indexable URL in Sitemap')))
        result('indexable pages missing from the sitemap include /b',
               '/b' in flagged('Indexable Page Not in Sitemap')
               and '/a' not in flagged('Indexable Page Not in Sitemap'))

        repeated = [k for k, n in Counter((i['url'], i['issue']) for i in issues).items() if n > 1]
        result('no issue repeated for the same URL', not repeated, str(repeated[:3]))

        # Journal: analysis results go out as small patches, never for a
        # row the client has not been sent
        sent, bad, patches = set(), [], 0
        for event in crawler.event_log._events:
            if event['kind'] == 'url':
                sent.add(event['data']['url'])
            elif event['kind'] == 'url_patch':
                patches += 1
                if event['data']['url'] not in sent:
                    bad.append(event['data']['url'])
        result('analysis patches follow their rows in the journal', patches > 0 and not bad,
               f'{patches} patches, {len(bad)} orphaned')

        # Redirects not followed: chains and loops traced through the rows
        listed = [base + p for p in ('/redir1', '/redir2', '/a', '/loop1', '/loop2',
                                     '/redir-bad', '/nowhere')]
        crawler = crawl(base + '/', url_list=listed, follow_redirects=False)
        issues = crawler.issue_detector.get_issues()
        result('unfollowed: chain traced through the 3xx rows', has('/redir1', 'Redirect Chain', '2 hops'),
               str(flagged('Redirect Chain')))
        result('unfollowed: loop traced through the 3xx rows',
               flagged('Redirect Loop') == ['/loop1', '/loop2'], str(flagged('Redirect Loop')))
        result('unfollowed: redirect ending in a 404',
               flagged('Redirect to Broken URL') == ['/redir-bad'], str(flagged('Redirect to Broken URL')))
    finally:
        a.shutdown()
        b.shutdown()


def test_crawl_analysis_scales_linearly():
    """The end-of-crawl analysis must not hold a large crawl in "finishing
    up": 20,000 pages and ~200,000 links, all templated alike."""
    from src.core.crawl_analysis import CrawlAnalyzer

    count = 20000
    rows = [{'url': f'https://x.au/p{i}', 'status_code': 200, 'content_type': 'text/html',
             'is_internal': True, 'title': f'Product {i % 500}', 'meta_description': 'Same for all',
             'h1': f'Product {i}', 'canonical_url': f'https://x.au/p{i}'} for i in range(count)]
    links = []
    for i in range(count):
        for step in (1, 7, 31, 101, 499, 997, 1999, 4999, 9973, 13):
            links.append({'source_url': f'https://x.au/p{i}', 'target_url': f'https://x.au/p{(i + step) % count}',
                          'is_internal': True, 'placement': 'body', 'target_status': 200})
    started = time.time()
    analyzer = CrawlAnalyzer()
    patches, issues = analyzer.analyze(rows, links, sitemap_urls={f'https://x.au/p{i}' for i in range(0, count, 2)},
                                       start_url='https://x.au/p0')
    elapsed = time.time() - started
    # ~2s on a laptop; an O(group²) slip (examples listed per duplicate
    # page) once made this 27s
    result('20k pages / 200k links analysed quickly', elapsed < 10 and not analyzer.link_score_truncated,
           f'{elapsed:.1f}s, {len(patches)} patches, {len(issues)} issues')
    per_page = sum(1 for i in issues if i['issue'] == 'Duplicate Meta Description')
    result('one duplicate issue per page, not per pair', per_page == count, f'{per_page}')


def test_analysis_persists_and_crawls_compare():
    """Analysis fields survive a save and reload, and two saved crawls of a
    site can be compared through the API."""
    import tempfile
    os.environ.setdefault('LOCAL_MODE', 'true')
    import main as app_module
    from src import auth_db, crawl_db

    site, external = BASE_PORT + 18, BASE_PORT + 19
    routes = _analysis_site(site, external)
    a = serve(make_handler(routes), site)
    b = serve(make_handler({}), external)
    base = f'http://127.0.0.1:{site}'
    saved = (auth_db.DB_FILE, crawl_db.DB_FILE)
    tmp = tempfile.TemporaryDirectory()
    try:
        auth_db.DB_FILE = crawl_db.DB_FILE = os.path.join(tmp.name, 'compare.db')
        auth_db.init_db()

        def saved_crawl():
            crawler = WebCrawler()
            crawler.config.update({
                'delay': 0.02, 'concurrency': 5, 'max_urls': 200, 'max_depth': 4,
                'crawl_external': False, 'discover_sitemaps': True, 'respect_robots': False})
            # Save every row as it arrives, so rows are in SQLite before the
            # analysis runs and only the end-of-crawl UPDATE can fill it in
            crawler.batch_save_size = 1
            ok, message = crawler.start_crawl(base + '/', user_id=1, session_id='fixture-session')
            assert ok, message
            deadline = time.time() + 120
            while crawler.is_running and time.time() < deadline:
                time.sleep(0.1)
            return crawler

        first = saved_crawl()
        loaded = {r['url']: r for r in crawl_db.load_crawled_urls(first.crawl_id)}
        page_a = loaded.get(base + '/a', {})
        result('reloaded rows keep indexability, inlinks, link score, sitemap flag',
               page_a.get('indexability') == 'Indexable' and page_a.get('inlinks') == 2
               and isinstance(page_a.get('link_score'), int) and page_a.get('in_sitemap') is True,
               str({k: page_a.get(k) for k in ('indexability', 'inlinks', 'link_score', 'in_sitemap')}))
        result('reloaded rows keep X-Robots-Tag and the final linked_from',
               loaded.get(base + '/noindex-hdr', {}).get('x_robots_tag') == 'googlebot: noindex'
               and sorted(page_a.get('linked_from') or []) == sorted([base + '/', base + '/b']),
               str(page_a.get('linked_from')))

        # The site changes: a page goes, one appears, a title changes, a page
        # turns noindex and the homepage gains a broken link
        routes['/'] = routes['/'].replace('<a href="/b">/b</a>', '<a href="/new">/new</a>'
                                           '<a href="/also-broken">x</a>')
        routes['/new'] = _page('New Page', '<h1>New</h1>')
        routes['/a'] = _page('Page A Renamed', '<h1>A</h1><a href="/">home</a>')
        routes['/multi-h1'] = _page('Multi', '<h1>One</h1>', '<meta name="robots" content="noindex">')
        second = saved_crawl()

        client = app_module.app.test_client()
        with client.session_transaction() as s:
            s['user_id'] = 1
            s['username'] = 'fixture'
            s['tier'] = 'admin'
        resp = client.get(f'/api/crawls/compare?previous={first.crawl_id}&current={second.crawl_id}')
        data = resp.get_json() or {}
        changes = data.get('changes') or []

        def changed(kind, path):
            return [c for c in changes if c['change'] == kind and c['url'] == base + path]

        result('compare: added and removed URLs',
               bool(changed('added', '/new')) and bool(changed('removed', '/b')),
               str(data.get('summary', data.get('error'))))
        title = changed('title', '/a')
        result('compare: title change with both values',
               bool(title) and title[0]['previous'] == 'Page A' and title[0]['current'] == 'Page A Renamed',
               str(title))
        result('compare: indexability change',
               any(c['current'].startswith('Non-Indexable (noindex)') for c in changed('indexability', '/multi-h1')),
               str(changed('indexability', '/multi-h1')))
        result('compare: new issue on an existing URL',
               any(c['current'] == 'Noindex Tag Present' for c in changed('new_issue', '/multi-h1')),
               str(changed('new_issue', '/multi-h1')))
        result('compare: resolved issue on an existing URL',
               any(c['previous'] == 'Multiple H1 Tags' for c in changed('resolved_issue', '/multi-h1')))
        result('compare: issue totals per issue name',
               any(i['issue'] == 'Noindex Tag Present' and i['delta'] == 1
                   for i in data.get('issue_changes') or []))
        result('compare: unchanged pages produce no rows', not [c for c in changes
                                                               if c['url'] == base + '/dup1'])

        csv_resp = client.get(f'/api/crawls/compare?previous={first.crawl_id}'
                              f'&current={second.crawl_id}&format=csv')
        lines = csv_resp.data.decode().strip().splitlines()
        result('compare: CSV has a header and one line per change',
               csv_resp.status_code == 200 and lines[0] == 'url,change,previous,current'
               and len(lines) == data.get('total_changes', -1) + 1, f'{len(lines)} lines')

        with client.session_transaction() as s:
            s['user_id'] = 2
        denied = client.get(f'/api/crawls/compare?previous={first.crawl_id}&current={second.crawl_id}')
        result("compare: another user's crawls are refused", denied.status_code == 403,
               str(denied.status_code))

        # Resuming a crawl whose analysis already ran recomputes the
        # site-wide issues instead of saving them a second time
        from collections import Counter
        before = Counter((i['url'], i['issue']) for i in crawl_db.load_crawl_issues(second.crawl_id))
        crawl_db.set_crawl_status(second.crawl_id, 'paused')
        resumed = WebCrawler()
        ok, message = resumed.resume_from_database(second.crawl_id, user_id=1)
        deadline = time.time() + 120
        while ok and resumed.is_running and time.time() < deadline:
            time.sleep(0.1)
        after = Counter((i['url'], i['issue']) for i in crawl_db.load_crawl_issues(second.crawl_id))
        repeated = [k for k, n in after.items() if n > 1 and before.get(k, 0) < n]
        result('resume: site-wide issues are recomputed, not duplicated',
               ok and not repeated and after[(base + '/', 'Broken Internal Links')] == 1,
               message if not ok else str(repeated[:3]))
    finally:
        auth_db.DB_FILE, crawl_db.DB_FILE = saved
        a.shutdown()
        b.shutdown()
        tmp.cleanup()


def test_hostile_input_regressions():
    """Bugs found by fuzzing the crawler and the analysis with malformed input."""
    import tempfile
    from src.crawler import _header_text
    from src.core.crawl_analysis import CrawlAnalyzer, indexability
    from src.core.crawl_compare import compare_crawls
    from src import auth_db, crawl_db

    site = BASE_PORT + 20
    base = f'http://127.0.0.1:{site}'
    routes = {
        '/': html('<a href="http://[bad/">bad</a><a href="/after">after</a>'
                  '<a href="/bad-location">r</a><a href="/nocontent">n</a><a href="/jscanon">j</a>'),
        '/after': html('after'),
        '/bad-location': (302, 'http://[bad/x'),
        '/jscanon': '<html><head><title>J</title><link rel="canonical" href="javascript:void(0)"></head></html>',
        '/sitemap.xml': ('<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                         '<url><loc>http://[bad</loc></url>'
                         f'<url><loc>{base}/listed-only</loc></url></urlset>'),
        '/listed-only': html('listed'),
    }

    class NoContent(make_handler(routes)):
        def do_GET(self):
            if self.path == '/nocontent':
                self.send_response(204)
                self.end_headers()
                return
            super().do_GET()
        do_HEAD = do_GET

    srv = serve(NoContent, site)
    try:
        crawler = crawl(base + '/', follow_redirects=False, discover_sitemaps=True)
        rows = {r['url']: r for r in crawler.crawl_results}
        home = rows.get(base + '/', {})
        result('a malformed href does not turn the page into a failed fetch',
               home.get('status_code') == 200 and base + '/after' in rows,
               f"{home.get('status_code')} {home.get('error')}")
        bad = rows.get(base + '/bad-location', {})
        result('a malformed Location is kept, not turned into an error row',
               bad.get('status_code') == 302 and bad.get('redirect_target') == 'http://[bad/x',
               f"{bad.get('status_code')} {bad.get('error')}")
        result('204 No Content is not indexable',
               rows.get(base + '/nocontent', {}).get('indexability_status') == 'Non-200 Status (204)')
        result('a javascript: canonical does not canonicalise the page',
               rows.get(base + '/jscanon', {}).get('indexability') == 'Indexable')
        result('a malformed sitemap <loc> does not stop the rest being queued',
               base + '/listed-only' in rows and all(u.startswith('http') for u in crawler.sitemap_urls),
               str(sorted(crawler.sitemap_urls)))
    finally:
        srv.shutdown()

    result('UTF-8 header bytes are decoded as UTF-8', _header_text('nÃ¶index') == 'nöindex'
           and _header_text('noindex') == 'noindex' and _header_text('ü') == 'ü')

    def scores(n, edges):
        rows = [{'url': f'https://x.au/{i}', 'status_code': 200, 'content_type': 'text/html',
                 'is_internal': True} for i in range(n)]
        links = [{'source_url': f'https://x.au/{a}', 'target_url': f'https://x.au/{b}',
                  'is_internal': True, 'placement': 'body'} for a, b in edges]
        CrawlAnalyzer().analyze(rows, links)
        return [r['link_score'] for r in rows]
    complete = scores(7, [(a, b) for a in range(7) for b in range(7) if a != b])
    result('equally linked pages share one Link Score, not 0', set(complete) == {100}, str(complete))

    try:
        compare_crawls([{'url': 'https://x.au/a'}], [{'url': 'https://x.au/a'}, {'url': None}],
                       [('https://x.au/a', None, None)], [('https://x.au/a', 'X', 'error')])
        result('compare tolerates NULL issue names and URL-less rows', True)
    except Exception as e:
        result('compare tolerates NULL issue names and URL-less rows', False, repr(e))

    result('indexability of a row with no status is "No Response"',
           indexability({'url': 'https://x.au/', 'status_code': None}) == ('Non-Indexable', 'No Response'))

    saved = (auth_db.DB_FILE, crawl_db.DB_FILE)
    tmp = tempfile.TemporaryDirectory()
    try:
        auth_db.DB_FILE = crawl_db.DB_FILE = os.path.join(tmp.name, 'corrupt.db')
        auth_db.init_db()
        cid = crawl_db.create_crawl(1, 's', 'https://x.au', 'x.au', {})
        crawl_db.save_url_batch(cid, [{'url': f'https://x.au/{i}', 'status_code': 200} for i in range(3)])
        with crawl_db.get_db() as conn:
            conn.execute("UPDATE crawled_urls SET analysis = 'null' WHERE url = 'https://x.au/0'")
            conn.execute("""UPDATE crawled_urls SET analysis = '{"url": "https://evil/"}' WHERE url = 'https://x.au/1'""")
        loaded = crawl_db.load_crawled_urls(cid)
        result('a corrupt analysis value loses nothing and overrides nothing',
               sorted(r['url'] for r in loaded) == ['https://x.au/0', 'https://x.au/1', 'https://x.au/2'],
               str([r['url'] for r in loaded]))
    finally:
        auth_db.DB_FILE, crawl_db.DB_FILE = saved
        tmp.cleanup()


def test_canonicals_and_titles():
    """Multiple and conflicting canonicals (HTML tags and Link headers), and
    title counting that skips embedded documents/graphics."""
    site = BASE_PORT + 21
    base = f'http://127.0.0.1:{site}'

    def canon(*hrefs, rel='canonical'):
        return ''.join(f'<link rel="{rel}" href="{h}">' for h in hrefs)

    pages = {
        '/same': _page('Same', head=canon('/same', f'{base}/same')),
        '/conflict': _page('Conflict', head=canon('/a', '/b')),
        '/mixed': {'body': _page('Mixed', head=canon('/a')),
                   'headers': {'Link': f'<{base}/b>; rel="canonical"'}},
        '/header-only': {'body': _page('Header only'),
                         'headers': {'Link': f'<{base}/a>; rel="canonical", <{base}/x.css>; rel="preload"'}},
        '/junk-first': _page('Junk first', head=canon('', '/a')),
        '/case': _page('Case', head=canon('/a', rel='CANONICAL') + canon('/a', rel='alternate canonical')),
        '/twohead': '<html><head><title>One</title></head><head><title>Two</title></head><body></body></html>',
        '/embedded': _page('Real', '<svg><title>icon</title></svg><object><title>obj</title></object>'
                                   '<iframe><title>frame</title></iframe>'),
        # <embed> is a void element: nothing can be inside it, so a title
        # written after it is an ordinary (second) title, in browsers too
        '/after-embed': _page('Real', '<embed src="x.swf"><title>stray</title>'),
        '/svg-only': '<html><head></head><body><svg><title>icon</title></svg></body></html>',
        '/a': _page('A'), '/b': _page('B'),
    }
    pages['/'] = _page('Home', ''.join(f'<a href="{p}">{p}</a>' for p in pages))
    srv = serve(make_handler(pages), site)
    try:
        crawler = crawl(base + '/')
        rows = {r['url'].replace(base, ''): r for r in crawler.crawl_results}
        issues = crawler.issue_detector.get_issues()

        def flagged(name):
            return sorted(i['url'].replace(base, '') for i in issues if i['issue'] == name)

        result('same URL declared twice: info, page stays indexable',
               flagged('Multiple Canonical Tags') == ['/case', '/junk-first', '/same']
               and rows['/same']['indexability'] == 'Indexable',
               str(flagged('Multiple Canonical Tags')))
        result('conflicting tags, and tag vs Link header, are errors',
               flagged('Conflicting Canonicals') == ['/conflict', '/mixed'],
               str(flagged('Conflicting Canonicals')))
        result('conflicting canonicals are ignored, as search engines do',
               rows['/conflict']['indexability'] == 'Indexable'
               and '/conflict' not in flagged('Canonical URL Different'),
               str((rows['/conflict']['indexability'], rows['/conflict']['indexability_status'])))
        result('Link header canonical is used when the HTML has none',
               rows['/header-only'].get('canonical_url') == f'{base}/a'
               and rows['/header-only']['indexability_status'] == 'Canonicalised'
               and '/header-only' not in flagged('Missing Canonical URL')
               and rows['/mixed'].get('canonical_header') == f'{base}/b',
               str(rows['/header-only'].get('canonical_url')))
        result('an empty href among canonicals defers to the valid one',
               rows['/junk-first']['indexability_status'] == 'Canonicalised')
        result('rel is matched case-insensitively and as a token list',
               rows['/case'].get('canonical_count') == 2)

        result('titles in a second <head> count', rows['/twohead'].get('title_count') == 2
               and '/twohead' in flagged('Multiple Title Tags'))
        result('titles inside svg, object and iframe do not count',
               rows['/embedded'].get('title_count') == 1 and rows['/embedded']['title'] == 'Real',
               str(rows['/embedded'].get('title_count')))
        result('a title after a (void) <embed> is a real second title',
               rows['/after-embed'].get('title_count') == 2)
        result('an SVG title is not the page title',
               rows['/svg-only']['title'] == '' and '/svg-only' in flagged('Missing Title Tag'))
    finally:
        srv.shutdown()


def _playwright_available():
    try:
        import playwright  # noqa: F401
        return True
    except ImportError:
        return False


TESTS = (
    test_cross_domain_redirect,
    test_external_images,
    test_sitemap_discovery_is_async,
    test_max_urls_counts_pages_not_images,
    test_event_ordering_under_polling,
    test_discovered_counts_image_rows,
    test_js_response_time_excludes_render_wait,
    test_duplicate_detection_is_linear,
    test_export_formats_apply_to_every_data_type,
    test_empty_alt_is_not_missing_alt,
    test_crawl_delay_is_honoured,
    test_list_mode_fetches_only_the_list,
    test_custom_extraction,
    test_ngram_analyzer,
    test_ngram_extraction,
    test_self_hosted_accounts_without_email,
    test_site_wide_analysis,
    test_crawl_analysis_scales_linearly,
    test_analysis_persists_and_crawls_compare,
    test_hostile_input_regressions,
    test_canonicals_and_titles,
)


def main():
    for test in TESTS:
        print(f'\n{test.__name__}:')
        try:
            test()
        except Exception as exc:  # a raised test is a failed test
            result(test.__name__, False, f'raised {type(exc).__name__}: {exc}')

    print('\n' + '=' * 64)
    print(f'  {len(PASSED)} passed, {len(FAILED)} failed')
    if FAILED:
        print('  failed: ' + ', '.join(FAILED))
    return 1 if FAILED else 0


if __name__ == '__main__':
    sys.exit(main())
