from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from random import uniform
from time import sleep
from typing import Any, Iterable
from urllib.parse import parse_qsl, quote_plus, urlencode, urljoin, urlparse, urlunparse
import json
import os
import re

import requests
from bs4 import BeautifulSoup, Tag

from .agent_client import load_env_files
from .collectors import is_review_like, trim_review
from .models import Review, dedupe_reviews, normalize_space, read_jsonl


TIEBA_HOST = "https://tieba.baidu.com"
THREAD_RE = re.compile(r"/p/(\d+)|[?&]kz=(\d+)")
THREAD_PATH_RE = re.compile(r"/p/([^/?#]+)")
POST_ID_RE = re.compile(r"pid(\d+)|post_content_(\d+)")


class TiebaBookReviewCrawler:
    """Crawler for Baidu Tieba search pages and thread floors."""

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
                "Referer": TIEBA_HOST + "/",
            }
        )
        cookie = cookie or os.getenv("TIEBA_COOKIE", "")
        if cookie:
            self.session.headers["Cookie"] = cookie

    def collect(
        self,
        book: str,
        keyword: str = "",
        pages: int = 1,
        limit: int = 100,
        min_chars: int = 80,
        fetch_threads: bool = True,
        thread_pages: int = 1,
        backend: str = "auto",
    ) -> list[Review]:
        if backend in {"auto", "aiotieba"}:
            try:
                reviews = collect_with_aiotieba(
                    book=book,
                    keyword=keyword,
                    pages=pages,
                    limit=limit,
                    min_chars=min_chars,
                    fetch_threads=fetch_threads,
                    thread_pages=thread_pages,
                    cookie=self.session.headers.get("Cookie", ""),
                )
            except RuntimeError as exc:
                if backend == "aiotieba":
                    raise
                print(f"[warn] aiotieba backend skipped: {exc}")
            else:
                if reviews or backend == "aiotieba":
                    return reviews[:limit]

        reviews: list[Review] = []
        seen_threads: set[str] = set()
        for page_index in range(max(pages, 1)):
            html = ""
            search_url = ""
            errors: list[str] = []
            for candidate_url in build_search_urls(book=book, keyword=keyword, page_index=page_index):
                try:
                    html = self.get_text(candidate_url)
                    search_url = candidate_url
                    break
                except RuntimeError as exc:
                    errors.append(str(exc))
                    print(f"[warn] Tieba search candidate skipped: {exc}")
            if not html:
                detail = " | ".join(errors[-2:])
                raise RuntimeError(f"All Tieba search strategies failed for page {page_index + 1}: {detail}")
            if fetch_threads:
                thread_urls = parse_thread_urls(html, search_url)
                print(f"[tieba] search page {page_index + 1}: {len(thread_urls)} threads")
                for thread_url in thread_urls:
                    thread_id = extract_thread_id(thread_url)
                    if thread_id in seen_threads:
                        continue
                    seen_threads.add(thread_id)
                    try:
                        page_reviews = self.collect_thread(
                            thread_url,
                            book=book,
                            min_chars=min_chars,
                            pages=thread_pages,
                        )
                    except RuntimeError as exc:
                        print(f"[warn] Tieba thread skipped: {exc}")
                        continue
                    print(f"[tieba] thread {thread_id or thread_url}: {len(page_reviews)} reviews")
                    reviews.extend(page_reviews)
                    if len(reviews) >= limit:
                        return dedupe_reviews(reviews)[:limit]
            else:
                page_reviews = parse_search_page(html, book=book, list_url=search_url, min_chars=min_chars)
                print(f"[tieba] search page {page_index + 1}: {len(page_reviews)} snippet reviews")
                reviews.extend(page_reviews)
            if len(reviews) >= limit:
                break
        return dedupe_reviews(reviews)[:limit]

    def collect_thread(
        self,
        url: str,
        book: str,
        min_chars: int = 80,
        pages: int = 1,
    ) -> list[Review]:
        reviews: list[Review] = []
        for page_no in range(1, max(pages, 1) + 1):
            page_url = build_thread_page_url(url, page_no)
            html = self.get_text(page_url, referer=url)
            page_reviews = parse_thread_page(html, book=book, url=page_url, min_chars=min_chars)
            reviews.extend(page_reviews)
            if not page_reviews and page_no > 1:
                break
        return dedupe_reviews(reviews)

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
            if looks_like_thread_page(html, str(path)):
                reviews.extend(parse_thread_page(html, book=book, url=str(path), min_chars=min_chars))
            else:
                reviews.extend(parse_search_page(html, book=book, list_url=str(path), min_chars=min_chars))
        return dedupe_reviews(reviews)

    def get_text(self, url: str, referer: str = "") -> str:
        headers = {"Referer": referer or TIEBA_HOST + "/"}
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            if self.delay:
                sleep(uniform(self.delay * 0.7, self.delay * 1.3))
            try:
                response = self.session.get(url, headers=headers, timeout=self.timeout)
                if response.status_code in {403, 418, 429}:
                    raise RuntimeError(f"Tieba blocked request with HTTP {response.status_code}: {url}")
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
    return f"{TIEBA_HOST}/f/search/res?ie=utf-8&qw={quote_plus(query)}&rn=10&pn={max(page_index, 0)}"


