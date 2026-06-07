"""从 Trend Explorer crawler 导入榜单数据到集中数据目录。

用法:
  python scripts/import_trend_data.py                           # 自动查找 crawler 数据
  python scripts/import_trend_data.py --source path/to/data     # 指定源目录
  python scripts/import_trend_data.py --source file.jsonl       # 指定单个文件
  python scripts/import_trend_data.py --rebuild-novels          # 导入后重建 novels.json
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DEFAULT_CRAWLER_DATA = ROOT.parent / "Trend Explorer" / "crawler-engine-v1.0" / "data"
TARGET_DIR = ROOT / "data" / "trend_items"


def find_jsonl_files(source: Path) -> list[Path]:
    if source.is_file():
        return [source] if source.suffix == ".jsonl" else []
    return sorted(source.glob("*.jsonl")) if source.exists() else []


def main() -> None:
    parser = argparse.ArgumentParser(description="从 crawler 导入榜单数据到集中目录")
    parser.add_argument("--source", default="", help=f"源路径，默认 {DEFAULT_CRAWLER_DATA}")
    parser.add_argument("--target", default="", help=f"目标目录，默认 {TARGET_DIR}")
    parser.add_argument("--rebuild-novels", action="store_true", help="导入后重建 novels.json")
    args = parser.parse_args()

    source = Path(args.source) if args.source else DEFAULT_CRAWLER_DATA
    target = Path(args.target) if args.target else TARGET_DIR

    files = find_jsonl_files(source)
    if not files:
        print(f"[import_trend] No JSONL files found in: {source}")
        print(f"[import_trend] Crawler default location: {DEFAULT_CRAWLER_DATA}")
        return

    target.mkdir(parents=True, exist_ok=True)
    imported = 0
    total_items = 0

    for src_file in files:
        dest_file = target / src_file.name
        if src_file.resolve() == dest_file.resolve():
            print(f"[import_trend] Skip same file: {src_file.name}")
            continue
        shutil.copy2(src_file, dest_file)
        item_count = 0
        try:
            with open(dest_file, encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        item_count += 1
        except OSError:
            pass
        imported += 1
        total_items += item_count
        print(f"[import_trend] {src_file.name} -> {dest_file} ({item_count} items)")

    print(f"[import_trend] Done: {imported} files, {total_items} items -> {target}")

    if args.rebuild_novels:
        from sentiment_critic.data_store import build_novels_from_reviews_and_trends, save_novels
        from sentiment_critic.models import read_json, write_json

        novels = build_novels_from_reviews_and_trends(
            reviews_dir=str(ROOT / "data"),
            trend_items_dir=str(target),
        )
        if novels:
            save_novels(novels)
            write_json(str(ROOT / "data" / "novels.json"), novels)
            print(f"[import_trend] Rebuilt novels.json with {len(novels)} entries")


if __name__ == "__main__":
    main()
