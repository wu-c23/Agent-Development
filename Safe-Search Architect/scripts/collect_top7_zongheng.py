"""采集排行榜前7本纵横书籍的评论。

用法:
  python scripts/collect_top7_zongheng.py
"""

from __future__ import annotations

import sys, os, time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from review_critic.zongheng import (
    RUNS_DIR,
    ZonghengReviewCrawler,
    collect_zongheng_reviews,
)
from review_critic.models import write_jsonl

BOOKS = [
    ("齐天",          "https://www.zongheng.com/detail/1435440"),
    ("无敌天命",      "https://www.zongheng.com/detail/1336976"),
    ("星辰大道",      "https://www.zongheng.com/detail/1385191"),
    ("众仙俯首",      "https://www.zongheng.com/detail/1410173"),
    ("帝族长歌",      ""),
    ("一剑镇山河",    ""),
    ("夜行规则",      ""),
]


def build_output_path(book: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = book.replace("/", "_").replace("\\", "_").replace(":", "_")[:80]
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    return RUNS_DIR / f"{safe_name}_zongheng_{timestamp}.jsonl"


def main():
    for book_title, platform_id in BOOKS:
        book_id = platform_id.rsplit("/detail/", 1)[-1] if "/detail/" in platform_id else ""

        print(f"\n{'=' * 50}")
        print(f"📖 {book_title}  (book_id={book_id or '需搜索'})")

        try:
            reviews = collect_zongheng_reviews(
                book=book_title,
                book_id=book_id,
                platform_id=platform_id,
                pages=5,
                min_chars=30,
                limit=200,
            )

            if reviews:
                output_path = build_output_path(book_title)
                write_jsonl(output_path, reviews)
                print(f"  ✅ 保存 {len(reviews)} 条评论 → {output_path.name}")
            else:
                print(f"  ⚠️ 未找到评论")

        except Exception as exc:
            print(f"  ❌ 错误: {exc}")

        # 每本书之间休息 3 秒
        if book_title != BOOKS[-1][0]:
            time.sleep(3)

    print("\n✅ 全部完成！运行 build_zongheng_sentiment_index.py 重建索引。")


if __name__ == "__main__":
    main()
