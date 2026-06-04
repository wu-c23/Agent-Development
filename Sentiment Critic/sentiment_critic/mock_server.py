"""Sentiment Critic Mock API Server — 符合 Data Contract v1.0。

独立于数据采集 pipeline，提供联调所需的标准 Mock 响应。

启动: uvicorn sentiment_critic.mock_server:app --port 8003
"""

from __future__ import annotations

import random
import time

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Sentiment Critic Mock API",
    description="网络小说舆情分析 Mock 服务 — Sentiment Critic",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MOCK_NOVELS = [
    {
        "uid": "987a2b45c6bd2baa73d750f13daf15b63c20145de2e85fff22ada96ad3d8b27b",
        "metadata": {"title": "诡秘之主", "platform": "qidian", "last_update": "2026-06-03T12:00:00Z"},
        "sentiment_scores": {
            "overall": 9.1, "style": 9.2, "logic": 9.5,
            "character": 9.0, "update_stability": 8.8, "toxicity_index": 0.08,
        },
        "critic_summary": {
            "one_liner": "逻辑严密的克苏鲁神作，但前200页像在读说明书。",
            "pros": ["世界观构建顶级", "伏笔回收大师级", "角色智商集体在线"],
            "cons": ["开头节奏偏慢", "对轻度读者门槛较高"],
        },
        "review_stats": {
            "total_count": 1250, "positive_ratio": 0.86, "negative_ratio": 0.05,
            "source_breakdown": {"douban": 620, "tieba": 430, "xiaohongshu": 200},
        },
    },
    {
        "uid": "26d4613826eb8819a9a601cfb88eb7621b0e6cc5c46ffefa96b5dea22ca938dc",
        "metadata": {"title": "我有一座恐怖屋", "platform": "qidian", "last_update": "2026-06-02T10:00:00Z"},
        "sentiment_scores": {
            "overall": 8.5, "style": 8.0, "logic": 8.2,
            "character": 8.8, "update_stability": 9.0, "toxicity_index": 0.05,
        },
        "critic_summary": {
            "one_liner": "不吓人的恐怖小说才是好喜剧，陈歌把鬼屋经营成了迪士尼。",
            "pros": ["角色塑造鲜明", "恐怖与搞笑平衡出色", "更新稳定"],
            "cons": ["后期略有套路化", "部分副本节奏不均"],
        },
        "review_stats": {
            "total_count": 890, "positive_ratio": 0.82, "negative_ratio": 0.06,
            "source_breakdown": {"douban": 420, "tieba": 350, "xiaohongshu": 120},
        },
    },
    {
        "uid": "f551b43b941bf7f47d6006792b26da44b8554945c72766133cb0c59771f48c89",
        "metadata": {"title": "修罗武神", "platform": "qidian", "last_update": "2026-06-03T08:00:00Z"},
        "sentiment_scores": {
            "overall": 5.2, "style": 5.0, "logic": 4.0,
            "character": 3.5, "update_stability": 6.0, "toxicity_index": 0.45,
        },
        "critic_summary": {
            "one_liner": "爽是真的爽，水也是真的水，后宫像Pokemon收集图鉴。",
            "pros": ["爽点密集节奏快", "适合无脑放松"],
            "cons": ["后宫角色扁平化", "后期严重注水", "逻辑经不起推敲"],
        },
        "review_stats": {
            "total_count": 2100, "positive_ratio": 0.45, "negative_ratio": 0.35,
            "source_breakdown": {"douban": 300, "tieba": 1500, "xiaohongshu": 300},
        },
    },
    {
        "uid": "22ed60b7b27cf4c8b77c1439cb7a9d82eb4667f6eafab681bcd415e18adbd0a4",
        "metadata": {"title": "凡人修仙传", "platform": "qidian", "last_update": "2026-05-28T16:00:00Z"},
        "sentiment_scores": {
            "overall": 8.3, "style": 7.5, "logic": 9.0,
            "character": 8.5, "update_stability": 9.5, "toxicity_index": 0.10,
        },
        "critic_summary": {
            "one_liner": "凡人流教科书，韩立教你什么叫真正的'凡人'——连老婆都是分身上位的。",
            "pros": ["逻辑自洽的修仙体系", "主角智商长期在线", "完结稳定不烂尾"],
            "cons": ["前期节奏偏慢", "女主存在感薄弱"],
        },
        "review_stats": {
            "total_count": 3200, "positive_ratio": 0.80, "negative_ratio": 0.08,
            "source_breakdown": {"douban": 1800, "tieba": 1100, "xiaohongshu": 300},
        },
    },
    {
        "uid": "587986904db3db77b83e2d7b49165f2f6e9ec1b6552b621e340695f21c240d8c",
        "metadata": {"title": "仙王的日常生活", "platform": "qidian", "last_update": "2026-06-01T09:00:00Z"},
        "sentiment_scores": {
            "overall": 7.8, "style": 7.2, "logic": 6.5,
            "character": 8.0, "update_stability": 8.5, "toxicity_index": 0.12,
        },
        "critic_summary": {
            "one_liner": "仙王装高中生的日常，像拿核弹打蚊子——浪费但好笑。",
            "pros": ["轻松解压", "反套路设定有趣", "角色讨喜"],
            "cons": ["深度不足", "单元剧形式缺乏主线推进"],
        },
        "review_stats": {
            "total_count": 780, "positive_ratio": 0.78, "negative_ratio": 0.09,
            "source_breakdown": {"douban": 350, "tieba": 280, "xiaohongshu": 150},
        },
    },
]

_UID_MAP = {n["uid"]: n for n in MOCK_NOVELS}
_TITLE_MAP = {n["metadata"]["title"]: n for n in MOCK_NOVELS}


@app.middleware("http")
async def add_mock_latency(request, call_next):
    delay = random.uniform(0.05, 0.15)
    time.sleep(delay)
    response = await call_next(request)
    response.headers["X-Mock"] = "true"
    response.headers["X-Mock-Latency"] = f"{delay:.3f}s"
    return response


def _fmt(novel: dict) -> dict:
    return {
        "uid": novel["uid"],
        "metadata": novel["metadata"],
        "sentiment_scores": novel["sentiment_scores"],
        "critic_summary": novel["critic_summary"],
        "review_stats": novel["review_stats"],
    }


@app.get("/api/v1/sentiment/detail/{uid}")
async def sentiment_detail(uid: str):
    novel = _UID_MAP.get(uid)
    if novel is None:
        raise HTTPException(status_code=404, detail=f"Sentiment data not found for UID: {uid}")
    return _fmt(novel)


@app.post("/api/v1/sentiment/refresh")
async def refresh_data():
    """强制重新从磁盘加载数据。Mock 模式下刷新 Mock 缓存。"""
    return {"status": "refreshed", "index_count": len(MOCK_NOVELS)}


@app.get("/api/v1/sentiment/compare")
async def sentiment_compare(uids: str = Query(..., description="逗号分隔的 UID 列表")):
    uid_list = [u.strip() for u in uids.split(",") if u.strip()]
    if not uid_list:
        raise HTTPException(status_code=400, detail="At least one UID required")
    results = []
    for uid in uid_list:
        novel = _UID_MAP.get(uid)
        if novel:
            results.append(_fmt(novel))
        else:
            results.append({"uid": uid, "error": "not_found"})
    return results


@app.get("/api/v1/sentiment/health")
async def health():
    return {"status": "healthy", "version": "1.0.0", "index_count": len(MOCK_NOVELS)}
