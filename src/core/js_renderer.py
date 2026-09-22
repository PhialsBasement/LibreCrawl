"""JavaScript rendering handler using Playwright"""
import asyncio
import threading
import time
import socket
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from urllib.parse import urlparse
from src.utils.ssrf_guard import is_blocked_ip, is_private_allowed, is_allowed_by_test_hook


class JavaScriptRenderer:
    """Handles JavaScript rendering for dynamic content using Playwright"""

    def __init__(self, config):
        self.config = config
        self.playwright = None
        self.browser = None
        self.page_pool = []
        self.pool_lock = threading.Lock()

    async def _guard_route(self, route, request):
        """Abort requests to private / reserved IPs.

        Note on DNS Rebinding residual risk:
        Playwright/Chromium resolves DNS independently when making the actual network request.
        While we intercept requests at the route level and resolve hostnames in Python here,
        a time-of-check to time-of-use (TOCTOU) DNS rebinding window exists where a malicious
        DNS server could return a public IP during this check, but subsequently return a private IP
        when Chromium establishes the actual socket. True connect-time enforcement inside Chromium
        would require browser-level proxy/socket hooks (or network namespace isolation).
        """
        allow_flag = self.config.get('allow_private_targets')
        if is_private_allowed(allow_flag):
            await route.continue_()
            return

        url = request.url
        try:
            parsed = urlparse(url)
            hostname = parsed.hostname
            if not hostname:
                await route.continue_()
                return

            port = parsed.port or (443 if parsed.scheme == 'https' else 80)
            clean_host = hostname.strip('[]')

            # Check if host is already an IP address
            try:
                if is_blocked_ip(clean_host):
                    if is_allowed_by_test_hook(hostname, clean_host, port):
                        await route.continue_()
                        return
                    await route.abort('blockedbyclient')
                    return
                await route.continue_()
                return
            except ValueError:
                pass

            # Resolve domain in thread pool to avoid blocking async event loop
            loop = asyncio.get_running_loop()
            addrs = await loop.run_in_executor(None, socket.getaddrinfo, hostname, port)
            for addr in addrs:
                ip_str = addr[4][0]
                if is_allowed_by_test_hook(hostname, ip_str, port):
                    continue
                if is_blocked_ip(ip_str):
                    await route.abort('blockedbyclient')
                    return

            await route.continue_()
        except Exception:
            try:
                await route.abort('blockedbyclient')
            except Exception:
                pass

    async def initialize(self):
        """Initialize Playwright browser and page pool"""
        try:
            print("Starting Playwright browser...")
            self.playwright = await async_playwright().start()

            # Choose browser based on configuration
            browser_type = self.config.get('js_browser', 'chromium').lower()
            headless = self.config.get('js_headless', True)

            if browser_type == 'firefox':
                self.browser = await self.playwright.firefox.launch(headless=headless)
            elif browser_type == 'webkit':
                self.browser = await self.playwright.webkit.launch(headless=headless)
            else:  # Default to chromium
                args = ['--no-sandbox', '--disable-dev-shm-usage'] if headless else []
                self.browser = await self.playwright.chromium.launch(headless=headless, args=args)

            # Create page pool
            max_pages = self.config.get('js_max_concurrent_pages', 3)
            for i in range(max_pages):
                context = await self.browser.new_context(
                    user_agent=self.config.get('js_user_agent', 'LibreCrawl/1.0 (Web Crawler with JavaScript)'),
                    viewport={
                        'width': self.config.get('js_viewport_width', 1920),
                        'height': self.config.get('js_viewport_height', 1080)
                    }
                )
                await context.route("**/*", self._guard_route)
                page = await context.new_page()
                page.set_default_timeout(self.config.get('js_timeout', 30) * 1000)
                self.page_pool.append(page)

            print(f"JavaScript rendering initialized with {len(self.page_pool)} browser pages")

        except Exception as e:
            print(f"Failed to initialize JavaScript rendering: {e}")
            await self.cleanup()
            raise

    async def cleanup(self):
        """Clean up Playwright browser and resources"""
        try:
            if self.page_pool:
                for page in self.page_pool:
                    try:
                        await page.context.close()
                    except:
                        pass
                self.page_pool.clear()

            if self.browser:
                await self.browser.close()
                self.browser = None

            if self.playwright:
                await self.playwright.stop()
                self.playwright = None

            print("JavaScript rendering resources cleaned up")

        except Exception as e:
            print(f"Error during JavaScript cleanup: {e}")

    async def get_page(self):
        """Get an available page from the pool"""
        with self.pool_lock:
            if self.page_pool:
                return self.page_pool.pop()
        return None

    async def return_page(self, page):
        """Return a page to the pool"""
        with self.pool_lock:
            self.page_pool.append(page)

    @staticmethod
    def _response_ms(response, navigation_ms):
        """How long the server actually took, from the browser's own timings.

        Falls back to the measured navigation time when timing data is missing.
        """
        try:
            timing = response.request.timing if response else None
            if timing:
                for key in ('responseEnd', 'responseStart'):
                    value = timing.get(key)
                    if value and value > 0:
                        return float(value)
        except Exception:
            pass
        return navigation_ms

    async def render_page(self, url):
        """
        Render a page with JavaScript and return the HTML content

        Returns:
            tuple: (html_content, status_code, error_message, final_url, timing)
            final_url is where the page ended up after any redirects.
            timing carries response_ms (the server's own response, excluding the
            configured render wait) and render_ms (the whole render). Keeping
            them apart matters because js_wait_time is a deliberate sleep, and
            counting it as response time flags every page as slow.
        """
        page = None
        empty_timing = {'response_ms': 0.0, 'render_ms': 0.0}
        try:
            page = await self.get_page()
            if not page:
                return None, 0, "No JavaScript page available", None, empty_timing

            # Navigate to the page
            try:
                started = time.monotonic()
                response = await page.goto(
                    url,
                    wait_until='domcontentloaded',
                    timeout=self.config.get('js_timeout', 30) * 1000
                )
                navigation_ms = (time.monotonic() - started) * 1000
                response_ms = self._response_ms(response, navigation_ms)

                # Wait for JavaScript to render
                await asyncio.sleep(self.config.get('js_wait_time', 3))

                # Get the rendered HTML content
                html_content = await page.content()
                status_code = response.status if response else 200
                render_ms = (time.monotonic() - started) * 1000

                return html_content, status_code, None, page.url, {
                    'response_ms': response_ms, 'render_ms': render_ms}

            except PlaywrightTimeoutError:
                return None, 0, "JavaScript rendering timeout", None, empty_timing
            except Exception as e:
                return None, 0, f"Navigation error: {str(e)}", None, empty_timing

        except Exception as e:
            return None, 0, f"JavaScript rendering error: {str(e)}", None, empty_timing

        finally:
            if page:
                await self.return_page(page)

    def should_use_javascript(self, url):
        """Determine if a URL should use JavaScript rendering"""
        parsed = urlparse(url)
        path = parsed.path.lower()

        # Skip if it's clearly a non-HTML resource
        if path.endswith(('.pdf', '.jpg', '.jpeg', '.png', '.gif', '.css', '.js', '.xml', '.txt', '.zip')):
            return False

        return True
