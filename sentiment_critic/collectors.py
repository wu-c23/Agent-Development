from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus, urlparse
from urllib.request import Request, urlopen
import os
import re

from .models import Review, dedupe_reviews, normalize_space, read_jsonl


DEEP_REVIEW_KEYWORDS = (
    "文笔",
    "剧情",
    "逻辑",
    "设定",
    "人物",
    "角色",
    "节奏",
    "伏笔",
    "世界观",
    "更新",
    "拖更",
    "水",
    "爽点",
    "毒点",
    "入坑",
    "弃文",
    "烂尾",
    "书评",
)


PLATFORM_DOMAINS = {
    "tieba": ("tieba.baidu.com",),
    "douban": ("douban.com",),
    "xiaohongshu": ("xiaohongshu.com", "xhslink.com"),
}


class ReviewHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.description = ""
        self.blocks: list[str] = []
        self._stack: list[str] = []
        self._buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key.lower(): value or "" for key, value in attrs}
        if tag == "meta":
            name = (attr_map.get("name") or attr_map.get("property") or "").lower()
            if name in {"description", "og:description"}:
                self.description = normalize_space(attr_map.get("content", ""))
        if tag in {"title", "h1", "h2", "h3", "p", "li", "article", "section", "div"}:
            self._stack.append(tag)
            self._buffer = []

    def handle_data(self, data: str) -> None:
        if self._stack:
            cleaned = normalize_space(data)
            if cleaned:
                self._buffer.append(cleaned)

    def handle_endtag(self, tag: str) -> None:
        if not self._stack:
            return
        if tag != self._stack[-1]:
            return
        text = normalize_space(" ".join(self._buffer))
        if text:
            if tag == "title" and not self.title:
                self.title = text
            elif tag != "title":
                self.blocks.append(text)
        self._stack.pop()
        self._buffer = []


def infer_platform(url: str, default: str = "manual") -> str:
    host = urlparse(url).netloc.lower()
    for platform, domains in PLATFORM_DOMAINS.items():
        if any(domain in host for domain in domains):
            return platform
    return default


def build_search_url(platform: str, book: str, page_index: int = 0) -> str:
    query = quote_plus(f"{book} 书评 文笔 逻辑 更新")
    platform = platform.lower()
    if platform == "tieba":
        return f"https://tieba.baidu.com/f/search/res?ie=utf-8&qw={query}&pn={page_index}"
    if platform == "douban":
        return f"https://www.douban.com/search?q={query}&start={page_index * 20}"
    if platform == "xiaohongshu":
        return f"https://www.xiaohongshu.com/search_result?keyword={query}"
    raise ValueError(f"Unsupported platform: {platform}")


def fetch_url(url: str, platform: str = "") -> str:
    platform = platform or infer_platform(url)
    headers = {
        "User-Agent": os.getenv(
            "SENTIMENT_CRITIC_UA",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        ),
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
    }
    cookie = platform_cookie(platform)
    if cookie:
        headers["Cookie"] = cookie
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=20) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="ignore")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")[:300]
        raise RuntimeError(f"HTTP {exc.code} when fetching {url}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Could not fetch {url}: {exc}") from exc


def platform_cookie(platform: str) -> str:
    key = {
        "tieba": "TIEBA_COOKIE",
        "douban": "DOUBAN_COOKIE",
        "xiaohongshu": "XHS_COOKIE",
    }.get(platform.lower(), "")
    return os.getenv(key, "") if key else ""


def extract_reviews_from_html(
    html: str,
    book: str,
    platform: str,
    source_url: str = "",
    min_chars: int = 80,
) -> list[Review]:
    parser = ReviewHTMLParser()
    parser.feed(html)
    blocks = [normalize_space(block) for block in parser.blocks if normalize_space(block)]
    candidates = candidate_review_blocks(blocks, parser.description, book, min_chars)
    reviews: list[Review] = []
    for index, content in enumerate(candidates):
        title = parser.title or make_title(content)
        if index:
            title = f"{title} #{index + 1}"
        reviews.append(
            Review(
                book=book,
                platform=platform,
                source_url=source_url,
                title=title,
                content=content,
            )
        )
    return dedupe_reviews(reviews)


def candidate_review_blocks(
    blocks: Iterable[str],
    description: str,
    book: str,
    min_chars: int,
) -> list[str]:
    candidates: list[str] = []
    if len(description) >= min_chars and relevance_score(description, book) > 0:
        candidates.append(description)

    paragraphs = [block for block in blocks if len(block) >= 18]
    for block in paragraphs:
        if len(block) >= min_chars and relevance_score(block, book) >= 1:
            candidates.append(trim_review(block))

    window: list[str] = []
    for block in paragraphs:
        window.append(block)
        text = normalize_space(" ".join(window))
        if len(text) >= min_chars:
            if relevance_score(text, book) >= 2:
                candidates.append(trim_review(text))
            window = []

    return dedupe_texts(candidates)


def relevance_score(text: str, book: str) -> int:
    score = 0
    if book and book in text:
        score += 2
    score += sum(1 for keyword in DEEP_REVIEW_KEYWORDS if keyword in text)
    if len(text) >= 180:
        score += 1
    return score


def trim_review(text: str, max_chars: int = 2400) -> str:
    text = normalize_space(text)
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0]


def dedupe_texts(texts: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for text in texts:
        key = re.sub(r"\W+", "", text.lower())[:500]
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(text)
    return unique


def make_title(content: str) -> str:
    text = normalize_space(content)
    return text[:32] + ("..." if len(text) > 32 else "")


def collect_reviews(
    book: str,
    platforms: list[str] | None = None,
    urls: list[str] | None = None,
    input_html: list[str] | None = None,
    input_jsonl: str = "",
    max_pages: int = 1,
    min_chars: int = 80,
    limit: int = 100,
) -> list[Review]:
    reviews: list[Review] = []

    if input_jsonl:
        reviews.extend(read_jsonl(input_jsonl, fallback_book=book))

    for html_path in input_html or []:
        path = Path(html_path)
        platform = infer_platform(path.name)
        html = path.read_text(encoding="utf-8", errors="ignore")
        reviews.extend(extract_reviews_from_html(html, book, platform, str(path), min_chars))

    for url in urls or []:
        platform = infer_platform(url)
        html = fetch_url(url, platform=platform)
        reviews.extend(extract_reviews_from_html(html, book, platform, url, min_chars))

    for platform in platforms or []:
        platform = platform.lower()
        for page_index in range(max_pages):
            url = build_search_url(platform, book, page_index)
            html = fetch_url(url, platform=platform)
            reviews.extend(extract_reviews_from_html(html, book, platform, url, min_chars))
            if platform == "xiaohongshu":
                break

    unique = dedupe_reviews(review for review in reviews if review.content)
    return unique[:limit]
