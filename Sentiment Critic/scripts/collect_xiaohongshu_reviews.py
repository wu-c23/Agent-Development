from __future__ import annotations

from pathlib import Path
import argparse
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sentiment_critic.artifacts import default_collect_output, unique_path
from sentiment_critic.models import write_jsonl
from sentiment_critic.xiaohongshu import collect_xiaohongshu_reviews


def main() -> None:
    parser = argparse.ArgumentParser(description="采集小红书笔记里的小说深度书评。")
    parser.add_argument("--book", required=True, help="小说名，例如：诡秘之主")
    parser.add_argument("--keyword", default="", help="搜索关键词；默认自动拼接书名、书评、文笔、逻辑、更新")
    parser.add_argument("--pages", type=int, default=1, help="小红书搜索结果页数；静态页可能只返回首屏")
    parser.add_argument("--limit", type=int, default=100, help="最多保留评论数")
    parser.add_argument("--min-chars", type=int, default=80, help="深度评论最小字数")
    parser.add_argument("--url", action="append", help="指定小红书搜索页、笔记页或 xhslink 分享 URL，可重复")
    parser.add_argument("--input-html", action="append", help="本地保存的小红书搜索页或笔记 HTML，可重复")
    parser.add_argument("--input-jsonl", default="", help="已有评论 JSONL，和本次采集合并")
    parser.add_argument("--output", default="", help="输出 JSONL 路径；不填时自动生成不覆盖的文件名")
    parser.add_argument("--overwrite", action="store_true", help="允许覆盖显式指定的输出文件")
    parser.add_argument("--cookie", default="", help="小红书 Cookie；也可以使用 XHS_COOKIE 环境变量")
    parser.add_argument("--delay", type=float, default=2.0, help="请求间隔秒数")
    parser.add_argument("--timeout", type=int, default=20, help="请求超时秒数")
    parser.add_argument("--retries", type=int, default=2, help="失败重试次数")
    parser.add_argument("--no-fetch-detail", action="store_true", help="只解析搜索页摘要，不进入笔记详情")
    parser.add_argument("--strict", action="store_true", help="抓取失败时直接抛出错误")
    parser.add_argument("--allow-empty-output", action="store_true", help="允许用空结果覆盖输出文件")
    args = parser.parse_args()
    output = resolve_output(args)

    reviews = collect_xiaohongshu_reviews(
        book=args.book,
        keyword=args.keyword,
        pages=args.pages,
        limit=args.limit,
        min_chars=args.min_chars,
        fetch_notes=not args.no_fetch_detail,
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
            f"No Xiaohongshu reviews collected; {output} was not overwritten. "
            "Use a real note/share URL, set XHS_COOKIE in .env, or use --input-html."
        )
        return
    write_jsonl(output, reviews)
    print(f"Collected {len(reviews)} Xiaohongshu reviews -> {output}")


def resolve_output(args: argparse.Namespace) -> Path:
    if args.output:
        path = Path(args.output)
        return path if args.overwrite else unique_path(path)
    return default_collect_output(args.book, ["xiaohongshu"])


if __name__ == "__main__":
    main()
