"""
Verify that _get_sitemaps_from_robots resolves relative Sitemap: values.

Before the fix, a relative value such as ``Sitemap: /sitemap-news.xml``
was passed to ``requests.get`` without a scheme, raising MissingSchema.
The error was caught and printed, and the sitemap's URLs were never
discovered.

Run:
    python tests/test_sitemap_relative.py
"""

import http.server
import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from src.core.sitemap_parser import SitemapParser

# ---------------------------------------------------------------------------
# Tiny HTTP server that serves a robots.txt with relative Sitemap lines.
# ---------------------------------------------------------------------------
ROBOTS_BODY = """\
User-agent: *
Disallow: /admin

Sitemap: http://{host}/sitemap-absolute.xml
Sitemap: /sitemap-relative.xml
Sitemap: sub/sitemap-deep.xml
Sitemap: /sitemap-comment.xml # inline comment describing sitemap
Sitemap: /sitemap-relative.xml
"""

SITEMAP_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://{host}/page-from-{name}</loc></url>
</urlset>
"""


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        host = self.headers["Host"] or f"127.0.0.1:{self.server.server_port}"
        if self.path == "/robots.txt":
            body = ROBOTS_BODY.format(host=host).encode()
        elif self.path.endswith(".xml"):
            name = self.path.strip("/").replace("/", "-").replace(".xml", "")
            body = SITEMAP_XML.format(host=host, name=name).encode()
        else:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass  # silence request logs during tests


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
passed = 0
failed = 0


def _report(name, ok):
    global passed, failed
    if ok:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}")


def test_relative_sitemaps_resolved(port):
    """Relative Sitemap: values must be resolved to full URLs."""
    session = requests.Session()
    base = f"http://127.0.0.1:{port}"
    parser = SitemapParser(session, base, timeout=5)

    sitemaps = parser._get_sitemaps_from_robots(base)

    _report("four unique sitemaps discovered (duplicates removed)", len(sitemaps) == 4)

    # Every URL must have a scheme — no bare /path values.
    all_have_scheme = all(s.startswith("http") for s in sitemaps)
    _report("all sitemaps have a scheme", all_have_scheme)

    # The absolute one must be unchanged.
    _report(
        "absolute sitemap preserved",
        f"http://127.0.0.1:{port}/sitemap-absolute.xml" in sitemaps,
    )

    # The relative ones must resolve against the robots.txt URL.
    _report(
        "root-relative sitemap resolved",
        f"http://127.0.0.1:{port}/sitemap-relative.xml" in sitemaps,
    )
    _report(
        "path-relative sitemap resolved",
        f"http://127.0.0.1:{port}/sub/sitemap-deep.xml" in sitemaps,
    )
    _report(
        "inline comments cleanly stripped",
        f"http://127.0.0.1:{port}/sitemap-comment.xml" in sitemaps,
    )


def test_resolved_sitemaps_are_fetchable(port):
    """The resolved URLs must actually be reachable."""
    session = requests.Session()
    base = f"http://127.0.0.1:{port}"
    parser = SitemapParser(session, base, timeout=5)

    urls = parser.discover_sitemaps(base)
    # We expect one <loc> from each of the three sitemaps, plus potentially
    # from the default probe paths (/sitemap.xml etc.) if they respond 200.
    _report("at least 3 URLs discovered from sitemaps", len(urls) >= 3)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    base_port = int(os.environ.get("FIXTURE_BASE_PORT", 8950))
    srv = http.server.HTTPServer(("127.0.0.1", base_port), _Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()

    try:
        print()
        test_relative_sitemaps_resolved(base_port)
        test_resolved_sitemaps_are_fetchable(base_port)
        print()

        if failed:
            print(f"{failed} FAILED, {passed} passed")
            sys.exit(1)
        else:
            print(f"All {passed} tests passed")
    finally:
        srv.shutdown()
