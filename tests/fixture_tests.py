"""Deterministic crawler tests against local fixture sites.

Runs WebCrawler in-process against tiny HTTP servers started by this script,
so every behaviour is checked without touching a third-party site. No test
framework and no network access required:

    python tests/fixture_tests.py

Each test pins down a bug that reached production once, so a failure here
means a real regression rather than a flaky expectation:

  1. relative links on a page reached through a cross-domain redirect resolve
     against the site that served the content, not the URL that was requested
  2. images hosted off-domain are neither requested nor listed while
     "crawl external links" is off
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
    """Build a handler serving `routes`: path -> html str, bytes, or (code, location)."""

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
                hits.append(self.path)
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
            else:
                self._send(200, route.encode())

        do_HEAD = do_GET

    return Handler


def crawl(url, timeout=120, **config):
    """Run a crawl to completion and return the crawler for inspection."""
    crawler = WebCrawler()
    crawler.config.update({
        'delay': 0.02, 'concurrency': 5, 'max_urls': 200, 'max_depth': 4,
        'crawl_external': False, 'crawl_images': False,
        'discover_sitemaps': False, 'respect_robots': False,
    })
    crawler.config.update(config)

    ok, message = crawler.start_crawl(url)
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
    b = serve(make_handler({
        '/landing': html('<a href="/issues">issues</a><a href="/pulls">pulls</a>'),
    }), site_b)
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
        result('redirect: offsite content does not enter the queue',
               f'http://127.0.0.1:{site_b}/issues' not in urls)
    finally:
        a.shutdown()
        b.shutdown()


def test_external_images():
    """crawl_external=off must also apply to image HEAD checks."""
    site, other = BASE_PORT + 2, BASE_PORT + 3
    other_hits = []
    a = serve(make_handler({
        '/': html(f'<img src="/in.png"><img src="http://127.0.0.1:{other}/out.png">'),
        '/in.png': png(),
    }), site)
    b = serve(make_handler({'/out.png': png()}, hits=other_hits), other)
    try:
        crawler = crawl(f'http://127.0.0.1:{site}/')
        urls = {r['url'] for r in crawler.crawl_results}
        result('images: offsite image not listed as a row',
               f'http://127.0.0.1:{other}/out.png' not in urls)
        result('images: offsite host never contacted', not other_hits, str(other_hits))
        result('images: same-domain image still listed',
               f'http://127.0.0.1:{site}/in.png' in urls)

        other_hits.clear()
        crawler = crawl(f'http://127.0.0.1:{site}/', crawl_external=True)
        urls = {r['url'] for r in crawler.crawl_results}
        result('images: offsite image checked when external crawling is on',
               f'http://127.0.0.1:{other}/out.png' in urls and bool(other_hits))
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
