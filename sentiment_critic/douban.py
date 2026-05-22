from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from random import uniform
from time import sleep
from typing import Iterable
from urllib.parse import quote_plus, urljoin
import os
import re

import requests
from bs4 import BeautifulSoup, Tag

from .collectors import is_review_like
from .models import Review, dedupe_reviews, normalize_space, read_jsonl


DOUBAN_HOST = "https://book.douban.com"
SUBJECT_RE = re.compile(r"/subject/(\d+)/?")
REVIEW_RE = re.compile(r"/review/(\d+)/?")
STAR_RE = re.compile(r"allstar(\d+)")


@dataclass
class DoubanSubject:
    subject_id: str
    title: str
    url: str
    summary: str = ""


class DoubanBookReviewCrawler:
    """Douban book review crawler inspired by common requests + bs4 scripts.

    The implementation keeps the moving parts explicit: a persistent session,
    optional cookie, polite delay, retry, list-page parsing, and detail-page
    parsing. It intentionally avoids generic page-text extraction so search
    pages, JavaScript snippets, and footers do not become fake reviews.
    """

    def __init__(
        self,
        cookie: str = "",
        delay: float = 2.0,
        timeout: int = 20,
        retries: int = 2,
    ) -> None:
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
                "Referer": DOUBAN_HOST + "/",
            }
        )
        cookie = cookie or os.getenv("DOUBAN_COOKIE", "")
        if cookie:
            self.session.headers["Cookie"] = cookie

    def collect(
        self,
        book: str,
        subject_id: str = "",
        subject_url: str = "",
        pages: int = 1,
        sort: str = "hotest",
        limit: int = 100,
        min_chars: int = 80,
        fetch_full: bool = True,
        input_jsonl: str = "",
    ) -> list[Review]:
        reviews: list[Review] = []
        if input_jsonl:
            reviews.extend(read_jsonl(input_jsonl, fallback_book=book))

        subject = self.resolve_subject(book, subject_id=subject_id, subject_url=subject_url)
        print(f"[douban] subject: {subject.title} ({subject.subject_id})")

        for page_index in range(max(pages, 1)):
            start = page_index * 20
            list_url = build_reviews_url(subject.subject_id, start=start, sort=sort)
            html = self.get_text(list_url, referer=subject.url)
            page_reviews = self.parse_review_list(
                html=html,
                book=book or subject.title,
                subject=subject,
                list_url=list_url,
                min_chars=min_chars,
                fetch_full=fetch_full,
            )
            print(f"[douban] page {page_index + 1}: {len(page_reviews)} reviews")
            reviews.extend(page_reviews)
            if len(reviews) >= limit:
                break
            if not page_reviews:
                break

        unique = dedupe_reviews(review for review in reviews if review.content)
        return unique[:limit]

    def resolve_subject(self, book: str, subject_id: str = "", subject_url: str = "") -> DoubanSubject:
        if subject_id:
            subject_url = f"{DOUBAN_HOST}/subject/{subject_id}/"
            return DoubanSubject(subject_id=subject_id, title=book or subject_id, url=subject_url)

        if subject_url:
            subject_id = extract_subject_id(subject_url)
            if not subject_id:
                raise ValueError(f"Cannot parse Douban subject id from {subject_url}")
            return DoubanSubject(subject_id=subject_id, title=book or subject_id, url=subject_url)

        candidates = self.search_subjects(book)
        if not candidates:
            raise RuntimeError(
                "No Douban book subject found. Try passing --subject-id or --subject-url from the Douban book page."
            )
        for candidate in candidates:
            haystack = f"{candidate.title} {candidate.summary}"
            if book and book in haystack:
                return candidate
        return candidates[0]

    def search_subjects(self, book: str, limit: int = 8) -> list[DoubanSubject]:
        urls = [
            f"{DOUBAN_HOST}/subject_search?search_text={quote_plus(book)}&cat=1001",
            f"https://www.douban.com/search?cat=1001&q={quote_plus(book)}",
        ]
        subjects: list[DoubanSubject] = []
        seen: set[str] = set()
        for url in urls:
            html = self.get_text(url)
            soup = BeautifulSoup(html, "html.parser")
            for subject in parse_subject_candidates(soup, base_url=url):
                if subject.subject_id in seen:
                    continue
                seen.add(subject.subject_id)
                subjects.append(subject)
                if len(subjects) >= limit:
                    return subjects
        return subjects

    def parse_review_list(
        self,
        html: str,
        book: str,
        subject: DoubanSubject,
        list_url: str,
        min_chars: int = 80,
        fetch_full: bool = True,
    ) -> list[Review]:
        soup = BeautifulSoup(html, "html.parser")
        detect_blocked_page(soup, list_url)
        items = soup.select(".review-item")
        if not items:
            items = soup.select("div[data-cid], div.review")

        reviews: list[Review] = []
        for item in items:
            parsed = parse_review_list_item(item, book=book, subject=subject, list_url=list_url)
            if not parsed:
                continue
            if fetch_full and parsed.source_url:
                try:
                    detail_html = self.get_text(parsed.source_url, referer=list_url)
                    parsed = merge_review(parsed, parse_review_detail(detail_html, parsed.source_url, book, subject))
                except RuntimeError as exc:
                    print(f"[warn] full review skipped: {exc}")
            if is_review_like(parsed.content, book, min_chars):
                reviews.append(parsed)
        return dedupe_reviews(reviews)

    def parse_saved_html(
        self,
        paths: Iterable[str],
        book: str,
        subject_id: str = "",
        subject_url: str = "",
        min_chars: int = 80,
    ) -> list[Review]:
        if subject_id or subject_url:
            subject = self.resolve_subject(book, subject_id=subject_id, subject_url=subject_url)
        else:
            subject = DoubanSubject(subject_id="local", title=book or "豆瓣图书", url="file://local")
        reviews: list[Review] = []
        for html_path in paths:
            path = Path(html_path)
            html = path.read_text(encoding="utf-8", errors="ignore")
            soup = BeautifulSoup(html, "html.parser")
            if soup.select(".review-item"):
                reviews.extend(
                    self.parse_review_list(
                        html=html,
                        book=book or subject.title,
                        subject=subject,
                        list_url=str(path),
                        min_chars=min_chars,
                        fetch_full=False,
                    )
                )
            else:
                review = parse_review_detail(html, str(path), book or subject.title, subject)
                if is_review_like(review.content, book or subject.title, min_chars):
                    reviews.append(review)
        return dedupe_reviews(reviews)

    def get_text(self, url: str, referer: str = "") -> str:
        headers = {"Referer": referer or DOUBAN_HOST + "/"}
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            if self.delay:
                sleep(uniform(self.delay * 0.7, self.delay * 1.3))
            try:
                response = self.session.get(url, headers=headers, timeout=self.timeout)
                if response.status_code in {403, 418, 429}:
                    raise RuntimeError(f"Douban blocked request with HTTP {response.status_code}: {url}")
                response.raise_for_status()
                response.encoding = response.apparent_encoding or response.encoding
                detect_blocked_text(response.text, url)
                return response.text
            except (requests.RequestException, RuntimeError) as exc:
                last_error = exc
                if attempt < self.retries:
                    sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"Failed to fetch {url}: {last_error}") from last_error


