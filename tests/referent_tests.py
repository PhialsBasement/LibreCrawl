"""Deterministic tests for the patches this fork carries over upstream.

Same shape as fixture_tests.py: no framework, no network, no extra
dependencies. Run it directly:

    python tests/referent_tests.py

Everything here guards a divergence from upstream, which is the code most
likely to break silently on the next rebase — upstream has no reason to keep
any of it working:

  1. retention only ever deletes crawls past BOTH bounds, never a live one,
     and never the crawls row or its crawled_urls
  2. a second retention pass over the same database is a no-op, so the thread
     does not re-delete the same rows every six hours forever
  3. the link status backfill reaches the links pointing at a newly crawled
     URL, and costs nothing when nothing new was crawled
  4. the paginated crawl-serve routes never return an unbounded page
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import paginated_routes  # noqa: E402
import src.crawl_db as crawl_db  # noqa: E402
from src.core.link_manager import LinkManager  # noqa: E402

PASSED, FAILED = [], []


def result(name, ok, detail=''):
    (PASSED if ok else FAILED).append(name)
    print(f"  {'PASS' if ok else 'FAIL'}  {name}{(' - ' + detail) if detail else ''}")


class temp_db:
    """Point crawl_db at an empty database for the duration of a test."""

    def __enter__(self):
        self._original = crawl_db.DB_FILE
        handle, self.path = tempfile.mkstemp(suffix='.db')
        os.close(handle)
        os.unlink(self.path)  # sqlite creates it; an empty file confuses nothing
        crawl_db.DB_FILE = self.path
        crawl_db.init_crawl_tables()
        return self

    def __exit__(self, *exc):
        crawl_db.DB_FILE = self._original
        for suffix in ('', '-wal', '-shm'):
            try:
                os.unlink(self.path + suffix)
            except OSError:
                pass


def add_crawl(crawl_id, days_ago, status, links=3, issues=1):
    with crawl_db.get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO crawls (id, user_id, session_id, base_url, status, started_at) "
            "VALUES (?, 1, 'session', ?, ?, datetime('now', ?))",
            (crawl_id, f'http://crawl{crawl_id}.test', status, f'-{days_ago} days'))
        for i in range(links):
            cursor.execute(
                'INSERT INTO crawl_links (crawl_id, source_url, target_url) VALUES (?, ?, ?)',
                (crawl_id, 'http://a.test/', f'http://b.test/{i}'))
        for _ in range(issues):
            cursor.execute(
                'INSERT INTO crawl_issues (crawl_id, url, category, issue) VALUES (?, ?, ?, ?)',
                (crawl_id, 'http://a.test/', 'seo', 'missing title'))


def crawls_with_links():
    with crawl_db.get_db() as conn:
        rows = conn.execute(
            'SELECT DISTINCT crawl_id FROM crawl_links ORDER BY crawl_id').fetchall()
    return [row['crawl_id'] for row in rows]


def test_retention_respects_both_bounds():
    """Age alone empties the database after a quiet month; count alone drops
    last week's crawls during a busy one. A crawl has to fail both to go."""
    with temp_db():
        for i in range(1, 9):
            add_crawl(i, 90 + i, 'completed')     # old; 1 is the newest of them
        add_crawl(20, 1, 'completed')
        add_crawl(21, 2, 'stopped')

        # min_crawls=4 protects the 4 newest overall: 20, 21, 1, 2.
        purgeable = sorted(crawl_db.find_purgeable_crawls(days=30, min_crawls=4))
        result('retention_respects_both_bounds', purgeable == [3, 4, 5, 6, 7, 8],
               f'purgeable={purgeable}')


def test_retention_never_touches_a_live_crawl():
    """A paused crawl still has a queue checkpoint to resume from, and a
    running one is being written to right now."""
    with temp_db():
        add_crawl(1, 400, 'running')
        add_crawl(2, 400, 'paused')
        add_crawl(3, 400, 'completed')

        crawl_db.purge_old_crawl_data(days=30, min_crawls=0)
        survivors = crawls_with_links()
        result('retention_never_touches_a_live_crawl', survivors == [1, 2],
               f'crawls with links left: {survivors}')


