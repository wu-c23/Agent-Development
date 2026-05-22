from __future__ import annotations

from pathlib import Path
import argparse
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sentiment_critic.analyzer import analyze_reviews
from sentiment_critic.models import read_jsonl, write_json


def main() -> None:
    parser = argparse.ArgumentParser(description="调用 Agent 对书评做多维舆情分析。")
    parser.add_argument("--input", default="data/raw_reviews.jsonl", help="评论 JSONL 路径")
    parser.add_argument("--output", default="outputs/analysis_report.json", help="分析报告 JSON 路径")
    parser.add_argument("--book", default="", help="当输入数据缺少 book 字段时使用")
    parser.add_argument("--batch-size", type=int, default=6, help="每次发给 Agent 的评论数")
    parser.add_argument("--no-agent", action="store_true", help="不调用模型，使用本地启发式规则兜底")
    parser.add_argument("--require-agent", action="store_true", help="如果 Agent 不可用或调用失败，直接报错，不回退启发式规则")
    parser.add_argument("--batch-delay", type=float, default=None, help="Agent batch 之间的等待秒数，默认读取 EASYCOMPUTE_BATCH_DELAY 或 8")
    args = parser.parse_args()

    reviews = read_jsonl(args.input, fallback_book=args.book)
    report = analyze_reviews(
        reviews,
        use_agent=not args.no_agent,
        batch_size=args.batch_size,
        require_agent=args.require_agent,
        batch_delay=args.batch_delay,
    )
    write_json(args.output, report)
    print(f"Analyzed {len(reviews)} reviews -> {args.output}")


if __name__ == "__main__":
    main()
