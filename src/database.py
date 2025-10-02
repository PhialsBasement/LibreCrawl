"""
Database backend for LibreCrawl with SQLite/PostgreSQL support
Handles unlimited URLs with efficient storage and retrieval
"""
import sqlite3
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
import threading


class CrawlDatabase:
    """Database handler for crawl data with support for unlimited URLs"""

    def __init__(self, db_type='sqlite', db_path=None, connection_string=None):
        self.db_type = db_type
        self.db_path = db_path or Path.home() / '.librecrawl' / 'crawls.db'
        self.connection_string = connection_string
        self.local = threading.local()

        if db_type == 'sqlite':
            self._init_sqlite()
        elif db_type == 'postgresql':
            self._init_postgresql()

    def _init_sqlite(self):
        """Initialize SQLite database"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = self._get_connection()
        self._create_tables(conn)
        conn.close()

    def _init_postgresql(self):
        """Initialize PostgreSQL database"""
        # TODO: Implement PostgreSQL support
        raise NotImplementedError("PostgreSQL support coming soon")

    def _get_connection(self):
        """Get thread-local database connection"""
        if not hasattr(self.local, 'conn') or self.local.conn is None:
            if self.db_type == 'sqlite':
                self.local.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
                self.local.conn.row_factory = sqlite3.Row
                # Enable WAL mode for better concurrency
                self.local.conn.execute("PRAGMA journal_mode=WAL")
                self.local.conn.execute("PRAGMA synchronous=NORMAL")
        return self.local.conn

    def _create_tables(self, conn):
        """Create database schema"""
        cursor = conn.cursor()

        # Crawl sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS crawl_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                base_url TEXT NOT NULL,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                status TEXT DEFAULT 'running',
                total_discovered INTEGER DEFAULT 0,
                total_crawled INTEGER DEFAULT 0,
                max_depth INTEGER DEFAULT 0,
                config TEXT
            )
        """)

        # URLs table - main storage
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS urls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                url TEXT NOT NULL,
                status_code INTEGER,
                content_type TEXT,
                size INTEGER,
                is_internal BOOLEAN,
                depth INTEGER,

                -- SEO fields
                title TEXT,
                meta_description TEXT,
                h1 TEXT,
                h2 TEXT,
                h3 TEXT,
                word_count INTEGER,
                canonical_url TEXT,
                lang TEXT,
                charset TEXT,
                viewport TEXT,
                robots TEXT,
                author TEXT,
                keywords TEXT,

                -- JSON stored fields
                og_tags TEXT,
                twitter_tags TEXT,
                json_ld TEXT,
                analytics TEXT,
                images TEXT,
                hreflang TEXT,
                schema_org TEXT,

                -- Link counts
                internal_links INTEGER DEFAULT 0,
                external_links INTEGER DEFAULT 0,

                -- Performance
                response_time REAL,
                javascript_rendered BOOLEAN DEFAULT 0,

                -- Timestamps
                crawled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (session_id) REFERENCES crawl_sessions(id),
                UNIQUE(session_id, url)
            )
        """)

        # Links table - relationship tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                source_url TEXT NOT NULL,
                target_url TEXT NOT NULL,
                anchor_text TEXT,
                is_internal BOOLEAN,
                target_domain TEXT,
                target_status INTEGER,
                placement TEXT,

                FOREIGN KEY (session_id) REFERENCES crawl_sessions(id)
            )
        """)

        # Issues table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                url TEXT NOT NULL,
                type TEXT,
                category TEXT,
                issue TEXT,
                details TEXT,
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (session_id) REFERENCES crawl_sessions(id)
            )
        """)

        # PageSpeed results table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pagespeed_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                url TEXT NOT NULL,
                strategy TEXT,
                performance_score INTEGER,
                metrics TEXT,
                analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (session_id) REFERENCES crawl_sessions(id)
            )
        """)

        # Create indexes for performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_urls_session ON urls(session_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_urls_url ON urls(url)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_urls_status ON urls(status_code)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_urls_internal ON urls(is_internal)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_links_session ON links(session_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_links_source ON links(source_url)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_links_target ON links(target_url)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_issues_session ON issues(session_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_issues_type ON issues(type)")

        conn.commit()

    def create_session(self, base_url: str, config: dict) -> int:
        """Create a new crawl session"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO crawl_sessions (base_url, config, status)
            VALUES (?, ?, 'running')
        """, (base_url, json.dumps(config)))

        conn.commit()
        return cursor.lastrowid

    def update_session_stats(self, session_id: int, discovered: int, crawled: int, max_depth: int):
        """Update session statistics"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE crawl_sessions
            SET total_discovered = ?, total_crawled = ?, max_depth = ?
            WHERE id = ?
        """, (discovered, crawled, max_depth, session_id))

        conn.commit()

    def complete_session(self, session_id: int):
        """Mark session as completed"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE crawl_sessions
            SET status = 'completed', completed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (session_id,))

        conn.commit()

    def add_url(self, session_id: int, url_data: dict):
        """Add or update a crawled URL"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Convert complex fields to JSON
        og_tags = json.dumps(url_data.get('og_tags', {}))
        twitter_tags = json.dumps(url_data.get('twitter_tags', {}))
        json_ld = json.dumps(url_data.get('json_ld', []))
        analytics = json.dumps(url_data.get('analytics', {}))
        images = json.dumps(url_data.get('images', []))
        hreflang = json.dumps(url_data.get('hreflang', []))
        schema_org = json.dumps(url_data.get('schema_org', []))
        h2 = json.dumps(url_data.get('h2', []))
        h3 = json.dumps(url_data.get('h3', []))

        cursor.execute("""
            INSERT OR REPLACE INTO urls (
                session_id, url, status_code, content_type, size, is_internal, depth,
                title, meta_description, h1, h2, h3, word_count,
                canonical_url, lang, charset, viewport, robots, author, keywords,
                og_tags, twitter_tags, json_ld, analytics, images, hreflang, schema_org,
                internal_links, external_links, response_time, javascript_rendered
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?
            )
        """, (
            session_id, url_data['url'], url_data.get('status_code'),
            url_data.get('content_type'), url_data.get('size'),
            url_data.get('is_internal'), url_data.get('depth'),
            url_data.get('title'), url_data.get('meta_description'),
            url_data.get('h1'), h2, h3, url_data.get('word_count'),
            url_data.get('canonical_url'), url_data.get('lang'),
            url_data.get('charset'), url_data.get('viewport'),
            url_data.get('robots'), url_data.get('author'),
            url_data.get('keywords'),
            og_tags, twitter_tags, json_ld, analytics, images, hreflang, schema_org,
            url_data.get('internal_links', 0), url_data.get('external_links', 0),
            url_data.get('response_time'), url_data.get('javascript_rendered', False)
        ))

        conn.commit()

    def add_link(self, session_id: int, link_data: dict):
        """Add a link relationship"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO links (
                session_id, source_url, target_url, anchor_text,
                is_internal, target_domain, target_status, placement
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id, link_data['source_url'], link_data['target_url'],
            link_data.get('anchor_text'), link_data.get('is_internal'),
            link_data.get('target_domain'), link_data.get('target_status'),
            link_data.get('placement', 'body')
        ))

        conn.commit()

    def add_issue(self, session_id: int, issue_data: dict):
        """Add an issue"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO issues (session_id, url, type, category, issue, details)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            session_id, issue_data['url'], issue_data['type'],
            issue_data['category'], issue_data['issue'], issue_data['details']
        ))

        conn.commit()

    def get_urls_paginated(self, session_id: int, offset: int = 0, limit: int = 100,
                          filters: dict = None) -> List[dict]:
        """Get URLs with pagination and filtering"""
        conn = self._get_connection()
        cursor = conn.cursor()

        query = "SELECT * FROM urls WHERE session_id = ?"
        params = [session_id]

        if filters:
            if filters.get('is_internal') is not None:
                query += " AND is_internal = ?"
                params.append(filters['is_internal'])

            if filters.get('status_code_min'):
                query += " AND status_code >= ?"
                params.append(filters['status_code_min'])

            if filters.get('status_code_max'):
                query += " AND status_code <= ?"
                params.append(filters['status_code_max'])

        query += " ORDER BY id LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()

        return [self._row_to_dict(row) for row in rows]

    def get_urls_count(self, session_id: int, filters: dict = None) -> int:
        """Get total count of URLs for pagination"""
        conn = self._get_connection()
        cursor = conn.cursor()

        query = "SELECT COUNT(*) FROM urls WHERE session_id = ?"
        params = [session_id]

        if filters:
            if filters.get('is_internal') is not None:
                query += " AND is_internal = ?"
                params.append(filters['is_internal'])

            if filters.get('status_code_min'):
                query += " AND status_code >= ?"
                params.append(filters['status_code_min'])

            if filters.get('status_code_max'):
                query += " AND status_code <= ?"
                params.append(filters['status_code_max'])

        cursor.execute(query, params)
        return cursor.fetchone()[0]

    def get_links_paginated(self, session_id: int, offset: int = 0, limit: int = 100,
                           internal_only: bool = None) -> List[dict]:
        """Get links with pagination"""
        conn = self._get_connection()
        cursor = conn.cursor()

        query = "SELECT * FROM links WHERE session_id = ?"
        params = [session_id]

        if internal_only is not None:
            query += " AND is_internal = ?"
            params.append(internal_only)

        query += " ORDER BY id LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def get_issues_paginated(self, session_id: int, offset: int = 0, limit: int = 100,
                            issue_type: str = None) -> List[dict]:
        """Get issues with pagination"""
        conn = self._get_connection()
        cursor = conn.cursor()

        query = "SELECT * FROM issues WHERE session_id = ?"
        params = [session_id]

        if issue_type:
            query += " AND type = ?"
            params.append(issue_type)

        query += " ORDER BY id LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def get_session_stats(self, session_id: int) -> dict:
        """Get session statistics"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM crawl_sessions WHERE id = ?", (session_id,))
        row = cursor.fetchone()

        if row:
            return dict(row)
        return None

    def _row_to_dict(self, row) -> dict:
        """Convert SQLite row to dictionary with JSON parsing"""
        data = dict(row)

        # Parse JSON fields
        json_fields = ['og_tags', 'twitter_tags', 'json_ld', 'analytics',
                      'images', 'hreflang', 'schema_org', 'h2', 'h3']

        for field in json_fields:
            if field in data and data[field]:
                try:
                    data[field] = json.loads(data[field])
                except:
                    data[field] = []

        return data

    def close(self):
        """Close database connection"""
        if hasattr(self.local, 'conn') and self.local.conn:
            self.local.conn.close()
            self.local.conn = None
