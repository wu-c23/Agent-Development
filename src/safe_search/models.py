from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Book:
    id: str
    title: str
    intro: str
    tags: List[str]
    status: Optional[str] = None
    sentiment_summary: Optional[str] = None
