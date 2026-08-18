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
