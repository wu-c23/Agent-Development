from __future__ import annotations

from pathlib import Path
import argparse
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sentiment_critic.collectors import collect_reviews
from sentiment_critic.models import write_jsonl


def main() -> None:
    parser = argparse.ArgumentParser(description="采集/导入贴吧、豆瓣、小红书等平台的小说深度书评。")
    parser.add_argument("--book", required=True, help="小说名，例如：诡秘之主")
    parser.add_argument("--platform", action="append", choices=["tieba", "douban", "xiaohongshu"], help="要搜索的平台，可重复")
    parser.add_argument("--url", action="append", help="指定评论页或搜索结果页 URL，可重复")
    parser.add_argument("--input-html", action="append", help="本地 HTML 文件，可重复")
    parser.add_argument("--input-jsonl", default="", help="已有评论 JSONL，字段可包含 book/platform/content/url")
    parser.add_argument("--output", default="data/raw_reviews.jsonl", help="输出 JSONL 路径")
    parser.add_argument("--max-pages", type=int, default=1, help="每个平台搜索页数")
    parser.add_argument("--min-chars", type=int, default=80, help="深度评论最小字数")
    parser.add_argument("--limit", type=int, default=100, help="最多保留评论数")
    args = parser.parse_args()

    reviews = collect_reviews(
        book=args.book,
        platforms=args.platform,
        urls=args.url,
        input_html=args.input_html,
        input_jsonl=args.input_jsonl,
        max_pages=args.max_pages,
        min_chars=args.min_chars,
        limit=args.limit,
    )
    write_jsonl(args.output, reviews)
    print(f"Collected {len(reviews)} reviews -> {args.output}")


if __name__ == "__main__":
    main()
