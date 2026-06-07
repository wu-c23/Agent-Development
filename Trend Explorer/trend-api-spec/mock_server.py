"""
mock_server.py — Trend Explorer Mock API (端口 8001)
符合 Data Contract v1.0 TrendData Schema.
使用方式: uvicorn mock_server:app --host 0.0.0.0 --port 8001
"""
import random
import time
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Trend Explorer Mock API", version="v1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_mock_headers(request, call_next):
    delay = random.uniform(0.05, 0.2)
    time.sleep(delay)
    response = await call_next(request)
    response.headers["X-Mock"] = "true"
    response.headers["X-Mock-Latency"] = f"{delay:.3f}s"
    return response


# ============================================================
# 5 本 Mock 小说 (有效 SHA256 UID)
# ============================================================

MOCK_NOVELS = [
    {
        "uid": "987a2b45c6bd2baa73d750f13daf15b63c20145de2e85fff22ada96ad3d8b27b",
        "metadata": {
            "title": "诡秘之主",
            "platform": "qidian",
            "last_update": "2026-06-03T12:00:00Z",
        },
        "trend_metrics": {
            "heat_score": 0.95,
            "rank": 1,
            "rank_change": 2,
            "tags": ["克苏鲁", "蒸汽朋克", "序列", "诡秘", "悬疑"],
            "trend_direction": "rising",
            "history_7d": [
                {"date": "2026-05-28", "heat_score": 0.88},
                {"date": "2026-05-29", "heat_score": 0.90},
                {"date": "2026-05-30", "heat_score": 0.89},
                {"date": "2026-05-31", "heat_score": 0.92},
                {"date": "2026-06-01", "heat_score": 0.93},
                {"date": "2026-06-02", "heat_score": 0.94},
                {"date": "2026-06-03", "heat_score": 0.95},
            ],
        },
    },
    {
        "uid": "5ee58c6e2a50c7b194ab73eaf787590384344a765ff1b682ec15d962daae2dee",
        "metadata": {
            "title": "斗破苍穹",
            "platform": "qidian",
            "last_update": "2026-06-03T10:00:00Z",
        },
        "trend_metrics": {
            "heat_score": 0.82,
            "rank": 3,
            "rank_change": -1,
            "tags": ["玄幻", "爽文", "升级流", "异火", "热血"],
            "trend_direction": "stable",
            "history_7d": [
                {"date": "2026-05-28", "heat_score": 0.84},
                {"date": "2026-05-29", "heat_score": 0.83},
                {"date": "2026-05-30", "heat_score": 0.85},
                {"date": "2026-05-31", "heat_score": 0.82},
                {"date": "2026-06-01", "heat_score": 0.83},
                {"date": "2026-06-02", "heat_score": 0.81},
                {"date": "2026-06-03", "heat_score": 0.82},
            ],
        },
    },
    {
        "uid": "8c2c257caf7438c0c5561c5584200deea9b11dd91283958002968646deeeec2b",
        "metadata": {
            "title": "剑来",
            "platform": "zongheng",
            "last_update": "2026-06-02T18:00:00Z",
        },
        "trend_metrics": {
            "heat_score": 0.78,
            "rank": 5,
            "rank_change": 3,
            "tags": ["仙侠", "剑道", "文青", "群像", "权谋"],
            "trend_direction": "rising",
            "history_7d": [
                {"date": "2026-05-28", "heat_score": 0.72},
                {"date": "2026-05-29", "heat_score": 0.73},
                {"date": "2026-05-30", "heat_score": 0.74},
                {"date": "2026-05-31", "heat_score": 0.75},
                {"date": "2026-06-01", "heat_score": 0.76},
                {"date": "2026-06-02", "heat_score": 0.77},
                {"date": "2026-06-03", "heat_score": 0.78},
            ],
        },
    },
    {
        "uid": "261d26f98be24a9423afba401b0fef88373220a3212166615613ad83b726d7fa",
        "metadata": {
            "title": "全职高手",
            "platform": "qidian",
            "last_update": "2026-06-01T08:00:00Z",
        },
        "trend_metrics": {
            "heat_score": 0.71,
            "rank": 8,
            "rank_change": -3,
            "tags": ["电竞", "群像", "热血", "竞技", "友情"],
            "trend_direction": "declining",
            "history_7d": [
                {"date": "2026-05-28", "heat_score": 0.76},
                {"date": "2026-05-29", "heat_score": 0.75},
                {"date": "2026-05-30", "heat_score": 0.74},
                {"date": "2026-05-31", "heat_score": 0.73},
                {"date": "2026-06-01", "heat_score": 0.72},
                {"date": "2026-06-02", "heat_score": 0.71},
                {"date": "2026-06-03", "heat_score": 0.71},
            ],
        },
    },
    {
        "uid": "22ed60b7b27cf4c8b77c1439cb7a9d82eb4667f6eafab681bcd415e18adbd0a4",
        "metadata": {
            "title": "凡人修仙传",
            "platform": "qidian",
            "last_update": "2026-06-03T14:00:00Z",
        },
        "trend_metrics": {
            "heat_score": 0.65,
            "rank": 12,
            "rank_change": 5,
            "tags": ["修仙", "凡人流", "韩立", "严谨", "慢热"],
            "trend_direction": "rising",
            "history_7d": [
                {"date": "2026-05-28", "heat_score": 0.58},
                {"date": "2026-05-29", "heat_score": 0.60},
                {"date": "2026-05-30", "heat_score": 0.61},
                {"date": "2026-05-31", "heat_score": 0.62},
                {"date": "2026-06-01", "heat_score": 0.63},
                {"date": "2026-06-02", "heat_score": 0.64},
                {"date": "2026-06-03", "heat_score": 0.65},
            ],
        },
    },
]

