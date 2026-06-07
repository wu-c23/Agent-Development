"""纵横中文网 (zongheng.com) 评论采集器。

从纵横中文网采集书籍评论。纵横中文网是 SPA 网站，需要 Playwright 渲染。
优先通过拦截网络请求发现评论 API，API 不可用时回退到 DOM 解析。
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# Windows asyncio 子进程管道关闭时的 ResourceWarning 是已知 harmless 问题，抑制掉
warnings.filterwarnings("ignore", message="unclosed transport", category=ResourceWarning)

from .models import Review, dedupe_reviews, normalize_space, now_iso

ZONGHENG_HOST = "https://www.zongheng.com"
SEARCH_URL = f"{ZONGHENG_HOST}/search"
DETAIL_URL = f"{ZONGHENG_HOST}/detail"
_PROJECT_ROOT = Path(__file__).resolve().parents[3]  # src/review_critic/zongheng.py -> project root
DEFAULT_CACHE_PATH = _PROJECT_ROOT / "Safe-Search Architect/data/zongheng_book_cache.json"
DEFAULT_PROGRESS_PATH = _PROJECT_ROOT / "Safe-Search Architect/data/zongheng_batch_progress.json"
NOVELS_PATH = _PROJECT_ROOT / "Sentiment Critic/data/novels.json"
RUNS_DIR = _PROJECT_ROOT / "Sentiment Critic/data/runs"

BLOCK_MARKERS = (
    "人机验证", "滑块验证", "点击验证",
    "安全验证", "验证码", "检测到有异常请求",
    "请稍后再试", "您的操作过于频繁",
)

REVIEW_API_PATTERNS = (
    "/comment", "/review", "/discuss", "/evaluate",
    "commentList", "reviewList", "getComment", "getReview",
)

REVIEW_CONTAINER_SELECTORS = (
    ".comment-list", ".review-list", ".book-comment", ".book-review",
    ".discuss-list", ".evaluate-list",
    '[class*="comment"]', '[class*="review"]',
    ".reader-comment", ".reader-review",
)


def _load_novels_json() -> list[dict[str, Any]]:
    if not NOVELS_PATH.exists():
        return []
    with NOVELS_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _save_novels_json(novels: list[dict[str, Any]]) -> None:
    NOVELS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with NOVELS_PATH.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(novels, f, ensure_ascii=False, indent=2)
        f.write("\n")


def extract_book_id_from_url(url: str) -> str:
    """从纵横 URL 中提取数字 book_id。"""
    if not url:
        return ""
    if url.isdigit():
        return url
    match = re.search(r"/detail/(\d+)", url)
    if match:
        return match.group(1)
    match = re.search(r"book/(\d+)", url)
    if match:
        return match.group(1)
    return ""


def parse_zongheng_date(date_str: str) -> str:
    """将纵横的各种日期格式标准化为 ISO 格式。"""
    if not date_str:
        return ""
    date_str = str(date_str).strip()
    # 处理毫秒级 Unix 时间戳 (如 1780762290000)
    if date_str.isdigit() and len(date_str) >= 13:
        try:
            ts = int(date_str) / 1000.0
            dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone()
            return dt.isoformat(timespec="seconds")
        except (ValueError, OSError):
            pass
    if date_str.isdigit() and len(date_str) == 10:
        try:
            dt = datetime.fromtimestamp(int(date_str), tz=timezone.utc).astimezone()
            return dt.isoformat(timespec="seconds")
        except (ValueError, OSError):
            pass
    iso_patterns = [
        (r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", None),
        (r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", lambda s: s.replace(" ", "T") + "+08:00"),
        (r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}", lambda s: s.replace(" ", "T") + ":00+08:00"),
        (r"^\d{4}-\d{2}-\d{2}", lambda s: s + "T00:00:00+08:00"),
        (r"^\d{2}-\d{2} \d{2}:\d{2}", lambda s: f"{datetime.now().year}-{s.replace(' ', 'T')}:00+08:00"),
    ]
    for pattern, transform in iso_patterns:
        if re.match(pattern, date_str):
            return transform(date_str) if transform else date_str
    hours_ago = re.match(r"(\d+)\s*小时前", date_str)
    if hours_ago:
        dt = datetime.now(timezone.utc) - timedelta(hours=int(hours_ago.group(1)))
        return dt.isoformat(timespec="seconds")
    minutes_ago = re.match(r"(\d+)\s*分钟前", date_str)
    if minutes_ago:
        dt = datetime.now(timezone.utc) - timedelta(minutes=int(minutes_ago.group(1)))
        return dt.isoformat(timespec="seconds")
    days_ago = re.match(r"(\d+)\s*天前", date_str)
    if days_ago:
        dt = datetime.now(timezone.utc) - timedelta(days=int(days_ago.group(1)))
        return dt.isoformat(timespec="seconds")
    return date_str


def _make_title(text: str, max_len: int = 64) -> str:
    """从评论正文生成标题（取前 max_len 字符）。"""
    text = normalize_space(text)
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def _detect_captcha(html: str) -> bool:
    """检测页面是否需要验证码。"""
    return any(marker in html for marker in BLOCK_MARKERS)


def _describe_json_structure(data: Any, depth: int = 0) -> str:
    """返回 JSON 数据的结构摘要，用于调试 API 响应。"""
    if depth > 3:
        return "..."
    if isinstance(data, dict):
        keys = list(data.keys())
        summary = []
        for k in keys[:8]:
            val = data[k]
            if isinstance(val, list):
                summary.append(f"{k}=list[{len(val)}]")
            elif isinstance(val, dict):
                summary.append(f"{k}=dict({','.join(list(val.keys())[:4])})")
            elif isinstance(val, str):
                summary.append(f"{k}=str({val[:40]})")
            else:
                summary.append(f"{k}={type(val).__name__}({val})")
        return "{" + ", ".join(summary) + ("..." if len(keys) > 8 else "") + "}"
    if isinstance(data, list):
        if not data:
            return "[]"
        return f"list[{len(data)}] of " + _describe_json_structure(data[0], depth + 1)
    return type(data).__name__


class ZonghengReviewCrawler:
    """纵横中文网评论爬虫。"""

    def __init__(
        self,
        delay: float = 2.0,
        timeout: int = 30,
        retries: int = 2,
        headless: bool = True,
        min_chars: int = 80,
        cookie: str = "",
    ) -> None:
        self.delay = max(delay, 0.5)
        self.timeout = timeout
        self.retries = max(retries, 0)
        self.headless = headless
        self.min_chars = min_chars
        self.cookie = cookie or os.getenv("ZONGHENG_COOKIE", "")
        self._browser = None
        self._context = None
        self._review_api_cache: dict[str, str] = {}
        self._book_cache: dict[str, dict[str, str]] = {}

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    def collect(
        self,
        book: str,
        book_id: str = "",
        platform_id: str = "",
        pages: int = 2,
        limit: int = 100,
    ) -> list[Review]:
        """采集一本书的评论——主入口（同步包装，含资源清理）。"""

        async def _run_and_close():
            try:
                return await self._collect_async(book, book_id, platform_id, pages, limit)
            finally:
                await self._close_browser()

        return asyncio.run(_run_and_close())

    def search_book(self, title: str) -> dict[str, str] | None:
        """搜索纵横中文网，返回 {book_id, title, author, url} 或 None。"""
        return asyncio.run(self._search_book_async(title))

    # ------------------------------------------------------------------
    # Playwright 生命周期
    # ------------------------------------------------------------------

    async def _ensure_browser(self):
        if self._browser is None:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=self.headless,
                args=[
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-features=IsolateOrigins,site-per-process",
                    "--disable-infobars",
                    "--disable-dev-shm-usage",
                    "--disable-setuid-sandbox",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--disable-background-networking",
                ],
            )
        if self._context is None:
            import random
            viewport = {"width": random.randint(1280, 1440), "height": random.randint(720, 900)}
            self._context = await self._browser.new_context(
                viewport=viewport,
                user_agent=os.getenv(
                    "SENTIMENT_CRITIC_UA",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                ),
                locale="zh-CN",
                timezone_id="Asia/Shanghai",
            )
            # 隐藏自动化特征
            await self._context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => false });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
                window.chrome = { runtime: {} };
            """)
            if self.cookie:
                await self._context.add_cookies([
                    {"name": c.split("=")[0], "value": "=".join(c.split("=")[1:]),
                     "domain": ".zongheng.com", "path": "/"}
                    for c in self.cookie.split("; ") if "=" in c
                ])

    async def _new_page(self):
        """创建新页面。"""
        await self._ensure_browser()
        page = await self._context.new_page()
        return page

    async def _close_browser(self):
        try:
            if self._context:
                await self._context.close()
        except Exception:
            pass
        finally:
            self._context = None
        try:
            if self._browser:
                await self._browser.close()
        except Exception:
            pass
        finally:
            self._browser = None
        try:
            if hasattr(self, "_playwright") and self._playwright:
                await self._playwright.stop()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 搜索
    # ------------------------------------------------------------------

    async def _search_book_async(self, title: str) -> dict[str, str] | None:
        """用 Playwright 搜索纵横中文网。"""
        if title in self._book_cache:
            return self._book_cache[title]

        page = await self._new_page()

        try:
            search_url = f"https://www.zongheng.com/search?keyword={title}"
            await page.goto(search_url, wait_until="domcontentloaded", timeout=self.timeout * 1000)
            await page.wait_for_timeout(1500)
            html = await page.content()

            if _detect_captcha(html):
                if self.headless:
                    print(f"[zongheng] Captcha detected during search for: {title}")
                    return None
                else:
                    print(f"[zongheng] Captcha detected during search! Please solve it in the browser window.")
                    print(f"[zongheng] Waiting 60 seconds...")
                    await asyncio.sleep(60)
                    await page.goto(search_url, wait_until="domcontentloaded", timeout=self.timeout * 1000)
                    await page.wait_for_timeout(2000)
                    html = await page.content()
                    if _detect_captcha(html):
                        print(f"[zongheng] Captcha still present, skipping search for: {title}")
                        return None

            # 尝试从搜索结果页提取第一本书的信息
            result = await self._extract_search_result(page, title)
            if result:
                self._book_cache[title] = result
                self._save_book_cache()
                print(f"[zongheng] Found: {result['title']} (book_id={result['book_id']})")
                return result

            print(f"[zongheng] Book not found in search: {title}")
            return None
        finally:
            await page.close()

    async def _extract_search_result(self, page, title: str) -> dict[str, str] | None:
        """从搜索结果页面提取第一本书的信息。"""
        try:
            # 等待搜索结果加载
            await page.wait_for_selector("a[href*='/detail/']", timeout=5000)

            result = await page.evaluate("""
                () => {
                    const links = document.querySelectorAll('a[href*="/detail/"]');
                    for (const link of links) {
                        const href = link.getAttribute('href') || '';
                        const match = href.match(/detail/(\\d+)/);
                        if (match) {
                            const bookName = link.querySelector('.book-name, .title, h3, h2')
                                || link.closest('li, div')?.querySelector('.book-name, .title, h3, h2');
                            return {
                                book_id: match[1],
                                title: (bookName || link).textContent.trim(),
                                url: 'https://www.zongheng.com/detail/' + match[1],
                            };
                        }
                    }
                    return null;
                }
            """)

            if result and result.get("book_id"):
                result["author"] = ""
                return result
        except Exception:
            pass

        # 回退：从 HTML 提取
        html = await page.content()
        detail_match = re.search(r'href="(/detail/\d+)"', html)
        title_match = re.search(r'title="([^"]*' + re.escape(title[:4]) + r'[^"]*)"', html)
        if detail_match:
            book_id = extract_book_id_from_url(detail_match.group(1))
            return {
                "book_id": book_id,
                "title": title_match.group(1) if title_match else title,
                "author": "",
                "url": f"{ZONGHENG_HOST}/detail/{book_id}",
            }
        return None

    # ------------------------------------------------------------------
    # 评论采集
    # ------------------------------------------------------------------

    async def _collect_async(
        self,
        book: str,
        book_id: str = "",
        platform_id: str = "",
        pages: int = 2,
        limit: int = 100,
    ) -> list[Review]:
        """异步评论采集主逻辑。"""
        page = await self._new_page()

        collected_at = now_iso()
        reviews: list[Review] = []

        try:
            detail_url = f"https://www.zongheng.com/detail/{book_id}" if book_id else ""

            # 拦截所有 API 响应
            api_responses: list[dict] = []
            all_api_urls: list[str] = []

            async def capture_response(response):
                url = response.url
                all_api_urls.append(url)  # 静默收集，不打印
                if response.ok:
                    ct = response.headers.get("content-type") or ""
                    if "json" in ct or "javascript" in ct or "text/plain" in ct:
                        try:
                            body = await response.text()
                            if len(body) > 50:
                                api_responses.append({"url": url, "body": body[:200000]})
                        except Exception:
                            pass

            page.on("response", capture_response)

            # 打开详情页
            if detail_url:
                print(f"[zongheng] Loading: {detail_url}")
                await page.goto(detail_url, wait_until="load", timeout=self.timeout * 1000)
                await page.wait_for_timeout(3000)

                # 查找并点击书友圈/讨论 tab
                tab_clicked = await page.evaluate("""
                    () => {
                        const keywords = ['书友圈', '圈子', '讨论', '评论', '社区', '书评'];
                        const allElements = document.querySelectorAll('*');
                        for (const el of allElements) {
                            if (el.children.length === 0 && el.textContent) {
                                const text = el.textContent.trim();
                                for (const kw of keywords) {
                                    if (text === kw || text.includes(kw)) {
                                        el.click();
                                        return 'clicked: ' + kw + ' on <' + el.tagName + '>';
                                    }
                                }
                            }
                        }
                        return 'no tab found';
                    }
                """)
                print(f"[zongheng] Tab click result: {tab_clicked}")
                await page.wait_for_timeout(2000)

                # 连续滚动到底部触发懒加载
                for i in range(6):
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await page.wait_for_timeout(1000)
                # 回到顶部再滚一次（有些组件需要可见才加载）
                await page.evaluate("window.scrollTo(0, 0)")
                await page.wait_for_timeout(500)
                for i in range(6):
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await page.wait_for_timeout(800)

                html = await page.content()
                page_title = await page.title()
                print(f"[zongheng] HTML length: {len(html)}")
                print(f"[zongheng] API URLs captured: {len(all_api_urls)}")

                if _detect_captcha(html):
                    debug_path = Path("data/debug")
                    debug_path.mkdir(parents=True, exist_ok=True)
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    fname = debug_path / f"zongheng_detail_{ts}.html"
                    fname.write_text(html[:20000], encoding="utf-8")
                    print(f"[zongheng] Debug HTML saved to: {fname}")
                    if self.headless:
                        print(f"[zongheng] Possible captcha/block page for: {book}")
                        print(f"[zongheng] Try --no-headless to inspect the browser window.")
                        return reviews
                    else:
                        print(f"[zongheng] Captcha detected! Please solve it in the browser window.")
                        print(f"[zongheng] Waiting 60 seconds...")
                        await asyncio.sleep(60)
                        await page.goto(detail_url, wait_until="load", timeout=self.timeout * 1000)
                        await page.wait_for_timeout(3000)
                        html = await page.content()
                        if _detect_captcha(html):
                            print(f"[zongheng] Captcha still present, skipping: {book}")
                            return reviews

            # 从拦截的 API 响应中提取评论（含分页）
            if api_responses:
                forum_base_url = ""
                forum_mark = ""
                forum_count = 0
                for resp in api_responses:
                    url = resp["url"]
                    body = resp["body"]
                    try:
                        data = json.loads(body)
                    except Exception:
                        data = None
                    parsed = self._parse_review_api(body, url, book, platform_id, book_id, collected_at)
                    if parsed:
                        forum_count += len(parsed)
                    reviews.extend(parsed)
                    if "forumapi/forums/postlist" in url and isinstance(data, dict):
                        forum_base_url = url
                        forum_mark = (data.get("data") or {}).get("mark") or ""
                if forum_count:
                    print(f"[zongheng]   Page 1: {forum_count} reviews")

                # 分页抓取更多评论
                if forum_base_url and forum_mark and len(reviews) < limit:
                    from urllib.parse import urlencode, urlparse, parse_qs
                    parsed = urlparse(forum_base_url)
                    params = parse_qs(parsed.query)
                    forum_id = (params.get("forumId") or [book_id])[0]
                    base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                    mark = forum_mark
                    for page_no in range(2, pages + 2):
                        if not mark or len(reviews) >= limit:
                            break
                        try:
                            fetch_url = f"{base_url}?bookId={book_id}&forumId={forum_id}&forumType=0&mark={mark}"
                            page_reviews, next_mark = await self._fetch_forum_page(
                                page, fetch_url, book, platform_id, book_id, collected_at
                            )
                            if page_reviews:
                                print(f"[zongheng]   -> Found {len(page_reviews)} reviews (page {page_no})")
                                reviews.extend(page_reviews)
                                mark = next_mark
                            else:
                                break
                        except Exception as exc:
                            print(f"[zongheng]   Page {page_no} error: {exc}")
                            break

                if reviews:
                    return dedupe_reviews(reviews)[:limit]

            # 回退：从 DOM 提取评论
            dom_reviews = await self._extract_reviews_from_dom(page, book, platform_id, book_id, collected_at)
            reviews.extend(dom_reviews)
            print(f"[zongheng] Extracted {len(dom_reviews)} reviews from DOM")

            if not reviews:
                print(f"[zongheng] No reviews found (checked {len(all_api_urls)} API URLs, looked for forum content in DOM)")

            return dedupe_reviews(reviews)[:limit]

        finally:
            await page.close()

    async def _fetch_forum_page(
        self,
        page,
        url: str,
        book: str,
        platform_id: str,
        book_id: str,
        collected_at: str,
    ) -> tuple[list[Review], str]:
        """通过浏览器 fetch 获取一页论坛数据，返回 (reviews, next_mark)。"""
        try:
            result = await page.evaluate("""
                async (url) => {
                    const resp = await fetch(url, { credentials: 'include' });
                    if (!resp.ok) return JSON.stringify({ error: resp.status });
                    const text = await resp.text();
                    return text;
                }
            """, url)
            data = json.loads(result)
            if "error" in data:
                return [], ""
            reviews = self._parse_review_api(data, url, book, platform_id, book_id, collected_at)
            next_mark = (data.get("data") or {}).get("mark") or ""
            return reviews, next_mark
        except Exception:
            return [], ""

    def _parse_review_api(
        self,
        payload: Any,
        source_url: str,
        book: str,
        platform_id: str,
        book_id: str,
        collected_at: str,
    ) -> list[Review]:
        """解析评论 API 的 JSON 响应。"""
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except (json.JSONDecodeError, TypeError):
                return []
        reviews: list[Review] = []
        items = self._extract_items(payload)

        for item in items:
            if not isinstance(item, dict):
                continue
            content = normalize_space(
                str(item.get("content") or item.get("body") or item.get("text")
                    or item.get("comment") or item.get("message") or item.get("detail")
                    or item.get("postContent") or item.get("replyContent") or "")
            )
            if len(content) < self.min_chars:
                continue

            author = str(item.get("userName") or item.get("nickname") or item.get("nickName")
                        or item.get("author") or item.get("posterName") or item.get("poster") or "")
            created = parse_zongheng_date(
                str(item.get("createTime") or item.get("created_at") or item.get("createdAt")
                    or item.get("time") or item.get("postTime") or item.get("createDate") or "")
            )
            title = str(item.get("title") or "") or _make_title(content)
            review_id = str(item.get("id") or item.get("threadId") or item.get("commentId")
                           or item.get("reviewId") or "")

            extra: dict[str, Any] = {"zongheng_book_id": book_id}
            if review_id:
                extra["zongheng_review_id"] = review_id
            if "rating" in item or "score" in item:
                extra["zongheng_rating"] = item.get("rating") or item.get("score")
            if "likeCount" in item or "votes" in item:
                extra["zongheng_votes"] = item.get("likeCount") or item.get("votes")

            reviews.append(Review(
                book=book,
                platform="zongheng",
                content=content,
                source_url=source_url,
                title=title,
                author=author,
                created_at=created,
                collected_at=collected_at,
                platform_id=platform_id,
                extra={k: v for k, v in extra.items() if v not in ("", None)},
            ))

        return reviews

    def _extract_items(self, payload: Any) -> list[dict]:
        """从 JSON payload 中递归提取评论列表。"""
        if isinstance(payload, list):
            dict_items = [i for i in payload if isinstance(i, dict)]
            if dict_items and any(
                isinstance(i, dict) and any(
                    k in i for k in ("content", "body", "text", "comment",
                                     "message", "detail", "postContent", "replyContent")
                )
                for i in dict_items
            ):
                return dict_items
            nested = []
            for item in payload:
                nested.extend(self._extract_items(item))
            return nested

        if isinstance(payload, dict):
            for key in ("data", "result", "list", "items", "records", "comments", "reviews",
                         "commentList", "reviewList", "posts", "postList", "threads",
                         "threadList", "forumPostList", "rows", "ThreadList"):
                if key in payload:
                    found = self._extract_items(payload[key])
                    if found:
                        return found
            nested = []
            for val in payload.values():
                nested.extend(self._extract_items(val))
            return nested

        return []

    async def _extract_reviews_from_dom(
        self,
        page,
        book: str,
        platform_id: str,
        book_id: str,
        collected_at: str,
    ) -> list[Review]:
        """从 DOM 中提取评论（API 不可用时的回退方案）。"""
        reviews: list[Review] = []
        detail_url = page.url

        for selector in REVIEW_CONTAINER_SELECTORS:
            try:
                await page.wait_for_selector(selector, timeout=3000)
                break
            except Exception:
                continue

        items = await page.evaluate("""
            (selectors) => {
                const results = [];
                for (const sel of selectors) {
                    const containers = document.querySelectorAll(sel);
                    if (containers.length > 0) {
                        containers.forEach(c => {
                            const contentEl = c.querySelector(
                                '.content, .text, .body, .desc, p, .comment-content, .review-content'
                            );
                            const authorEl = c.querySelector(
                                '.author, .user, .nickname, .name, .user-name'
                            );
                            const dateEl = c.querySelector(
                                '.time, .date, .create-time, .created-at'
                            );
                            const titleEl = c.querySelector(
                                '.title, h3, h4, .subject'
                            );
                            const text = contentEl ? contentEl.textContent.trim() : c.textContent.trim();
                            if (text.length > 20) {
                                results.push({
                                    title: titleEl ? titleEl.textContent.trim() : '',
                                    content: text,
                                    author: authorEl ? authorEl.textContent.trim() : '',
                                    created_at: dateEl ? dateEl.textContent.trim() : '',
                                });
                            }
                        });
                        if (results.length > 0) break;
                    }
                }
                return results;
            }
        """, REVIEW_CONTAINER_SELECTORS)

        for item in items:
            content = normalize_space(item.get("content") or "")
            if len(content) < self.min_chars:
                continue

            reviews.append(Review(
                book=book,
                platform="zongheng",
                content=content,
                source_url=detail_url,
                title=item.get("title") or _make_title(content),
                author=normalize_space(item.get("author") or ""),
                created_at=parse_zongheng_date(item.get("created_at") or ""),
                collected_at=collected_at,
                platform_id=platform_id,
                extra={"zongheng_book_id": book_id} if book_id else {},
            ))

        return reviews

    # ------------------------------------------------------------------
    # 缓存管理
    # ------------------------------------------------------------------

    def _load_book_cache(self) -> dict[str, dict[str, str]]:
        if DEFAULT_CACHE_PATH.exists():
            try:
                return json.loads(DEFAULT_CACHE_PATH.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return {}
        return {}

    def _save_book_cache(self) -> None:
        DEFAULT_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        DEFAULT_CACHE_PATH.write_text(
            json.dumps(self._book_cache, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


# ------------------------------------------------------------------
# 便捷函数
# ------------------------------------------------------------------

def collect_zongheng_reviews(
    book: str,
    book_id: str = "",
    platform_id: str = "",
    pages: int = 2,
    min_chars: int = 80,
    limit: int = 100,
    delay: float = 2.0,
    timeout: int = 30,
    retries: int = 2,
    headless: bool = True,
    cookie: str = "",
) -> list[Review]:
    """采集纵横中文网评论——便捷函数。

    参数：
        book: 书名
        book_id: 纵横的数字 book_id（有则直接用，无则搜索）
        platform_id: novels.json 中的 platform_id（用于生成 uid）
        pages: 爬取页数
        min_chars: 评论最小字符数
        limit: 最多返回评论数
        delay: 请求间隔（秒）
        timeout: 超时（秒）
        retries: 重试次数
        headless: 是否无头模式
        cookie: Cookie 字符串
    """
    crawler = ZonghengReviewCrawler(
        delay=delay,
        timeout=timeout,
        retries=retries,
        headless=headless,
        min_chars=min_chars,
        cookie=cookie,
    )

    # 如果没有 book_id，尝试搜索
    if not book_id and platform_id:
        book_id = extract_book_id_from_url(platform_id)

    if not book_id:
        print(f"[zongheng] No book_id, searching by title: {book}")
        result = crawler.search_book(book)
        if result:
            book_id = result["book_id"]
            book = result.get("title") or book
        else:
            print(f"[zongheng] Could not find book on Zongheng: {book}")
            return []

    print(f"[zongheng] Collecting reviews for: {book} (book_id={book_id})")
    return crawler.collect(
        book=book,
        book_id=book_id,
        platform_id=platform_id,
        pages=pages,
        limit=limit,
    )
