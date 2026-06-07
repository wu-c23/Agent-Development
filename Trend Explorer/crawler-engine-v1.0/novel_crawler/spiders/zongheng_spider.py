from __future__ import annotations

import json
import os
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import scrapy

from novel_crawler.items import TrendItem, utc_now_iso
from novel_crawler.spiders.base_platform_spider import BasePlatformSpider


class ZonghengTrendSpider(BasePlatformSpider):
    """Spider for public Zongheng ranking data.

    The rendered ranking page only exposes the first screen reliably. Zongheng's
    public rank details endpoint accepts pageNum/pageSize, so the spider uses it
    for pagination and keeps the HTML parser in BasePlatformSpider as fallback.
    """

    name = "zongheng_trends"
    allowed_domains = ["zongheng.com", "www.zongheng.com"]
    platform_key = "zongheng"
    platform_name = "纵横中文网"
    list_type = "综合榜"
    env_start_urls = "ZONGHENG_START_URLS"
    start_urls = [
        "https://www.zongheng.com/rank?nav=monthly-ticket&rankType=1&month=20261",
        "https://www.zongheng.com/rank?nav=monthly-ticket&rankType=1&month=20262",
        "https://www.zongheng.com/rank?nav=monthly-ticket&rankType=1&month=20263",
        "https://www.zongheng.com/rank?nav=monthly-ticket&rankType=1&month=20264",
        "https://www.zongheng.com/rank?nav=monthly-ticket&rankType=1&month=20265",
        "https://www.zongheng.com/rank?nav=one-day&rankType=3",
        "https://www.zongheng.com/rank?nav=recommend&rankType=6",
        "https://www.zongheng.com/rank?nav=click&rankType=5",
    ]
    url_list_type_map = [
        ("nav=monthly-ticket", "月票榜"),
        ("nav=one-day", "畅销榜"),
        ("nav=recommend", "推荐榜"),
        ("nav=click", "点击榜"),
    ]
    rank_type_name_map = {
        "1": "月票榜",
        "3": "畅销榜",
        "5": "点击榜",
        "6": "推荐榜",
    }
    api_url = "https://www.zongheng.com/api/rank/details"
    use_playwright = True
    wait_for_selector = "body"
    excluded_detail_tags = {
        "已签约",
        "未签约",
        "签约",
        "连载中",
        "连载",
        "已完结",
        "完结",
        "已完成",
        "VIP",
        "vip",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._seen_api_page_signatures: set[tuple[str, str, tuple[str, ...]]] = set()
        self._detail_tag_cache: dict[str, list[str]] = {}
        self._pending_detail_items: dict[str, list[TrendItem]] = {}

    def start_requests(self):
        """Prefer the public JSON endpoint so all ranking pages can be collected."""

        if os.getenv("ZONGHENG_USE_API", "true").strip().lower() not in {"1", "true", "yes", "on"}:
            self.logger.info("Zongheng API pagination disabled; fallback to rendered ranking pages.")
            yield from super().start_requests()
            return

        self.logger.info("Zongheng API pagination enabled: %s", self.api_url)
        for source_url in self.get_start_urls():
            if not self.is_allowed_url(source_url):
                self.logger.warning("Skip start URL outside allowed domains: %s", source_url)
                continue

            rank_type = self.extract_query_value(source_url, "rankType")
            if not rank_type:
                self.logger.warning("Skip Zongheng URL without rankType: %s", source_url)
                continue

            month = self.extract_query_value(source_url, "month")
            list_type = self.resolve_api_list_type(source_url, rank_type, month)
            yield self.build_api_request(
                rank_type=rank_type,
                list_type=list_type,
                source_url=source_url,
                page_no=1,
                month=month,
            )

    def build_api_request(
        self,
        rank_type: str,
        list_type: str,
        source_url: str,
        page_no: int,
        month: str | None = None,
    ):
        """Create one public rank API request for a specific list/page."""

        page_size = self.settings.getint("DEFAULT_PAGE_SIZE")
        self.logger.info(
            "Request Zongheng API page %s for %s rankType=%s month=%s pageSize=%s",
            page_no,
            list_type,
            rank_type,
            month or "",
            page_size,
        )
        formdata = {
            "cateFineId": "0",
            "cateType": "0",
            "pageNum": str(page_no),
            "pageSize": str(page_size),
            "period": "0",
            "rankNo": month if rank_type == "1" and month else "",
            "rankType": rank_type,
        }
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": "https://www.zongheng.com",
            "Referer": source_url,
        }
        return scrapy.Request(
            self.api_url,
            method="POST",
            body=urlencode(formdata),
            headers=headers,
            callback=self.parse_api,
            meta={
                "platform_key": self.platform_key,
                "list_type": list_type,
                "page_no": page_no,
                "rank_type": rank_type,
                "rank_month": month,
                "source_page_url": source_url,
            },
        )

    def parse_api(self, response):
        """Parse one Zongheng JSON rank page and enqueue the next page if available."""

        list_type = response.meta.get("list_type", self.list_type)
        page_no = int(response.meta.get("page_no", 1))
        source_url = response.meta.get("source_page_url", response.url)
        self.logger.info(
            "Parsing %s %s API page %s status=%s body=%s bytes source=%s",
            self.platform_name,
            list_type,
            page_no,
            response.status,
            len(response.body or b""),
            source_url,
        )

        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            self.logger.warning("Zongheng API returned non-JSON, fallback to rendered HTML: %s", source_url)
            yield self.build_html_fallback_request(source_url, list_type)
            return

        records = self.extract_rank_records(payload)
        if not records:
            if page_no == 1:
                self.logger.warning("Zongheng API page 1 returned no records, fallback to rendered HTML: %s", source_url)
                yield self.build_html_fallback_request(source_url, list_type)
            else:
                self.logger.info("Stop pagination for %s %s at empty API page %s", self.platform_name, list_type, page_no)
            return

        signature = self.build_records_signature(response.meta.get("rank_type", ""), list_type, records)
        if signature in self._seen_api_page_signatures:
            self.logger.warning(
                "Stop pagination for %s %s because API page %s repeated a previous page",
                self.platform_name,
                list_type,
                page_no,
            )
            return
        self._seen_api_page_signatures.add(signature)

        captured_at = utc_now_iso()
        page_size = self.settings.getint("DEFAULT_PAGE_SIZE")
        for index, record in enumerate(records, start=1):
            fallback_rank = index + ((page_no - 1) * page_size)
            item = self.build_item_from_record(record, response, fallback_rank, captured_at)
            if not item.get("title"):
                self.logger.debug("Skip empty Zongheng API record at page %s #%s", page_no, index)
                continue
            yield from self.enrich_or_yield_item(item, response)

        max_pages = self.settings.getint("MAX_PAGES_PER_LIST")
        if len(records) != page_size:
            self.logger.warning(
                "%s %s API page %s returned %s records, expected pageSize=%s",
                self.platform_name,
                list_type,
                page_no,
                len(records),
                page_size,
            )

        if page_no >= max_pages:
            self.logger.info(
                "Stop pagination for %s %s after fixed %s pages; expected maximum records=%s",
                self.platform_name,
                list_type,
                max_pages,
                max_pages * page_size,
            )
            return

        yield self.build_api_request(
            rank_type=response.meta.get("rank_type", ""),
            list_type=list_type,
            source_url=source_url,
            page_no=page_no + 1,
            month=response.meta.get("rank_month"),
        )

    def build_html_fallback_request(self, source_url: str, list_type: str):
        """Fallback to the rendered public page when the JSON endpoint is unavailable."""

        return scrapy.Request(
            source_url,
            callback=super().parse,
            meta={
                "platform_key": self.platform_key,
                "list_type": list_type,
                "use_playwright": self.use_playwright,
                "wait_for_selector": self.wait_for_selector,
                "page_no": 1,
            },
            dont_filter=True,
        )

    def resolve_list_type(self, url: str) -> str:
        """Resolve HTML fallback list type while preserving monthly rank periods."""

        rank_type = self.extract_query_value(url, "rankType") or ""
        month = self.extract_query_value(url, "month")
        return self.resolve_api_list_type(url, rank_type, month)

    def build_item_from_record(self, record: dict[str, Any], response, fallback_rank: int, captured_at: str) -> TrendItem:
        """Build the unified TrendItem shape from one Zongheng API record."""

        book_id = self.first_value(record, "bookId", "book_id", "id")
        title = self.first_value(record, "bookName", "name", "title")
        author = self.first_value(record, "authorName", "pseudonym", "author")
        category = self.first_value(record, "cateFineName", "cateName", "categoryName", "category")
        summary = self.first_value(record, "description", "desc", "intro")
        rank_value = self.first_value(record, "orderNo", "rankNo", "rank", "rankNum", "rank_no")
        heat_value = self.first_value(record, "number", "heatScore", "score", "hotScore")
        detail_url = self.build_detail_url(book_id)

        source_url = response.meta.get("source_page_url", response.url)
        page_no = int(response.meta.get("page_no", 1))
        return TrendItem(
            title=title,
            author=author,
            platform=self.platform_name,
            rank=self.parse_rank(str(rank_value) if rank_value is not None else None, fallback_rank),
            rankChange=0,
            category=category,
            tags=[tag for tag in [category] if tag],
            heatScore=self.parse_heat_score(str(heat_value) if heat_value is not None else None, fallback_rank),
            listType=response.meta.get("list_type", self.list_type),
            summary=summary,
            capturedAt=captured_at,
            sourceUrl=f"{source_url}#page={page_no}",
            detailUrl=detail_url,
        )

    def enrich_or_yield_item(self, item: TrendItem, response):
        """Fetch detail tags once per book and merge them into pending ranking items."""

        detail_url = item.get("detailUrl")
        if not self.detail_enrichment_enabled() or not detail_url:
            yield item
            return

        cached_tags = self._detail_tag_cache.get(detail_url)
        if cached_tags is not None:
            item["tags"] = self.merge_tags(item.get("tags", []), cached_tags)
            yield item
            return

        if detail_url in self._pending_detail_items:
            self._pending_detail_items[detail_url].append(item)
            return

        self._pending_detail_items[detail_url] = [item]
        yield scrapy.Request(
            detail_url,
            callback=self.parse_detail,
            errback=self.handle_detail_error,
            headers={"Referer": response.meta.get("source_page_url", response.url)},
            meta={"detail_url": detail_url},
        )

    def parse_detail(self, response):
        """Parse Zongheng detail-page tags and release all waiting ranking items."""

        detail_url = response.meta.get("detail_url", response.url)
        detail_tags = self.extract_detail_tags(response)
        self._detail_tag_cache[detail_url] = detail_tags
        pending_items = self._pending_detail_items.pop(detail_url, [])
        if detail_tags:
            self.logger.debug("Detail tags for %s: %s", detail_url, detail_tags)
        else:
            self.logger.info("No detail tags found for %s; keep ranking-page tags", detail_url)

        for item in pending_items:
            item["tags"] = self.merge_tags(item.get("tags", []), detail_tags)
            yield item

    def handle_detail_error(self, failure):
        """Release pending ranking items when a detail page request fails."""

        request = failure.request
        detail_url = request.meta.get("detail_url", request.url)
        self.logger.warning("Detail tag request failed for %s: %s", detail_url, failure.value)
        self._detail_tag_cache[detail_url] = []
        pending_items = self._pending_detail_items.pop(detail_url, [])
        for item in pending_items:
            yield item

    def extract_detail_tags(self, response) -> list[str]:
        """Extract fine-grained public tags from Zongheng book detail pages."""

        raw_tags = response.css(".book-info--tags span::text").getall()
        tags = [self.clean_text(tag) for tag in raw_tags]
        return self.filter_detail_tags([tag for tag in tags if tag])

    def filter_detail_tags(self, tags: list[str]) -> list[str]:
        """Remove status and contract labels from detail-page tags."""

        filtered: list[str] = []
        seen: set[str] = set()
        for tag in tags:
            if tag in self.excluded_detail_tags or tag in seen:
                continue
            seen.add(tag)
            filtered.append(tag)
        return filtered

    def merge_tags(self, base_tags, detail_tags: list[str]) -> list[str]:
        """Merge ranking-page tags with detail-page tags while preserving order."""

        merged: list[str] = []
        seen: set[str] = set()
        for tag in list(base_tags or []) + detail_tags:
            value = self.clean_text(str(tag))
            if value and value not in seen:
                seen.add(value)
                merged.append(value)
        return merged

    @staticmethod
    def detail_enrichment_enabled() -> bool:
        """Read the feature switch for detail-page tag enrichment."""

        return os.getenv("ZONGHENG_DETAIL_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def build_detail_url(book_id) -> str | None:
        """Build a public Zongheng detail URL from the API book id."""

        if book_id in (None, ""):
            return None
        return f"https://www.zongheng.com/detail/{book_id}"

    def extract_rank_records(self, payload: Any) -> list[dict[str, Any]]:
        """Find the most likely book-record list inside a Zongheng API payload."""

        candidate_lists = self.find_record_lists(payload)
        if not candidate_lists:
            return []
        return max(candidate_lists, key=len)

    def find_record_lists(self, value: Any) -> list[list[dict[str, Any]]]:
        """Recursively collect lists that look like ranking book records."""

        if isinstance(value, list):
            dict_items = [item for item in value if isinstance(item, dict)]
            if dict_items and any(self.looks_like_book_record(item) for item in dict_items):
                return [dict_items]
            nested: list[list[dict[str, Any]]] = []
            for item in value:
                nested.extend(self.find_record_lists(item))
            return nested

        if isinstance(value, dict):
            nested = []
            preferred_keys = (
                "data",
                "result",
                "rankList",
                "bookList",
                "list",
                "records",
                "items",
                "page",
            )
            for key in preferred_keys:
                if key in value:
                    nested.extend(self.find_record_lists(value[key]))
            for key, item in value.items():
                if key not in preferred_keys:
                    nested.extend(self.find_record_lists(item))
            return nested

        return []

    @staticmethod
    def looks_like_book_record(record: dict[str, Any]) -> bool:
        """Return True when a dict contains common Zongheng book fields."""

        return any(key in record for key in ("bookName", "bookId", "authorName"))

    @staticmethod
    def first_value(record: dict[str, Any], *keys: str):
        """Return the first non-empty value from a record."""

        for key in keys:
            value = record.get(key)
            if value not in (None, "", []):
                return value
        return None

    @staticmethod
    def extract_query_value(url: str, key: str) -> str | None:
        """Extract the first query value from a URL."""

        values = parse_qs(urlparse(url).query).get(key)
        return values[0] if values else None

    def resolve_api_list_type(self, source_url: str, rank_type: str, month: str | None) -> str:
        """Resolve list type and append month labels for historical monthly-ticket ranks."""

        base = self.rank_type_name_map.get(rank_type) or self.resolve_list_type(source_url)
        if rank_type == "1" and month:
            return f"{base}-{self.format_month_label(month)}"
        return base

    @staticmethod
    def format_month_label(month: str) -> str:
        """Convert compact month values such as 20261 into 2026年01月."""

        if len(month) < 5 or not month.isdigit():
            return month
        year = month[:4]
        month_no = int(month[4:])
        return f"{year}年{month_no:02d}月"

    @staticmethod
    def build_records_signature(rank_type: str, list_type: str, records: list[dict[str, Any]]) -> tuple[str, str, tuple[str, ...]]:
        """Build a compact signature so ignored pageNum does not create loops."""

        identities = tuple(
            str(record.get("bookId") or record.get("bookName") or record.get("title") or "")
            for record in records[:10]
        )
        return rank_type, list_type, identities
