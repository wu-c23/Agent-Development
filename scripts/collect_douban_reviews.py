from __future__ import annotations

from pathlib import Path
import argparse
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sentiment_critic.douban import DoubanBookReviewCrawler, collect_douban_reviews
from sentiment_critic.douban import load_subject_from_cache, load_subject_from_existing_reviews
from sentiment_critic.models import write_jsonl


def main() -> None:
    parser = argparse.ArgumentParser(description="只采集豆瓣读书的深度书评。")
    parser.add_argument("--book", required=True, help="书名，例如：诡秘之主")
    parser.add_argument("--subject-id", default="", help="豆瓣图书 subject id，推荐填写，最稳定")
    parser.add_argument("--subject-url", default="", help="豆瓣图书页面 URL，例如 https://book.douban.com/subject/xxxx/")
    parser.add_argument("--pages", type=int, default=1, help="抓取书评列表页数，每页约 20 条")
    parser.add_argument("--sort", default="hotest", help="豆瓣书评排序参数，例如 hotest/new_score")
    parser.add_argument("--limit", type=int, default=100, help="最多保留评论数")
    parser.add_argument("--min-chars", type=int, default=80, help="深度书评最小字数")
    parser.add_argument("--input-html", action="append", help="本地保存的豆瓣书评列表页或单篇书评 HTML")
    parser.add_argument("--input-jsonl", default="", help="已有 JSONL，和本次采集合并")
    parser.add_argument("--output", default="data/raw_reviews.jsonl", help="输出 JSONL 路径")
    parser.add_argument("--cookie", default="", help="豆瓣 Cookie；也可以用 DOUBAN_COOKIE 环境变量")
    parser.add_argument("--delay", type=float, default=2.0, help="请求间隔秒数，避免过快")
    parser.add_argument("--timeout", type=int, default=20, help="请求超时秒数")
    parser.add_argument("--retries", type=int, default=2, help="失败重试次数")
    parser.add_argument("--no-full-review", action="store_true", help="只用列表页摘要，不进入单篇书评页抓全文")
    parser.add_argument("--search-only", action="store_true", help="只搜索豆瓣图书条目并打印候选 subject，不抓书评")
    parser.add_argument("--strict", action="store_true", help="抓取失败时直接抛出错误")
    parser.add_argument("--allow-empty-output", action="store_true", help="允许用空结果覆盖输出文件")
    args = parser.parse_args()

    if args.search_only:
        cached = load_subject_from_cache(args.book) or load_subject_from_existing_reviews(args.book)
        if cached:
            print(f"{cached.subject_id}\t{cached.title}\t{cached.url}\t{cached.summary}\t(local)")
            return
        crawler = DoubanBookReviewCrawler(
            cookie=args.cookie,
            delay=args.delay,
            timeout=args.timeout,
            retries=args.retries,
        )
        subjects = crawler.search_subjects(args.book)
        if not subjects:
            print("No Douban subjects found. Try setting DOUBAN_COOKIE or passing --subject-url manually.")
            return
        for subject in subjects:
            print(f"{subject.subject_id}\t{subject.title}\t{subject.url}\t{subject.summary}")
        return

    reviews = collect_douban_reviews(
        book=args.book,
        subject_id=args.subject_id,
        subject_url=args.subject_url,
        pages=args.pages,
        sort=args.sort,
        limit=args.limit,
        min_chars=args.min_chars,
        fetch_full=not args.no_full_review,
        input_html=args.input_html,
        input_jsonl=args.input_jsonl,
        cookie=args.cookie,
        delay=args.delay,
        timeout=args.timeout,
        retries=args.retries,
        strict=args.strict,
    )
    if not reviews and not args.allow_empty_output:
        print(
            f"No Douban reviews collected; {args.output} was not overwritten. "
            "Try --subject-id/--subject-url, set DOUBAN_COOKIE, or use --input-html."
        )
        return
    write_jsonl(args.output, reviews)
    print(f"Collected {len(reviews)} Douban reviews -> {args.output}")


if __name__ == "__main__":
    main()
