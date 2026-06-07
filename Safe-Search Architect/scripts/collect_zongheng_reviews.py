"""纵横中文网 (zongheng.com) 评论采集 CLI。

用法:
  # 单本书（提供 book_id）
  python scripts/collect_zongheng_reviews.py --book "看守废丹房三年，我偷偷成仙了" --book-id 1395709

  # 单本书（无 book_id，自动搜索）
  python scripts/collect_zongheng_reviews.py --book "剑来"

  # 批量爬取（从 novels.json 读取所有纵横书籍）
  python scripts/collect_zongheng_reviews.py --batch --limit-books 10

  # 只搜索匹配 book_id，不爬评论
  python scripts/collect_zongheng_reviews.py --book "书名" --search-only

  # 指定输出路径
  python scripts/collect_zongheng_reviews.py --book "书名" --book-id 123 --output data/runs/my_output.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# 确保项目根目录在 sys.path 中
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from review_critic.zongheng import (
    RUNS_DIR,
    ZONGHENG_HOST,
    ZonghengReviewCrawler,
    collect_zongheng_reviews,
    extract_book_id_from_url,
)
from review_critic.models import write_jsonl


def build_output_path(book: str, output_dir: Path | None = None) -> Path:
    """生成输出文件路径：{书名}_zongheng_{timestamp}.jsonl"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = book.replace("/", "_").replace("\\", "_").replace(":", "_")[:80]
    out_dir = output_dir or RUNS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"{safe_name}_zongheng_{timestamp}.jsonl"


def load_novels_json() -> list[dict]:
    """加载 novels.json"""
    from review_critic.zongheng import NOVELS_PATH
    if not NOVELS_PATH.exists():
        print(f"[error] novels.json not found at: {NOVELS_PATH}")
        return []
    with NOVELS_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def get_zongheng_books() -> list[dict]:
    """获取所有纵横中文网的书籍，有 URL 的排在前面。"""
    novels = load_novels_json()
    zongheng = [n for n in novels if n.get("platform") == "纵横中文网"]

    with_url = []
    without_url = []
    for book in zongheng:
        pid = book.get("platform_id", "")
        if extract_book_id_from_url(pid):
            with_url.append(book)
        else:
            without_url.append(book)

    print(f"[zongheng] Total Zongheng books: {len(zongheng)} "
          f"({len(with_url)} with URL, {len(without_url)} without URL)")
    return with_url + without_url


_PROJECT_ROOT = Path(__file__).resolve().parents[2]  # scripts/ -> Safe-Search Architect/ -> project root

