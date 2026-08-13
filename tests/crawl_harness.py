"""End-to-end harness: drive a running LibreCrawl against a real site.

Start LibreCrawl (`python main.py --local`), then point this at any URL:

    python tests/crawl_harness.py https://example.com/ --max-urls 150
    python tests/crawl_harness.py https://example.com/ --js --pause-test

It polls /api/crawl_status with the same event protocol the browser uses and
accumulates state exactly like web/static/js/incremental_poller.js, then checks
the invariants the UI depends on:

  * no duplicate url/link events, and no update for a row never sent
  * the accumulated client state matches the server's full snapshot
  * mutations (link status backfill, linked_from) actually reach the client
  * rows stay in scope (nothing off-domain unless crawl_external is on)
  * streaming exports contain one row per item
  * reloading the saved crawl flips the epoch and replays everything

Be considerate with --delay and --max-urls when pointing this at sites you do
not own. Exits non-zero on the first violation and prints the poll history so
a failure can be explained rather than just reported.
"""
import argparse
import csv
import io
import json
import sys
import time
import urllib.parse

import requests

DEFAULT_BASE = 'http://localhost:5000'


class Violation(Exception):
    pass


def check(condition, message):
    if not condition:
        raise Violation(message)


class Client:
    """Accumulates crawl state from events, mirroring the browser client."""

    def __init__(self):
        self.history = []
        self.seq_regressions = []
        self.reset_state()

    def reset_state(self, keep_history=False):
        if not keep_history:
            self.history = []
            self.seq_regressions = []
        self.epoch = ''
        self.seq = 0
        self.urls = {}
        self.links = {}
        self.issues = []
        self.resets = 0
        self.url_updates = 0
        self.link_updates = 0

    def apply(self, data):
        self.history.append({
            'seq_sent': self.seq,
            'latest_seq': data.get('latest_seq'),
            'events': len(data.get('events') or []),
            'reset': data.get('reset'),
            'epoch': (data.get('epoch') or '')[:8],
            'status': data.get('status'),
            'crawled': (data.get('stats') or {}).get('crawled'),
        })
        if data.get('latest_seq') is not None and data['latest_seq'] < self.seq:
            self.seq_regressions.append((self.seq, data['latest_seq']))

        if data.get('reset'):
            self.reset_state(keep_history=True)
            self.resets += 1
        self.epoch = data.get('epoch', self.epoch)
        self.seq = data.get('latest_seq', self.seq)

        for event in data.get('events', []):
            kind, row = event['kind'], event['data']
            if kind == 'url':
                check(row['url'] not in self.urls,
                      f"duplicate 'url' event for {row['url']}")
                self.urls[row['url']] = row
            elif kind == 'url_update':
                check(row['url'] in self.urls,
                      f"'url_update' for a url never sent: {row['url']}")
                self.urls[row['url']] = row
                self.url_updates += 1
            elif kind == 'link':
                key = row['source_url'] + '|' + row['target_url']
                check(key not in self.links, f"duplicate 'link' event for {key}")
                self.links[key] = row
            elif kind == 'link_update':
                key = row['source_url'] + '|' + row['target_url']
                check(key in self.links, f"'link_update' for a link never sent: {key}")
                self.links[key] = row
                self.link_updates += 1
            elif kind == 'issue':
                self.issues.append(row)
            else:
                raise Violation(f'unknown event kind: {kind}')

    def print_history(self, tail=8):
        print(f'  seq regressions: {self.seq_regressions[:5]}')
        print('  last polls (seq sent -> latest, events, reset, epoch, status, crawled):')
        for row in self.history[-tail:]:
            print(f"    {row['seq_sent']:>8} -> {str(row['latest_seq']):>8}  "
                  f"n={row['events']:<6} reset={str(row['reset']):<5} "
                  f"ep={row['epoch']} {row['status']} crawled={row['crawled']}")


def configure(session, base, **overrides):
    settings = session.get(f'{base}/api/get_settings', timeout=30).json()['settings']
    settings.update(overrides)
    saved = session.post(f'{base}/api/save_settings', json=settings, timeout=30).json()
    check(saved.get('success'), f'save_settings failed: {saved}')


