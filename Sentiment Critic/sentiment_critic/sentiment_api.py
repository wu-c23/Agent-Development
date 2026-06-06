"""FastAPI REST application for Sentiment Critic.

符合 Data Contract v1.0 规范，端口 8003。

Endpoints:
  GET  /api/v1/sentiment/detail/{uid}  — 单书舆情详情
  GET  /api/v1/sentiment/compare       — 多书舆情对比
  GET  /api/v1/sentiment/health        — 健康检查
  POST /api/v1/sentiment/chat          — RAG 智能问答
  GET  /api/v1/sentiment/kb/stats      — 知识库统计
"""

from __future__ import annotations

import random
import sys
import time
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .data_store import build_mock_sentiment_store, reload as reload_data_store
from .data_store import get_all_characters, get_character, get_novel_by_title
from .rag_engine import get_rag_engine
from pydantic import BaseModel, Field

app = FastAPI(
    title="Sentiment Critic API",
    description="网络小说舆情分析与深度评价 — Sentiment Critic 模块",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# 内存数据存储 — 启动时从集中数据源加载，缺失时回退到 Mock
# ---------------------------------------------------------------------------

_SENTIMENT_STORE: dict[str, dict] = {}


def _init_store() -> None:
    """从 data_store 加载舆情数据到内存缓存。"""
    global _SENTIMENT_STORE
    _SENTIMENT_STORE = build_mock_sentiment_store()


_init_store()


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500, description="用户问题")
    top_k: int = Field(default=5, ge=1, le=10, description="检索数量")
    session_id: str = Field(default="", max_length=128, description="会话ID，用于多轮对话上下文关联")


# ---------------------------------------------------------------------------
# Middleware
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
# Helper
# ---------------------------------------------------------------------------

def _sentiment_response(uid: str) -> dict:
    """构建符合 Data Contract SentimentData 的响应。"""
    data = _SENTIMENT_STORE.get(uid)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Sentiment data not found for UID: {uid}")
    return {
        "uid": data["uid"],
        "metadata": data["metadata"],
        "sentiment_scores": data["sentiment_scores"],
        "critic_summary": data["critic_summary"],
        "review_stats": data["review_stats"],
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/api/v1/sentiment/health")
async def health():
    return {
        "status": "healthy",
        "version": "1.0.0",
        "index_count": len(_SENTIMENT_STORE),
    }


@app.post("/api/v1/sentiment/refresh")
async def refresh_data():
    """强制重新从磁盘加载数据（采集/分析后调用）。"""
    reload_data_store()
    _init_store()
    return {"status": "refreshed", "index_count": len(_SENTIMENT_STORE)}


@app.post("/api/v1/sentiment/chat")
async def rag_chat(request: ChatRequest):
    """RAG 智能问答 — 基于知识库检索 + LLM 生成自然语言回答。

    示例问题:
      - 推荐悬疑小说
      - 诡秘之主好看吗
      - 有没有类似凡人修仙传的书
      - 修罗武神评价怎么样
    """
    engine = get_rag_engine()
    result = engine.answer(request.query, top_k=request.top_k, session_id=request.session_id)
    return {
        "query": request.query,
        "answer": result["answer"],
        "sources": result["sources"],
        "method": result["method"],
    }


@app.get("/api/v1/sentiment/kb/stats")
async def kb_stats():
    """知识库统计 — 返回索引的文档块数量、检索方式等信息。"""
    from .rag_engine import get_vector_store

    engine = get_rag_engine()
    vs = get_vector_store()
    stats = {
        "total_chunks": engine.kb.total_chunks,
        "llm_available": engine.use_agent,
        "retrieval_method": engine.retrieval_method,
        "vector_enabled": vs is not None and vs.ready,
        "vector_chunks": vs.total_chunks if vs and vs.ready else 0,
    }
    return stats


# ---------------------------------------------------------------------------
# 角色对话端点
# ---------------------------------------------------------------------------


class CharacterChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500, description="用户对角色说的话")
    character_id: str = Field(..., min_length=1, description="角色ID，如 'klein'、'hanli'")
    top_k: int = Field(default=5, ge=1, le=10, description="检索数量")
    session_id: str = Field(default="", max_length=128, description="会话ID，用于多轮对话上下文关联")


@app.get("/api/v1/sentiment/character/list")
async def character_list():
    """获取所有可用的角色扮演角色列表。"""
    characters = get_all_characters()
    return {
        "characters": [
            {
                "id": c["id"],
                "name": c["name"],
                "novel": c["novel"],
                "personality": c.get("personality", []),
                "avatar_emoji": c.get("avatar_emoji", "🎭"),
                "catchphrases": c.get("catchphrases", [])[:2],
            }
            for c in characters
        ],
        "total": len(characters),
    }


