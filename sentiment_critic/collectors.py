from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus, urlparse
from urllib.request import Request, urlopen
import os
import re

from .agent_client import load_env_files
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
        self._ignore_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg", "canvas", "template"}:
            self._ignore_depth += 1
            return
        attr_map = {key.lower(): value or "" for key, value in attrs}
        if tag == "meta":
            name = (attr_map.get("name") or attr_map.get("property") or "").lower()
            if name in {"description", "og:description"}:
                self.description = normalize_space(attr_map.get("content", ""))
        if tag in {"title", "h1", "h2", "h3", "p", "li", "article", "section", "div"}:
            self._stack.append(tag)
            self._buffer = []

    def handle_data(self, data: str) -> None:
        if self._ignore_depth:
            return
        if self._stack:
            cleaned = normalize_space(data)
            if cleaned:
                self._buffer.append(cleaned)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg", "canvas", "template"}:
            self._ignore_depth = max(0, self._ignore_depth - 1)
            return
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
    load_env_files()
    platform = platform or infer_platform(url)
    headers = {
        "User-Agent": os.getenv(
            "SENTIMENT_CRITIC_UA",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
        "Referer": platform_referer(platform),
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


def platform_referer(platform: str) -> str:
    return {
        "tieba": "https://tieba.baidu.com/",
        "douban": "https://www.douban.com/",
        "xiaohongshu": "https://www.xiaohongshu.com/",
    }.get(platform.lower(), "")


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
    if is_review_like(description, book, min_chars):
        candidates.append(description)

    paragraphs = [block for block in blocks if len(block) >= 18]
    for block in paragraphs:
        if is_review_like(block, book, min_chars):
            candidates.append(trim_review(block))

    window: list[str] = []
    for block in paragraphs:
        window.append(block)
        text = normalize_space(" ".join(window))
        if len(text) >= min_chars:
            if is_review_like(text, book, min_chars):
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


def is_review_like(text: str, book: str, min_chars: int = 80) -> bool:
    text = normalize_space(text)
    if looks_like_boilerplate(text):
        return False
    chinese_count = chinese_char_count(text)
    relevance = relevance_score(text, book)
    if chinese_count < 40:
        return False
    if sentence_mark_count(text) < 2:
        return False
    if len(text) >= min_chars:
        return relevance >= 2
    return chinese_count >= 60 and relevance >= 4


def looks_like_boilerplate(text: str) -> bool:
    lower = text.lower()
    code_markers = (
        "function",
        "var ",
        "window.",
        "document.",
        "json.",
        "encodeuricomponent",
        "addeventlistener",
        "rendersearchresult",
        "search_config",
    )
    boilerplate_markers = (
        "备案",
        "营业执照",
        "许可证",
        "举报",
        "用户协议",
        "隐私政策",
        "违法不良信息",
        "算法",
        "安全验证",
        "captcha",
    )
    if any(marker in lower for marker in code_markers):
        return True
    return any(marker in text for marker in boilerplate_markers)


def chinese_char_count(text: str) -> int:
    return sum(1 for char in text if "\u4e00" <= char <= "\u9fff")


def sentence_mark_count(text: str) -> int:
    return sum(text.count(mark) for mark in "。！？；，")


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
    keyword: str = "",
    douban_subject_id: str = "",
    douban_subject_url: str = "",
    douban_fetch_full: bool = True,
    max_pages: int = 1,
    min_chars: int = 80,
    limit: int = 100,
    fetch_detail: bool = True,
    thread_pages: int = 1,
    delay: float = 2.0,
    timeout: int = 20,
    retries: int = 2,
    strict: bool = False,
) -> list[Review]:
    reviews: list[Review] = []
    errors: list[str] = []
    platforms = [platform.lower() for platform in platforms or []]

    if input_jsonl:
        reviews.extend(read_jsonl(input_jsonl, fallback_book=book))

    for html_path in input_html or []:
        path = Path(html_path)
        platform = infer_platform(path.name)
        if platform == "manual" and len(platforms) == 1:
            platform = platforms[0]
        if platform == "tieba":
            from .tieba import TiebaBookReviewCrawler

            reviews.extend(TiebaBookReviewCrawler(delay=0).parse_saved_html([html_path], book, min_chars))
            continue
        if platform == "xiaohongshu":
            from .xiaohongshu import XiaohongshuBookReviewCrawler

            reviews.extend(XiaohongshuBookReviewCrawler(delay=0).parse_saved_html([html_path], book, min_chars))
            continue
        html = path.read_text(encoding="utf-8", errors="ignore")
        reviews.extend(extract_reviews_from_html(html, book, platform, str(path), min_chars))

    for url in urls or []:
        platform = infer_platform(url)
        try:
            if platform == "tieba":
                from .tieba import collect_tieba_reviews

                reviews.extend(
                    collect_tieba_reviews(
                        book=book,
                        pages=0,
                        min_chars=min_chars,
                        limit=limit,
                        fetch_threads=fetch_detail,
                        thread_pages=thread_pages,
                        urls=[url],
                        delay=delay,
                        timeout=timeout,
                        retries=retries,
                        strict=strict,
                    )
                )
                continue
            if platform == "xiaohongshu":
                from .xiaohongshu import collect_xiaohongshu_reviews

                reviews.extend(
                    collect_xiaohongshu_reviews(
                        book=book,
                        pages=0,
                        min_chars=min_chars,
                        limit=limit,
                        fetch_notes=fetch_detail,
                        urls=[url],
                        delay=delay,
                        timeout=timeout,
                        retries=retries,
                        strict=strict,
                    )
                )
                continue
            html = fetch_url(url, platform=platform)
        except RuntimeError as exc:
            if strict:
                raise
            errors.append(str(exc))
            continue
        reviews.extend(extract_reviews_from_html(html, book, platform, url, min_chars))

    for platform in platforms:
        if platform == "douban":
            from .douban import collect_douban_reviews

            if max_pages <= 0:
                continue
            try:
                reviews.extend(
                    collect_douban_reviews(
                        book=book,
                        subject_id=douban_subject_id,
                        subject_url=douban_subject_url,
                        pages=max_pages,
                        min_chars=min_chars,
                        limit=limit,
                        fetch_full=douban_fetch_full,
                        delay=delay,
                        timeout=timeout,
                        retries=retries,
                        strict=strict,
                    )
                )
            except (RuntimeError, ValueError) as exc:
                if strict:
                    raise
                errors.append(str(exc))
            continue
        if platform == "tieba":
            from .tieba import collect_tieba_reviews

            try:
                reviews.extend(
                    collect_tieba_reviews(
                        book=book,
                        keyword=keyword,
                        pages=max_pages,
                        min_chars=min_chars,
                        limit=limit,
                        fetch_threads=fetch_detail,
                        thread_pages=thread_pages,
                        delay=delay,
                        timeout=timeout,
                        retries=retries,
                        strict=strict,
                    )
                )
            except RuntimeError as exc:
                if strict:
                    raise
                errors.append(str(exc))
            continue
        if platform == "xiaohongshu":
            from .xiaohongshu import collect_xiaohongshu_reviews

            try:
                reviews.extend(
                    collect_xiaohongshu_reviews(
                        book=book,
                        keyword=keyword,
                        pages=max_pages,
                        min_chars=min_chars,
                        limit=limit,
                        fetch_notes=fetch_detail,
                        delay=delay,
                        timeout=timeout,
                        retries=retries,
                    )
                )
            except RuntimeError as exc:
                if strict:
                    raise
                errors.append(str(exc))
            continue
        for page_index in range(max_pages):
            url = build_search_url(platform, book, page_index)
            try:
                html = fetch_url(url, platform=platform)
            except RuntimeError as exc:
                if strict:
                    raise
                errors.append(str(exc))
                break
            reviews.extend(extract_reviews_from_html(html, book, platform, url, min_chars))
            if platform == "xiaohongshu":
                break

    unique = dedupe_reviews(review for review in reviews if review.content)
    for error in errors:
        print(f"[warn] skipped blocked/unavailable page: {error}")
    if errors and not unique:
        print(
            "[warn] no reviews collected from live pages. "
            "Try --url with a specific review page, --input-html with saved pages, "
            "or set platform cookies such as TIEBA_COOKIE/DOUBAN_COOKIE/XHS_COOKIE."
        )
    return unique[:limit]
