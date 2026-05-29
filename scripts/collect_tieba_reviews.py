from __future__ import annotations

from pathlib import Path
import argparse
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sentiment_critic.artifacts import default_collect_output, unique_path
from sentiment_critic.models import write_jsonl
from sentiment_critic.tieba import collect_tieba_reviews


def main() -> None:
    parser = argparse.ArgumentParser(description="采集百度贴吧帖子里的小说深度书评。")
    parser.add_argument("--book", required=True, help="小说名，例如：诡秘之主")
    parser.add_argument("--keyword", default="", help="搜索关键词；默认自动拼接书名、书评、文笔、逻辑、更新")
    parser.add_argument("--pages", type=int, default=1, help="贴吧搜索结果页数")
    parser.add_argument("--thread-pages", type=int, default=1, help="每个帖子最多抓取页数")
    parser.add_argument("--limit", type=int, default=100, help="最多保留评论数")
    parser.add_argument("--min-chars", type=int, default=80, help="深度评论最小字数")
    parser.add_argument("--url", action="append", help="指定贴吧搜索页或帖子 URL，可重复")
    parser.add_argument("--input-html", action="append", help="本地保存的贴吧搜索页或帖子 HTML，可重复")
    parser.add_argument("--input-jsonl", default="", help="已有评论 JSONL，和本次采集合并")
    parser.add_argument("--output", default="", help="输出 JSONL 路径；不填时自动生成不覆盖的文件名")
    parser.add_argument("--overwrite", action="store_true", help="允许覆盖显式指定的输出文件")
    parser.add_argument("--cookie", default="", help="贴吧 Cookie；也可以使用 TIEBA_COOKIE 环境变量")
    parser.add_argument("--delay", type=float, default=2.0, help="请求间隔秒数")
    parser.add_argument("--timeout", type=int, default=20, help="请求超时秒数")
    parser.add_argument("--retries", type=int, default=2, help="失败重试次数")
    parser.add_argument(
        "--backend",
        choices=["auto", "web", "aiotieba"],
        default="auto",
        help="采集后端；auto 会优先尝试可选 aiotieba，再回退网页解析",
    )
    parser.add_argument("--no-fetch-detail", action="store_true", help="只解析搜索页摘要，不进入帖子楼层")
    parser.add_argument("--strict", action="store_true", help="抓取失败时直接抛出错误")
    parser.add_argument("--allow-empty-output", action="store_true", help="允许用空结果覆盖输出文件")
    args = parser.parse_args()
    output = resolve_output(args)

    reviews = collect_tieba_reviews(
        book=args.book,
        keyword=args.keyword,
        pages=args.pages,
        limit=args.limit,
        min_chars=args.min_chars,
        fetch_threads=not args.no_fetch_detail,
        thread_pages=args.thread_pages,
        backend=args.backend,
        urls=args.url,
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
            f"No Tieba reviews collected; {output} was not overwritten. "
            "Automatic search tries Tieba full search, the same-name forum page, and the mobile forum page. "
            "If a real URL still returns 403, set TIEBA_COOKIE in .env or use --input-html."
        )
        return
    write_jsonl(output, reviews)
    print(f"Collected {len(reviews)} Tieba reviews -> {output}")


def resolve_output(args: argparse.Namespace) -> Path:
    if args.output:
        path = Path(args.output)
        return path if args.overwrite else unique_path(path)
    return default_collect_output(args.book, ["tieba"])


if __name__ == "__main__":
    main()