@app.post("/api/v1/sentiment/character/chat")
async def character_chat(request: CharacterChatRequest):
    """以小说角色身份与用户对话。

    选择一部小说中的角色，AI 会以该角色的身份和口吻与用户自然对话。
    示例角色ID: 'klein'（克莱恩·莫雷蒂）、'hanli'（韩立）、'chenge'（陈歌）
    """
    character = get_character(request.character_id)
    if character is None:
        raise HTTPException(
            status_code=404,
            detail=f"角色 '{request.character_id}' 不存在。GET /api/v1/sentiment/character/list 查看可用角色。",
        )

    engine = get_rag_engine()
    result = engine.character_answer(
        query=request.query,
        character=character,
        top_k=request.top_k,
        session_id=request.session_id,
    )
    return {
        "query": request.query,
        "answer": result["answer"],
        "character": {
            "id": character["id"],
            "name": character["name"],
            "novel": character["novel"],
            "avatar_emoji": character.get("avatar_emoji", "🎭"),
        },
        "sources": result["sources"],
        "method": result["method"],
    }


class CharacterChatByNameRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500, description="用户问题")
    character_name: str = Field(..., min_length=1, max_length=100, description="角色名，如 '叶凡'、'唐三'")
    novel_name: str = Field(..., min_length=1, max_length=100, description="小说名，如 '遮天'、'斗罗大陆'")
    top_k: int = Field(default=5, ge=1, le=10, description="检索数量")
    session_id: str = Field(default="", max_length=128, description="会话ID")


@app.post("/api/v1/sentiment/character/chat-by-name")
async def character_chat_by_name(request: CharacterChatByNameRequest):
    """以任意指定的小说角色身份对话（无需预定义角色 ID）。

    客户端只需提供角色名和小说名，系统会在知识库中查找该小说的信息，
    自动构建角色 persona 并生成回复。

    如果小说未收录，返回 404 错误。
    """
    engine = get_rag_engine()
    result = engine.dynamic_character_answer(
        query=request.query,
        character_name=request.character_name,
        novel_name=request.novel_name,
        top_k=request.top_k,
        session_id=request.session_id,
    )

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return {
        "query": request.query,
        "answer": result["answer"],
        "character": {
            "name": request.character_name,
            "novel": request.novel_name,
            "avatar_emoji": "📖",
        },
        "sources": result.get("sources", []),
        "method": result.get("method", "dynamic_character"),
    }


@app.get("/api/v1/sentiment/detail/{uid}")
async def sentiment_detail(uid: str):
    """获取单书舆情详情 — 符合 Data Contract SentimentData Schema。

    返回多维度评分 (overall/style/logic/character/update_stability/toxicity_index)、
    毒舌点评 (critic_summary)、评论统计 (review_stats)。
    """
    return _sentiment_response(uid)


@app.get("/api/v1/sentiment/compare")
async def sentiment_compare(uids: str = Query(..., description="逗号分隔的 UID 列表")):
    """多书舆情对比。返回各书的 SentimentData 数组。"""
    uid_list = [u.strip() for u in uids.split(",") if u.strip()]
    if not uid_list:
        raise HTTPException(status_code=400, detail="At least one UID is required")
    results = []
    for uid in uid_list:
        try:
            results.append(_sentiment_response(uid))
        except HTTPException:
            results.append({"uid": uid, "error": "not_found"})
    return results


@app.get("/api/v1/sentiment/detail/{uid}/raw")
async def sentiment_raw(uid: str):
    """返回原始完整数据 (含内部字段，调试用)。"""
    data = _SENTIMENT_STORE.get(uid)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Sentiment data not found for UID: {uid}")
    return data


# ---------------------------------------------------------------------------
# Startup diagnostic
# ---------------------------------------------------------------------------

try:
    from .agent_client import AgentClientConfig
    cfg = AgentClientConfig.from_env()
    for line in cfg.diagnostic_lines():
        print(f"[sentiment_api] {line}", file=sys.stderr, flush=True)
    if cfg.validation_errors():
        print(f"[sentiment_api] LLM unavailable: {cfg.validation_errors()}", file=sys.stderr, flush=True)
        print(f"[sentiment_api] 角色对话将使用启发式规则回复（无 LLM 生成）", file=sys.stderr, flush=True)
        print(f"[sentiment_api] 如需 LLM 支持，请在 Safe-Search Architect/.env 中配置 DEEPSEEK_API_KEY", file=sys.stderr, flush=True)
    else:
        print(f"[sentiment_api] LLM 已就绪 — 角色对话将使用 DeepSeek 生成回复", file=sys.stderr, flush=True)
except Exception as e:
    print(f"[sentiment_api] Config diagnostic skipped: {e}", file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------
# RAG engine warm-up (background, avoids 20s+ delay on first request)
# ---------------------------------------------------------------------------

import threading


@app.on_event("startup")
async def warm_up_rag_engine():
    """在后台预初始化 RAG 引擎，避免首请求阻塞。"""
    import asyncio

    def _warm():
        import time
        t0 = time.time()
        try:
            from .rag_engine import get_rag_engine
            engine = get_rag_engine()
            elapsed = time.time() - t0
            print(f"[sentiment_api] RAG engine warmed up in {elapsed:.0f}s "
                  f"(method={engine.retrieval_method}, agent={engine.use_agent})",
                  file=sys.stderr, flush=True)
        except Exception as exc:
            print(f"[sentiment_api] RAG engine warm-up failed: {exc}", file=sys.stderr, flush=True)

    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, _warm)
