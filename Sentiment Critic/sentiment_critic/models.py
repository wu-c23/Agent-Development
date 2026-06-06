from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
import hashlib
import json
import re


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def stable_review_id(platform: str, source_url: str, content: str) -> str:
    seed = f"{platform}|{source_url}|{normalize_space(content)[:800]}"
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]
    return f"{platform}-{digest}"


def generate_uid(platform_id: str, novel_title: str) -> str:
    """生成系统 UID — 遵循 System Integrator uid-specification v1.0。

    UID = SHA256(platform_id + \"|\" + novel_title)
    """
    raw = f"{platform_id}|{novel_title.strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass
class Review:
    book: str
    platform: str
    content: str
    source_url: str = ""
    title: str = ""
    author: str = ""
    created_at: str = ""
    collected_at: str = field(default_factory=now_iso)
    review_id: str = ""
    uid: str = ""                                # 系统 UID，关联 novels 表
    platform_id: str = ""                        # 源平台 ID，用于生成 UID
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.book = normalize_space(self.book)
        self.platform = normalize_space(self.platform).lower() or "unknown"
        self.content = normalize_space(self.content)
        self.title = normalize_space(self.title)
        self.author = normalize_space(self.author)
        if not self.review_id:
            self.review_id = stable_review_id(self.platform, self.source_url, self.content)
        if not self.uid and self.platform_id and self.book:
            self.uid = generate_uid(self.platform_id, self.book)

    @classmethod
    def from_dict(cls, data: dict[str, Any], fallback_book: str = "") -> "Review":
        return cls(
            book=data.get("book") or fallback_book,
            platform=data.get("platform") or "manual",
            content=data.get("content") or data.get("text") or "",
            source_url=data.get("source_url") or data.get("url") or "",
            title=data.get("title") or "",
            author=data.get("author") or "",
            created_at=data.get("created_at") or "",
            collected_at=data.get("collected_at") or now_iso(),
            review_id=data.get("review_id") or data.get("id") or "",
            uid=data.get("uid") or "",
            platform_id=data.get("platform_id") or "",
            extra=data.get("extra") or {},
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ReviewAnalysis:
    review_id: str
    platform: str
    title: str
    source_url: str
    sentiment: str
    sentiment_score: float
    writing_score: float
    logic_score: float
    update_speed_score: float
    character_score: float = 5.0                  # 人物塑造分数 [0, 10]
    toxicity_index: float = 0.0                   # 毒性指数 [0, 1]，越低越好
    one_liner: str = ""
    entry_reason: str = ""
    tags: list[str] = field(default_factory=list)
    evidence: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any], review: Review | None = None) -> "ReviewAnalysis":
        review = review or Review(book="", platform=data.get("platform", "manual"), content="")
        return cls(
            review_id=str(data.get("review_id") or review.review_id),
            platform=str(data.get("platform") or review.platform),
            title=str(data.get("title") or review.title),
            source_url=str(data.get("source_url") or review.source_url),
            sentiment=coerce_sentiment(data.get("sentiment")),
            sentiment_score=coerce_score(data.get("sentiment_score"), -1.0, 1.0, 0.0),
            writing_score=coerce_score(data.get("writing_score"), 0.0, 10.0, 5.0),
            logic_score=coerce_score(data.get("logic_score"), 0.0, 10.0, 5.0),
            update_speed_score=coerce_score(data.get("update_speed_score"), 0.0, 10.0, 5.0),
            character_score=coerce_score(data.get("character_score"), 0.0, 10.0, 5.0),
            toxicity_index=coerce_score(data.get("toxicity_index"), 0.0, 1.0, 0.0),
            one_liner=str(data.get("one_liner") or ""),
            entry_reason=str(data.get("entry_reason") or ""),
            tags=[normalize_space(str(tag)) for tag in data.get("tags", []) if normalize_space(str(tag))],
            evidence=str(data.get("evidence") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def coerce_score(value: Any, lower: float, upper: float, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    return round(max(lower, min(upper, number)), 2)


def coerce_sentiment(value: Any) -> str:
    sentiment = str(value or "neutral").lower()
    if sentiment in {"positive", "pos", "好评", "正面"}:
        return "positive"
    if sentiment in {"negative", "neg", "差评", "负面"}:
        return "negative"
    return "neutral"


def read_jsonl(path: str | Path, fallback_book: str = "") -> list[Review]:
    reviews: list[Review] = []
    target = Path(path)
    if not target.exists():
        return reviews
    with target.open("r", encoding="utf-8") as file:
        for line_no, line in enumerate(file, 1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{target}:{line_no} is not valid JSONL: {exc}") from exc
            review = Review.from_dict(data, fallback_book=fallback_book)
            if review.content:
                reviews.append(review)
    return dedupe_reviews(reviews)


def write_jsonl(path: str | Path, reviews: Iterable[Review]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="\n") as file:
        for review in reviews:
            file.write(json.dumps(review.to_dict(), ensure_ascii=False) + "\n")


def read_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as file:
        return json.load(file)


def write_json(path: str | Path, data: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="\n") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")


@dataclass
class CharacterProfile:
    """小说角色画像 — 用于角色扮演对话。"""
    id: str                                    # 角色唯一标识
    name: str                                  # 角色名
    novel: str                                 # 所属小说
    author: str = ""                           # 作者
    personality: list[str] = field(default_factory=list)  # 性格特征
    speaking_style: str = ""                   # 说话风格描述
    background: str = ""                       # 角色背景
    catchphrases: list[str] = field(default_factory=list)  # 经典台词
    knowledge_boundary: str = ""               # 角色认知边界 (in-universe only / meta)
    avatar_emoji: str = "🎭"                   # 头像 emoji

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CharacterProfile":
        return cls(
            id=str(data.get("id", "")),
            name=str(data.get("name", "")),
            novel=str(data.get("novel", "")),
            author=str(data.get("author", "")),
            personality=list(data.get("personality", [])),
            speaking_style=str(data.get("speaking_style", "")),
            background=str(data.get("background", "")),
            catchphrases=list(data.get("catchphrases", [])),
            knowledge_boundary=str(data.get("knowledge_boundary", "in-universe")),
            avatar_emoji=str(data.get("avatar_emoji", "🎭")),
        )


def dedupe_reviews(reviews: Iterable[Review]) -> list[Review]:
    seen: set[str] = set()
    unique: list[Review] = []
    for review in reviews:
        key = hashlib.sha1(
            f"{review.platform}|{normalize_space(review.content)[:500]}".encode("utf-8")
        ).hexdigest()
        if key in seen:
            continue
        seen.add(key)
        unique.append(review)
    return unique
