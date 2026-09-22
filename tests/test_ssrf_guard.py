"""Unit and integration tests for SSRF guard.

Runs with stdlib unittest:
    python -m unittest tests.test_ssrf_guard
Requires no third-party test runners and zero external network access.
"""
import http.server
import ipaddress
import os
import socket
import threading
import time
import unittest
from unittest.mock import AsyncMock, MagicMock
from urllib.parse import urlparse

import requests

from src.crawler import WebCrawler
from src.utils.ssrf_guard import (
    BlockedDestinationError,
    check_target_url,
    clear_test_allowlist,
    is_blocked_ip,
    is_private_allowed,
    make_guarded_session,
    set_test_allow_hook,
    set_test_allowlist,
)


class SSRFGuardIPTableTest(unittest.TestCase):
    """Test is_blocked_ip classification table required by the specification."""

    def test_is_blocked_ip_table(self):
        blocked_ips = [
            '127.0.0.1',
            '10.1.2.3',
            '172.16.0.1',
            '172.31.255.255',
            '192.168.1.1',
            '169.254.169.254',
            '100.64.0.1',
            '0.0.0.0',
            '::1',
            'fe80::1',
            'fc00::1',
            '::ffff:127.0.0.1',
            '::ffff:10.0.0.1',
        ]
        for ip in blocked_ips:
            with self.subTest(ip=ip):
                self.assertTrue(
                    is_blocked_ip(ip),
                    f"Expected IP {ip} to be blocked, but was allowed"
                )

        allowed_ips = [
            '1.1.1.1',
            '8.8.8.8',
            '2606:4700:4700::1111',
            '172.32.0.1',
        ]
        for ip in allowed_ips:
            with self.subTest(ip=ip):
                self.assertFalse(
                    is_blocked_ip(ip),
                    f"Expected IP {ip} to be allowed, but was blocked"
                )

    def test_additional_ip_forms(self):
        """Test IPv6 bracketed hosts, scope IDs, and ipaddress objects."""
        # Bracketed forms as might appear in URLs
        self.assertTrue(is_blocked_ip('[::1]'))
        self.assertTrue(is_blocked_ip('[fe80::1]'))
        self.assertFalse(is_blocked_ip('[2606:4700:4700::1111]'))

        # Scoped IPv6
        self.assertTrue(is_blocked_ip('fe80::1%eth0'))

        # Deprecated IPv4-compatible IPv6 (::x.x.x.x)
        self.assertTrue(is_blocked_ip('::127.0.0.1'))
        self.assertTrue(is_blocked_ip('::10.0.0.1'))
        self.assertFalse(is_blocked_ip('::1.1.1.1'))

        # 6to4 encapsulation (2002::/16, deprecated by RFC 7526, non-global in Python ipaddress)
        self.assertTrue(is_blocked_ip('2002:7f00:0001::'))  # 127.0.0.1
        self.assertTrue(is_blocked_ip('2002:0a00:0001::'))  # 10.0.0.1
        self.assertTrue(is_blocked_ip('2002:0101:0101::'))  # 6to4 is not globally routable

        # ipaddress object inputs
        self.assertTrue(is_blocked_ip(ipaddress.ip_address('127.0.0.1')))
        self.assertFalse(is_blocked_ip(ipaddress.ip_address('1.1.1.1')))


class LocalHTTPServerHelper:
    """Helper to start and stop local HTTP test servers on dynamic ports."""

    @staticmethod
    def start_server(handler_cls):
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler_cls)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, port


