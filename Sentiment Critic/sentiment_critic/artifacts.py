from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re


def timestamp_slug() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def safe_slug(value: str, fallback: str = "book") -> str:
    value = re.sub(r"\s+", "_", value.strip())
    value = re.sub(r'[\\/:*?"<>|]+', "_", value)
    value = re.sub(r"_+", "_", value).strip("._ ")
    return value or fallback


def platform_slug(platforms: list[str] | None, fallback: str = "reviews") -> str:
    if not platforms:
        return fallback
    return "_".join(safe_slug(platform, "platform") for platform in platforms)


def unique_path(path: str | Path) -> Path:
    target = Path(path)
    if not target.exists():
        return target
    stem = target.stem
    suffix = target.suffix
    for index in range(2, 10_000):
        candidate = target.with_name(f"{stem}_{index}{suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Could not find a free output path near {target}")


def default_collect_output(book: str, platforms: list[str] | None = None) -> Path:
    name = f"{safe_slug(book)}_{platform_slug(platforms)}_{timestamp_slug()}.jsonl"
    return Path("data") / "runs" / name


def default_pipeline_outputs(book: str, platforms: list[str] | None = None) -> tuple[Path, Path, Path]:
    run_id = f"{safe_slug(book)}_{platform_slug(platforms, 'douban_tieba')}_{timestamp_slug()}"
    run_dir = Path("outputs") / "runs" / run_id
    return (
        run_dir / "raw_reviews.jsonl",
        run_dir / "analysis_report.json",
        run_dir / "sentiment_dashboard.html",
    )
