# Mock API 接口模板与规范 v1.0

## 概述

在正式接口开发完成前，各模块负责人 **必须** 提供符合 Data Contract 的 Mock 接口，供集成端 (System Integrator) 和其他模块联调。Mock 接口需与最终接口保持 **完全一致的路径、方法和响应结构**。

## Mock 接口通用要求

| 要求 | 说明 |
|------|------|
| 路径一致 | Mock 与最终接口的 URL 路径、HTTP 方法完全相同 |
| Schema 一致 | 响应体必须通过对应 Data Contract JSON Schema 校验 |
| 延迟模拟 | 需模拟真实网络延迟 (建议 50-200ms 随机延迟) |
| 错误模拟 | 需提供至少 1 个可触发错误响应的场景 (如无效 UID) |
| 数据多样性 | 至少提供 5 条不同的小说 Mock 数据 |

## Mock 实现模板 (FastAPI)

```python
"""
mock_server.py — 模块 Mock 接口模板
使用方式: uvicorn mock_server:app --port {module_port}
"""
import random
import time
from typing import Optional
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

app = FastAPI(title="{Module Name} Mock API", version="v1.0")

# ============================================================
# 延迟中间件 (模拟真实网络)
# ============================================================
@app.middleware("http")
async def add_latency(request, call_next):
    delay = random.uniform(0.05, 0.2)  # 50-200ms
    time.sleep(delay)
    response = await call_next(request)
    response.headers["X-Mock-Latency"] = f"{delay:.3f}s"
    response.headers["X-Mock"] = "true"
    return response

# ============================================================
# Mock 数据 (至少 5 条)
# ============================================================
MOCK_NOVELS = [
    {
        "uid": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "metadata": {
            "title": "诡秘之主",
            "platform": "qidian",
            "last_update": "2026-06-03T12:00:00Z"
        },
        # ... 按模块 Data Contract 填充
    },
    # ... 至少 5 条
]

# ============================================================
# Mock 接口实现
# ============================================================
@app.get("/api/v1/{module}/detail/{uid}")
async def get_detail(uid: str):
    """获取单条详情"""
    for novel in MOCK_NOVELS:
        if novel["uid"] == uid:
            return novel
    raise HTTPException(status_code=404, detail=f"UID not found: {uid}")

# ... 其他接口
```

## 各模块 Mock 接口清单

### Trend Explorer (吴隐) — 端口 8001

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/trend/hot` | 热门趋势榜单 |
| GET | `/api/v1/trend/detail/{uid}` | 单书趋势详情 |
| GET | `/api/v1/trend/tags/evolution` | 标签演变数据 |

### Safe-Search Architect (吴宸) — 端口 8002

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/search/semantic` | 语义搜索 |
| GET | `/api/v1/search/vector/health` | 向量库健康检查 |

### Sentiment Critic (武文杰) — 端口 8003

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/sentiment/detail/{uid}` | 单书舆情详情 |
| GET | `/api/v1/sentiment/compare` | 多书舆情对比 |

## 验收标准

Mock 接口将被集成端通过以下脚本自动验收：

```bash
# Trend Explorer Mock 验收
curl http://localhost:8001/api/v1/trend/hot?limit=5 | python -c "import sys,json; d=json.load(sys.stdin); assert len(d)>0, 'empty response'"

# Search Mock 验收
curl -X POST http://localhost:8002/api/v1/search/semantic \
  -H "Content-Type: application/json" \
  -d '{"query":"类似诡秘之主但基调轻快","safe_tags":["严禁烂尾"],"top_k":5}'

# Sentiment Mock 验收
curl http://localhost:8003/api/v1/sentiment/detail/{valid_uid}
```

## 约束

- Mock 接口禁止返回硬编码的空数组 `[]`，必须包含真实结构的样例数据
- UID 必须使用有效的 SHA256 格式（64 位 hex），不能使用占位符如 `"uid_001"`
- 所有 Mock 响应必须在 header 中标注 `X-Mock: true`
