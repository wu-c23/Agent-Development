from __future__ import annotations

import os
import re
from hashlib import sha1
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

import scrapy

from novel_crawler.items import TrendItem, utc_now_iso
from novel_crawler.selectors import PLATFORM_SELECTORS


class BasePlatformSpider(scrapy.Spider):
    """Shared parsing helpers for platform ranking pages."""

    access_challenge_markers = (
        "TCaptcha",
        "captcha.qq.com",
        "t-captcha",
        "__captcha",
    )

    platform_key = ""
    platform_name = ""
    list_type = "趋势榜"
    env_start_urls = ""
    start_urls: list[str] = []
    url_list_type_map: list[tuple[str, str]] = []
    use_playwright = False
    wait_for_selector = ""

    def start_requests(self):
        for url in self.get_start_urls():
            if not self.is_allowed_url(url):
                self.logger.warning("Skip start URL outside allowed domains: %s", url)
                continue
            yield scrapy.Request(
                url,
                callback=self.parse,
                meta={
                    "platform_key": self.platform_key,
                    "list_type": self.resolve_list_type(url),
                    "use_playwright": self.use_playwright,
                    "wait_for_selector": self.wait_for_selector,
                    "page_no": 1,
                },
            )

    def get_start_urls(self) -> list[str]:
        configured = os.getenv(self.env_start_urls, "")
        if configured:
            return [url.strip() for url in configured.split(",") if url.strip()]
        return self.start_urls

    def parse(self, response):
        selectors = PLATFORM_SELECTORS[self.platform_key]
        self.dump_response_html(response)
        self.logger.info(
            "Parsing %s %s page %s status=%s body=%s bytes url=%s",
            self.platform_name,
            response.meta.get("list_type", self.list_type),
            response.meta.get("page_no", 1),
            response.status,
            len(response.body or b""),
            response.url,
        )
        if self.is_access_challenge(response):
            self.logger.warning(
                "Access challenge detected for %s %s: %s. Stop this response without bypassing captcha.",
                self.platform_name,
                response.meta.get("list_type", self.list_type),
                response.url,
            )
            if self.settings.getbool("SAVE_HTML_ON_EMPTY"):
                self.dump_response_html(response, force=True)
            return

        cards = self.select_cards(response, selectors["item"])
        if not cards:
            self.logger.warning(
                "No trend cards matched for %s %s: %s",
                self.platform_name,
                response.meta.get("list_type", self.list_type),
                response.url,
            )
            if self.settings.getbool("SAVE_HTML_ON_EMPTY"):
                self.dump_response_html(response, force=True)
            return

        captured_at = utc_now_iso()
        page_no = int(response.meta.get("page_no", 1))
        page_size = self.settings.getint("DEFAULT_PAGE_SIZE")
        for index, card in enumerate(cards, start=1):
            fallback_rank = index + ((page_no - 1) * page_size)
            item = self.build_item(card, response, fallback_rank, captured_at, selectors)
            if not item.get("title"):
                self.logger.debug("Skip empty card at %s #%s", response.url, index)
                continue
            yield item

        next_request = self.build_next_page_request(response, selectors)
        if next_request:
            yield next_request

    def build_item(self, card, response, fallback_rank: int, captured_at: str, selectors: dict[str, list[str]]) -> TrendItem:
        """Build a unified TrendItem from one ranking card."""

        rank_text = self.first_text(card, selectors.get("rank", []))
        heat_text = self.first_text(card, selectors.get("heat", []))
        tags = self.all_text(card, selectors.get("tags", []))

        return TrendItem(
            title=self.first_text(card, selectors["title"]),
            author=self.first_text(card, selectors.get("author", [])),
            platform=self.platform_name,
            rank=self.parse_rank(rank_text, fallback_rank),
            rankChange=0,
            category=self.first_text(card, selectors.get("category", [])),
            tags=tags,
            heatScore=self.parse_heat_score(heat_text, fallback_rank),
            listType=response.meta.get("list_type", self.list_type),
            summary=self.first_text(card, selectors.get("summary", [])),
            capturedAt=captured_at,
            sourceUrl=response.url,
        )

    def select_cards(self, response, selector_candidates: Iterable[str]):
        """Try selector candidates in order and return the first non-empty card list."""

        for selector in selector_candidates:
            cards = response.css(selector)
            if cards:
                self.logger.debug("Matched %s cards with selector: %s", len(cards), selector)
                return cards
        return []

    def resolve_list_type(self, url: str) -> str:
        """Resolve list type from configured URL fragments."""

        for fragment, list_type in self.url_list_type_map:
            if fragment in url:
                return list_type
        return self.list_type

    def build_next_page_request(self, response, selectors: dict[str, list[str]]):
        """Create a request for the next ranking page when a public next link exists."""

        page_no = int(response.meta.get("page_no", 1))
        max_pages = self.settings.getint("MAX_PAGES_PER_LIST")
        if page_no >= max_pages:
            self.logger.info(
                "Stop pagination for %s %s at page %s because MAX_PAGES_PER_LIST=%s",
                self.platform_name,
                response.meta.get("list_type", self.list_type),
                page_no,
                max_pages,
            )
            return None

        next_href = self.extract_next_href(response, selectors.get("next_page", []))
        if not next_href:
            self.logger.info(
                "No next page link found for %s %s page %s",
                self.platform_name,
                response.meta.get("list_type", self.list_type),
                page_no,
            )
            return None

        next_url = response.urljoin(next_href)
        if next_url == response.url:
            return None
        if not self.is_allowed_url(next_url):
            self.logger.warning("Skip next page outside allowed domains: %s", next_url)
            return None

        meta = dict(response.meta)
        meta["page_no"] = page_no + 1
        self.logger.info(
            "Follow next page for %s %s: page %s -> %s",
            self.platform_name,
            meta.get("list_type", self.list_type),
            meta["page_no"],
            next_url,
        )
        return response.follow(next_url, callback=self.parse, meta=meta)

    def is_allowed_url(self, url: str) -> bool:
        """Allow only configured platform domains for start and pagination URLs."""

        if not self.allowed_domains:
            return True
        hostname = urlparse(url).hostname or ""
        return any(hostname == domain or hostname.endswith(f".{domain}") for domain in self.allowed_domains)

    def is_access_challenge(self, response) -> bool:
        """Detect common public access challenge pages and avoid retry/bypass behavior."""

        text = response.text or ""
        return any(marker in text for marker in self.access_challenge_markers)

    def extract_next_href(self, response, selector_candidates: Iterable[str]) -> str | None:
        """Extract the next page URL from CSS candidates or visible next-page text."""

        for selector in selector_candidates:
            href = self.clean_href(response.css(selector).get())
            if href:
                return href

        xpath_candidates = [
            "//a[contains(normalize-space(.), '下一页')]/@href",
            "//a[contains(normalize-space(.), '下页')]/@href",
            "//a[contains(@class, 'next')]/@href",
            "//a[@rel='next']/@href",
        ]
        for xpath in xpath_candidates:
            href = self.clean_href(response.xpath(xpath).get())
            if href:
                return href
        return None

    @staticmethod
    def clean_href(value: str | None) -> str | None:
        """Reject empty, disabled, and JavaScript pseudo-links."""

        if not value:
            return None
        href = value.strip()
        lowered = href.lower()
        if not href or href == "#" or lowered.startswith("javascript:"):
            return None
        return href

    def dump_response_html(self, response, force: bool = False) -> None:
        """Save rendered HTML for selector debugging when explicitly enabled."""

        if not force and not self.settings.getbool("SAVE_RESPONSE_HTML"):
            return
        debug_dir = Path(self.settings.get("DEBUG_RESPONSE_DIR", "data/debug_html"))
        debug_dir.mkdir(parents=True, exist_ok=True)
        digest = sha1(response.url.encode("utf-8")).hexdigest()[:10]
        list_type = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", response.meta.get("list_type", self.list_type))
        path = debug_dir / f"{self.name}_{list_type}_{digest}.html"
        path.write_text(response.text, encoding="utf-8")
        self.logger.info("Saved response HTML for selector debugging: %s", path)

    def first_text(self, node, selector_candidates: Iterable[str]) -> str | None:
        """Return the first non-empty text extracted by candidate selectors."""

        for selector in selector_candidates:
            values = node.css(selector).getall()
            cleaned = [self.clean_text(value) for value in values]
            cleaned = [value for value in cleaned if value]
            if cleaned:
                return cleaned[0]
        return None

    def all_text(self, node, selector_candidates: Iterable[str]) -> list[str]:
        """Return all non-empty texts from the first selector that yields values."""

        for selector in selector_candidates:
            values = [self.clean_text(value) for value in node.css(selector).getall()]
            values = [value for value in values if value]
            if values:
                return values
        return []

    @staticmethod
    def clean_text(value: str | None) -> str | None:
        if value is None:
            return None
        value = re.sub(r"<[^>]+>", "", value)
        value = value.replace("\u3000", " ")
        value = " ".join(value.strip().split())
        return value or None

    @staticmethod
    def parse_rank(value: str | None, fallback: int) -> int:
        if not value:
            return fallback
        match = re.search(r"\d+", value)
        return int(match.group(0)) if match else fallback

    @staticmethod
    def parse_heat_score(value: str | None, fallback_rank: int) -> float:
        """Parse common Chinese heat text; fallback keeps sorting deterministic."""

        if not value:
            return max(1.0, 1000.0 - fallback_rank)
        normalized = value.replace(",", "").strip()
        match = re.search(r"(\d+(?:\.\d+)?)", normalized)
        if not match:
            return max(1.0, 1000.0 - fallback_rank)
        score = float(match.group(1))
        if "\u4ebf" in normalized:
            score *= 100000000
        elif "\u4e07" in normalized:
            score *= 10000
        return score
