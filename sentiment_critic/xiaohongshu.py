from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from random import uniform
from time import sleep
from typing import Any, Iterable
from urllib.parse import quote_plus, urljoin, urlparse
import json
import os
import re

import requests
from bs4 import BeautifulSoup, Tag

from .agent_client import load_env_files
from .collectors import candidate_review_blocks, is_review_like, trim_review
from .models import Review, dedupe_reviews, normalize_space, read_jsonl


XHS_HOST = "https://www.xiaohongshu.com"
NOTE_RE = re.compile(r"/(?:explore|discovery/item)/([A-Za-z0-9]+)")
NOTE_URL_RE = re.compile(
    r"(?:https?:)?//www\.xiaohongshu\.com/(?:explore|discovery/item)/[A-Za-z0-9][^\"'\s<\\]*"
    r"|/(?:explore|discovery/item)/[A-Za-z0-9][^\"'\s<\\]*"
)
STATE_MARKERS = (
    "__INITIAL_STATE__",
    "__INITIAL_SSR_STATE__",
    "__NEXT_DATA__",
    "window.__INITIAL_STATE__",
)
TITLE_KEYS = ("title", "displayTitle", "name")
CONTENT_KEYS = ("desc", "description", "content", "noteContent", "noteDesc", "text")
AUTHOR_KEYS = ("nickname", "nickName", "name", "username", "userName")


class XiaohongshuBookReviewCrawler:
    """Best-effort crawler for Xiaohongshu search pages and note pages."""

    def __init__(
        self,
        cookie: str = "",
        delay: float = 2.0,
        timeout: int = 20,
        retries: int = 2,
    ) -> None:
        load_env_files()
        self.delay = max(delay, 0.0)
        self.timeout = timeout
        self.retries = max(retries, 0)
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": os.getenv(
                    "SENTIMENT_CRITIC_UA",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
                "Referer": XHS_HOST + "/",
            }
        )
        cookie = cookie or os.getenv("XHS_COOKIE", "")
        if cookie:
            self.session.headers["Cookie"] = cookie

    def collect(
        self,
        book: str,
        keyword: str = "",
        pages: int = 1,
        limit: int = 100,
        min_chars: int = 80,
        fetch_notes: bool = True,
    ) -> list[Review]:
        reviews: list[Review] = []
        seen_notes: set[str] = set()
        for page_index in range(max(pages, 1)):
            search_url = build_search_url(book=book, keyword=keyword, page_index=page_index)
            html = self.get_text(search_url)
            if fetch_notes:
                note_urls = parse_note_urls(html, search_url)
                print(f"[xiaohongshu] search page {page_index + 1}: {len(note_urls)} notes")
                for note_url in note_urls:
                    note_id = extract_note_id(note_url)
                    if note_id in seen_notes:
                        continue
                    seen_notes.add(note_id)
                    try:
                        note_reviews = self.collect_note(note_url, book=book, min_chars=min_chars)
                    except RuntimeError as exc:
                        print(f"[warn] Xiaohongshu note skipped: {exc}")
                        continue
                    print(f"[xiaohongshu] note {note_id or note_url}: {len(note_reviews)} reviews")
                    reviews.extend(note_reviews)
                    if len(reviews) >= limit:
                        return dedupe_reviews(reviews)[:limit]
            else:
                page_reviews = parse_search_page(html, book=book, list_url=search_url, min_chars=min_chars)
                print(f"[xiaohongshu] search page {page_index + 1}: {len(page_reviews)} snippet reviews")
                reviews.extend(page_reviews)
            if len(reviews) >= limit:
                break
        return dedupe_reviews(reviews)[:limit]

    def collect_note(self, url: str, book: str, min_chars: int = 80) -> list[Review]:
        html = self.get_text(url)
        return parse_note_page(html, book=book, url=url, min_chars=min_chars)

    def parse_saved_html(
        self,
        paths: Iterable[str],
        book: str,
        min_chars: int = 80,
        strict: bool = False,
    ) -> list[Review]:
        reviews: list[Review] = []
        for html_path in paths:
            path = Path(html_path)
            if not path.exists():
                message = f"Local HTML file not found: {path}"
                if strict:
                    raise RuntimeError(message)
                print(f"[warn] {message}")
                continue
            html = path.read_text(encoding="utf-8", errors="ignore")
            if looks_like_note_page(html, str(path)):
                reviews.extend(parse_note_page(html, book=book, url=str(path), min_chars=min_chars))
            else:
                reviews.extend(parse_search_page(html, book=book, list_url=str(path), min_chars=min_chars))
        return dedupe_reviews(reviews)

    def get_text(self, url: str, referer: str = "") -> str:
        headers = {"Referer": referer or XHS_HOST + "/"}
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            if self.delay:
                sleep(uniform(self.delay * 0.7, self.delay * 1.3))
            try:
                response = self.session.get(url, headers=headers, timeout=self.timeout)
                if response.status_code in {403, 418, 429}:
                    raise RuntimeError(f"Xiaohongshu blocked request with HTTP {response.status_code}: {url}")
                response.raise_for_status()
                response.encoding = response.apparent_encoding or response.encoding
                detect_blocked_text(response.text, url)
                return response.text
            except (requests.RequestException, RuntimeError) as exc:
                last_error = exc
                if attempt < self.retries:
                    sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"Failed to fetch {url}: {last_error}") from last_error


