from __future__ import annotations

from pathlib import Path
import argparse
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sentiment_critic.collectors import is_review_like
from sentiment_critic.models import read_jsonl, write_jsonl


def main() -> None:
    parser = argparse.ArgumentParser(description="清理 JSONL 中误抓的脚本、页脚、备案等非书评内容。")
    parser.add_argument("--input", default="data/raw_reviews.jsonl", help="输入 JSONL")
    parser.add_argument("--output", default="data/raw_reviews.cleaned.jsonl", help="输出 JSONL")
    parser.add_argument("--book", default="", help="小说名；输入缺少 book 字段时使用")
    parser.add_argument("--min-chars", type=int, default=80, help="深度评论最小字数")
    args = parser.parse_args()

    reviews = read_jsonl(args.input, fallback_book=args.book)
    cleaned = [review for review in reviews if is_review_like(review.content, review.book or args.book, args.min_chars)]
    write_jsonl(args.output, cleaned)
    print(f"Kept {len(cleaned)} / {len(reviews)} reviews -> {args.output}")


if __name__ == "__main__":
    main()