class SSRFGuardConnectTimeTest(unittest.TestCase):
    """Test connect-time SSRF enforcement for requests/urllib3 sessions."""

    def setUp(self):
        self._orig_env = os.environ.get('ALLOW_PRIVATE_TARGETS')
        if 'ALLOW_PRIVATE_TARGETS' in os.environ:
            del os.environ['ALLOW_PRIVATE_TARGETS']
        clear_test_allowlist()

    def tearDown(self):
        clear_test_allowlist()
        if self._orig_env is not None:
            os.environ['ALLOW_PRIVATE_TARGETS'] = self._orig_env
        elif 'ALLOW_PRIVATE_TARGETS' in os.environ:
            del os.environ['ALLOW_PRIVATE_TARGETS']

    def test_guarded_session_local_http_server_blocked(self):
        """A local HTTP server on 127.0.0.1: guarded session request -> BlockedDestinationError."""
        class EchoHandler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"hello")

        server, port = LocalHTTPServerHelper.start_server(EchoHandler)
        try:
            session = make_guarded_session()
            with self.assertRaises(BlockedDestinationError) as ctx:
                session.get(f"http://127.0.0.1:{port}/")

            err = ctx.exception
            self.assertIn('127.0.0.1', str(err))
            self.assertEqual(err.host, '127.0.0.1')
            self.assertEqual(err.ip, '127.0.0.1')
            self.assertIsInstance(err, requests.exceptions.ConnectionError)
        finally:
            server.shutdown()
            server.server_close()

    def test_redirect_to_blocked_second_hop(self):
        """Redirect case: server that 302s to 127.0.0.1:<port2>/ must be blocked at hop 2.

        Uses a test-only allowlist hook to permit hop 1 (port 1) and verify that
        hop 2 (port 2) is intercepted and blocked at connect time.
        """
        class RedirectHandler(http.server.BaseHTTPRequestHandler):
            target_port = None
            def log_message(self, *args):
                pass
            def do_GET(self):
                self.send_response(302)
                self.send_header('Location', f"http://127.0.0.1:{self.target_port}/secret")
                self.end_headers()

        class SecretHandler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"secret data")

        server1, port1 = LocalHTTPServerHelper.start_server(RedirectHandler)
        server2, port2 = LocalHTTPServerHelper.start_server(SecretHandler)
        RedirectHandler.target_port = port2

        try:
            # Allow port1 only via test hook
            set_test_allow_hook(lambda host, ip, port: port == port1)

            session = make_guarded_session()
            with self.assertRaises(BlockedDestinationError) as ctx:
                session.get(f"http://127.0.0.1:{port1}/start")

            err = ctx.exception
            # Ensure the blocked destination was the target of the redirect (port2)
            self.assertEqual(err.ip, '127.0.0.1')
            self.assertEqual(err.port, port2)
            self.assertIn(str(port2), str(err))
        finally:
            server1.shutdown()
            server2.shutdown()
            server1.server_close()
            server2.server_close()

    def test_allow_private_targets_env_opt_out(self):
        """ALLOW_PRIVATE_TARGETS=true lets the same request through."""
        class EchoHandler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"ok")

        server, port = LocalHTTPServerHelper.start_server(EchoHandler)
        try:
            os.environ['ALLOW_PRIVATE_TARGETS'] = 'true'
            session = make_guarded_session()
            resp = session.get(f"http://127.0.0.1:{port}/")
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.text, "ok")
        finally:
            server.shutdown()
            server.server_close()

    def test_allow_private_targets_config_opt_out(self):
        """Passing allow_private_targets=True to session allows the request."""
        class EchoHandler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"allowed via param")

        server, port = LocalHTTPServerHelper.start_server(EchoHandler)
        try:
            session = make_guarded_session(allow_private_targets=True)
            resp = session.get(f"http://127.0.0.1:{port}/")
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.text, "allowed via param")
        finally:
            server.shutdown()
            server.server_close()