def build_search_url(book: str, keyword: str = "", page_index: int = 0) -> str:
    query = keyword or f"{book} 书评 文笔 逻辑 更新"
    url = f"{XHS_HOST}/search_result?keyword={quote_plus(query)}&source=web_search_result_notes"
    if page_index:
        url += f"&page={page_index + 1}"
    return url


def parse_note_urls(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    detect_blocked_page(soup, base_url)
    urls: list[str] = []
    seen: set[str] = set()
    for anchor in soup.select('a[href*="/explore/"], a[href*="/discovery/item/"]'):
        url = normalize_xhs_url(anchor.get("href", ""), base_url)
        note_id = extract_note_id(url)
        if not note_id or note_id in seen:
            continue
        seen.add(note_id)
        urls.append(url)

    escaped_html = html.replace("\\u002F", "/").replace("\\/", "/")
    for match in NOTE_URL_RE.finditer(escaped_html):
        url = normalize_xhs_url(match.group(0), base_url)
        note_id = extract_note_id(url)
        if not note_id or note_id in seen:
            continue
        seen.add(note_id)
        urls.append(url)
    return urls


def parse_search_page(
    html: str,
    book: str,
    list_url: str,
    min_chars: int = 80,
) -> list[Review]:
    soup = BeautifulSoup(html, "html.parser")
    detect_blocked_page(soup, list_url)
    reviews: list[Review] = []
    seen_notes: set[str] = set()
    for anchor in soup.select('a[href*="/explore/"], a[href*="/discovery/item/"]'):
        note_url = normalize_xhs_url(anchor.get("href", ""), list_url)
        note_id = extract_note_id(note_url)
        if not note_id or note_id in seen_notes:
            continue
        seen_notes.add(note_id)
        container = find_container(anchor, ("note-item", "feeds-page", "search-note", "card"))
        title = clean_text(anchor.get_text(" ", strip=True))
        content = clean_note_content(container.get_text(" ", strip=True) if container else title)
        if not is_review_like(content, book, min_chars):
            continue
        reviews.append(
            Review(
                book=book,
                platform="xiaohongshu",
                title=title or make_title(content),
                source_url=note_url,
                content=trim_review(content),
                extra={"xhs_note_id": note_id, "xhs_list_url": list_url},
            )
        )
    return dedupe_reviews(reviews)


def parse_note_page(
    html: str,
    book: str,
    url: str,
    min_chars: int = 80,
) -> list[Review]:
    soup = BeautifulSoup(html, "html.parser")
    detect_blocked_page(soup, url)
    note_id = extract_note_id(url) or extract_note_id_from_html(html)
    meta = parse_meta(soup)
    payload = select_best_note_payload(iter_state_payloads(soup), note_id=note_id, book=book)
    title = clean_text(first_text(payload, TITLE_KEYS) or meta.get("title") or "")
    content = clean_note_content(first_text(payload, CONTENT_KEYS) or meta.get("description") or "")
    author = extract_author(payload)
    created_at = format_timestamp(first_value(payload, ("time", "timestamp", "createTime", "create_time", "lastUpdateTime")))
    extra = extract_note_extra(payload)

    if is_review_like(content, book, min_chars):
        return [
            Review(
                book=book,
                platform="xiaohongshu",
                title=title or make_title(content),
                author=author,
                created_at=created_at,
                source_url=url,
                content=trim_review(content, max_chars=3200),
                extra={key: value for key, value in {"xhs_note_id": note_id, **extra}.items() if has_value(value)},
            )
        ]

    blocks = extract_visible_blocks(soup)
    candidates = candidate_review_blocks(blocks, content or meta.get("description", ""), book, min_chars)
    reviews: list[Review] = []
    for index, candidate in enumerate(candidates):
        reviews.append(
            Review(
                book=book,
                platform="xiaohongshu",
                title=(title or make_title(candidate)) + (f" #{index + 1}" if index else ""),
                author=author,
                created_at=created_at,
                source_url=url,
                content=trim_review(clean_note_content(candidate), max_chars=3200),
                extra={key: value for key, value in {"xhs_note_id": note_id, **extra}.items() if has_value(value)},
            )
        )
    return dedupe_reviews(reviews)


def parse_meta(soup: BeautifulSoup) -> dict[str, str]:
    title = ""
    description = ""
    for selector in (
        'meta[property="og:title"]',
        'meta[name="og:title"]',
        'meta[name="twitter:title"]',
    ):
        node = soup.select_one(selector)
        if isinstance(node, Tag) and node.get("content"):
            title = clean_xhs_title(str(node.get("content")))
            break
    if not title:
        title_node = soup.select_one("title")
        title = clean_xhs_title(title_node.get_text(" ", strip=True) if title_node else "")

    for selector in (
        'meta[property="og:description"]',
        'meta[name="description"]',
        'meta[name="twitter:description"]',
    ):
        node = soup.select_one(selector)
        if isinstance(node, Tag) and node.get("content"):
            description = clean_note_content(str(node.get("content")))
            break
    return {"title": title, "description": description}


def iter_state_payloads(soup: BeautifulSoup) -> Iterable[Any]:
    for script in soup.find_all("script"):
        text = script.string or script.get_text("", strip=False)
        if not text:
            continue
        stripped = text.strip()
        if stripped.startswith("{") or stripped.startswith("["):
            payload = try_json_loads(stripped)
            if payload is not None:
                yield payload
        for marker in STATE_MARKERS:
            marker_index = text.find(marker)
            if marker_index < 0:
                continue
            raw_json = extract_balanced_json(text, marker_index)
            if not raw_json:
                continue
            payload = try_json_loads(raw_json)
            if payload is not None:
                yield payload


def select_best_note_payload(payloads: Iterable[Any], note_id: str = "", book: str = "") -> dict[str, Any]:
    best: dict[str, Any] = {}
    best_score = 0
    for payload in payloads:
        for candidate in walk_dicts(payload):
            score = score_note_candidate(candidate, note_id=note_id, book=book)
            if score > best_score:
                best = candidate
                best_score = score
    return best


def score_note_candidate(candidate: dict[str, Any], note_id: str = "", book: str = "") -> int:
    content = first_text(candidate, CONTENT_KEYS)
    title = first_text(candidate, TITLE_KEYS)
    if not content and not title:
        return 0
    text = f"{title} {content}"
    score = min(len(content), 500)
    if title:
        score += 20
    if book and book in text:
        score += 80
    if note_id and note_id in json.dumps(candidate, ensure_ascii=False):
        score += 120
    if any(key in candidate for key in ("user", "userInfo", "author", "interactInfo")):
        score += 20
    if "小红书" in text and len(content) < 80:
        score -= 80
    return score


def walk_dicts(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_dicts(child)


def try_json_loads(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def extract_balanced_json(text: str, start_index: int = 0) -> str:
    start = text.find("{", start_index)
    if start < 0:
        start = text.find("[", start_index)
    if start < 0:
        return ""
    opener = text[start]
    closer = "}" if opener == "{" else "]"
    depth = 0
    in_string = False
    quote = ""
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == quote:
                in_string = False
            continue
        if char in {'"', "'"}:
            in_string = True
            quote = char
            continue
        if char == opener:
            depth += 1
        elif char == closer:
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return ""


def first_text(data: dict[str, Any], keys: tuple[str, ...]) -> str:
    value = first_value(data, keys)
    if isinstance(value, str):
        return clean_note_content(value)
    if value is None:
        return ""
    return clean_note_content(str(value))


def first_value(data: dict[str, Any], keys: tuple[str, ...]) -> Any:
    if not data:
        return None
    for key in keys:
        value = data.get(key)
        if has_value(value):
            return value
    for value in data.values():
        if isinstance(value, dict):
            nested = first_value(value, keys)
            if has_value(nested):
                return nested
    return None


def has_value(value: Any) -> bool:
    return value is not None and value != "" and value != [] and value != {}


def extract_author(data: dict[str, Any]) -> str:
    for key in ("user", "userInfo", "author", "authorInfo"):
        user = data.get(key) if isinstance(data, dict) else None
        if isinstance(user, dict):
            author = first_text(user, AUTHOR_KEYS)
            if author:
                return author
    return first_text(data, AUTHOR_KEYS)


def extract_note_extra(data: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in {
            "xhs_liked_count": first_value(data, ("likedCount", "likes", "likeCount")),
            "xhs_collected_count": first_value(data, ("collectedCount", "collectCount")),
            "xhs_comment_count": first_value(data, ("commentCount", "comments")),
        }.items()
        if has_value(value)
    }


def extract_visible_blocks(soup: BeautifulSoup) -> list[str]:
    for node in soup.select("script, style, noscript, svg, canvas, template"):
        node.decompose()
    blocks: list[str] = []
    for node in soup.select(".note-content, .desc, .content, article, section, p, div"):
        text = clean_note_content(node.get_text(" ", strip=True))
        if text and len(text) >= 18:
            blocks.append(text)
    return blocks


def normalize_xhs_url(href: str, base_url: str) -> str:
    href = (href or "").strip()
    if not href:
        return ""
    if href.startswith("//"):
        href = "https:" + href
    return urljoin(base_url, href)


def extract_note_id(url: str) -> str:
    match = NOTE_RE.search(url or "")
    return match.group(1) if match else ""


def extract_note_id_from_html(html: str) -> str:
    match = NOTE_RE.search(html.replace("\\u002F", "/").replace("\\/", "/"))
    return match.group(1) if match else ""


def clean_xhs_title(text: str) -> str:
    text = clean_text(text)
    text = re.sub(r"[-_]\s*小红书\s*$", "", text)
    text = re.sub(r"\s*-\s*小红书.*$", "", text)
    return clean_text(text)


def clean_note_content(text: str) -> str:
    text = clean_text(text)
    text = text.replace("\\n", " ").replace("\n", " ")
    text = re.sub(r"\s*展开\s*$", "", text)
    text = re.sub(r"\s*收起\s*$", "", text)
    text = re.sub(r"\s*#\s*", " #", text)
    text = re.sub(r"\s*小红书号[:：]\s*\S+", "", text)
    text = re.sub(r"\s*点击查看全文\s*", " ", text)
    return normalize_space(text)


def clean_text(text: str) -> str:
    return normalize_space((text or "").replace("\xa0", " "))


def make_title(content: str) -> str:
    text = normalize_space(content)
    return text[:32] + ("..." if len(text) > 32 else "")


def find_container(node: Tag, class_names: tuple[str, ...]) -> Tag | None:
    current = node
    for _ in range(6):
        parent = current.parent
        if not isinstance(parent, Tag):
            return None
        classes = set(parent.get("class", []))
        if any(class_name in classes for class_name in class_names):
            return parent
        current = parent
    return None


def format_timestamp(value: Any) -> str:
    if not has_value(value):
        return ""
    if isinstance(value, str) and not value.isdigit():
        return clean_text(value)
    try:
        timestamp = int(value)
    except (TypeError, ValueError):
        return clean_text(str(value))
    if timestamp > 10_000_000_000:
        timestamp = timestamp // 1000
    try:
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).astimezone().isoformat(timespec="seconds")
    except (OSError, ValueError):
        return clean_text(str(value))


def looks_like_note_page(html: str, source: str = "") -> bool:
    if extract_note_id(source):
        return True
    if extract_note_id_from_html(html):
        return True
    soup = BeautifulSoup(html, "html.parser")
    return bool(soup.select_one('meta[property="og:title"], .note-content, .note-detail'))


def looks_like_placeholder_url(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    if "xhslink.com" in host:
        return False
    if "/explore/" not in url and "/discovery/item/" not in url:
        return False
    note_id = extract_note_id(url)
    return note_id.lower() in {"", "xxxx", "xxx", "your_note_id", "note_id"}


def detect_blocked_page(soup: BeautifulSoup, url: str) -> None:
    text = clean_text(soup.get_text(" ", strip=True))[:1200]
    detect_blocked_text(text, url)


def detect_blocked_text(text: str, url: str) -> None:
    markers = (
        "滑块验证",
        "验证码",
        "安全验证",
        "访问太频繁",
        "captcha",
        "verify",
    )
    lower = text.lower()
    if any(marker in text for marker in markers) or any(marker in lower for marker in ("captcha", "verify")):
        raise RuntimeError(f"Xiaohongshu returned a login/anti-bot page for {url}")


def collect_xiaohongshu_reviews(
    book: str,
    keyword: str = "",
    pages: int = 1,
    limit: int = 100,
    min_chars: int = 80,
    fetch_notes: bool = True,
    urls: list[str] | None = None,
    input_html: list[str] | None = None,
    input_jsonl: str = "",
    cookie: str = "",
    delay: float = 2.0,
    timeout: int = 20,
    retries: int = 2,
    strict: bool = False,
) -> list[Review]:
    crawler = XiaohongshuBookReviewCrawler(cookie=cookie, delay=delay, timeout=timeout, retries=retries)
    reviews: list[Review] = []
    if input_jsonl:
        reviews.extend(read_jsonl(input_jsonl, fallback_book=book))
    if input_html:
        reviews.extend(crawler.parse_saved_html(input_html, book=book, min_chars=min_chars, strict=strict))
    for url in urls or []:
        try:
            if looks_like_placeholder_url(url):
                raise RuntimeError(f"{url} looks like a placeholder, not a real Xiaohongshu note URL")
            if extract_note_id(url) or "xhslink.com" in urlparse(url).netloc.lower():
                reviews.extend(crawler.collect_note(url, book=book, min_chars=min_chars))
            else:
                html = crawler.get_text(url)
                if fetch_notes:
                    for note_url in parse_note_urls(html, url):
                        reviews.extend(crawler.collect_note(note_url, book=book, min_chars=min_chars))
                else:
                    reviews.extend(parse_search_page(html, book=book, list_url=url, min_chars=min_chars))
        except RuntimeError as exc:
            if strict:
                raise
            print(f"[warn] Xiaohongshu page skipped: {exc}")
    if not urls and not input_html and pages:
        try:
            reviews.extend(
                crawler.collect(
                    book=book,
                    keyword=keyword,
                    pages=pages,
                    limit=limit,
                    min_chars=min_chars,
                    fetch_notes=fetch_notes,
                )
            )
        except RuntimeError as exc:
            if strict:
                raise
            print(f"[warn] Xiaohongshu search skipped: {exc}")
    return dedupe_reviews(review for review in reviews if review.content)[:limit]


collect_xhs_reviews = collect_xiaohongshu_reviews
