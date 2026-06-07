from __future__ import annotations

import os


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: list[str], sep: str = "|") -> list[str]:
    value = os.getenv(name)
    if not value:
        return default
    return [part.strip() for part in value.split(sep) if part.strip()]


BOT_NAME = "novel_crawler"

SPIDER_MODULES = ["novel_crawler.spiders"]
NEWSPIDER_MODULE = "novel_crawler.spiders"

TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

ROBOTSTXT_OBEY = env_bool("ROBOTSTXT_OBEY", True)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

CONCURRENT_REQUESTS = int(os.getenv("CONCURRENT_REQUESTS", "4"))
CONCURRENT_REQUESTS_PER_DOMAIN = int(os.getenv("CONCURRENT_REQUESTS_PER_DOMAIN", "2"))
DOWNLOAD_DELAY = float(os.getenv("DOWNLOAD_DELAY", "2.0"))
RANDOMIZE_DOWNLOAD_DELAY = env_bool("RANDOMIZE_DOWNLOAD_DELAY", True)
DOWNLOAD_TIMEOUT = int(os.getenv("DOWNLOAD_TIMEOUT", "20"))

COOKIES_ENABLED = True
RETRY_ENABLED = True
RETRY_TIMES = int(os.getenv("RETRY_TIMES", "2"))
RETRY_HTTP_CODES = [408, 429, 500, 502, 503, 504, 522, 524]
MAX_PAGES_PER_LIST = int(os.getenv("MAX_PAGES_PER_LIST", "10"))
DEFAULT_PAGE_SIZE = int(os.getenv("DEFAULT_PAGE_SIZE", "20"))

AUTOTHROTTLE_ENABLED = env_bool("AUTOTHROTTLE_ENABLED", True)
AUTOTHROTTLE_START_DELAY = float(os.getenv("AUTOTHROTTLE_START_DELAY", "2.0"))
AUTOTHROTTLE_MAX_DELAY = float(os.getenv("AUTOTHROTTLE_MAX_DELAY", "12.0"))
AUTOTHROTTLE_TARGET_CONCURRENCY = float(os.getenv("AUTOTHROTTLE_TARGET_CONCURRENCY", "1.0"))
AUTOTHROTTLE_DEBUG = env_bool("AUTOTHROTTLE_DEBUG", False)

HTTPCACHE_ENABLED = env_bool("HTTPCACHE_ENABLED", False)
HTTPCACHE_EXPIRATION_SECS = int(os.getenv("HTTPCACHE_EXPIRATION_SECS", "3600"))
HTTPCACHE_DIR = "httpcache"

OUTPUT_DIR = os.getenv("OUTPUT_DIR", "data")
OUTPUT_FILE_PREFIX = os.getenv("OUTPUT_FILE_PREFIX", "trend_items")
OUTPUT_INCLUDE_SPIDER = env_bool("OUTPUT_INCLUDE_SPIDER", True)
DATABASE_SINK_ENABLED = env_bool("DATABASE_SINK_ENABLED", False)

USER_AGENT_POOL = env_list(
    "USER_AGENT_POOL",
    [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/17.0 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/123.0 Safari/537.36",
    ],
)

PROXY_LIST = env_list("PROXY_LIST", [], sep=",")
PROXY_POOL_URL = os.getenv("PROXY_POOL_URL", "")
PLATFORM_COOKIES = {
    "qidian": os.getenv("QIDIAN_COOKIE", ""),
    "zongheng": os.getenv("ZONGHENG_COOKIE", ""),
}

PLAYWRIGHT_ENABLED = env_bool("PLAYWRIGHT_ENABLED", False)
PLAYWRIGHT_HEADLESS = env_bool("PLAYWRIGHT_HEADLESS", True)
PLAYWRIGHT_TIMEOUT_MS = int(os.getenv("PLAYWRIGHT_TIMEOUT_MS", "15000"))
PLAYWRIGHT_WAIT_UNTIL = os.getenv("PLAYWRIGHT_WAIT_UNTIL", "domcontentloaded")
PLAYWRIGHT_POST_LOAD_WAIT_MS = int(os.getenv("PLAYWRIGHT_POST_LOAD_WAIT_MS", "1500"))
PLAYWRIGHT_SCROLL_TIMES = int(os.getenv("PLAYWRIGHT_SCROLL_TIMES", "1"))
PLAYWRIGHT_SCROLL_DELAY_MS = int(os.getenv("PLAYWRIGHT_SCROLL_DELAY_MS", "800"))
PLAYWRIGHT_BLOCK_RESOURCE_TYPES = env_list(
    "PLAYWRIGHT_BLOCK_RESOURCE_TYPES",
    ["image", "media", "font"],
    sep=",",
)

SAVE_RESPONSE_HTML = env_bool("SAVE_RESPONSE_HTML", False)
SAVE_HTML_ON_EMPTY = env_bool("SAVE_HTML_ON_EMPTY", True)
DEBUG_RESPONSE_DIR = os.getenv("DEBUG_RESPONSE_DIR", "data/debug_html")

DOWNLOADER_MIDDLEWARES = {
    "novel_crawler.middlewares.UserAgentRotationMiddleware": 400,
    "novel_crawler.middlewares.CookieInjectionMiddleware": 410,
    "novel_crawler.middlewares.ProxyProviderMiddleware": 420,
    "novel_crawler.playwright_middleware.NovelPlaywrightMiddleware": 543,
}

SPIDER_MIDDLEWARES = {
    "novel_crawler.middlewares.EmptyResultLoggingSpiderMiddleware": 543,
}

ITEM_PIPELINES = {
    "novel_crawler.pipelines.TrendItemValidationPipeline": 200,
    "novel_crawler.pipelines.JsonLinesWriterPipeline": 300,
    "novel_crawler.pipelines.DatabaseSinkPipeline": 900,
}

REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
FEED_EXPORT_ENCODING = "utf-8"

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
if env_bool("USE_REDIS_SCHEDULER", False):
    SCHEDULER = "scrapy_redis.scheduler.Scheduler"
    DUPEFILTER_CLASS = "scrapy_redis.dupefilter.RFPDupeFilter"
    SCHEDULER_PERSIST = env_bool("SCHEDULER_PERSIST", True)
