from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Book:
    id: str
    title: str
    intro: str
    tags: List[str]
    status: Optional[str] = None
    sentiment_summary: Optional[str] = None


@dataclass
class IntentResult:
    summary: str = ""
    topics: List[str] = field(default_factory=list)
    style: List[str] = field(default_factory=list)
    protagonist_traits: List[str] = field(default_factory=list)
    mood: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
