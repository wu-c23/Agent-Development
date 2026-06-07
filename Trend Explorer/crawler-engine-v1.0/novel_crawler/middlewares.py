from __future__ import annotations

import random


class UserAgentRotationMiddleware:
    """Rotate User-Agent headers from a configurable pool."""

    def __init__(self, user_agents: list[str]):
        self.user_agents = user_agents

    @classmethod
    def from_crawler(cls, crawler):
        return cls(user_agents=crawler.settings.getlist("USER_AGENT_POOL"))

    def process_request(self, request, spider):
        if self.user_agents:
            request.headers.setdefault("User-Agent", random.choice(self.user_agents))
        request.headers.setdefault("Accept-Language", "zh-CN,zh;q=0.9,en;q=0.6")
        request.headers.setdefault("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
        return None


class ProxyProviderMiddleware:
    """Attach a static proxy when configured; proxy pool HTTP API is reserved."""

    def __init__(self, proxies: list[str], proxy_pool_url: str):
        self.proxies = proxies
        self.proxy_pool_url = proxy_pool_url

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            proxies=crawler.settings.getlist("PROXY_LIST"),
            proxy_pool_url=crawler.settings.get("PROXY_POOL_URL", ""),
        )

    def process_request(self, request, spider):
        if self.proxies:
            request.meta["proxy"] = random.choice(self.proxies)
        elif self.proxy_pool_url:
            spider.logger.debug("Proxy pool URL configured but not fetched automatically: %s", self.proxy_pool_url)
        return None


class CookieInjectionMiddleware:
    """Inject platform cookies only when explicitly provided by environment variables."""

    def __init__(self, platform_cookies: dict[str, str]):
        self.platform_cookies = platform_cookies

    @classmethod
    def from_crawler(cls, crawler):
        return cls(platform_cookies=crawler.settings.getdict("PLATFORM_COOKIES"))

    def process_request(self, request, spider):
        platform_key = request.meta.get("platform_key", getattr(spider, "platform_key", ""))
        cookie = self.platform_cookies.get(platform_key)
        if cookie:
            request.headers.setdefault("Cookie", cookie)
        return None


class EmptyResultLoggingSpiderMiddleware:
    """Log parse errors without hiding them from Scrapy's normal error handling."""

    @classmethod
    def from_crawler(cls, crawler):
        return cls()

    def process_spider_exception(self, response, exception, spider):
        spider.logger.exception("Spider parse failed for %s: %s", response.url, exception)
        return None

