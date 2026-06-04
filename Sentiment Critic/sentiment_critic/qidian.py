"""起点中文网 (qidian.com) 评论采集器。

从起点中文网采集书籍评论、评分、阅读量等数据。
使用公开页面解析，遵守 robots.txt。
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

from .collectors import (
    ReviewHTMLParser,
    fetch_url,
    is_review_like,
    make_title,
    trim_review,
    normalize_space,
)
from .models import Review, dedupe_reviews


def search_qidian_book(book: str, delay: float = 2.0, timeout: int = 20, retries: int = 2) -> dict | None:
    """搜索起点中文网书籍，返回 {book_id, title, author, url, intro} 或 None。

    注意：起点中文网使用 Cloudflare 反爬保护，简单 HTTP 请求大概率被拦截。
    建议通过 Playwright/浏览器手动导出 HTML 后使用 --input-html 导入。
    """
    from urllib.parse import quote

    book_id = ""
    book_id_match = None

    search_urls = [f"https://www.qidian.com/soushu/{quote(book)}.html"]
    simple_name = re.sub(r'[（(•·].*', '', book).strip()
    if simple_name != book and len(simple_name) >= 2:
        search_urls.append(f"https://www.qidian.com/soushu/{quote(simple_name)}.html")

    html = ""
    for search_url in search_urls:
        for attempt in range(retries):
            try:
                html = fetch_url(search_url, platform="qidian")
                break
            except RuntimeError:
                if attempt < retries - 1:
                    time.sleep(delay * (attempt + 1))
                else:
                    html = ""

        if not html or len(html) < 500:
            if "probe.js" in html or "C2WF" in html:
                print(f"[qidian] Blocked by anti-bot protection — Qidian requires Playwright/browser automation")
                return None
            continue

        for pattern in [r'data-bid="(\d+)"', r'/book/(\d+)/', r'bookId[=:]\s*["\']?(\d+)']:
            book_id_match = re.search(pattern, html)
            if book_id_match:
                book_id = book_id_match.group(1)
                break
        if book_id:
            break

    if not book_id:
        print(f"[qidian] Book not on Qidian or blocked: {book}")
        return None

    title_match = re.search(r'<h2[^>]*>.*?<a[^>]*>(.*?)</a>', html, re.DOTALL)
    if not title_match:
        title_match = re.search(r'data-bookname="([^"]*)"', html)
    title = normalize_space(title_match.group(1)) if title_match else book

    author_match = re.search(r'data-authorname="([^"]*)"', html)
    author = author_match.group(1) if author_match else ""

    return {
        "book_id": book_id,
        "title": title,
        "author": author,
        "url": f"https://www.qidian.com/book/{book_id}/",
    }


def fetch_qidian_book_info(book_id: str, delay: float = 2.0, timeout: int = 20, retries: int = 2) -> dict:
    """获取起点书籍详情页的元数据（评分、标签、阅读量等）。"""
    url = f"https://www.qidian.com/book/{book_id}/"
    for attempt in range(retries):
        try:
            html = fetch_url(url, platform="qidian")
            break
        except RuntimeError as exc:
            if attempt == retries - 1:
                print(f"[qidian] Book detail failed: {exc}")
                return {"book_id": book_id, "url": url}
            time.sleep(delay * (attempt + 1))

    info: dict = {"book_id": book_id, "url": url}

    # 评分
    score_match = re.search(r'data-score="([\d.]+)"', html) or re.search(r'"score":\s*"([\d.]+)"', html)
    if score_match:
        info["rating"] = float(score_match.group(1))

    # 标签/分类
    tag_matches = re.findall(r'<a[^>]*class="[^"]*tag[^"]*"[^>]*>(.*?)</a>', html, re.DOTALL)
    if tag_matches:
        info["tags"] = [normalize_space(t) for t in tag_matches if normalize_space(t) and len(normalize_space(t)) < 10]

    # 简介
    intro_match = re.search(r'<div[^>]*class="[^"]*intro[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
    if not intro_match:
        intro_match = re.search(r'<p[^>]*class="[^"]*intro[^"]*"[^>]*>(.*?)</p>', html, re.DOTALL)
    if intro_match:
        info["intro"] = normalize_space(intro_match.group(1))[:500]

    # 字数/阅读量 (从页面 meta 数据提取)
    word_count_match = re.search(r'<em[^>]*class="[^"]*count[^"]*"[^>]*>(\d+[万字]*)</em>', html)
    if word_count_match:
        info["word_count"] = word_count_match.group(1)

    return info


def fetch_qidian_reviews(
    book_id: str,
    pages: int = 1,
    min_chars: int = 80,
    limit: int = 100,
    delay: float = 2.0,
    timeout: int = 20,
    retries: int = 2,
    strict: bool = False,
) -> list[Review]:
    """从起点中文网书籍评论区采集评论。

    Qidian 评论区通常通过 AJAX 加载，格式如:
      https://www.qidian.com/book/{book_id}/review/?page={page}
    部分页面使用 JSON 接口返回评论数据。
    """
    reviews: list[Review] = []
    errors: list[str] = []

    for page in range(1, pages + 1):
        url = f"https://www.qidian.com/book/{book_id}/review/?page={page}"
        for attempt in range(retries):
            try:
                html = fetch_url(url, platform="qidian")
                break
            except RuntimeError as exc:
                if attempt == retries - 1:
                    msg = f"Page {page}: {exc}"
                    if strict:
                        raise RuntimeError(msg)
                    errors.append(msg)
                    html = ""
                else:
                    time.sleep(delay * (attempt + 1))

        if not html:
            continue

        page_reviews = _parse_qidian_review_html(html, book_id, min_chars, page)
        if not page_reviews:
            # 尝试从 JSON 解析（有些页面在 script 标签中包含初始数据）
            page_reviews = _parse_qidian_review_json(html, book_id, min_chars, page)

        reviews.extend(page_reviews)
        print(f"[qidian] page {page}: {len(page_reviews)} reviews")

        if len(reviews) >= limit:
            break
        if page < pages:
            time.sleep(delay)

    for error in errors:
        print(f"[qidian] {error}")

    return dedupe_reviews(reviews)[:limit]


def _parse_qidian_review_html(html: str, book_id: str, min_chars: int, page: int) -> list[Review]:
    """从 HTML 页面解析评论列表。"""
    reviews: list[Review] = []

    # Qidian 评论常见的 HTML 结构
    review_blocks = re.findall(
        r'<div[^>]*class="[^"]*(?:review|comment|discuss)[^"]*"[^>]*>(.*?)</div>\s*</div>\s*</div>',
        html, re.DOTALL,
    )
    if not review_blocks:
        # 更宽松的匹配
        review_blocks = re.findall(
            r'<(?:div|li)[^>]*class="[^"]*(?:review-item|comment-item|post-item)[^"]*"[^>]*>(.*?)</(?:div|li)>',
            html, re.DOTALL,
        )

    for block in review_blocks:
        # 提取评论文本
        text_match = re.search(r'<(?:div|p|span)[^>]*class="[^"]*(?:content|text|body|desc)[^"]*"[^>]*>(.*?)</(?:div|p|span)>', block, re.DOTALL)
        if not text_match:
            text_match = re.search(r'<(?:div|p)[^>]*>(.{40,})</(?:div|p)>', block, re.DOTALL)

        if text_match:
            text = normalize_space(re.sub(r'<[^>]+>', '', text_match.group(1)))
            if len(text) >= min_chars:
                reviews.append(Review(
                    book=book_id,
                    platform="qidian",
                    source_url=f"https://www.qidian.com/book/{book_id}/review/?page={page}",
                    title=make_title(text),
                    content=trim_review(text),
                ))

    return reviews


def _parse_qidian_review_json(html: str, book_id: str, min_chars: int, page: int) -> list[Review]:
    """从页面内嵌的 JSON 数据中提取评论。"""
    reviews: list[Review] = []

    # 尝试匹配 window.__INITIAL_STATE__ 或类似的 JSON 数据
    json_patterns = [
        r'window\.__INITIAL_STATE__\s*=\s*({.*?});\s*</script>',
        r'"reviewList":\s*(\[.*?\])',
        r'"commentList":\s*(\[.*?\])',
        r'"reviews":\s*(\[.*?\])',
    ]

    for pattern in json_patterns:
        match = re.search(pattern, html, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                items = data if isinstance(data, list) else data.get("list") or data.get("items") or []
                if isinstance(items, dict):
                    items = list(items.values())
                for item in items:
                    if isinstance(item, str):
                        text = normalize_space(item)
                    elif isinstance(item, dict):
                        text = normalize_space(item.get("content") or item.get("body") or item.get("text") or "")
                    else:
                        continue
                    if len(text) >= min_chars:
                        reviews.append(Review(
                            book=book_id,
                            platform="qidian",
                            source_url=f"https://www.qidian.com/book/{book_id}/review/?page={page}",
                            title=make_title(text),
                            content=trim_review(text),
                        ))
            except (json.JSONDecodeError, TypeError):
                continue
        if reviews:
            break

    return reviews


def collect_qidian_reviews(
    book: str,
    book_id: str = "",
    pages: int = 2,
    min_chars: int = 80,
    limit: int = 100,
    delay: float = 2.0,
    timeout: int = 20,
    retries: int = 2,
    strict: bool = False,
) -> list[Review]:
    """采集起点中文网评论 — 主入口。

    若未提供 book_id，先搜索获取。
    返回 Review 列表。
    """
    if not book_id:
        result = search_qidian_book(book, delay=delay, timeout=timeout, retries=retries)
        if result is None:
            print(f"[qidian] Could not find book on Qidian: {book}")
            return []
        book_id = result["book_id"]
        title = result["title"]
        print(f"[qidian] Found: {title} (book_id={book_id})")
    else:
        title = book

    # 获取书籍元数据
    info = fetch_qidian_book_info(book_id, delay=delay, timeout=timeout, retries=retries)
    if info.get("intro"):
        print(f"[qidian] Rating: {info.get('rating', 'N/A')}, Tags: {info.get('tags', [])}")

    # 采集评论
    reviews = fetch_qidian_reviews(
        book_id=book_id,
        pages=pages,
        min_chars=min_chars,
        limit=limit,
        delay=delay,
        timeout=timeout,
        retries=retries,
        strict=strict,
    )

    # 确保评论关联到正确书名
    for review in reviews:
        review.book = book

    return reviews
