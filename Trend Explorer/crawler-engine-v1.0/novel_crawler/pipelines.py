from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from itemadapter import ItemAdapter
from scrapy.exceptions import DropItem

from novel_crawler.items import make_trend_id, normalize_tags, utc_now_iso


class TrendItemValidationPipeline:
    """Validate and normalize spider output before it reaches storage."""

    required_fields = ("title", "platform", "rank", "heatScore", "listType", "capturedAt")

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)

        if not adapter.get("capturedAt"):
            adapter["capturedAt"] = utc_now_iso()

        adapter["title"] = self._clean_string(adapter.get("title"))
        adapter["platform"] = self._clean_string(adapter.get("platform"))
        adapter["listType"] = self._clean_string(adapter.get("listType"))
        adapter["author"] = self._clean_string(adapter.get("author"))
        adapter["category"] = self._clean_string(adapter.get("category"))
        adapter["summary"] = self._clean_string(adapter.get("summary"))
        adapter["sourceUrl"] = self._clean_string(adapter.get("sourceUrl"))
        adapter["detailUrl"] = self._clean_string(adapter.get("detailUrl"))
        adapter["tags"] = normalize_tags(adapter.get("tags"))
        adapter["rank"] = self._to_int(adapter.get("rank"), default=0)
        adapter["rankChange"] = self._to_int(adapter.get("rankChange"), default=0)
        adapter["heatScore"] = self._to_float(adapter.get("heatScore"), default=0.0)

        if not adapter.get("id"):
            adapter["id"] = make_trend_id(
                adapter.get("platform", ""),
                adapter.get("listType", ""),
                adapter.get("title", ""),
                adapter.get("capturedAt", ""),
            )

        missing = [field for field in self.required_fields if adapter.get(field) in (None, "", [])]
        if missing:
            raise DropItem(f"Drop invalid trend item, missing fields: {missing}")

        return item

    @staticmethod
    def _clean_string(value) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(str(value).strip().split())
        return cleaned or None

    @staticmethod
    def _to_int(value, default: int) -> int:
        try:
            return int(float(str(value).strip()))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _to_float(value, default: float) -> float:
        try:
            return float(str(value).strip())
        except (TypeError, ValueError):
            return default


class JsonLinesWriterPipeline:
    """Persist normalized trend items into local JSONL files."""

    def open_spider(self, spider):
        output_dir = Path(os.getenv("OUTPUT_DIR", spider.settings.get("OUTPUT_DIR", "data")))
        output_dir.mkdir(parents=True, exist_ok=True)
        prefix = os.getenv("OUTPUT_FILE_PREFIX", spider.settings.get("OUTPUT_FILE_PREFIX", "trend_items"))
        if spider.settings.getbool("OUTPUT_INCLUDE_SPIDER"):
            prefix = f"{prefix}_{spider.name}"
        run_id = os.getenv("OUTPUT_RUN_ID") or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.output_path = output_dir / f"{prefix}_{run_id}.jsonl"
        self.file = self.output_path.open("w", encoding="utf-8")
        spider.logger.info("JSONL output enabled: %s", self.output_path)

    def close_spider(self, spider):
        if getattr(self, "file", None):
            self.file.close()
            spider.logger.info("JSONL output closed: %s", self.output_path)

    def process_item(self, item, spider):
        payload = dict(ItemAdapter(item))
        self.file.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self.file.flush()
        return item


class DatabaseSinkPipeline:
    """Placeholder for PostgreSQL, MongoDB, or stream sink integration."""

    def __init__(self, enabled: bool):
        self.enabled = enabled

    @classmethod
    def from_crawler(cls, crawler):
        return cls(enabled=crawler.settings.getbool("DATABASE_SINK_ENABLED", False))

    def open_spider(self, spider):
        if self.enabled:
            spider.logger.warning("DATABASE_SINK_ENABLED=true, but no concrete DB sink is configured yet.")

    def process_item(self, item, spider):
        return item
