from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

from .uid_utils import generate_uid


@dataclass
class Book:
    """小说数据模型 — 对齐 Data Contract v1.0。

    id 字段存储系统 UID。若创建时未提供 id，则通过 platform_id + title 自动生成。
    """

    title: str
    intro: str
    tags: List[str] = field(default_factory=list)
    id: str = ""                         # 系统 UID
    platform: str = "unknown"            # 来源平台: qidian / zongheng / douban / ...
    platform_id: str = ""                # 源平台原始 ID，用于生成 UID
    author: str = ""
    status: Optional[str] = None         # completed / ongoing
    sentiment_summary: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.id:
            pid = self.platform_id or f"{self.platform}:{self.title}"
            self.id = generate_uid(pid, self.title)

    @property
    def metadata(self) -> dict:
        """返回符合 Data Contract 的 metadata 结构。"""
        return {
            "title": self.title,
            "platform": self.platform,
            "last_update": datetime.now(timezone.utc).isoformat(),
        }


@dataclass
class IntentResult:
    summary: str = ""
    topics: List[str] = field(default_factory=list)
    style: List[str] = field(default_factory=list)
    protagonist_traits: List[str] = field(default_factory=list)
    mood: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
