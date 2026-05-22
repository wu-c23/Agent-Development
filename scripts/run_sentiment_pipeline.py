from __future__ import annotations

from pathlib import Path
import argparse
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sentiment_critic.analyzer import analyze_reviews
from sentiment_critic.collectors import collect_reviews
from sentiment_critic.dashboard import render_dashboard
from sentiment_critic.models import write_json, write_jsonl


def main() -> None:
    parser = argparse.ArgumentParser(description="一键执行采集、Agent 分析、舆情看板生成。")
    parser.add_argument("--book", required=True, help="小说名")
    parser.add_argument("--platform", action="append", choices=["tieba", "douban", "xiaohongshu"], help="要搜索的平台，可重复")
    parser.add_argument("--url", action="append", help="指定评论页或搜索结果页 URL，可重复")
    parser.add_argument("--input-html", action="append", help="本地 HTML 文件，可重复")
    parser.add_argument("--input", default="", help="已有评论 JSONL；提供后会和抓取结果合并")
    parser.add_argument("--raw-output", default="data/raw_reviews.jsonl", help="采集结果 JSONL")
    parser.add_argument("--report-output", default="outputs/analysis_report.json", help="分析报告 JSON")
    parser.add_argument("--dashboard-output", default="outputs/sentiment_dashboard.html", help="看板 HTML")
    parser.add_argument("--max-pages", type=int, default=1)
    parser.add_argument("--min-chars", type=int, default=80)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=6)
    parser.add_argument("--no-agent", action="store_true", help="不调用模型，使用本地启发式规则")
    args = parser.parse_args()

    reviews = collect_reviews(
        book=args.book,
        platforms=args.platform,
        urls=args.url,
        input_html=args.input_html,
        input_jsonl=args.input,
        max_pages=args.max_pages,
        min_chars=args.min_chars,
        limit=args.limit,
    )
    write_jsonl(args.raw_output, reviews)

    report = analyze_reviews(reviews, use_agent=not args.no_agent, batch_size=args.batch_size)
    write_json(args.report_output, report)

    dashboard = render_dashboard(report, args.dashboard_output)
    print(f"Collected {len(reviews)} reviews -> {args.raw_output}")
    print(f"Analysis report -> {args.report_output}")
    print(f"Dashboard -> {dashboard}")


if __name__ == "__main__":
    main()
