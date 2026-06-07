from __future__ import annotations

from scrapy import signals
from scrapy.http import HtmlResponse
from scrapy.utils.defer import deferred_from_coro


class NovelPlaywrightMiddleware:
    """Render selected requests with Playwright when request.meta['use_playwright'] is true."""

    def __init__(self, crawler):
        self.crawler = crawler
        self.enabled = crawler.settings.getbool("PLAYWRIGHT_ENABLED")
        self.headless = crawler.settings.getbool("PLAYWRIGHT_HEADLESS")
        self.timeout_ms = crawler.settings.getint("PLAYWRIGHT_TIMEOUT_MS")
        self.wait_until = crawler.settings.get("PLAYWRIGHT_WAIT_UNTIL", "networkidle")
        self.post_load_wait_ms = crawler.settings.getint("PLAYWRIGHT_POST_LOAD_WAIT_MS")
        self.scroll_times = crawler.settings.getint("PLAYWRIGHT_SCROLL_TIMES")
        self.scroll_delay_ms = crawler.settings.getint("PLAYWRIGHT_SCROLL_DELAY_MS")
        self.block_resource_types = set(crawler.settings.getlist("PLAYWRIGHT_BLOCK_RESOURCE_TYPES"))
        self.playwright = None
        self.browser = None

    @classmethod
    def from_crawler(cls, crawler):
        middleware = cls(crawler)
        crawler.signals.connect(middleware.close, signal=signals.spider_closed)
        return middleware

    def process_request(self, request, spider):
        if not request.meta.get("use_playwright"):
            return None
        if not self.enabled:
            spider.logger.info("Playwright requested for %s but PLAYWRIGHT_ENABLED=false; using Scrapy downloader.", request.url)
            return None
        return deferred_from_coro(self._download(request, spider))

    async def _download(self, request, spider):
        await self._ensure_browser()
        context = await self.browser.new_context(
            user_agent=request.headers.get("User-Agent", b"").decode("utf-8", errors="ignore") or None,
            locale="zh-CN",
        )
        page = await context.new_page()
        try:
            if self.block_resource_types:
                await page.route("**/*", self._route_request)
            await page.goto(request.url, wait_until=self.wait_until, timeout=self.timeout_ms)
            wait_for_selector = request.meta.get("wait_for_selector")
            if wait_for_selector:
                await page.wait_for_selector(wait_for_selector, timeout=self.timeout_ms)
            if self.post_load_wait_ms > 0:
                await page.wait_for_timeout(self.post_load_wait_ms)
            for _ in range(max(0, self.scroll_times)):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(self.scroll_delay_ms)
            body = await page.content()
            final_url = page.url
            status = 200
            spider.logger.debug("Playwright rendered %s", request.url)
            return HtmlResponse(
                url=final_url,
                status=status,
                body=body.encode("utf-8"),
                encoding="utf-8",
                request=request,
            )
        finally:
            await page.close()
            await context.close()

    async def _route_request(self, route):
        if route.request.resource_type in self.block_resource_types:
            await route.abort()
            return
        await route.continue_()

    async def _ensure_browser(self):
        if self.browser:
            return
        from playwright.async_api import async_playwright

        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=self.headless)

    def close(self, spider):
        if self.browser or self.playwright:
            return deferred_from_coro(self._close_async(spider))
        return None

    async def _close_async(self, spider):
        if self.browser:
            await self.browser.close()
            self.browser = None
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None
        spider.logger.info("Playwright browser closed.")