def poll_until_done(session, base, client, timeout, pause_test=False):
    deadline = time.time() + timeout
    polls = 0
    paused = False
    while time.time() < deadline:
        data = session.get(f'{base}/api/crawl_status',
                           params={'since_seq': client.seq, 'epoch': client.epoch},
                           timeout=60).json()
        client.apply(data)
        polls += 1

        # the route reads events before stats, so the counter must never be
        # behind the rows the client has already been handed
        crawled = data['stats']['crawled']
        check(len(client.urls) <= crawled,
              f'client holds {len(client.urls)} urls but stats say crawled={crawled}')

        if polls % 5 == 0:
            print(f'    poll {polls}: {data["status"]} urls={len(client.urls)} '
                  f'links={len(client.links)} issues={len(client.issues)} seq={client.seq}')

        if pause_test and not paused and len(client.urls) >= 5:
            paused = True
            reply = session.post(f'{base}/api/pause_crawl', timeout=30).json()
            check(reply.get('success'), f'pause failed: {reply}')
            time.sleep(2)
            before = session.get(f'{base}/api/crawl_status', params={'stats_only': 1},
                                 timeout=30).json()['stats']['crawled']
            time.sleep(3)
            after = session.get(f'{base}/api/crawl_status', params={'stats_only': 1},
                                timeout=30).json()['stats']['crawled']
            check(after - before <= 2, f'crawl kept working while paused ({before} -> {after})')
            reply = session.post(f'{base}/api/resume_crawl', timeout=30).json()
            check(reply.get('success'), f'resume failed: {reply}')
            print(f'    pause/resume verified (held at {before} urls)')

        if data['status'] in ('completed', 'demo_stopped'):
            for _ in range(3):  # drain end-of-crawl update events
                tail = session.get(f'{base}/api/crawl_status',
                                   params={'since_seq': client.seq, 'epoch': client.epoch},
                                   timeout=60).json()
                client.apply(tail)
                if not tail.get('events'):
                    break
                time.sleep(1)
            return data, polls
        time.sleep(1)
    raise Violation('crawl did not complete within the timeout')


def export_rows(session, base, data_type, fmt='csv', fields='url,status_code,title'):
    query = urllib.parse.urlencode({'format': fmt, 'type': data_type, 'fields': fields})
    response = session.get(f'{base}/api/export_stream?{query}', timeout=600)
    check(response.status_code == 200,
          f'export {data_type} returned HTTP {response.status_code}')
    if fmt == 'csv':
        rows = list(csv.reader(io.StringIO(response.text)))
        return max(0, len(rows) - 1), len(response.content)
    return len(json.loads(response.text).get('data', [])), len(response.content)


