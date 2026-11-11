"""
Verify that SQLite foreign-key enforcement and cascades operate correctly.

Before the fix, SQLite's default ``foreign_keys = OFF`` meant that
ON DELETE CASCADE declarations across the schema were silently ignored.
Deleting a crawl removed only its ``crawls`` row while all
``crawled_urls``, ``crawl_links``, ``crawl_issues`` and ``crawl_queue``
rows that belonged to it stayed behind as orphans.

Supports running both as a standalone script:
    python tests/test_foreign_keys.py
and under a test runner:
    pytest tests/test_foreign_keys.py
"""

import os
import sys
import tempfile
import contextlib

# ---------------------------------------------------------------------------
# Bootstrap: make ``from src import …`` work from the repo root.
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
from src import crawl_db, auth_db

CHILD_TABLES = ['crawled_urls', 'crawl_links', 'crawl_issues', 'crawl_queue']


def _count_children(conn, crawl_id):
    """Return the total number of child rows for *crawl_id* across all child tables."""
    total = 0
    for table in CHILD_TABLES:
        row = conn.execute(
            f'SELECT COUNT(*) FROM {table} WHERE crawl_id = ?', (crawl_id,)
        ).fetchone()
        total += row[0]
    return total


@contextlib.contextmanager
def isolated_db():
    """Create an isolated temporary database for a test and clean up afterwards."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name

    saved_crawl_db = crawl_db.DB_FILE
    saved_auth_db = auth_db.DB_FILE
    crawl_db.DB_FILE = db_path
    auth_db.DB_FILE = db_path

    try:
        auth_db.init_db()
        yield db_path
    finally:
        crawl_db.DB_FILE = saved_crawl_db
        auth_db.DB_FILE = saved_auth_db
        if os.path.exists(db_path):
            try:
                os.unlink(db_path)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Test Cases (compatible with both standalone execution and pytest)
# ---------------------------------------------------------------------------

def test_pragma_is_on():
    """get_db() connections in both crawl_db and auth_db must have foreign_keys enabled."""
    with isolated_db():
        with crawl_db.get_db() as conn:
            fk_crawl = conn.execute('PRAGMA foreign_keys').fetchone()[0]
            assert fk_crawl == 1, "crawl_db must have PRAGMA foreign_keys = 1"

        with auth_db.get_db() as conn:
            fk_auth = conn.execute('PRAGMA foreign_keys').fetchone()[0]
            assert fk_auth == 1, "auth_db must have PRAGMA foreign_keys = 1"


def test_cascade_deletes_children():
    """DELETE FROM crawls must cascade to all four child tables."""
    with isolated_db():
        with crawl_db.get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO crawls (session_id, base_url, status) "
                "VALUES ('test-sess', 'https://example.com', 'completed')"
            )
            crawl_id = cursor.lastrowid

            cursor.execute("INSERT INTO crawled_urls (crawl_id, url) VALUES (?, ?)", (crawl_id, 'https://example.com/p1'))
            cursor.execute("INSERT INTO crawl_links (crawl_id, source_url, target_url) VALUES (?, ?, ?)", (crawl_id, 'https://example.com/', 'https://example.com/p1'))
            cursor.execute("INSERT INTO crawl_issues (crawl_id, url, issue) VALUES (?, ?, ?)", (crawl_id, 'https://example.com/p1', 'missing title'))
            cursor.execute("INSERT INTO crawl_queue (crawl_id, url) VALUES (?, ?)", (crawl_id, 'https://example.com/queued'))

            before = _count_children(conn, crawl_id)
            assert before == 4, f"Expected 4 child rows before deletion, got {before}"

            cursor.execute('DELETE FROM crawls WHERE id = ?', (crawl_id,))

            after = _count_children(conn, crawl_id)
            assert after == 0, f"Expected 0 child rows after crawl deletion, got {after}"


def test_user_cascade_deletes_crawls_and_children():
    """Deleting a user must cascade to crawls and recursively to child rows."""
    with isolated_db():
        with auth_db.get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (username, email, password_hash, verified, tier) "
                "VALUES ('testuser', 'test@example.com', 'hash', 1, 'user')"
            )
            user_id = cursor.lastrowid

        crawl_id = crawl_db.create_crawl(user_id, 'user-sess', 'https://example.com', 'example.com', {})
        assert crawl_id is not None, "Failed to create crawl for valid user"

        with crawl_db.get_db() as conn:
            conn.execute("INSERT INTO crawled_urls (crawl_id, url) VALUES (?, ?)", (crawl_id, 'https://example.com/sub'))
            assert _count_children(conn, crawl_id) == 1, "Child row was not created"

            conn.execute("DELETE FROM users WHERE id = ?", (user_id,))

            crawls_left = conn.execute("SELECT COUNT(*) FROM crawls WHERE id = ?", (crawl_id,)).fetchone()[0]
            children_left = _count_children(conn, crawl_id)
            assert crawls_left == 0, f"Expected crawl to be deleted with user, found {crawls_left}"
            assert children_left == 0, f"Expected child rows to be deleted with user, found {children_left}"


def test_foreign_key_rejects_invalid_user():
    """Foreign key enforcement must reject non-existent user_id."""
    with isolated_db():
        with crawl_db.get_db() as conn:
            cursor = conn.cursor()
            rejected = False
            try:
                cursor.execute(
                    "INSERT INTO crawls (user_id, session_id, base_url, status) "
                    "VALUES (999999, 'invalid-user', 'https://example.com', 'completed')"
                )
            except sqlite3.IntegrityError:
                rejected = True

            assert rejected, "Foreign key constraint should have rejected non-existent user_id"


def test_cleanup_preserves_valid_rows_and_removes_orphans():
    """Orphan cleanup must delete orphaned rows while strictly preserving valid crawl data."""
    with isolated_db() as db_path:
        with crawl_db.get_db() as conn:
            cursor = conn.cursor()

            # 1. Valid crawl with legitimate child rows
            cursor.execute("INSERT INTO crawls (session_id, base_url, status) VALUES ('valid-sess', 'https://example.com', 'completed')")
            valid_id = cursor.lastrowid
            cursor.execute("INSERT INTO crawled_urls (crawl_id, url) VALUES (?, ?)", (valid_id, 'https://example.com/valid'))
            cursor.execute("INSERT INTO crawl_links (crawl_id, source_url, target_url) VALUES (?, ?, ?)", (valid_id, 'https://example.com/', 'https://example.com/valid'))

        # 2. Simulate historical orphaned rows created before foreign_keys was enabled.
        # Direct raw connection defaults to foreign_keys=OFF, allowing orphan insertion.
        raw_conn = sqlite3.connect(db_path)
        raw_conn.execute("INSERT INTO crawled_urls (crawl_id, url) VALUES (88888, 'https://example.com/orphan')")
        raw_conn.execute("INSERT INTO crawl_links (crawl_id, source_url, target_url) VALUES (88888, 'https://example.com/', 'https://example.com/orphan')")
        raw_conn.commit()
        raw_conn.close()

        with crawl_db.get_db() as conn:
            assert _count_children(conn, valid_id) == 2, "Valid children not set up"
            assert _count_children(conn, 88888) == 2, "Orphan children not set up"

        # Run init_crawl_tables() which triggers the NOT EXISTS orphan cleanup
        crawl_db.init_crawl_tables()

        with crawl_db.get_db() as conn:
            valid_count = _count_children(conn, valid_id)
            orphan_count = _count_children(conn, 88888)

            assert valid_count == 2, f"Cleanup must NOT delete valid rows! Expected 2, got {valid_count}"
            assert orphan_count == 0, f"Cleanup must remove orphan rows! Expected 0, got {orphan_count}"


def test_cleanup_old_crawls_cascades():
    """cleanup_old_crawls() removes parent crawls and all their child rows."""
    with isolated_db():
        with crawl_db.get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO crawls (session_id, base_url, status, started_at) "
                "VALUES ('old-sess', 'https://example.com', 'completed', datetime('now', '-100 days'))"
            )
            old_id = cursor.lastrowid
            cursor.execute("INSERT INTO crawled_urls (crawl_id, url) VALUES (?, ?)", (old_id, 'https://example.com/old'))
            assert _count_children(conn, old_id) == 1

        deleted = crawl_db.cleanup_old_crawls(days=90)
        assert deleted >= 1, f"Expected cleanup_old_crawls to delete at least 1 crawl, got {deleted}"

        with crawl_db.get_db() as conn:
            children_left = _count_children(conn, old_id)
            assert children_left == 0, f"Expected 0 child rows after cleanup_old_crawls, got {children_left}"


# ---------------------------------------------------------------------------
# Standalone CLI runner
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    tests = [
        test_pragma_is_on,
        test_cascade_deletes_children,
        test_user_cascade_deletes_crawls_and_children,
        test_foreign_key_rejects_invalid_user,
        test_cleanup_preserves_valid_rows_and_removes_orphans,
        test_cleanup_old_crawls_cascades,
    ]

    print("\nRunning foreign keys test suite...")
    passed = 0
    failed = 0

    for test in tests:
        name = test.__name__
        try:
            test()
            passed += 1
            print(f"  PASS  {name}")
        except Exception as e:
            failed += 1
            print(f"  FAIL  {name}: {e}")

    print()
    if failed:
        print(f"{failed} FAILED, {passed} passed")
        sys.exit(1)
    else:
        print(f"All {passed} tests passed successfully.")
