"""
Retry requests that fail TLS verification with verification disabled.

Many real-world sites ship broken certificate chains (missing intermediates
that browsers fetch via AIA but Python does not). For an SEO audit tool we
prefer to continue crawling and flag the issue over aborting the run.
"""

import requests
import urllib3
from requests.exceptions import SSLError

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_original_request = requests.Session.request


def _request_with_ssl_fallback(self, method, url, **kwargs):
    try:
        return _original_request(self, method, url, **kwargs)
    except SSLError as e:
        print(
            f"[librecrawl] TLS verification failed for {url}, "
            f"retrying with verify=False: {e}",
            flush=True,
        )
        kwargs["verify"] = False
        return _original_request(self, method, url, **kwargs)


requests.Session.request = _request_with_ssl_fallback
