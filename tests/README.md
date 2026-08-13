# LibreCrawl tests

No test framework and no extra dependencies. Both files are plain scripts that
run against the code already in this repo.

## fixture_tests.py

Deterministic tests. Starts tiny HTTP servers on localhost and runs the crawler
against them in-process, so nothing touches the internet.

```bash
python tests/fixture_tests.py
```

Prints a PASS/FAIL line per behaviour and exits non-zero if any fail. If ports
8911-8917 are taken locally, set `FIXTURE_BASE_PORT` to move the range.

Each test pins a bug that reached production once:

| Test | What breaks if it fails |
|---|---|
| `test_cross_domain_redirect` | A page redirecting off-site makes the crawler resolve that site's relative links against your domain, inventing internal 404s |
| `test_external_images` | Off-domain images get requested and listed even with external crawling off |
| `test_sitemap_discovery_is_async` | Sitemap probing blocks the start-crawl request, or the crawl finishes before discovery delivers its URLs |
| `test_max_urls_counts_pages_not_images` | Image rows consume the max-URL budget, so an image-heavy site crawls only a page or two |
| `test_event_ordering_under_polling` | The UI receives an update for a row it was never sent, or the same row twice |

## crawl_harness.py

End-to-end test against a real site. Start LibreCrawl first, then point the
harness at a URL. It polls `/api/crawl_status` using the same event protocol as
the browser and accumulates state the same way
`web/static/js/incremental_poller.js` does.

```bash
python main.py --local          # in one terminal
python tests/crawl_harness.py https://example.com/ --max-urls 150
```

Useful flags: `--js` (JavaScript rendering), `--images`, `--external`,
`--pause-test` (also verifies pause actually halts work and resume continues),
`--delay` and `--max-urls` to stay polite on sites you do not own, and `--base`
to drive an instance on another host or port.

It verifies, on every run:

- no duplicate `url`/`link` events, and no update for a row that was never sent
- the client's accumulated state matches the server's full snapshot exactly
- mutations reach the client, specifically link status backfills and the
  `linked_from` values filled in at the end of a crawl
- rows stay in scope: nothing off-domain unless `--external` is set
- the counter never reports fewer crawled URLs than the rows already sent
- streaming exports contain exactly one row per URL, link and issue
- reloading the crawl from SQLite flips the epoch, replays every row, and
  matches what was crawled

On failure it prints the poll history (sequence numbers, event counts, epoch
changes) so the violation can be explained rather than just reported.