def load_progress() -> dict:
    """加载批量进度文件。"""
    progress_path = _PROJECT_ROOT / "Safe-Search Architect/data/zongheng_batch_progress.json"
    if progress_path.exists():
        try:
            return json.loads(progress_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return {"completed": [], "failed": [], "last_index": 0}


def save_progress(progress: dict) -> None:
    """保存批量进度。"""
    progress_path = _PROJECT_ROOT / "Safe-Search Architect/data/zongheng_batch_progress.json"
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    progress_path.write_text(json.dumps(progress, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def batch_collect(
    limit_books: int = 0,
    start_index: int = 0,
    pages: int = 2,
    min_chars: int = 80,
    review_limit: int = 100,
    delay: float = 2.0,
    timeout: int = 30,
    retries: int = 2,
    headless: bool = True,
    search_only: bool = False,
    cookie: str = "",
) -> None:
    """批量爬取所有纵横书籍的评论。"""
    books = get_zongheng_books()
    if not books:
        print("[zongheng] No Zongheng books found in novels.json")
        return

    progress = load_progress()
    start = max(start_index, progress["last_index"])
    end = min(start + limit_books, len(books)) if limit_books else len(books)

    print(f"[zongheng] Batch: books [{start}:{end}] of {len(books)}")
    crawler = ZonghengReviewCrawler(delay=delay, timeout=timeout, retries=retries, headless=headless, cookie=os.getenv("ZONGHENG_COOKIE", ""))

    success_count = 0
    fail_count = 0
    skip_count = 0

    for i in range(start, end):
        book_entry = books[i]
        title = book_entry.get("title", "")
        platform_id = book_entry.get("platform_id", "")
        book_id = extract_book_id_from_url(platform_id)

        print(f"\n[zongheng] [{i + 1}/{len(books)}] {title} "
              f"(book_id={book_id or 'search needed'})")

        if not title:
            skip_count += 1
            continue

        try:
            if search_only:
                if not book_id:
                    result = crawler.search_book(title)
                    if result:
                        print(f"  -> Found: {result['title']} (book_id={result['book_id']})")
                        success_count += 1
                    else:
                        print(f"  -> Not found")
                        fail_count += 1
                else:
                    print(f"  -> Already has book_id: {book_id}")
                    success_count += 1
            else:
                reviews = collect_zongheng_reviews(
                    book=title,
                    book_id=book_id,
                    platform_id=platform_id,
                    pages=pages,
                    min_chars=min_chars,
                    limit=review_limit,
                    delay=delay,
                    timeout=timeout,
                    retries=retries,
                    headless=headless,
                    cookie=cookie,
                )

                if reviews:
                    output_path = build_output_path(title)
                    write_jsonl(output_path, reviews)
                    print(f"  -> Saved {len(reviews)} reviews to {output_path}")
                    success_count += 1
                else:
                    print(f"  -> No reviews found")
                    fail_count += 1

        except Exception as exc:
            print(f"  -> Error: {exc}")
            fail_count += 1

        progress["last_index"] = i + 1
        progress["completed"].append(title) if title not in progress["failed"] else None
        if i % 10 == 0:
            save_progress(progress)

        if i < end - 1:
            time.sleep(delay)

    save_progress(progress)
    print(f"\n[zongheng] Batch complete: {success_count} success, {fail_count} failed, {skip_count} skipped")

    import asyncio
    asyncio.run(crawler._close_browser())


def main():
    parser = argparse.ArgumentParser(
        description="纵横中文网 (zongheng.com) 评论采集器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s --book "剑来" --search-only
  %(prog)s --book "看守废丹房三年，我偷偷成仙了" --book-id 1395709
  %(prog)s --batch --limit-books 10
  %(prog)s --batch --start-index 0 --limit-books 50
        """,
    )
    parser.add_argument("--book", type=str, help="书名")
    parser.add_argument("--book-id", type=str, default="", help="纵横数字 book_id")
    parser.add_argument("--platform-id", type=str, default="", help="novels.json 中的 platform_id")
    parser.add_argument("--pages", type=int, default=2, help="抓取评论页数 (default: 2)")
    parser.add_argument("--limit", type=int, default=100, help="最多返回评论数 (default: 100)")
    parser.add_argument("--min-chars", type=int, default=80, help="评论最小字符数 (default: 80)")
    parser.add_argument("--output", type=str, default="", help="输出 JSONL 路径（默认自动生成）")
    parser.add_argument("--batch", action="store_true", help="批量处理所有纵横书籍")
    parser.add_argument("--limit-books", type=int, default=0, help="批量模式下最多处理书籍数 (0=全部)")
    parser.add_argument("--start-index", type=int, default=0, help="批量模式下起始索引")
    parser.add_argument("--headless", action="store_true", default=True, help="无头模式 (default: True)")
    parser.add_argument("--no-headless", action="store_true", help="显示浏览器窗口（调试用）")
    parser.add_argument("--delay", type=float, default=2.0, help="请求间隔秒数 (default: 2.0)")
    parser.add_argument("--timeout", type=int, default=30, help="请求超时秒数 (default: 30)")
    parser.add_argument("--retries", type=int, default=2, help="重试次数 (default: 2)")
    parser.add_argument("--search-only", action="store_true", help="只搜索匹配 book_id，不抓评论")
    parser.add_argument("--cookie", type=str, default="", help="Cookie 字符串（或设置 ZONGHENG_COOKIE 环境变量）")

    args = parser.parse_args()

    headless = args.headless and not args.no_headless

    if args.batch:
        cookie = args.cookie or os.getenv("ZONGHENG_COOKIE", "")
        batch_collect(
            limit_books=args.limit_books,
            start_index=args.start_index,
            pages=args.pages,
            min_chars=args.min_chars,
            review_limit=args.limit,
            delay=args.delay,
            timeout=args.timeout,
            retries=args.retries,
            headless=headless,
            search_only=args.search_only,
            cookie=cookie,
        )
        return

    if not args.book:
        parser.error("需要提供 --book 参数，或使用 --batch 批量模式")

    book = args.book

    if args.search_only:
        crawler = ZonghengReviewCrawler(delay=args.delay, timeout=args.timeout, headless=headless)
        result = crawler.search_book(book)
        import asyncio
        asyncio.run(crawler._close_browser())
        if result:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"Book not found on Zongheng: {book}")
            sys.exit(1)
        return

    reviews = collect_zongheng_reviews(
        book=book,
        book_id=args.book_id,
        platform_id=args.platform_id,
        pages=args.pages,
        min_chars=args.min_chars,
        limit=args.limit,
        delay=args.delay,
        timeout=args.timeout,
        retries=args.retries,
        headless=headless,
        cookie=args.cookie,
    )

    if reviews:
        output_path = Path(args.output) if args.output else build_output_path(book)
        write_jsonl(output_path, reviews)
        print(f"\n[zongheng] Saved {len(reviews)} reviews to {output_path}")
    else:
        print(f"\n[zongheng] No reviews collected for: {book}")


if __name__ == "__main__":
    main()