def build_forum_url(book: str, page_index: int = 0) -> str:
    return f"{TIEBA_HOST}/f?kw={quote_plus(book)}&ie=utf-8&pn={max(page_index, 0) * 50}"


def build_mobile_forum_url(book: str, page_index: int = 0) -> str:
    return f"{TIEBA_HOST}/mo/q/m?kw={quote_plus(book)}&pn={max(page_index, 0) * 20}"


def build_search_urls(book: str, keyword: str = "", page_index: int = 0) -> list[str]:
    urls = [
        build_search_url(book=book, keyword=keyword, page_index=page_index),
        build_forum_url(book=book, page_index=page_index),
        build_mobile_forum_url(book=book, page_index=page_index),
    ]
    seen: set[str] = set()
    unique: list[str] = []
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        unique.append(url)
    return unique


def collect_with_aiotieba(
    book: str,
    keyword: str = "",
    pages: int = 1,
    limit: int = 100,
    min_chars: int = 80,
    fetch_threads: bool = True,
    thread_pages: int = 1,
    cookie: str = "",
) -> list[Review]:
    try:
        import asyncio
        import aiotieba as tb
    except ImportError as exc:
        raise RuntimeError("aiotieba is not installed; run `pip install aiotieba` to enable this backend") from exc

    async def run() -> list[Review]:
        auth = parse_tieba_cookie(cookie)
        client_kwargs = {key: value for key, value in auth.items() if value}
        async with tb.Client(**client_kwargs) as client:
            reviews: list[Review] = []
            seen_threads: set[str] = set()
            forum_name = book
            for page_no in range(1, max(pages, 1) + 1):
                try:
                    threads = await client.get_threads(forum_name, pn=page_no, rn=30)
                except Exception as exc:
                    raise RuntimeError(f"aiotieba get_threads failed for {forum_name}: {exc}") from exc
                thread_items = list(getattr(threads, "objs", threads) or [])
                print(f"[tieba:aiotieba] forum page {page_no}: {len(thread_items)} threads")
                for thread in thread_items:
                    thread_id = str(getattr(thread, "tid", "") or "")
                    if not thread_id or thread_id in seen_threads:
                        continue
                    seen_threads.add(thread_id)
                    title = clean_text(str(getattr(thread, "title", "") or getattr(thread, "text", "") or ""))
                    snippet = clean_post_content(str(getattr(thread, "text", "") or ""))
                    thread_url = f"{TIEBA_HOST}/p/{thread_id}"
                    if not fetch_threads:
                        if is_review_like(f"{title} {snippet}", book, min_chars):
                            reviews.append(
                                Review(
                                    book=book,
                                    platform="tieba",
                                    title=title or make_title(snippet),
                                    author=extract_user_name(getattr(thread, "user", None)),
                                    created_at=format_timestamp(getattr(thread, "create_time", "")),
                                    source_url=thread_url,
                                    content=trim_review(f"{title} {snippet}".strip(), max_chars=2400),
                                    extra={"tieba_thread_id": thread_id, "tieba_backend": "aiotieba"},
                                )
                            )
                    else:
                        reviews.extend(
                            await collect_thread_with_aiotieba(
                                client,
                                thread_id=thread_id,
                                book=book,
                                title=title,
                                pages=thread_pages,
                                min_chars=min_chars,
                            )
                        )
                    if len(reviews) >= limit:
                        return dedupe_reviews(reviews)[:limit]
            return dedupe_reviews(reviews)[:limit]

    try:
        return asyncio.run(run())
    except RuntimeError as exc:
        # asyncio.run cannot be used from an existing event loop. That should not
        # happen in the command-line scripts, but this keeps library use explicit.
        if "asyncio.run() cannot be called from a running event loop" in str(exc):
            raise RuntimeError("aiotieba backend cannot run inside an existing asyncio event loop") from exc
        raise


