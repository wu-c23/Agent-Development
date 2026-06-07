"""FastAPI REST application for Safe-Search Architect.

符合 Data Contract v1.0 规范，端口 8002。

Endpoints:
  POST /api/v1/search/semantic       — 语义搜索 + 避雷过滤
  GET  /api/v1/search/vector/health  — 向量库健康检查
  POST /api/v1/search/books/index    — 批量添加/更新书籍索引
  GET  /api/v1/search/books/{uid}    — 查询单本书 + 风险评分
  DELETE /api/v1/search/books/{uid}  — 从索引中删除书籍
  GET  /api/v1/search/intent         — 意图解析 (调试用)
"""

from __future__ import annotations

import random
import time
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .config import API_KEY, CHAT_MODEL
from .engine import SafeSearchEngine
from .models import Book

# 尝试加载集中数据源 (Sentiment Critic/data/)
def _get_central_books() -> list[dict]:
    """从集中数据源加载小说列表。不可用时返回空列表。"""
    try:
        import sys
        from pathlib import Path
        central_path = Path(__file__).resolve().parents[3] / "Sentiment Critic"
        if str(central_path) not in sys.path:
            sys.path.insert(0, str(central_path))
        from sentiment_critic.data_store import get_novel_list_for_search
        return get_novel_list_for_search()
    except Exception:
        return []

