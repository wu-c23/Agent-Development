"""MCP server exposing SafeSearch tools for Claude Code.

Provides:
  - search_novels: full semantic search + risk-avoidance pipeline
  - index_books: add/update books in the persistent index
  - score_novel_risks: risk dimension scoring for a single novel
  - extract_search_intent: structured intent extraction from natural-language queries
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

try:
    from ..sentiment_critic.critic import score_risks
except ImportError:
    from sentiment_critic.critic import score_risks
from .config import API_KEY, CHAT_MODEL
from .engine import SafeSearchEngine
from .models import Book

mcp = FastMCP(
    "SafeSearch",
    instructions="网络小说智能搜索与避雷推荐 — 语义搜索 + 风险评分 + 自动过滤",
)

_engine: SafeSearchEngine | None = None


def _get_engine() -> SafeSearchEngine:
    global _engine
    if _engine is None:
        if not API_KEY:
            raise RuntimeError(
                "DEEPSEEK_API_KEY is not set. Copy .env.example to .env and fill in your key."
            )
        _engine = SafeSearchEngine()
    return _engine


def _dicts_to_books(books: list[dict[str, Any]]) -> list[Book]:
    return [
        Book(
            id=b["id"],
            title=b["title"],
            intro=b.get("intro", ""),
            tags=b.get("tags", []),
            status=b.get("status"),
            sentiment_summary=b.get("sentiment_summary"),
        )
        for b in books
    ]


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def index_books(books: list[dict[str, Any]]) -> dict[str, Any]:
    """Add or update books in the persistent search index.

    Books are upserted by id. After indexing, search_novels can be called
    without the books parameter to search against the persistent store.

    Parameters
    ----------
    books : list[dict]
        Books to index. Each dict needs: id, title, intro, tags (list[str]).
        Optional: status ("completed"/"ongoing"), sentiment_summary (str).
    """
    engine = _get_engine()
    book_objs = _dicts_to_books(books)
    engine.index_books(book_objs)
    return {"indexed": len(book_objs), "total_in_index": engine.store.book_count()}


@mcp.tool()
def search_novels(
    query: str,
    books: list[dict[str, Any]] | None = None,
    avoid_tags: list[str] | None = None,
    top_k: int = 10,
) -> dict[str, Any]:
    """Search novels by natural language query with automatic risk avoidance.

    If `books` is provided, they are indexed and searched on-the-fly (ad-hoc mode).
    If `books` is None, the persistent index is used (requires prior index_books call).

    Returns: query intent analysis, retrieval candidates ranked by relevance,
    risk scores for each candidate, final filtered recommendations, blocked
    results with reasons, and data quality gaps.

    Parameters
    ----------
    query : str
        Natural language query, e.g. "想看类似诡秘之主但主角不那么压抑的"
    books : list[dict] | None
        Candidate books for ad-hoc search. If None, uses persistent index.
        Each dict needs: id, title, intro, tags (list[str]).
        Optional: status ("completed"/"ongoing"), sentiment_summary (str).
    avoid_tags : list[str] | None
        Tags the user wants to avoid, e.g. ["angst", "烂尾", "虐主"].
    top_k : int
        Number of top candidates to return (default 10).
    """
    engine = _get_engine()
    book_objs = _dicts_to_books(books) if books else None
    return engine.search(query=query, avoid_tags=avoid_tags or [], top_k=top_k, books=book_objs)


@mcp.tool()
def score_novel_risks(
    title: str,
    intro: str,
    tags: list[str],
    sentiment_summary: str | None = None,
) -> dict[str, Any]:
    """Score five risk dimensions for a single novel using rules + LLM.

    Dimensions scored (0.0 = safe, 1.0 = high risk):
      - abuse_protagonist : 虐主 / protagonist abuse
      - unfinished         : 烂尾 / abandoned ending
      - melodrama          : 狗血 / over-the-top drama
      - harem              : 后宫 / harem
      - slow_pacing        : 节奏慢 / slow pacing

    Returns scores and evidence for each flagged dimension.
    """
    engine = _get_engine()
    return score_risks(
        client=engine._client,
        model=CHAT_MODEL,
        title=title,
        intro=intro,
        tags=tags,
        sentiment_summary=sentiment_summary,
    )


@mcp.tool()
def extract_search_intent(query: str) -> dict[str, Any]:
    """Extract structured search intent from a natural language query.

    Returns JSON with: summary, topics, style, protagonist_traits, mood, constraints.
    Useful for understanding what a reader is really looking for before searching.
    """
    engine = _get_engine()
    intent = engine.extract_intent(query)
    return {
        "summary": intent.summary,
        "topics": intent.topics,
        "style": intent.style,
        "protagonist_traits": intent.protagonist_traits,
        "mood": intent.mood,
        "constraints": intent.constraints,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
