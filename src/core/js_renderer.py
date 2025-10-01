"""JavaScript rendering handler using Playwright"""
import asyncio
import threading
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from urllib.parse import urlparse


class JavaScriptRenderer:
    """Handles JavaScript rendering for dynamic content using Playwright"""

    def __init__(self, config):
        self.config = config
        self.playwright = None
        self.browser = None
        self.page_pool = []
        self.pool_lock = threading.Lock()

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

    async def render_page(self, url):
        """
        Render a page with JavaScript and return the HTML content

        Returns:
            tuple: (html_content, status_code, error_message)
        """
        page = None
        try:
            page = await self.get_page()
            if not page:
                return None, 0, "No JavaScript page available"

            # Navigate to the page
            try:
                response = await page.goto(
                    url,
                    wait_until='domcontentloaded',
                    timeout=self.config.get('js_timeout', 30) * 1000
                )

                # Wait for JavaScript to render
                await asyncio.sleep(self.config.get('js_wait_time', 3))

                # Get the rendered HTML content
                html_content = await page.content()
                status_code = response.status if response else 200

                return html_content, status_code, None

            except PlaywrightTimeoutError:
                return None, 0, "JavaScript rendering timeout"
            except Exception as e:
                return None, 0, f"Navigation error: {str(e)}"

        except Exception as e:
            return None, 0, f"JavaScript rendering error: {str(e)}"

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