app = FastAPI(
    title="Safe-Search API",
    description="网络小说语义搜索与智能避雷 — Safe-Search Architect 模块",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
# Request / Response models — 对齐 Data Contract v1.0
# ---------------------------------------------------------------------------


class SearchFilters(BaseModel):
    tags_include: List[str] = Field(default_factory=list)
    tags_exclude: List[str] = Field(default_factory=list)
    min_heat: Optional[float] = None
    platforms: List[str] = Field(default_factory=list)


class SearchRequest(BaseModel):
    query: str = Field(..., description="自然语言搜索语句")
    filters: SearchFilters = Field(default_factory=SearchFilters)
    safe_tags: List[str] = Field(
        default_factory=list, description="避雷标签，如 ['严禁烂尾', '主角智商在线']"
    )
    top_k: int = Field(default=10, ge=1, le=50)


class BookInput(BaseModel):
    id: str = ""                                  # UID，可选（不填则自动生成）
    title: str
    intro: str = ""
    tags: List[str] = Field(default_factory=list)
    platform: str = "unknown"
    platform_id: str = ""
    author: str = ""
    status: Optional[str] = None
    sentiment_summary: Optional[str] = None


class IndexRequest(BaseModel):
    books: List[BookInput] = Field(..., description="需索引的书籍列表")


# ---------------------------------------------------------------------------
# Middleware: Mock 延迟 + 标记 (联调阶段)
# ---------------------------------------------------------------------------

@app.middleware("http")
async def mock_headers(request: Request, call_next):
    delay = random.uniform(0.03, 0.08)
    time.sleep(delay)
    response = await call_next(request)
    response.headers["X-Mock"] = "true"
    response.headers["X-Mock-Latency"] = f"{delay:.3f}s"
    return response


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/api/v1/search/vector/health")
async def vector_health():
    """向量库健康检查 + 索引统计。"""
    engine = _get_engine()
    stats = engine.store.get_index_stats()
    return {
        "status": "healthy",
        "version": "1.0.0",
        "index_count": stats["book_count"],
        "last_updated": stats.get("last_updated", ""),
    }


@app.post("/api/v1/search/semantic")
async def semantic_search(request: SearchRequest):
    """语义搜索 + 智能避雷。

    接收自然语言查询，经过意图解析、混合检索、风险评分、避雷过滤后返回结果。
    响应结构符合 Data Contract SearchResult Schema。
    """
    engine = _get_engine()
    result = engine.search(
        query=request.query,
        avoid_tags=request.safe_tags,
        top_k=request.top_k,
    )
    # 转换到 Data Contract SearchResult 格式
    query_rewrite = result.get("query_intent", {}).get("summary", request.query)
    return _to_search_result(result, engine, query_rewrite)


def _to_search_result(raw: dict, engine: SafeSearchEngine, query_rewrite: str = "") -> dict:
    """将 engine 内部结果转为 Data Contract SearchResult 格式。"""
    results = []
    for item in raw.get("filtered_results", []):
        uid = item["id"]
        book = engine.store.get_book(uid)
        results.append({
            "uid": uid,
            "metadata": book.metadata if book else {
                "title": item.get("title", ""),
                "platform": "unknown",
                "last_update": "",
            },
            "relevance_score": item.get("final_score", 0.0),
            "match_reason": ", ".join(item.get("reasons_recommend", [])) or "semantic_match",
            "safe_check": {
                "passed": True,
                "warnings": item.get("reasons_risk", []),
            },
        })

    # 被屏蔽的结果
    for item in raw.get("blocked_results", []):
        uid = item["id"]
        book = engine.store.get_book(uid)
        results.append({
            "uid": uid,
            "metadata": book.metadata if book else {
                "title": item.get("title", ""),
                "platform": "unknown",
                "last_update": "",
            },
            "relevance_score": 0.0,
            "match_reason": "",
            "safe_check": {
                "passed": False,
                "warnings": item.get("blocked_by", []),
            },
        })

    return {
        "results": results,
        "query_rewrite": query_rewrite,
        "total_hits": len(raw.get("retrieval_candidates", [])),
    }


@app.post("/api/v1/search/books/index")
async def index_books(request: IndexRequest):
    """批量添加/更新书籍索引。同一 UID 执行 upsert。"""
    engine = _get_engine()
    books = [
        Book(
            id=b.id,
            title=b.title,
            intro=b.intro,
            tags=b.tags,
            platform=b.platform,
            platform_id=b.platform_id,
            author=b.author,
            status=b.status,
            sentiment_summary=b.sentiment_summary,
        )
        for b in request.books
    ]
    engine.index_books(books)
    return {"indexed": len(books), "total_in_index": engine.store.book_count()}


@app.post("/api/v1/search/books/sync-from-central")
async def sync_from_central():
    """从 Sentiment Critic/data/ 集中数据源同步小说到向量库。

    读取 novels.json 中的所有小说元数据，批量导入向量索引。
    """
    central_books = _get_central_books()
    if not central_books:
        raise HTTPException(
            status_code=404,
            detail="Central data source not available. Make sure Sentiment Critic/data/novels.json exists.",
        )
    engine = _get_engine()
    books = [
        Book(
            id=b["id"],
            title=b["title"],
            intro=b.get("intro", ""),
            tags=b.get("tags", []),
            platform=b.get("platform", "unknown"),
            platform_id=b.get("platform_id", ""),
            author=b.get("author", ""),
            status=b.get("status"),
            sentiment_summary=b.get("sentiment_summary", ""),
        )
        for b in central_books
    ]
    engine.index_books(books)
    return {
        "indexed": len(books),
        "total_in_index": engine.store.book_count(),
        "source": "Sentiment Critic/data/novels.json",
    }


@app.get("/api/v1/search/books/{uid}")
async def get_book(uid: str):
    """查询单本已索引书籍及其风险评分。"""
    engine = _get_engine()
    book = engine.store.get_book(uid)
    if book is None:
        raise HTTPException(status_code=404, detail=f"Book '{uid}' not found in index")

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
        "uid": book.id,
        "metadata": book.metadata,
        "intro": book.intro,
        "tags": book.tags,
        "status": book.status,
        "sentiment_summary": book.sentiment_summary,
        "risk_scores": risk["scores"],
        "risk_evidence": risk["evidence"],
    }


@app.delete("/api/v1/search/books/{uid}")
async def delete_book(uid: str):
    """从索引中删除书籍。"""
    engine = _get_engine()
    if engine.store.get_book(uid) is None:
        raise HTTPException(status_code=404, detail=f"Book '{uid}' not found in index")
    engine.remove_book(uid)
    return {"deleted": uid, "total_in_index": engine.store.book_count()}


@app.get("/api/v1/search/intent")
async def extract_intent(query: str):
    """提取结构化搜索意图 (调试用)。"""
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
