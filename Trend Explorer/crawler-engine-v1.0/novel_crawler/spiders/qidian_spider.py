from __future__ import annotations

from novel_crawler.spiders.base_platform_spider import BasePlatformSpider


class QidianTrendSpider(BasePlatformSpider):
    """Example spider for public Qidian ranking pages."""

    name = "qidian_trends"
    allowed_domains = ["qidian.com", "www.qidian.com"]
    platform_key = "qidian"
    platform_name = "起点中文网"
    list_type = "月票榜"
    env_start_urls = "QIDIAN_START_URLS"
    start_urls = [
        "https://www.qidian.com/rank/yuepiao/",
        "https://www.qidian.com/rank/hotsales/",
        "https://www.qidian.com/rank/recom/",
        "https://www.qidian.com/rank/readindex/",
    ]
    url_list_type_map = [
        ("/rank/yuepiao/", "月票榜"),
        ("/rank/hotsales/", "畅销榜"),
        ("/rank/recom/", "推荐榜"),
        ("/rank/readindex/", "阅读指数榜"),
    ]
    use_playwright = True
    wait_for_selector = "body"