def collect_thread_id_with_aiotieba(
    thread_id: str,
    book: str,
    min_chars: int = 80,
    pages: int = 1,
    cookie: str = "",
) -> list[Review]:
    try:
        import asyncio
        import aiotieba as tb
    except ImportError as exc:
        raise RuntimeError("aiotieba is not installed; run `pip install aiotieba` to enable this backend") from exc

    async def run() -> list[Review]:
        auth = parse_tieba_cookie(cookie)
        client_kwargs = {key: value for key, value in auth.items() if value}
        async with tb.Client(**client_kwargs) as client:
            return await collect_thread_with_aiotieba(
                client,
                thread_id=thread_id,
                book=book,
                pages=pages,
                min_chars=min_chars,
            )

    return asyncio.run(run())


async def collect_thread_with_aiotieba(
    client: Any,
    thread_id: str,
    book: str,
    title: str = "",
    pages: int = 1,
    min_chars: int = 80,
) -> list[Review]:
    reviews: list[Review] = []
    for page_no in range(1, max(pages, 1) + 1):
        try:
            posts = await client.get_posts(int(thread_id), pn=page_no, rn=30)
        except Exception as exc:
            print(f"[warn] aiotieba thread {thread_id} page {page_no} skipped: {exc}")
            continue
        post_items = list(getattr(posts, "objs", posts) or [])
        for index, post in enumerate(post_items, 1):
            content = clean_post_content(str(getattr(post, "text", "") or ""))
            if not is_review_like(content, book, min_chars):
                continue
            post_id = str(getattr(post, "pid", "") or "")
            floor = getattr(post, "floor", "") or index
            reviews.append(
                Review(
                    book=book,
                    platform="tieba",
                    title=title or make_title(content),
                    author=extract_user_name(getattr(post, "user", None)),
                    created_at=format_timestamp(getattr(post, "create_time", "")),
                    source_url=build_post_url(f"{TIEBA_HOST}/p/{thread_id}", post_id, floor),
                    content=trim_review(content, max_chars=3200),
                    extra={
                        key: value
                        for key, value in {
                            "tieba_thread_id": thread_id,
                            "tieba_post_id": post_id,
                            "tieba_floor": floor,
                            "tieba_backend": "aiotieba",
                        }.items()
                        if value not in {"", None}
                    },
                )
            )
    return dedupe_reviews(reviews)


def build_thread_page_url(url: str, page_no: int) -> str:
    parsed = urlparse(normalize_tieba_url(url, TIEBA_HOST + "/"))
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if page_no > 1:
        query["pn"] = str(page_no)
    elif "pn" in query:
        query.pop("pn", None)
    return urlunparse(parsed._replace(query=urlencode(query)))