MOCK_TAG_EVOLUTION = {
    "克苏鲁": [
        {"date": "2026-01", "heat": 1200, "label": "01月"},
        {"date": "2026-02", "heat": 1450, "label": "02月"},
        {"date": "2026-03", "heat": 1680, "label": "03月"},
        {"date": "2026-04", "heat": 2100, "label": "04月"},
        {"date": "2026-05", "heat": 2850, "label": "05月"},
    ],
    "系统流": [
        {"date": "2026-01", "heat": 3200, "label": "01月"},
        {"date": "2026-02", "heat": 3100, "label": "02月"},
        {"date": "2026-03", "heat": 2950, "label": "03月"},
        {"date": "2026-04", "heat": 2700, "label": "04月"},
        {"date": "2026-05", "heat": 2500, "label": "05月"},
    ],
    "家族群像流": [
        {"date": "2026-01", "heat": 800, "label": "01月"},
        {"date": "2026-02", "heat": 1100, "label": "02月"},
        {"date": "2026-03", "heat": 1400, "label": "03月"},
        {"date": "2026-04", "heat": 1750, "label": "04月"},
        {"date": "2026-05", "heat": 2200, "label": "05月"},
    ],
    "爽文": [
        {"date": "2026-01", "heat": 2500, "label": "01月"},
        {"date": "2026-02", "heat": 2400, "label": "02月"},
        {"date": "2026-03", "heat": 2350, "label": "03月"},
        {"date": "2026-04", "heat": 2300, "label": "04月"},
        {"date": "2026-05", "heat": 2250, "label": "05月"},
    ],
    "规则怪谈": [
        {"date": "2026-01", "heat": 500, "label": "01月"},
        {"date": "2026-02", "heat": 750, "label": "02月"},
        {"date": "2026-03", "heat": 1100, "label": "03月"},
        {"date": "2026-04", "heat": 1600, "label": "04月"},
        {"date": "2026-05", "heat": 2400, "label": "05月"},
    ],
}


# ============================================================
# Data Contract v1.0 端点
# ============================================================

@app.get("/api/v1/trend/hot")
def get_trend_hot(limit: int = Query(20, ge=1, le=100)):
    """热门趋势榜单 — 符合 Data Contract TrendData 结构."""
    items = MOCK_NOVELS[:limit]
    return {"items": items, "total": len(MOCK_NOVELS)}


@app.get("/api/v1/trend/detail/{uid}")
def get_trend_detail(uid: str):
    """单书趋势详情 — 符合 Data Contract TrendData 结构."""
    for novel in MOCK_NOVELS:
        if novel["uid"] == uid:
            return novel
    raise HTTPException(status_code=404, detail=f"UID not found: {uid}")


@app.get("/api/v1/trend/tags/evolution")
def get_tags_evolution(
    tag: str = Query(..., description="标签名称"),
    period: str = Query("30d", description="时间范围"),
):
    """标签演变数据."""
    evolution_data = MOCK_TAG_EVOLUTION.get(tag)
    if not evolution_data:
        raise HTTPException(status_code=404, detail=f"Tag not found: {tag}")

    period_limit = {"7d": 2, "30d": 5, "90d": 12}.get(period, 5)
    evolution = evolution_data[-period_limit:]

    first_heat = evolution[0]["heat"] if evolution else 0
    last_heat = evolution[-1]["heat"] if evolution else 0
    if first_heat > 0 and last_heat >= first_heat * 1.05:
        trend = "rising"
    elif first_heat > 0 and last_heat <= first_heat * 0.95:
        trend = "declining"
    else:
        trend = "stable"

    return {
        "tag": tag,
        "period": period,
        "evolution": evolution,
        "trend": trend,
        "related_works": [
            {"title": f"{tag}代表作{i}", "heat": round(100 - i * 10 + random.uniform(-5, 5), 2)}
            for i in range(5)
        ],
    }


@app.get("/api/v1/trend/health")
def health():
    return {"status": "ok", "module": "trend-explorer", "mock": True}