def run(args, client_holder=None):
    base = args.base.rstrip('/')
    session = requests.Session()
    session.get(base + '/', timeout=30)  # establishes the session (local mode auto-login)

    print(f'\n{"=" * 78}\n  {args.url}\n{"=" * 78}')
    configure(session, base,
              maxUrls=args.max_urls, maxDepth=args.depth, crawlDelay=args.delay,
              concurrency=args.concurrency, crawlExternalLinks=args.external,
              crawlImages=args.images, enableJavaScript=args.js, jsWaitTime=2,
              jsMaxConcurrentPages=3, respectRobotsTxt=True,
              discoverSitemaps=True, enablePageSpeed=False)
    print(f'  config: max_urls={args.max_urls} depth={args.depth} delay={args.delay} '
          f'js={args.js} images={args.images} external={args.external}')

    client = Client()
    if client_holder is not None:
        client_holder['client'] = client  # so a failure can print the poll history
    started = time.time()
    reply = session.post(f'{base}/api/start_crawl', json={'url': args.url}, timeout=60).json()
    start_latency = time.time() - started
    check(reply.get('success'), f'start_crawl failed: {reply}')
    crawl_id = reply.get('crawl_id')
    print(f'  start_crawl returned in {start_latency * 1000:.0f}ms (crawl_id={crawl_id})')
    check(start_latency < 5,
          f'start_crawl blocked for {start_latency:.1f}s; sitemap discovery should be async')

    final, polls = poll_until_done(session, base, client, args.timeout, args.pause_test)
    elapsed = time.time() - started

    # client state vs the server's own snapshot
    snapshot = session.get(f'{base}/api/crawl_status', timeout=600).json()
    server_urls = {u['url'] for u in snapshot['urls']}
    server_links = {l['source_url'] + '|' + l['target_url'] for l in snapshot['links']}
    check(set(client.urls) == server_urls,
          f'url mismatch: client-only={list(set(client.urls) - server_urls)[:3]} '
          f'server-only={list(server_urls - set(client.urls))[:3]}')
    check(set(client.links) == server_links,
          f'{len(set(client.links) ^ server_links)} links differ between client and server')
    check(len(client.issues) == len(snapshot['issues']),
          f'issues: client={len(client.issues)} server={len(snapshot["issues"])}')

    # mutations must have reached the client, not just the server
    stale = [u for u in snapshot['urls']
             if client.urls[u['url']].get('linked_from') != u.get('linked_from')]
    check(not stale,
          f'{len(stale)} rows hold stale linked_from on the client, e.g. {stale[0]["url"] if stale else ""}')

    host = urllib.parse.urlparse(args.url).netloc.replace('www.', '', 1)
    offdomain = [u for u in client.urls
                 if urllib.parse.urlparse(u).netloc.replace('www.', '', 1) != host]
    if not args.external:
        check(not offdomain,
              f'{len(offdomain)} off-domain rows with external crawling off: {offdomain[:3]}')

    crawled_urls = set(client.urls)
    missing_status = [key for key, link in client.links.items()
                      if link['target_url'] in crawled_urls and link.get('target_status') is None]
    check(not missing_status,
          f'{len(missing_status)} links never got a status backfill, e.g. {missing_status[:2]}')

    exports = {}
    if not args.no_export:
        for data_type in ('urls', 'links', 'issues'):
            exports[data_type] = export_rows(session, base, data_type)
        check(exports['urls'][0] == len(client.urls),
              f'url export has {exports["urls"][0]} rows, client has {len(client.urls)}')
        check(exports['links'][0] == len(client.links),
              f'link export has {exports["links"][0]} rows, client has {len(client.links)}')

    replay = None
    if crawl_id:
        loaded = session.post(f'{base}/api/crawls/{crawl_id}/load', timeout=600).json()
        check(loaded.get('success'), f'loading the saved crawl failed: {loaded}')
        data = session.get(f'{base}/api/crawl_status',
                           params={'since_seq': client.seq, 'epoch': client.epoch},
                           timeout=600).json()
        check(data.get('reset'), 'loading a saved crawl did not reset the client epoch')
        reloaded = Client()
        reloaded.apply(data)
        while True:
            more = session.get(f'{base}/api/crawl_status',
                               params={'since_seq': reloaded.seq, 'epoch': reloaded.epoch},
                               timeout=600).json()
            if not more.get('events'):
                break
            reloaded.apply(more)
        replay = (len(reloaded.urls), len(reloaded.links), len(reloaded.issues))
        check(replay[0] == len(client.urls),
              f'saved crawl replays {replay[0]} urls vs {len(client.urls)} crawled')
        check(replay[1] == len(client.links),
              f'saved crawl replays {replay[1]} links vs {len(client.links)} in memory')
        check(replay[2] == len(client.issues),
              f'saved crawl replays {replay[2]} issues vs {len(client.issues)} in memory')

    codes = {}
    for row in client.urls.values():
        codes[row.get('status_code')] = codes.get(row.get('status_code'), 0) + 1
    rendered = sum(1 for row in client.urls.values() if row.get('javascript_rendered'))
    redirected = sum(1 for row in client.urls.values() if row.get('redirects'))

    print(f'  PASS in {elapsed:.0f}s over {polls} polls')
    print(f'    urls={len(client.urls)} links={len(client.links)} issues={len(client.issues)}')
    print(f'    status codes: {dict(sorted(codes.items(), key=lambda kv: str(kv[0])))}')
    print(f'    url_updates={client.url_updates} link_updates={client.link_updates} '
          f'resets={client.resets}')
    print(f'    js_rendered={rendered} with_redirect_chain={redirected} '
          f'offdomain_rows={len(offdomain)}')
    if exports:
        print('    exports: ' + ', '.join(f'{k}={v[0]} rows/{v[1] // 1024}KB'
                                          for k, v in exports.items()))
    if replay:
        print(f'    saved-crawl replay: urls={replay[0]} links={replay[1]} issues={replay[2]}')
    sizes = final.get('memory_data') or {}
    if sizes:
        print(f'    memory: {sizes.get("total_deep_mb", 0):.1f}MB data, '
              f'{sizes.get("avg_per_url_kb", 0):.1f}KB/url')


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('url')
    parser.add_argument('--base', default=DEFAULT_BASE, help='LibreCrawl instance to drive')
    parser.add_argument('--max-urls', type=int, default=150)
    parser.add_argument('--depth', type=int, default=4)
    parser.add_argument('--delay', type=float, default=0.25, help='seconds between requests')
    parser.add_argument('--concurrency', type=int, default=5)
    parser.add_argument('--timeout', type=int, default=900)
    parser.add_argument('--js', action='store_true', help='enable JavaScript rendering')
    parser.add_argument('--images', action='store_true', help='enable image crawling')
    parser.add_argument('--external', action='store_true', help='crawl external links')
    parser.add_argument('--pause-test', action='store_true', help='also verify pause/resume')
    parser.add_argument('--no-export', action='store_true', help='skip export checks')
    args = parser.parse_args()

    client_holder = {}
    try:
        run(args, client_holder)
        return 0
    except Violation as violation:
        print(f'  FAIL: {violation}')
        holder = client_holder.get('client')
        if holder is not None:
            holder.print_history()
        return 1
    except requests.exceptions.ConnectionError:
        print(f'  FAIL: could not reach {args.base}. Is LibreCrawl running?')
        return 2


if __name__ == '__main__':
    sys.exit(main())
