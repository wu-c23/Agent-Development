from __future__ import annotations

from pathlib import Path
import argparse
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sentiment_critic.collectors import collect_reviews
from sentiment_critic.douban import collect_douban_reviews
from sentiment_critic.models import write_jsonl


def main() -> None:
    parser = argparse.ArgumentParser(description="采集/导入贴吧、豆瓣、小红书等平台的小说深度书评。")
    parser.add_argument("--book", required=True, help="小说名，例如：诡秘之主")
    parser.add_argument("--platform", action="append", choices=["tieba", "douban", "xiaohongshu"], help="要搜索的平台，可重复")
    parser.add_argument("--subject-id", default="", help="豆瓣图书 subject id；只抓豆瓣时推荐填写")
    parser.add_argument("--subject-url", default="", help="豆瓣图书页面 URL；只抓豆瓣时可填写")
    parser.add_argument("--no-full-review", action="store_true", help="豆瓣模式下只抓列表摘要，不进入书评详情页")
    parser.add_argument("--url", action="append", help="指定评论页或搜索结果页 URL，可重复")
    parser.add_argument("--input-html", action="append", help="本地 HTML 文件，可重复")
    parser.add_argument("--input-jsonl", default="", help="已有评论 JSONL，字段可包含 book/platform/content/url")
    parser.add_argument("--output", default="data/raw_reviews.jsonl", help="输出 JSONL 路径")
    parser.add_argument("--max-pages", type=int, default=1, help="每个平台搜索页数")
    parser.add_argument("--min-chars", type=int, default=80, help="深度评论最小字数")
    parser.add_argument("--limit", type=int, default=100, help="最多保留评论数")
    parser.add_argument("--strict", action="store_true", help="抓取失败时立即退出；默认会跳过失败页面")
    parser.add_argument("--allow-empty-output", action="store_true", help="允许用空结果覆盖输出文件")
    args = parser.parse_args()

    platforms = args.platform or []
    if platforms == ["douban"] and not args.url:
        reviews = collect_douban_reviews(
            book=args.book,
            subject_id=args.subject_id,
            subject_url=args.subject_url,
            pages=args.max_pages,
            limit=args.limit,
            min_chars=args.min_chars,
            fetch_full=not args.no_full_review,
            input_html=args.input_html,
            input_jsonl=args.input_jsonl,
        )
    else:
        reviews = collect_reviews(
            book=args.book,
            platforms=args.platform,
            urls=args.url,
            input_html=args.input_html,
            input_jsonl=args.input_jsonl,
            max_pages=args.max_pages,
            min_chars=args.min_chars,
            limit=args.limit,
            strict=args.strict,
        )
    if not reviews and not args.allow_empty_output:
        print(
            f"No reviews collected; {args.output} was not overwritten. "
            "Use --allow-empty-output if you really want an empty file."
        )
        return
    write_jsonl(args.output, reviews)
    print(f"Collected {len(reviews)} reviews -> {args.output}")


if __name__ == "__main__":
    main()
