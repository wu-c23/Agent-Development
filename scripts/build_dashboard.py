from __future__ import annotations

from pathlib import Path
import argparse
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sentiment_critic.dashboard import render_dashboard
from sentiment_critic.models import read_json


def main() -> None:
    parser = argparse.ArgumentParser(description="根据分析报告生成小说详情页舆情看板 HTML。")
    parser.add_argument("--report", default="outputs/analysis_report.json", help="分析报告 JSON 路径")
    parser.add_argument("--output", default="outputs/sentiment_dashboard.html", help="输出 HTML 路径")
    args = parser.parse_args()

    report = read_json(args.report)
    target = render_dashboard(report, args.output)
    print(f"Dashboard written -> {target}")


if __name__ == "__main__":
    main()
