from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Iterable

import scrapy


class TrendItem(scrapy.Item):
    """Unified trend record shared by spiders, pipelines, APIs, and dashboard."""

    uid = scrapy.Field()
    id = scrapy.Field()
    title = scrapy.Field()
    author = scrapy.Field()
    platform = scrapy.Field()
    rank = scrapy.Field()
    rankChange = scrapy.Field()
    category = scrapy.Field()
    tags = scrapy.Field()
    heatScore = scrapy.Field()
    listType = scrapy.Field()
    summary = scrapy.Field()
    capturedAt = scrapy.Field()
    sourceUrl = scrapy.Field()
    detailUrl = scrapy.Field()


def generate_uid(platform_id: str, novel_title: str) -> str:
    """Generate SHA256 UID per System Integrator spec: SHA256(platform_id + "|" + novel_title)."""
    raw = f"{platform_id}|{novel_title.strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def utc_now_iso() -> str:
    """Return a timezone-aware UTC timestamp in API-friendly ISO format."""

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def make_trend_id(platform: str, list_type: str, title: str, captured_at: str) -> str:
    """Build a stable id from the business identity of a captured trend item."""

    day = captured_at[:10] if captured_at else utc_now_iso()[:10]
    raw = f"{platform}|{list_type}|{title}|{day}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def normalize_tags(tags: str | Iterable[str] | None) -> list[str]:
    """Normalize tag input from selectors into a de-duplicated string list."""

    if tags is None:
        return []
    if isinstance(tags, str):
        parts = tags.replace("/", ",").replace("、", ",").replace("|", ",").split(",")
    else:
        parts = [str(tag) for tag in tags]

    seen: set[str] = set()
    normalized: list[str] = []
    for tag in parts:
        value = " ".join(tag.strip().split())
        if value and value not in seen:
            seen.add(value)
            normalized.append(value)
    return normalized