def build_reviews_url(subject_id: str, start: int = 0, sort: str = "hotest") -> str:
    sort = sort or "hotest"
    return f"{DOUBAN_HOST}/subject/{subject_id}/reviews?sort={quote_plus(sort)}&start={start}"


def parse_subject_candidates(soup: BeautifulSoup, base_url: str) -> list[DoubanSubject]:
    candidates: list[DoubanSubject] = []
    for anchor in soup.select('a[href*="/subject/"]'):
        href = normalize_douban_url(anchor.get("href", ""), base_url)
        subject_id = extract_subject_id(href)
        if not subject_id:
            continue
        container = find_container(anchor, ("subject-item", "result", "item-root", "detail"))
        title = clean_text(anchor.get_text(" ", strip=True))
        if not title and container:
            title_node = container.select_one(".title, h3, h2")
            title = clean_text(title_node.get_text(" ", strip=True) if title_node else "")
        summary = clean_text(container.get_text(" ", strip=True) if container else "")
        if title and len(title) <= 2 and summary:
            title = summary[:40]
        candidates.append(DoubanSubject(subject_id=subject_id, title=title or subject_id, url=href, summary=summary))
    return dedupe_subjects(candidates)


def parse_review_list_item(item: Tag, book: str, subject: DoubanSubject, list_url: str) -> Review | None:
    title_anchor = item.select_one("h2 a[href], .review-hd a[href], a[href*='/review/']")
    review_url = normalize_douban_url(title_anchor.get("href", ""), list_url) if title_anchor else ""
    title = clean_text(title_anchor.get_text(" ", strip=True) if title_anchor else "")
    content_node = item.select_one(".short-content, .review-short, .review-content, .content")
    content = clean_review_content(content_node.get_text(" ", strip=True) if content_node else "")
    if not content and title:
        content = title

    author_node = item.select_one(".name, .main-hd a, a[property='v:reviewer']")
    author = clean_text(author_node.get_text(" ", strip=True) if author_node else "")
    date_node = item.select_one(".main-meta, .review-meta, span[property='v:dtreviewed']")
    created_at = clean_text(date_node.get_text(" ", strip=True) if date_node else "")

    rating_value = parse_rating(item)
    votes = parse_first_int(item.select_one(".vote-count, .action a[property='v:votes']"))
    extra = {
        "douban_subject_id": subject.subject_id,
        "douban_review_id": extract_review_id(review_url),
        "douban_rating": rating_value,
        "douban_votes": votes,
        "douban_list_url": list_url,
    }
    return Review(
        book=book or subject.title,
        platform="douban",
        title=title,
        author=author,
        created_at=created_at,
        source_url=review_url or list_url,
        content=content,
        extra={key: value for key, value in extra.items() if value not in {"", None}},
    )