def parse_thread_urls(html: str, list_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    detect_blocked_page(soup, list_url)
    urls: list[str] = []
    seen: set[str] = set()
    for anchor in soup.select('a[href*="/p/"], a[href*="kz="]'):
        url = normalize_thread_url(anchor.get("href", ""), list_url)
        thread_id = extract_thread_id(url)
        if not thread_id or thread_id in seen:
            continue
        seen.add(thread_id)
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
    seen_threads: set[str] = set()
    for anchor in soup.select('a[href*="/p/"], a[href*="kz="]'):
        thread_url = normalize_thread_url(anchor.get("href", ""), list_url)
        thread_id = extract_thread_id(thread_url)
        if not thread_id or thread_id in seen_threads:
            continue
        seen_threads.add(thread_id)
        container = find_container(anchor, ("s_post", "result", "thread", "search_result"))
        title = clean_text(anchor.get_text(" ", strip=True))
        content = clean_text(container.get_text(" ", strip=True) if container else title)
        content = strip_search_boilerplate(content, title)
        if not is_review_like(content, book, min_chars):
            continue
        reviews.append(
            Review(
                book=book,
                platform="tieba",
                title=title or make_title(content),
                source_url=thread_url,
                content=trim_review(content),
                extra={"tieba_thread_id": thread_id, "tieba_list_url": list_url},
            )
        )
    return dedupe_reviews(reviews)


def parse_thread_page(
    html: str,
    book: str,
    url: str,
    min_chars: int = 80,
) -> list[Review]:
    soup = BeautifulSoup(html, "html.parser")
    detect_blocked_page(soup, url)
    title = parse_thread_title(soup)
    thread_id = extract_thread_id(url)
    posts = parse_posts(soup, url)
    reviews: list[Review] = []
    for post in posts:
        content = post["content"]
        if not is_review_like(content, book, min_chars):
            continue
        post_id = str(post.get("post_id") or "")
        floor = post.get("floor")
        reviews.append(
            Review(
                book=book,
                platform="tieba",
                title=title or make_title(content),
                author=str(post.get("author") or ""),
                created_at=str(post.get("created_at") or ""),
                source_url=build_post_url(url, post_id, floor),
                content=trim_review(content, max_chars=3200),
                extra={
                    key: value
                    for key, value in {
                        "tieba_thread_id": thread_id,
                        "tieba_post_id": post_id,
                        "tieba_floor": floor,
                    }.items()
                    if value not in {"", None}
                },
            )
        )

    if not reviews:
        combined = normalize_space(" ".join(post["content"] for post in posts[:6]))
        if is_review_like(combined, book, min_chars):
            reviews.append(
                Review(
                    book=book,
                    platform="tieba",
                    title=title or make_title(combined),
                    source_url=url,
                    content=trim_review(combined, max_chars=4000),
                    extra={"tieba_thread_id": thread_id, "tieba_combined_floors": min(len(posts), 6)},
                )
            )
    return dedupe_reviews(reviews)


def parse_posts(soup: BeautifulSoup, url: str) -> list[dict[str, Any]]:
    posts: list[dict[str, Any]] = []
    containers = soup.select("div.l_post, div[data-field]")
    if not containers:
        containers = soup.select(".d_post_content, .j_d_post_content")

    for index, node in enumerate(containers, 1):
        if not isinstance(node, Tag):
            continue
        content_node = node.select_one(".d_post_content, .j_d_post_content")
        if not content_node and "d_post_content" in node.get("class", []):
            content_node = node
        if not content_node:
            continue
        content = clean_post_content(content_node.get_text("\n", strip=True))
        if not content:
            continue
        data = parse_data_field(node)
        content_data = data.get("content", {}) if isinstance(data.get("content"), dict) else {}
        author_data = data.get("author", {}) if isinstance(data.get("author"), dict) else {}
        post_id = str(content_data.get("post_id") or node.get("data-pid") or extract_post_id(str(content_node.get("id", ""))))
        floor = content_data.get("post_no") or index
        author = clean_text(
            str(
                author_data.get("user_name")
                or author_data.get("name")
                or select_text(node, ".p_author_name, .d_name a, .userinfo_username")
            )
        )
        created_at = clean_text(str(content_data.get("date") or select_tail_date(node)))
        posts.append(
            {
                "content": content,
                "post_id": post_id,
                "floor": floor,
                "author": author,
                "created_at": created_at,
                "source_url": url,
            }
        )
    return posts


def parse_data_field(node: Tag) -> dict[str, Any]:
    raw = node.get("data-field", "")
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def parse_thread_title(soup: BeautifulSoup) -> str:
    node = soup.select_one(".core_title_txt, h3[title], h1")
    if isinstance(node, Tag):
        title = clean_text(node.get("title") or node.get_text(" ", strip=True))
        if title:
            return title
    title_node = soup.select_one("title")
    title = clean_text(title_node.get_text(" ", strip=True) if title_node else "")
    title = re.sub(r"[_-].*?百度贴吧.*$", "", title)
    return title


def select_text(node: Tag, selector: str) -> str:
    target = node.select_one(selector)
    return clean_text(target.get_text(" ", strip=True) if target else "")


def select_tail_date(node: Tag) -> str:
    candidates = [
        clean_text(target.get_text(" ", strip=True))
        for target in node.select(".tail-info, .post-tail-wrap span, .post-tail-wrap a")
    ]
    for text in candidates:
        if re.search(r"\d{4}-\d{1,2}-\d{1,2}|\d{1,2}:\d{2}", text):
            return text
    return ""


def normalize_tieba_url(href: str, base_url: str) -> str:
    href = (href or "").strip()
    if not href:
        return ""
    return urljoin(base_url, href)


def normalize_thread_url(href: str, base_url: str) -> str:
    url = normalize_tieba_url(href, base_url)
    thread_id = extract_thread_id(url)
    if thread_id:
        return f"{TIEBA_HOST}/p/{thread_id}"
    return url


def build_post_url(thread_url: str, post_id: str = "", floor: Any = "") -> str:
    if post_id:
        parsed = urlparse(build_thread_page_url(thread_url, 1))
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query["pid"] = post_id
        return urlunparse(parsed._replace(query=urlencode(query), fragment=f"pid{post_id}"))
    if floor:
        return f"{thread_url}#floor{floor}"
    return thread_url


def parse_tieba_cookie(cookie: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for part in (cookie or "").split(";"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key in {"BDUSS", "STOKEN", "BAIDUID"}:
            parsed[key] = value
    return parsed


def extract_user_name(user: Any) -> str:
    if user is None:
        return ""
    for attr in ("name", "user_name", "name_show", "portrait"):
        value = getattr(user, attr, "")
        if value:
            return clean_text(str(value))
    if isinstance(user, dict):
        for key in ("name", "user_name", "name_show", "portrait"):
            value = user.get(key)
            if value:
                return clean_text(str(value))
    return ""


def format_timestamp(value: Any) -> str:
    if value is None or value == "":
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


def extract_thread_id(url: str) -> str:
    match = THREAD_RE.search(url or "")
    if not match:
        return ""
    return next(group for group in match.groups() if group)


def invalid_thread_url_reason(url: str) -> str:
    match = THREAD_PATH_RE.search(url or "")
    if not match:
        return ""
    raw_id = match.group(1)
    if raw_id.isdigit():
        return ""
    if raw_id in {"真实帖子ID", "帖子ID", "thread_id", "xxxx", "xxx"}:
        return f"{url} still contains a placeholder; replace it with the numeric id after /p/."
    return f"{url} is not a valid Tieba thread URL; the id after /p/ must be digits."


def extract_post_id(value: str) -> str:
    match = POST_ID_RE.search(value or "")
    if not match:
        return ""
    return next(group for group in match.groups() if group)


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


def clean_post_content(text: str) -> str:
    text = clean_text(text)
    text = re.sub(r"\s*(来自|发自).{0,20}(客户端|贴吧)\s*", " ", text)
    text = re.sub(r"\s*回复\s*$", "", text)
    return normalize_space(text)


def strip_search_boilerplate(text: str, title: str) -> str:
    text = clean_text(text)
    if title and text.startswith(title):
        text = text[len(title) :]
    text = re.sub(r"百度贴吧\s*$", "", text)
    return normalize_space(text)


def clean_text(text: str) -> str:
    return normalize_space((text or "").replace("\xa0", " "))


def make_title(content: str) -> str:
    text = normalize_space(content)
    return text[:32] + ("..." if len(text) > 32 else "")


def looks_like_thread_page(html: str, source: str = "") -> bool:
    if extract_thread_id(source):
        return True
    soup = BeautifulSoup(html, "html.parser")
    return bool(soup.select_one(".d_post_content, .j_d_post_content, div.l_post"))


def detect_blocked_page(soup: BeautifulSoup, url: str) -> None:
    text = clean_text(soup.get_text(" ", strip=True))[:1200]
    detect_blocked_text(text, url)


def detect_blocked_text(text: str, url: str) -> None:
    markers = (
        "百度安全验证",
        "请输入验证码",
        "安全验证",
        "访问过于频繁",
        "网络不给力",
        "captcha",
        "verify",
    )
    lower = text.lower()
    if any(marker in text for marker in markers) or any(marker in lower for marker in ("captcha", "verify")):
        raise RuntimeError(f"Tieba returned an anti-bot page for {url}")


def collect_tieba_reviews(
    book: str,
    keyword: str = "",
    pages: int = 1,
    limit: int = 100,
    min_chars: int = 80,
    fetch_threads: bool = True,
    thread_pages: int = 1,
    backend: str = "auto",
    urls: list[str] | None = None,
    input_html: list[str] | None = None,
    input_jsonl: str = "",
    cookie: str = "",
    delay: float = 2.0,
    timeout: int = 20,
    retries: int = 2,
    strict: bool = False,
) -> list[Review]:
    crawler = TiebaBookReviewCrawler(cookie=cookie, delay=delay, timeout=timeout, retries=retries)
    reviews: list[Review] = []
    if input_jsonl:
        reviews.extend(read_jsonl(input_jsonl, fallback_book=book))
    if input_html:
        reviews.extend(crawler.parse_saved_html(input_html, book=book, min_chars=min_chars, strict=strict))
    for url in urls or []:
        try:
            invalid_reason = invalid_thread_url_reason(url)
            if invalid_reason:
                raise RuntimeError(invalid_reason)
            thread_id = extract_thread_id(url)
            if thread_id:
                if backend in {"auto", "aiotieba"}:
                    try:
                        api_reviews = collect_thread_id_with_aiotieba(
                            thread_id,
                            book=book,
                            min_chars=min_chars,
                            pages=thread_pages,
                            cookie=crawler.session.headers.get("Cookie", ""),
                        )
                    except RuntimeError as exc:
                        if backend == "aiotieba":
                            raise
                        print(f"[warn] aiotieba thread backend skipped: {exc}")
                    else:
                        reviews.extend(api_reviews)
                        if api_reviews or backend == "aiotieba":
                            continue
                reviews.extend(crawler.collect_thread(url, book=book, min_chars=min_chars, pages=thread_pages))
            else:
                html = crawler.get_text(url)
                if fetch_threads:
                    for thread_url in parse_thread_urls(html, url):
                        reviews.extend(
                            crawler.collect_thread(thread_url, book=book, min_chars=min_chars, pages=thread_pages)
                        )
                else:
                    reviews.extend(parse_search_page(html, book=book, list_url=url, min_chars=min_chars))
        except RuntimeError as exc:
            if strict:
                raise
            print(f"[warn] Tieba page skipped: {exc}")
    if not urls and not input_html and pages:
        try:
            reviews.extend(
                crawler.collect(
                    book=book,
                    keyword=keyword,
                    pages=pages,
                    limit=limit,
                    min_chars=min_chars,
                    fetch_threads=fetch_threads,
                    thread_pages=thread_pages,
                    backend=backend,
                )
            )
        except RuntimeError as exc:
            if strict:
                raise
            print(f"[warn] Tieba search skipped: {exc}")
    return dedupe_reviews(review for review in reviews if review.content)[:limit]