def test_retention_keeps_the_crawl_record():
    """Only links and issues are bulky. What was crawled and when is cheap to
    keep and stays queryable after the rest is gone."""
    with temp_db():
        add_crawl(1, 400, 'completed')
        with crawl_db.get_db() as conn:
            conn.execute(
                "INSERT INTO crawled_urls (crawl_id, url, status_code) VALUES (1, 'http://a/', 200)")

        crawl_db.purge_old_crawl_data(days=30, min_crawls=0)

        with crawl_db.get_db() as conn:
            crawls = conn.execute('SELECT COUNT(*) c FROM crawls').fetchone()['c']
            urls = conn.execute('SELECT COUNT(*) c FROM crawled_urls').fetchone()['c']
            links = conn.execute('SELECT COUNT(*) c FROM crawl_links').fetchone()['c']
        result('retention_keeps_the_crawl_record', (crawls, urls, links) == (1, 1, 0),
               f'crawls={crawls} urls={urls} links={links}')


def test_retention_second_pass_is_a_noop():
    """Without this the thread re-deletes the same already-empty crawls on
    every run, forever."""
    with temp_db():
        add_crawl(1, 400, 'completed')
        first = crawl_db.purge_old_crawl_data(days=30, min_crawls=0)
        second = crawl_db.purge_old_crawl_data(days=30, min_crawls=0)
        result('retention_second_pass_is_a_noop',
               first[0] == 1 and second == (0, 0, 0),
               f'first={first} second={second}')


def link(source, target, status=None):
    return {'source_url': source, 'target_url': target, 'target_status': status,
            'is_internal': True, 'anchor_text': '', 'depth': 1}


def test_backfill_reaches_the_links_for_a_crawled_url():
    manager = LinkManager('a.test')
    manager._commit_links([link('http://a.test/', 'http://a.test/page'),
                           link('http://a.test/other', 'http://a.test/page'),
                           link('http://a.test/', 'http://a.test/untouched')])

    changed = manager.update_link_statuses([{'url': 'http://a.test/page', 'status_code': 404}])

    hit = [l['target_status'] for l in manager.all_links if l['target_url'].endswith('/page')]
    missed = [l['target_status'] for l in manager.all_links if l['target_url'].endswith('untouched')]
    result('backfill_reaches_the_links_for_a_crawled_url',
           len(changed) == 2 and hit == [404, 404] and missed == [None],
           f'changed={len(changed)} hit={hit} missed={missed}')


def test_backfill_ignores_already_seen_results():
    """The whole point of the cursor: a poll that arrives with nothing newly
    crawled must not walk anything."""
    manager = LinkManager('a.test')
    manager._commit_links([link('http://a.test/', 'http://a.test/page')])
    results = [{'url': 'http://a.test/page', 'status_code': 200}]

    manager.update_link_statuses(results)
    again = manager.update_link_statuses(results)

    result('backfill_ignores_already_seen_results',
           again == [] and manager._backfill_cursor == 1,
           f'changed={again} cursor={manager._backfill_cursor}')


def test_paginated_limits_are_clamped():
    """A falsy limit makes the crawl_db loaders skip pagination and return the
    whole table, which is the OOM these routes exist to avoid."""
    cases = {
        'none': paginated_routes._clamp_limit(None) == paginated_routes.DEFAULT_PAGE_LIMIT,
        'zero': paginated_routes._clamp_limit(0) == paginated_routes.MIN_PAGE_LIMIT,
        'negative': paginated_routes._clamp_limit(-5) == paginated_routes.MIN_PAGE_LIMIT,
        'huge': paginated_routes._clamp_limit(10 ** 9) == paginated_routes.MAX_PAGE_LIMIT,
        'offset': paginated_routes._clamp_offset(-1) == 0,
    }
    broken = [name for name, ok in cases.items() if not ok]
    result('paginated_limits_are_clamped', not broken, f'broken: {broken}')


TESTS = (
    test_retention_respects_both_bounds,
    test_retention_never_touches_a_live_crawl,
    test_retention_keeps_the_crawl_record,
    test_retention_second_pass_is_a_noop,
    test_backfill_reaches_the_links_for_a_crawled_url,
    test_backfill_ignores_already_seen_results,
    test_paginated_limits_are_clamped,
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
