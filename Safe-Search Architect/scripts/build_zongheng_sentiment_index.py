"""从所有评论 JSONL 文件构建 sentiment_index.json，让评论数据出现在小说评论面板。

用法:
  python scripts/build_zongheng_sentiment_index.py

扫描 Sentiment Critic/data/runs/*.jsonl（含 zongheng/douban/tieba），
按书聚合评论，用启发式规则分析每本书，输出 sentiment_index.json。
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC = _PROJECT_ROOT / "Safe-Search Architect" / "src"
sys.path.insert(0, str(SRC))

from review_critic.models import (
    Review, ReviewAnalysis, dedupe_reviews, generate_uid,
    normalize_space, read_jsonl, write_json,
)
from review_critic.analyzer import heuristic_analysis

# 路径
RUNS_DIR = _PROJECT_ROOT / "Sentiment Critic" / "data" / "runs"
SENTIMENT_INDEX_PATH = _PROJECT_ROOT / "Sentiment Critic" / "data" / "sentiment_index.json"
NOVELS_PATH = _PROJECT_ROOT / "Sentiment Critic" / "data" / "novels.json"


def collect_all_reviews() -> dict[str, list[Review]]:
    """扫描所有 JSONL 文件（zongheng/douban/tieba），按书名分组。"""
    by_book: dict[str, list[Review]] = defaultdict(list)
    files = sorted(RUNS_DIR.glob("*.jsonl"))
    print(f"扫描到 {len(files)} 个评论文件")

    for f in files:
        # 从文件名推断书名（去掉平台和时间戳）
        for marker in ("_zongheng_", "_douban_", "_tieba_"):
            if marker in f.stem:
                book = f.stem.split(marker)[0]
                break
        else:
            book = f.stem[:20]  # fallback
        try:
            reviews = read_jsonl(str(f), fallback_book=book)
            by_book[book].extend(reviews)
        except Exception as e:
            print(f"  跳过 {f.name}: {e}")

    # 去重
    for book in by_book:
        by_book[book] = dedupe_reviews(by_book[book])

    total = sum(len(v) for v in by_book.values())
    print(f"聚合完成: {len(by_book)} 本书, {total} 条评论(去重后)")
    return dict(by_book)


def load_or_build_novels() -> dict[str, dict]:
    """加载 novels.json，补充缺失的纵横书籍。"""
    novels: dict[str, dict] = {}
    if NOVELS_PATH.exists():
        try:
            with NOVELS_PATH.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                for n in data:
                    title = normalize_space(n.get("title", ""))
                    if title:
                        novels[title] = n
            print(f"从 novels.json 加载 {len(novels)} 本书")
        except Exception:
            pass
    return novels


def _count_by_platform(reviews: list[Review]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for r in reviews:
        counts[r.platform or "unknown"] += 1
    return dict(counts)


def build_sentiment_index(by_book: dict[str, list[Review]]) -> dict[str, dict]:
    """对每本书运行启发式分析，生成 sentiment_index.json 格式。"""
    novels = load_or_build_novels()
    index: dict[str, dict] = {}
    missing_uid = 0
    skipped_no_uid = 0

    for book, reviews in sorted(by_book.items()):
        # 获取或生成 UID：优先使用 novels.json 中已有的 UID
        novel = novels.get(normalize_space(book))
        if novel and novel.get("uid") and novel.get("platform_id"):
            uid = novel["uid"]
        elif novel and novel.get("uid"):
            uid = novel["uid"]
        elif reviews and reviews[0].uid:
            uid = reviews[0].uid
        elif novel and novel.get("platform_id"):
            uid = generate_uid(novel["platform_id"], book)
        elif reviews and reviews[0].platform_id:
            uid = generate_uid(reviews[0].platform_id, book)
        else:
            pid = f"zongheng:{book}"
            uid = generate_uid(pid, book)
            missing_uid += 1

        if not uid:
            skipped_no_uid += 1
            continue

        # 对每条评论做启发式分析
        analyses: list[ReviewAnalysis] = []
        sentiments: list[float] = []
        for review in reviews:
            analysis = heuristic_analysis(review)
            analyses.append(analysis)
            if analysis.sentiment == "positive":
                sentiments.append(1.0)
            elif analysis.sentiment == "negative":
                sentiments.append(-1.0)
            else:
                sentiments.append(0.0)

        if not analyses:
            continue

        # 聚合分数
        n = len(analyses)
        avg_sentiment = sum(sentiments) / n if sentiments else 0
        positive_count = sum(1 for s in sentiments if s > 0)
        negative_count = sum(1 for s in sentiments if s < 0)
        neutral_count = n - positive_count - negative_count

        avg_writing = sum(a.writing_score for a in analyses) / n
        avg_logic = sum(a.logic_score for a in analyses) / n
        avg_update = sum(a.update_speed_score for a in analyses) / n
        avg_character = sum(a.character_score for a in analyses) / n
        avg_toxicity = sum(a.toxicity_index for a in analyses) / n

        # 收集所有标签
        tag_counts: dict[str, int] = defaultdict(int)
        for a in analyses:
            for tag in a.tags:
                tag_counts[tag] += 1
        top_tags = sorted(tag_counts.items(), key=lambda x: -x[1])[:5]

        # 找代表性的一句评价
        one_liner = ""
        for a in analyses:
            if a.one_liner:
                one_liner = a.one_liner
                break
        if not one_liner and reviews:
            one_liner = reviews[0].content[:120]

        # 构建 entry
        index[uid] = {
            "uid": uid,
            "overall": round((avg_sentiment + 1) * 5, 1),  # 映射到 0-10
            "style": round(avg_writing, 1),
            "logic": round(avg_logic, 1),
            "character": round(avg_character, 1),
            "update_stability": round(avg_update, 1),
            "toxicity_index": round(avg_toxicity, 2),
            "one_liner": one_liner,
            "pros": [t for t, c in top_tags if c > 1][:3],
            "cons": [],
            "review_count": n,
            "positive_ratio": round(positive_count / n, 3) if n else 0,
            "negative_ratio": round(negative_count / n, 3) if n else 0,
            "source_breakdown": _count_by_platform(reviews),
        }

        print(f"  {book}: {n} reviews, score={index[uid]['overall']:.1f}, "
              f"pos={positive_count} neg={negative_count} neu={neutral_count}")

    print(f"\n生成 {len(index)} 条 sentiment 索引")
    if missing_uid:
        print(f"  ({missing_uid} 本书使用自动生成的 UID)")
    if skipped_no_uid:
        print(f"  ({skipped_no_uid} 本书因缺少 UID 跳过)")
    return index


def update_novels_json(by_book: dict[str, list[Review]], sentiment_index: dict[str, dict]):
    """确保 novels.json 包含所有有评论的书籍。"""
    novels = load_or_build_novels()
    modified = False

    # 从 sentiment_index 找到 uid，反向建立 uid -> book 映射
    uid_to_book: dict[str, str] = {}
    for suid in sentiment_index:
        for novel in novels.values():
            if novel.get("uid") == suid:
                uid_to_book[suid] = normalize_space(novel["title"])
                break

    for book, reviews in by_book.items():
        key = normalize_space(book)
        r = reviews[0]
        pid = r.platform_id or f"{r.platform}:{book}" if r.platform else f"unknown:{book}"
        uid = r.uid or generate_uid(pid, book)

        if key not in novels:
            novels[key] = {
                "uid": uid,
                "title": book,
                "author": r.author or "",
                "platform": r.platform or "unknown",
                "platform_id": pid,
                "tags": [],
                "status": "unknown",
                "intro": "",
                "last_update": r.collected_at or "",
                "heat_score": 0.0,
            }
            modified = True
            print(f"  新增 novels.json 条目: {book}")
        elif not novels[key].get("uid"):
            novels[key]["uid"] = uid
            novels[key]["platform_id"] = novels[key].get("platform_id") or pid
            modified = True

    if modified:
        novel_list = list(novels.values())
        write_json(str(NOVELS_PATH), novel_list)
        print(f"novels.json 已更新 ({len(novel_list)} 本书)")


def main():
    print("=" * 60)
    print("构建纵横评论 sentiment_index.json")
    print("=" * 60)

    # 1. 收集所有评论
    by_book = collect_all_reviews()
    if not by_book:
        print("没有找到纵横评论文件！请先运行 collect_zongheng_reviews.py")
        return

    # 2. 分析并构建索引
    sentiment_index = build_sentiment_index(by_book)

    # 3. 写入 sentiment_index.json
    write_json(str(SENTIMENT_INDEX_PATH), sentiment_index)
    print(f"\nsentiment_index.json 已写入: {SENTIMENT_INDEX_PATH}")
    print(f"包含 {len(sentiment_index)} 本书的舆情评分")

    # 4. 更新 novels.json
    update_novels_json(by_book, sentiment_index)

    print("\n" + "=" * 60)
    print("完成！重启 Sentiment Critic API 后，评论数据将出现在小说评论面板。")
    print(f"文件位置: {SENTIMENT_INDEX_PATH}")


if __name__ == "__main__":
    main()