def parse_review_detail(html: str, url: str, book: str, subject: DoubanSubject) -> Review:
    soup = BeautifulSoup(html, "html.parser")
    detect_blocked_page(soup, url)
    title_node = soup.select_one("h1, span[property='v:summary'], .review-title")
    content_node = soup.select_one("#link-report .review-content, .review-content, div[property='v:description']")
    author_node = soup.select_one(".main-hd .name, a[property='v:reviewer'], .reviewer")
    date_node = soup.select_one(".main-meta, span[property='v:dtreviewed']")
    content = clean_review_content(content_node.get_text("\n", strip=True) if content_node else "")
    title = clean_text(title_node.get_text(" ", strip=True) if title_node else "")
    review_id = extract_review_id(url)
    return Review(
        book=book or subject.title,
        platform="douban",
        title=title,
        author=clean_text(author_node.get_text(" ", strip=True) if author_node else ""),
        created_at=clean_text(date_node.get_text(" ", strip=True) if date_node else ""),
        source_url=url,
        content=content,
        extra={
            "douban_subject_id": subject.subject_id,
            "douban_review_id": review_id,
            "douban_rating": parse_rating(soup),
        },
    )


def merge_review(base: Review, detail: Review) -> Review:
    if detail.content:
        base.content = detail.content
    if detail.title:
        base.title = detail.title
    if detail.author:
        base.author = detail.author
    if detail.created_at:
        base.created_at = detail.created_at
    base.extra.update({key: value for key, value in detail.extra.items() if value not in {"", None}})
    return base


def extract_subject_id(url: str) -> str:
    match = SUBJECT_RE.search(url)
    return match.group(1) if match else ""


def extract_review_id(url: str) -> str:
    match = REVIEW_RE.search(url)
    return match.group(1) if match else ""


def normalize_douban_url(href: str, base_url: str) -> str:
    href = href.strip()
    if not href:
        return ""
    return urljoin(base_url, href)


def find_container(node: Tag, class_names: tuple[str, ...]) -> Tag | None:
    current = node
    for _ in range(5):
        parent = current.parent
        if not isinstance(parent, Tag):
            return None
        classes = set(parent.get("class", []))
        if any(class_name in classes for class_name in class_names):
            return parent
        current = parent
    return None


def parse_rating(node: Tag | BeautifulSoup) -> float | None:
    rating_node = node.select_one("span[class*='allstar']")
    if not rating_node:
        return None
    classes = " ".join(rating_node.get("class", []))
    match = STAR_RE.search(classes)
    if not match:
        return None
    return int(match.group(1)) / 10


def parse_first_int(node: Tag | None) -> int | None:
    if not node:
        return None
    match = re.search(r"\d+", node.get_text(" ", strip=True))
    return int(match.group(0)) if match else None


def clean_review_content(text: str) -> str:
    text = clean_text(text)
    text = re.sub(r"\(?\s*展开\s*\)?$", "", text)
    text = re.sub(r"\(?\s*这篇书评可能有关键情节透露\s*\)?", "", text)
    return normalize_space(text)


def clean_text(text: str) -> str:
    return normalize_space(text.replace("\xa0", " "))


def dedupe_subjects(subjects: Iterable[DoubanSubject]) -> list[DoubanSubject]:
    seen: set[str] = set()
    unique: list[DoubanSubject] = []
    for subject in subjects:
        if subject.subject_id in seen:
            continue
        seen.add(subject.subject_id)
        unique.append(subject)
    return unique


def detect_blocked_page(soup: BeautifulSoup, url: str) -> None:
    text = clean_text(soup.get_text(" ", strip=True))[:1000]
    detect_blocked_text(text, url)


def detect_blocked_text(text: str, url: str) -> None:
    markers = ("安全验证", "验证码", "检测到有异常请求", "sec.douban.com", "Forbidden")
    if any(marker in text for marker in markers):
        raise RuntimeError(f"Douban returned an anti-bot page for {url}")


def collect_douban_reviews(
    book: str,
    subject_id: str = "",
    subject_url: str = "",
    pages: int = 1,
    sort: str = "hotest",
    limit: int = 100,
    min_chars: int = 80,
    fetch_full: bool = True,
    input_html: list[str] | None = None,
    input_jsonl: str = "",
    cookie: str = "",
    delay: float = 2.0,
    timeout: int = 20,
    retries: int = 2,
) -> list[Review]:
    crawler = DoubanBookReviewCrawler(cookie=cookie, delay=delay, timeout=timeout, retries=retries)
    reviews: list[Review] = []
    if input_jsonl:
        reviews.extend(read_jsonl(input_jsonl, fallback_book=book))
    if input_html:
        reviews.extend(
            crawler.parse_saved_html(
                input_html,
                book=book,
                subject_id=subject_id,
                subject_url=subject_url,
                min_chars=min_chars,
            )
        )
    if not input_html:
        reviews.extend(
            crawler.collect(
                book=book,
                subject_id=subject_id,
                subject_url=subject_url,
                pages=pages,
                sort=sort,
                limit=limit,
                min_chars=min_chars,
                fetch_full=fetch_full,
            )
        )
    return dedupe_reviews(reviews)[:limit]
