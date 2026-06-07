"""从评论数据 + 榜单数据构建 novels.json 小说元数据索引。

用法:
  python scripts/build_novel_index.py                     # 扫描默认目录
  python scripts/build_novel_index.py --reviews-dir data  # 指定评论目录
  python scripts/build_novel_index.py --trend-dir data/trend_items  # 指定榜单目录
  python scripts/build_novel_index.py --output data/novels.json     # 指定输出
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sentiment_critic.data_store import build_novels_from_reviews_and_trends, save_novels
from sentiment_critic.models import read_json, write_json


def main() -> None:
    parser = argparse.ArgumentParser(description="从评论+榜单数据构建 novels.json")
    parser.add_argument("--reviews-dir", default="", help="评论 JSONL 目录，默认 Sentiment Critic/data")
    parser.add_argument("--trend-dir", default="", help="榜单数据目录，默认 data/trend_items")
    parser.add_argument("--output", default="", help="输出路径，默认 data/novels.json")
    args = parser.parse_args()

    reviews_dir = args.reviews_dir or str(ROOT / "data")
    trend_dir = args.trend_dir or str(ROOT / "data" / "trend_items")
    output = args.output or str(ROOT / "data" / "novels.json")

    print(f"[build_novel_index] Scanning reviews: {reviews_dir}")
    print(f"[build_novel_index] Scanning trends: {trend_dir}")

    novels = build_novels_from_reviews_and_trends(
        reviews_dir=reviews_dir if Path(reviews_dir).exists() else None,
        trend_items_dir=trend_dir if Path(trend_dir).exists() else None,
    )

    if not novels:
        print("[build_novel_index] No novels found. novels.json will not be overwritten without --force.")
        if "--force" not in sys.argv:
            return

    save_novels(novels)
    write_json(output, novels)
    print(f"[build_novel_index] Wrote {len(novels)} novels -> {output}")
    for novel in novels:
        print(f"  - {novel['title']} ({novel['platform']}) tags={novel.get('tags', [])}")


if __name__ == "__main__":
    main()