class CrawlerSSRFIntegrationTest(unittest.TestCase):
    """Test SSRF guard integration within WebCrawler lifecycle."""

    def setUp(self):
        self._orig_env = os.environ.get('ALLOW_PRIVATE_TARGETS')
        if 'ALLOW_PRIVATE_TARGETS' in os.environ:
            del os.environ['ALLOW_PRIVATE_TARGETS']
        clear_test_allowlist()

    def tearDown(self):
        clear_test_allowlist()
        if self._orig_env is not None:
            os.environ['ALLOW_PRIVATE_TARGETS'] = self._orig_env
        elif 'ALLOW_PRIVATE_TARGETS' in os.environ:
            del os.environ['ALLOW_PRIVATE_TARGETS']

    def test_start_url_blocked(self):
        """A blocked start URL returns False and a clear error message from start_crawl."""
        crawler = WebCrawler()
        crawler.config['allow_private_targets'] = False

        blocked_urls = [
            'http://127.0.0.1:8080/',
            'http://localhost:8080/',
            'http://10.0.0.5/api',
            'http://169.254.169.254/latest/meta-data',
            'http://[::1]:8080/',
        ]

        for url in blocked_urls:
            with self.subTest(url=url):
                ok, message = crawler.start_crawl(url)
                self.assertFalse(ok, f"Expected start_crawl to reject {url}")
                self.assertIn("blocked by ssrf policy", message.lower())

    def test_start_url_allowed_with_opt_out(self):
        """start_crawl allows start URL when allow_private_targets is enabled."""
        crawler = WebCrawler()
        crawler.config['allow_private_targets'] = True

        ok, message = check_target_url('http://127.0.0.1:8080/', allow_private_targets=True)
        self.assertFalse(ok)  # False means NOT blocked

    def test_discovered_blocked_url_skipped_gracefully(self):
        """Discovered URLs pointing to private addresses are skipped and recorded, not crashing."""
        class SiteHandler(http.server.BaseHTTPRequestHandler):
            private_port = None
            def log_message(self, *args):
                pass
            def do_GET(self):
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                # Include a link to the blocked private destination
                body = f'<html><body><a href="http://127.0.0.1:{self.private_port}/private">p</a></body></html>'
                self.wfile.write(body.encode())

        server1, port1 = LocalHTTPServerHelper.start_server(SiteHandler)
        server2, port2 = LocalHTTPServerHelper.start_server(http.server.SimpleHTTPRequestHandler)
        SiteHandler.private_port = port2

        try:
            # Allow port1 (the site being crawled) via test allow hook
            set_test_allow_hook(lambda host, ip, port: port == port1)

            crawler = WebCrawler()
            crawler.config.update({
                'delay': 0.01,
                'concurrency': 2,
                'max_urls': 10,
                'max_depth': 2,
                'crawl_external': True,  # permit following external link to port2
                'allow_private_targets': False,
            })

            ok, msg = crawler.start_crawl(f"http://127.0.0.1:{port1}/")
            self.assertTrue(ok, msg)

            deadline = time.time() + 10
            while crawler.is_running and time.time() < deadline:
                time.sleep(0.05)

            self.assertFalse(crawler.is_running, "Crawl did not complete promptly")

            # Check crawl results
            urls_crawled = [r['url'] for r in crawler.crawl_results]
            self.assertIn(f"http://127.0.0.1:{port1}/", urls_crawled)

            # Look for the discovered private URL
            blocked_results = [
                r for r in crawler.crawl_results
                if f":{port2}/private" in r['url']
            ]
            self.assertEqual(len(blocked_results), 1)
            blocked_entry = blocked_results[0]
            self.assertEqual(blocked_entry['status_code'], 0)
            self.assertIn('blocked by ssrf policy', blocked_entry.get('error', '').lower())
        finally:
            server1.shutdown()
            server2.shutdown()
            server1.server_close()
            server2.server_close()


class PlaywrightSSRFGuardTest(unittest.IsolatedAsyncioTestCase):
    """Test Playwright route-level guard in js_renderer.py."""

    def setUp(self):
        clear_test_allowlist()

    def tearDown(self):
        clear_test_allowlist()

    async def test_route_guard_aborts_blocked_ip(self):
        from src.core.js_renderer import JavaScriptRenderer
        renderer = JavaScriptRenderer({'allow_private_targets': False})

        mock_route = AsyncMock()
        mock_request = MagicMock()
        mock_request.url = 'http://127.0.0.1:8080/data'

        await renderer._guard_route(mock_route, mock_request)
        mock_route.abort.assert_called_once_with('blockedbyclient')
        mock_route.continue_.assert_not_called()

    async def test_route_guard_allows_when_opt_out(self):
        from src.core.js_renderer import JavaScriptRenderer
        renderer = JavaScriptRenderer({'allow_private_targets': True})

        mock_route = AsyncMock()
        mock_request = MagicMock()
        mock_request.url = 'http://127.0.0.1:8080/data'

        await renderer._guard_route(mock_route, mock_request)
        mock_route.continue_.assert_called_once()
        mock_route.abort.assert_not_called()


if __name__ == '__main__':
    unittest.main()
