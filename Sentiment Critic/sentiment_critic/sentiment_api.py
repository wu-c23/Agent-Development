"""FastAPI REST application for Sentiment Critic.

符合 Data Contract v1.0 规范，端口 8003。

Endpoints:
  GET  /api/v1/sentiment/detail/{uid}  — 单书舆情详情
  GET  /api/v1/sentiment/compare       — 多书舆情对比
  GET  /api/v1/sentiment/health        — 健康检查
"""

from __future__ import annotations

import random
import time
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .data_store import build_mock_sentiment_store, reload as reload_data_store

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
