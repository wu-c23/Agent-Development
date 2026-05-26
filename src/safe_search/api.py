"""FastAPI REST application for SafeSearch.

Endpoints:
  POST /api/v1/search        — semantic search + risk avoidance
  POST /api/v1/books/index   — batch add/update books
  GET  /api/v1/books/{id}    — get a single book with risk scores
  DELETE /api/v1/books/{id}  — remove a book from the index
  GET  /api/v1/health        — health check + index stats
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .config import API_KEY, CHAT_MODEL
from .engine import SafeSearchEngine
from .models import Book

app = FastAPI(
    title="SafeSearch API",
    description="网络小说智能搜索与避雷推荐 — 语义搜索 + 风险评分 + 自动过滤",
    version="1.0.0",
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


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class BookInput(BaseModel):
    id: str
    title: str
    intro: str = ""
    tags: List[str] = Field(default_factory=list)
    status: Optional[str] = None
    sentiment_summary: Optional[str] = None


class SearchRequest(BaseModel):
    query: str = Field(..., description="Natural language query, e.g. '类似诡秘之主但基调轻快'")
    avoid_tags: List[str] = Field(default_factory=list, description="Tags to avoid")
    top_k: int = Field(default=10, ge=1, le=50, description="Max results to return")


class IndexRequest(BaseModel):
    books: List[BookInput] = Field(..., description="Books to add or update")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/api/v1/health")
async def health():
    engine = _get_engine()
    stats = engine.store.get_index_stats()
    return {
        "status": "ok",
        "version": "1.0.0",
        "index_stats": stats,
    }


@app.post("/api/v1/search")
async def search_novels(request: SearchRequest):
    """Search novels with automatic risk avoidance.

    Uses hybrid dense+sparse retrieval with LLM intent extraction.
    Returns ranked recommendations, blocked items, risk scores, and data gaps.
    """
    engine = _get_engine()
    result = engine.search(
        query=request.query,
        avoid_tags=request.avoid_tags,
        top_k=request.top_k,
    )
    return result


@app.post("/api/v1/books/index")
async def index_books(request: IndexRequest):
    """Add or update books in the search index.

    Books are upserted by id — existing books with the same id are replaced.
    Dense embeddings are computed and persisted to ChromaDB.
    """
    engine = _get_engine()
    books = [
        Book(
            id=b.id,
            title=b.title,
            intro=b.intro,
            tags=b.tags,
            status=b.status,
            sentiment_summary=b.sentiment_summary,
        )
        for b in request.books
    ]
    engine.index_books(books)
    return {"indexed": len(books), "total_in_index": engine.store.book_count()}


@app.get("/api/v1/books/{book_id}")
async def get_book(book_id: str):
    """Get a single indexed book with its risk scores computed on-the-fly."""
    engine = _get_engine()
    book = engine.store.get_book(book_id)
    if book is None:
        raise HTTPException(status_code=404, detail=f"Book '{book_id}' not found in index")

    # Compute risk scores on demand
    try:
        from ..sentiment_critic.critic import score_risks as _score_risks
    except ImportError:
        from sentiment_critic.critic import score_risks as _score_risks

    risk = _score_risks(
        client=engine._client,
        model=CHAT_MODEL,
        title=book.title,
        intro=book.intro,
        tags=book.tags,
        sentiment_summary=book.sentiment_summary,
    )
    return {
        "id": book.id,
        "title": book.title,
        "intro": book.intro,
        "tags": book.tags,
        "status": book.status,
        "sentiment_summary": book.sentiment_summary,
        "risk_scores": risk["scores"],
        "risk_evidence": risk["evidence"],
    }


@app.delete("/api/v1/books/{book_id}")
async def delete_book(book_id: str):
    """Remove a book from the index."""
    engine = _get_engine()
    if engine.store.get_book(book_id) is None:
        raise HTTPException(status_code=404, detail=f"Book '{book_id}' not found in index")
    engine.remove_book(book_id)
    return {"deleted": book_id, "total_in_index": engine.store.book_count()}


@app.get("/api/v1/intent")
async def extract_intent(query: str):
    """Extract structured search intent from a query (for debugging/demo)."""
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
