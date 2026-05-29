from __future__ import annotations

from pathlib import Path
import argparse
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sentiment_critic.analyzer import analyze_reviews
from sentiment_critic.collectors import collect_reviews
from sentiment_critic.douban import collect_douban_reviews
from sentiment_critic.dashboard import render_dashboard
from sentiment_critic.models import write_json, write_jsonl


def main() -> None:
    parser = argparse.ArgumentParser(description="一键执行采集、Agent 分析、舆情看板生成。")
    parser.add_argument("--book", required=True, help="小说名")
    parser.add_argument("--platform", action="append", choices=["tieba", "douban", "xiaohongshu"], help="要搜索的平台，可重复")
    parser.add_argument("--subject-id", default="", help="豆瓣图书 subject id；只抓豆瓣时推荐填写")
    parser.add_argument("--subject-url", default="", help="豆瓣图书页面 URL；只抓豆瓣时可填写")
    parser.add_argument("--no-full-review", action="store_true", help="豆瓣模式下只抓列表摘要，不进入书评详情页")
    parser.add_argument("--keyword", default="", help="贴吧/小红书搜索关键词；默认自动拼接书名、书评、文笔、逻辑、更新")
    parser.add_argument("--no-fetch-detail", action="store_true", help="贴吧/小红书只解析搜索页摘要，不进入帖子或笔记详情")
    parser.add_argument("--thread-pages", type=int, default=1, help="贴吧每个帖子最多抓取页数")
    parser.add_argument("--url", action="append", help="指定评论页或搜索结果页 URL，可重复")
    parser.add_argument("--input-html", action="append", help="本地 HTML 文件，可重复")
    parser.add_argument("--input", default="", help="已有评论 JSONL；提供后会和抓取结果合并")
    parser.add_argument("--raw-output", default="data/raw_reviews.jsonl", help="采集结果 JSONL")
    parser.add_argument("--report-output", default="outputs/analysis_report.json", help="分析报告 JSON")
    parser.add_argument("--dashboard-output", default="outputs/sentiment_dashboard.html", help="看板 HTML")
    parser.add_argument("--max-pages", type=int, default=1)
    parser.add_argument("--min-chars", type=int, default=80)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--delay", type=float, default=2.0, help="采集请求间隔秒数")
    parser.add_argument("--timeout", type=int, default=20, help="采集请求超时秒数")
    parser.add_argument("--retries", type=int, default=2, help="采集失败重试次数")
    parser.add_argument("--batch-size", type=int, default=6)
    parser.add_argument("--no-agent", action="store_true", help="不调用模型，使用本地启发式规则")
    parser.add_argument("--require-agent", action="store_true", help="如果 Agent 不可用或调用失败，直接报错，不回退启发式规则")
    parser.add_argument("--batch-delay", type=float, default=None, help="Agent batch 之间的等待秒数，默认读取 EASYCOMPUTE_BATCH_DELAY 或 8")
    parser.add_argument("--strict", action="store_true", help="抓取失败时立即退出；默认会跳过失败页面")
    parser.add_argument("--allow-empty-output", action="store_true", help="允许用空结果覆盖输出文件并继续生成空报告")
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
            input_jsonl=args.input,
            delay=args.delay,
            timeout=args.timeout,
            retries=args.retries,
        )
    else:
        reviews = collect_reviews(
            book=args.book,
            platforms=args.platform,
            urls=args.url,
            input_html=args.input_html,
            input_jsonl=args.input,
            keyword=args.keyword,
            douban_subject_id=args.subject_id,
            douban_subject_url=args.subject_url,
            douban_fetch_full=not args.no_full_review,
            max_pages=args.max_pages,
            min_chars=args.min_chars,
            limit=args.limit,
            fetch_detail=not args.no_fetch_detail,
            thread_pages=args.thread_pages,
            delay=args.delay,
            timeout=args.timeout,
            retries=args.retries,
            strict=args.strict,
        )
    if not reviews and not args.allow_empty_output:
        print(
            "No reviews collected; existing raw/report/dashboard outputs were not overwritten. "
            "Use --allow-empty-output if you really want empty artifacts."
        )
        return
    write_jsonl(args.raw_output, reviews)

    report = analyze_reviews(
        reviews,
        use_agent=not args.no_agent,
        batch_size=args.batch_size,
        require_agent=args.require_agent,
        batch_delay=args.batch_delay,
    )
    write_json(args.report_output, report)

    dashboard = render_dashboard(report, args.dashboard_output)
    print(f"Collected {len(reviews)} reviews -> {args.raw_output}")
    print(f"Analysis report -> {args.report_output}")
    print(f"Dashboard -> {dashboard}")


if __name__ == "__main__":
    main()
