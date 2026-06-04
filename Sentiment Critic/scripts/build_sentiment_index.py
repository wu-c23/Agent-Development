"""从评论数据和分析报告构建 sentiment_index.json 舆情评分索引。

用法:
  python scripts/build_sentiment_index.py                      # 自动扫描 data/runs + outputs/runs
  python scripts/build_sentiment_index.py --analyze             # 同时运行分析（需要 LLM）
  python scripts/build_sentiment_index.py --no-agent            # 分析时只用启发式，不调 LLM
  python scripts/build_sentiment_index.py --reports-dir outputs/runs
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sentiment_critic.data_store import (
    build_sentiment_from_analysis_reports,
    build_novels_from_reviews_and_trends,
    save_novels,
    save_sentiment_index,
    reload,
)
from sentiment_critic.models import read_jsonl, write_json


def find_review_files() -> list[tuple[str, Path]]:
    """扫描 data/ 下所有 JSONL 评论文件，返回 [(书名, 路径), ...]。

    同时扫描 data/runs/ (批量采集输出) 和 data/ 根目录。
    """
    results: list[tuple[str, Path]] = []
    search_dirs = [ROOT / "data" / "runs", ROOT / "data"]
    seen: set[str] = set()

    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        for jsonl_file in sorted(search_dir.glob("*.jsonl")):
            if jsonl_file.stat().st_size == 0:
                continue
            # 提取书名: 文件命名格式为 {书名}_{平台}_{时间}.jsonl
            stem = jsonl_file.stem
            book = stem.rsplit("_", 2)[0] if "_" in stem else stem
            if book not in seen:
                seen.add(book)
                results.append((book, jsonl_file))

    return results


def analyze_book(book: str, input_path: Path, use_agent: bool = True) -> dict | None:
    """对单本书的评论运行分析，返回报告 dict。"""
    from sentiment_critic.models import Review
    from sentiment_critic.analyzer import analyze_reviews

    reviews = read_jsonl(str(input_path), fallback_book=book)
    if not reviews:
        print(f"  [skip] No valid reviews in {input_path.name}")
        return None

    print(f"  Analyzing {len(reviews)} reviews...")
    try:
        report = analyze_reviews(reviews, use_agent=use_agent, batch_size=4)
        return report
    except Exception as exc:
        print(f"  [warn] Analysis failed: {exc}")
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="从评论/报告构建 sentiment_index.json")
    parser.add_argument("--reports-dir", default="", help="分析报告目录，默认扫描 outputs/runs + data/runs")
    parser.add_argument("--analyze", action="store_true", help="自动对 data/runs 中的评论运行分析")
    parser.add_argument("--no-agent", action="store_true", help="分析时仅使用启发式规则（更快）")
    parser.add_argument("--output", default="", help="输出路径，默认 data/sentiment_index.json")
    args = parser.parse_args()

    output = args.output or str(ROOT / "data" / "sentiment_index.json")

    # Step 1: 先扫描分析报告
    reports_dir = args.reports_dir or str(ROOT / "outputs" / "runs")
    print(f"[build_sentiment_index] Scanning reports: {reports_dir}")
    index = build_sentiment_from_analysis_reports(reports_dir)

    # Step 2: 如果无报告且有评论文件，自动运行分析
    if not index or args.analyze:
        review_files = find_review_files()
        if review_files:
            print(f"[build_sentiment_index] Found {len(review_files)} review files:")
            for book, path in review_files:
                print(f"  - {book}: {path.name}")

            if args.analyze:
                use_agent = not args.no_agent
                for book, path in review_files:
                    uid = _find_uid_for_book(book)
                    if uid and uid in index:
                        print(f"[build_sentiment_index] Skip {book} (already in index)")
                        continue
                    print(f"\n[analyze] {book} <- {path}")
                    report = analyze_book(book, path, use_agent=use_agent)
                    if report:
                        # Save report
                        runs_dir = ROOT / "outputs" / "runs"
                        runs_dir.mkdir(parents=True, exist_ok=True)
                        report_path = runs_dir / f"analysis_report_{book}.json"
                        write_json(str(report_path), report)
                        print(f"  Report saved: {report_path}")
            else:
                print("[build_sentiment_index] Use --analyze to run analysis automatically.")
        else:
            print("[build_sentiment_index] No review files found in data/runs/ or data/.")

    # Step 3: 重新扫描（包含刚才生成的报告）
    index = build_sentiment_from_analysis_reports(reports_dir)

    if not index:
        print("[build_sentiment_index] No sentiment entries generated.")
        print("  Collect reviews:  python scripts/batch_collect_reviews.py --top 5")
        print("  Then:             python scripts/build_sentiment_index.py --analyze")
        return

    save_sentiment_index(index)
    write_json(output, index)
    print(f"\n[build_sentiment_index] Wrote {len(index)} sentiment entries -> {output}")
    for uid, entry in list(index.items())[:10]:
        print(f"  - {uid[:16]}... overall={entry.get('overall', 0)} reviews={entry.get('review_count', 0)}")


def _find_uid_for_book(book: str) -> str:
    """根据书名查找 UID。"""
    from sentiment_critic.data_store import get_novel_by_title
    reload()
    novel = get_novel_by_title(book)
    return novel["uid"] if novel else ""


if __name__ == "__main__":
    main()
