from __future__ import annotations

from pathlib import Path
import argparse
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sentiment_critic.artifacts import safe_slug, timestamp_slug, unique_path
from sentiment_critic.dashboard import render_dashboard
from sentiment_critic.models import read_json


def main() -> None:
    parser = argparse.ArgumentParser(description="根据分析报告生成小说详情页舆情看板 HTML。")
    parser.add_argument("--report", default="outputs/analysis_report.json", help="分析报告 JSON 路径")
    parser.add_argument("--output", default="", help="输出 HTML 路径；不填时自动生成不覆盖的文件名")
    parser.add_argument("--overwrite", action="store_true", help="允许覆盖显式指定的输出文件")
    args = parser.parse_args()

    report = read_json(args.report)
    output = resolve_output(args, str(report.get("book") or Path(args.report).stem))
    target = render_dashboard(report, output)
    print(f"Dashboard written -> {target}")


def resolve_output(args: argparse.Namespace, book: str) -> Path:
    if args.output:
        path = Path(args.output)
        return path if args.overwrite else unique_path(path)
    return Path("outputs") / "runs" / f"{safe_slug(book)}_dashboard_{timestamp_slug()}.html"


if __name__ == "__main__":
    main()
