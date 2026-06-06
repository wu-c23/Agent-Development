"""批量豆瓣采集 — 仅使用 book.douban.com subject_suggest 定位条目。

这个脚本用于没有 DOUBAN_COOKIE 时的保守批量采集：
  1. 从 data/novels.json 读取榜单书籍
  2. 先调用 book.douban.com/j/subject_suggest 解析 subject id
  3. 能解析到 subject 的书再抓豆瓣书评列表
  4. 解析不到的书直接记录 no_subject，避免继续访问容易 403 的搜索兜底

用法:
  python scripts/batch_collect_douban_suggest.py --all
  python scripts/batch_collect_douban_suggest.py --top 50 --skip-existing
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RUNS_DIR = DATA_DIR / "runs"
RUNS_DIR.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT))


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def safe_title(value: str) -> str:
    return "".join(c for c in value if c.isalnum() or c in " _-")[:30].strip() or "book"


def write_manifest(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_novels() -> list[dict[str, Any]]:
    from sentiment_critic.data_store import get_all_novels, reload

    reload()
    return get_all_novels()


def filter_novels(novels: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    result = list(novels)
    if args.min_heat > 0:
        result = [n for n in result if n.get("heat_score", 0) >= args.min_heat]
    if args.tags:
        tags_lower = {t.lower() for t in args.tags}
        result = [
            n for n in result
            if tags_lower & {str(t).lower() for t in n.get("tags", [])}
        ]
    if args.filter_platform:
        allowed = {p.lower() for p in args.filter_platform}
        result = [n for n in result if str(n.get("platform", "")).lower() in allowed]
    if args.top > 0:
        result.sort(key=lambda n: n.get("heat_score", 0), reverse=True)
        result = result[: args.top]
    if args.limit_novels > 0:
        result = result[: args.limit_novels]
    return result


def load_existing_douban_books() -> set[str]:
    from sentiment_critic.models import read_jsonl

    existing: set[str] = set()
    for path in list(DATA_DIR.glob("*.jsonl")) + list(RUNS_DIR.glob("*.jsonl")):
        try:
            reviews = read_jsonl(path)
        except (OSError, ValueError):
            continue
        for review in reviews:
            if review.platform == "douban" and review.book:
                existing.add(review.book)
    return existing


def choose_subject(book: str, subjects: list[Any]) -> Any | None:
    if not subjects:
        return None
    normalized_book = normalize_title(book)
    for subject in subjects:
        if normalize_title(getattr(subject, "title", "")) == normalized_book:
            return subject
    for subject in subjects:
        title = normalize_title(getattr(subject, "title", ""))
        if normalized_book and (normalized_book in title or title in normalized_book):
            return subject
    return subjects[0]


def normalize_title(value: str) -> str:
    value = re.sub(r"[（(].*?[）)]", "", value or "")
    return re.sub(r"\s+", "", value).strip().lower()


def collect_subject_reviews(
    book: str,
    subject_id: str,
    pages: int,
    limit: int,
    min_chars: int,
    delay: float,
    timeout: int,
    retries: int,
    fetch_full: bool,
) -> tuple[str, int]:
    from sentiment_critic.douban import collect_douban_reviews
    from sentiment_critic.models import write_jsonl

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = RUNS_DIR / f"{safe_title(book)}_douban_{timestamp}.jsonl"
    reviews = collect_douban_reviews(
        book=book,
        subject_id=subject_id,
        pages=pages,
        limit=limit,
        min_chars=min_chars,
        fetch_full=fetch_full,
        delay=delay,
        timeout=timeout,
        retries=retries,
        strict=False,
    )
    if not reviews:
        return "", 0
    write_jsonl(output_path, reviews)
    return output_path.name, len(reviews)


def main() -> None:
    parser = argparse.ArgumentParser(description="用豆瓣 subject_suggest 批量采集榜单豆瓣书评")
    parser.add_argument("--top", type=int, default=0, help="排行榜前 N 本（按热度）")
    parser.add_argument("--all", action="store_true", help="采集所有已索引小说")
    parser.add_argument("--min-heat", type=float, default=0, help="最低热度阈值")
    parser.add_argument("--tags", nargs="*", default=[], help="按标签筛选")
    parser.add_argument("--filter-platform", nargs="*", default=[], help="仅某平台的书籍")
    parser.add_argument("--limit-novels", type=int, default=0, help="最多采集几本书")
    parser.add_argument("--pages", type=int, default=1, help="每本书采集豆瓣书评页数")
    parser.add_argument("--limit", type=int, default=10, help="每本书最多保留评论数")
    parser.add_argument("--min-chars", type=int, default=60, help="评论正文最小字数")
    parser.add_argument("--delay", type=float, default=0.5, help="请求间隔秒数")
    parser.add_argument("--timeout", type=int, default=12, help="请求超时秒数")
    parser.add_argument("--retries", type=int, default=0, help="失败重试次数")
    parser.add_argument("--no-full-review", action="store_true", help="只抓列表摘要，不进入详情页")
    parser.add_argument("--skip-existing", action="store_true", help="跳过已有豆瓣评论的书")
    parser.add_argument("--manifest", default="", help="批量任务记录 JSON")
    args = parser.parse_args()

    if not args.top and not args.all and args.min_heat <= 0 and not args.limit_novels:
        parser.error("请指定 --top N、--all、--min-heat 或 --limit-novels")

    from sentiment_critic.douban import DoubanBookReviewCrawler, save_subject_cache

    novels = filter_novels(load_novels(), args)
    manifest_path = Path(args.manifest) if args.manifest else (
        RUNS_DIR / f"batch_collect_all_douban_suggest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    manifest: dict[str, Any] = {
        "started_at": now_iso(),
        "source": str(DATA_DIR / "novels.json"),
        "candidate_count": len(novels),
        "mode": "douban_subject_suggest",
        "items": [],
    }
    write_manifest(manifest_path, manifest)

    existing = load_existing_douban_books() if args.skip_existing else set()
    crawler = DoubanBookReviewCrawler(delay=args.delay, timeout=args.timeout, retries=args.retries)

    counts = {"collected": 0, "empty": 0, "no_subject": 0, "skipped_existing": 0, "error": 0}
    total_reviews = 0
    print(f"[douban-batch] Candidates: {len(novels)}")
    print(f"[douban-batch] Existing douban books: {len(existing)}")
    print(f"[douban-batch] Manifest: {manifest_path}")

    for index, novel in enumerate(novels, 1):
        title = str(novel.get("title") or "").strip()
        if not title:
            continue
        item: dict[str, Any] = {
            "index": index,
            "title": title,
            "heat_score": novel.get("heat_score", 0),
            "status": "pending",
            "started_at": now_iso(),
        }
        manifest["items"].append(item)
        print(f"\n[{index}/{len(novels)}] {title}")

        if args.skip_existing and title in existing:
            item["status"] = "skipped_existing"
            item["finished_at"] = now_iso()
            counts["skipped_existing"] += 1
            print("  -> skipped existing")
            write_manifest(manifest_path, manifest)
            continue

        try:
            subjects = crawler.search_subjects_suggest(title, limit=5)
            subject = choose_subject(title, subjects)
            if subject is None:
                item["status"] = "no_subject"
                counts["no_subject"] += 1
                print("  -> no subject")
            else:
                item["subject_id"] = subject.subject_id
                item["subject_title"] = subject.title
                item["subject_url"] = subject.url
                save_subject_cache(subject, title)
                actual_delay = args.delay + random.uniform(0, 0.4)
                filename, review_count = collect_subject_reviews(
                    book=title,
                    subject_id=subject.subject_id,
                    pages=args.pages,
                    limit=args.limit,
                    min_chars=args.min_chars,
                    delay=actual_delay,
                    timeout=args.timeout,
                    retries=args.retries,
                    fetch_full=not args.no_full_review,
                )
                item["review_count"] = review_count
                if review_count > 0:
                    item["status"] = "collected"
                    item["output"] = filename
                    counts["collected"] += 1
                    total_reviews += review_count
                    print(f"  -> {filename} ({review_count} reviews)")
                else:
                    item["status"] = "empty"
                    counts["empty"] += 1
                    print("  -> empty")
        except Exception as exc:  # noqa: BLE001 - batch job should keep going.
            item["status"] = "error"
            item["error"] = str(exc)
            counts["error"] += 1
            print(f"  -> error: {exc}")

        item["finished_at"] = now_iso()
        write_manifest(manifest_path, manifest)

    manifest["finished_at"] = now_iso()
    manifest["summary"] = {**counts, "total_reviews": total_reviews}
    write_manifest(manifest_path, manifest)
    print(f"\n[douban-batch] Done: {manifest['summary']}")


if __name__ == "__main__":
    main()
