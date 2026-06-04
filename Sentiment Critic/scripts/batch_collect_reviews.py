"""批量采集评论 — 从 novels.json 读取小说列表，一键采集多个平台的评论。

用法:
  # 从榜单 Top 10 采集（默认：豆瓣+起点）
  python scripts/batch_collect_reviews.py --top 10

  # 指定平台 + 指定本数
  python scripts/batch_collect_reviews.py --top 20 --platform douban
  python scripts/batch_collect_reviews.py --top 5 --platform qidian --platform douban

  # 按热度阈值筛选
  python scripts/batch_collect_reviews.py --min-heat 500 --limit 100

  # 按标签筛选 + 仅采集
  python scripts/batch_collect_reviews.py --tags 修仙 --top 10

  # 全部采集（慎用，速度慢）
  python scripts/batch_collect_reviews.py --all --platform douban

采集结果写入 data/runs/{书名}_{平台}_{时间}.jsonl
"""

from __future__ import annotations

import argparse
import random
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RUNS_DIR = DATA_DIR / "runs"
RUNS_DIR.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT))


def load_novels() -> list[dict]:
    """从集中数据源加载小说列表。"""
    from sentiment_critic.data_store import get_all_novels, reload

    reload()
    return get_all_novels()


def filter_novels(novels: list[dict], args: argparse.Namespace) -> list[dict]:
    """根据参数筛选小说。"""
    result = novels

    # 按热度筛选
    if args.min_heat > 0:
        result = [n for n in result if n.get("heat_score", 0) >= args.min_heat]

    # 按标签筛选
    if args.tags:
        tags_lower = set(t.lower() for t in args.tags)
        result = []
        for n in novels:
            novel_tags = set(t.lower() for t in n.get("tags", []))
            if tags_lower & novel_tags:
                result.append(n)

    # 按平台筛选
    if args.filter_platform:
        result = [n for n in result if n.get("platform", "").lower() in args.filter_platform]

    # 排行榜前 N
    if args.top > 0:
        # 按热度降序
        result.sort(key=lambda n: n.get("heat_score", 0), reverse=True)
        result = result[: args.top]

    if args.limit_novels > 0:
        result = result[: args.limit_novels]

    return result


def collect_one(
    title: str,
    platform: str,
    pages: int,
    limit: int,
    delay: float,
) -> tuple[str, int]:
    """采集单本书的评论，返回 (文件名, 评论数)。"""
    from sentiment_critic.collectors import collect_reviews

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_title = "".join(c for c in title if c.isalnum() or c in " _-")[:30].strip()
    output_path = RUNS_DIR / f"{safe_title}_{platform}_{timestamp}.jsonl"

    reviews = collect_reviews(
        book=title,
        platforms=[platform],
        max_pages=pages,
        min_chars=60,
        limit=limit,
        delay=delay,
    )

    if reviews:
        from sentiment_critic.models import write_jsonl

        write_jsonl(str(output_path), reviews)
        return str(output_path.name), len(reviews)
    return "", 0


def main() -> None:
    parser = argparse.ArgumentParser(description="从 novels.json 批量采集评论")
    parser.add_argument("--top", type=int, default=0, help="排行榜前 N 本（按热度）")
    parser.add_argument("--all", action="store_true", help="采集所有已索引小说（慎用）")
    parser.add_argument("--min-heat", type=float, default=0, help="最低热度阈值")
    parser.add_argument("--tags", nargs="*", default=[], help="按标签筛选")
    parser.add_argument("--filter-platform", nargs="*", default=[], help="仅某平台的书籍")
    parser.add_argument("--platform", nargs="*", default=["qidian", "douban"],
                        choices=["qidian", "douban", "tieba", "xiaohongshu"],
                        help="采集哪些平台（默认 qidian douban）")
    parser.add_argument("--pages", type=int, default=2, help="每本书每平台采集页数")
    parser.add_argument("--limit", type=int, default=100, help="每本书每平台最多评论数")
    parser.add_argument("--limit-novels", type=int, default=0, help="最多采集几本书")
    parser.add_argument("--delay", type=float, default=2.0, help="请求间隔（秒）")
    parser.add_argument("--skip-existing", action="store_true", help="跳过已有评论数据的书籍")
    args = parser.parse_args()

    if not args.top and not args.all and args.min_heat <= 0 and not args.limit_novels:
        parser.error("请指定 --top N、--all、--min-heat 或 --limit-novels")

    novels = load_novels()
    print(f"[batch] Total novels in index: {len(novels)}")

    candidates = filter_novels(novels, args)
    print(f"[batch] Candidates after filter: {len(candidates)}")

    total_collected = 0
    success_count = 0
    skip_count = 0

    for i, novel in enumerate(candidates):
        title = novel.get("title", "")
        if not title:
            continue

        novel_platform = novel.get("platform", "").lower()
        heat = novel.get("heat_score", 0)

        # 根据书籍平台自动选择采集平台
        platforms_to_try = list(args.platform)
        if "qidian" in platforms_to_try and novel_platform not in ("qidian", "起点中文网", ""):
            platforms_to_try.remove("qidian")
            if not platforms_to_try:
                platforms_to_try = ["douban"]  # 兜底

        print(f"\n[{i+1}/{len(candidates)}] {title} (heat={heat}, platform={novel_platform})")

        for platform in platforms_to_try:
            # 添加随机延迟避免被封
            actual_delay = args.delay + random.uniform(0, 1.5)
            print(f"  [{platform}] Collecting...")
            filename, count = collect_one(
                title=title,
                platform=platform,
                pages=args.pages,
                limit=args.limit,
                delay=actual_delay,
            )
            if count > 0:
                print(f"  [{platform}] -> {filename} ({count} reviews)")
                total_collected += count
                success_count += 1
            else:
                print(f"  [{platform}] -> No reviews found")
                skip_count += 1

    print(f"\n[batch] Done: {success_count} collected, {skip_count} skipped, {total_collected} total reviews -> {RUNS_DIR}")


if __name__ == "__main__":
    main()
