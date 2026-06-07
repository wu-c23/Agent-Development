"""一键刷新全流程：采集评论 → 分析 → 建索引 → 刷新 API 缓存。

用法:
  python scripts/refresh_all_data.py                    # 仅从已有数据重建索引
  python scripts/refresh_all_data.py --collect            # 先采集新评论
  python scripts/refresh_all_data.py --book 诡秘之主      # 指定书名采集+分析

采集参数透传给 collect_reviews.py 和 run_sentiment_pipeline.py。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT))


def run(cmd: list[str], description: str) -> bool:
    print(f"\n{'='*60}")
    print(f"[refresh] {description}")
    print(f"[refresh] CMD: {' '.join(cmd)}")
    print(f"{'='*60}")
    result = subprocess.run(cmd, cwd=str(ROOT))
    if result.returncode != 0:
        print(f"[refresh] FAILED: {description}")
        return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="一键刷新全流程数据")
    parser.add_argument("--collect", action="store_true", help="先采集评论（从豆瓣/贴吧等）")
    parser.add_argument("--analyze", action="store_true", help="运行分析（采集后自动分析）")
    parser.add_argument("--book", default="", help="采集+分析的目标书名")
    parser.add_argument("--platform", action="append", choices=["douban", "tieba", "xiaohongshu"],
                        help="平台，可重复")
    parser.add_argument("--input", default="", help="已有评论 JSONL（跳过采集直接用）")
    parser.add_argument("--max-pages", type=int, default=1, help="搜索页数")
    parser.add_argument("--limit", type=int, default=100, help="最多保留评论数")
    parser.add_argument("--no-agent", action="store_true", help="不使用 LLM Agent")
    parser.add_argument("--no-collect", action="store_true", help="跳过采集，仅从已有数据重建索引")
    parser.add_argument("--skip-refresh-api", action="store_true", help="建完索引后不刷新 API 缓存")
    args = parser.parse_args()

    success = True

    # Step 1: 采集评论
    if args.collect and args.book and not args.no_collect:
        cmd = [
            sys.executable, str(SCRIPTS / "collect_reviews.py"),
            "--book", args.book,
            "--max-pages", str(args.max_pages),
            "--limit", str(args.limit),
        ]
        if args.platform:
            for p in args.platform:
                cmd.extend(["--platform", p])
        success = run(cmd, "Step 1: Collect reviews") and success

    # Step 2: 分析评论
    if (args.analyze or args.book) and not args.no_collect:
        if args.book and (args.collect or args.input):
            cmd = [
                sys.executable, str(SCRIPTS / "analyze_reviews.py"),
                "--input", args.input or str(ROOT / "data" / "raw_reviews.jsonl"),
                "--book", args.book,
            ]
            if args.no_agent:
                cmd.append("--no-agent")
            success = run(cmd, "Step 2: Analyze reviews") and success

    # Step 3: 构建小说索引
    success = run(
        [sys.executable, str(SCRIPTS / "build_novel_index.py")],
        "Step 3: Build novels.json",
    ) and success

    # Step 4: 构建舆情索引
    success = run(
        [sys.executable, str(SCRIPTS / "build_sentiment_index.py")],
        "Step 4: Build sentiment_index.json",
    ) and success

    # Step 5: 刷新 API 缓存
    if not args.skip_refresh_api:
        try:
            from sentiment_critic.data_store import reload as reload_store
            from sentiment_critic.data_store import build_mock_sentiment_store
            reload_store()
            store = build_mock_sentiment_store()
            print(f"\n[refresh] Step 5: API cache refreshed — {len(store)} entries loaded")
        except Exception as exc:
            print(f"[refresh] Step 5: API refresh skipped (API not running): {exc}")

    if success:
        print("\n[refresh] All steps completed successfully.")
    else:
        print("\n[refresh] Some steps failed. Check output above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
