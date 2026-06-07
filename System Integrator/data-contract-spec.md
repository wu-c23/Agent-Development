# Data Contract 数据契约规范 v1.0

## 概述

本规范定义各模块间数据交互的标准 JSON Schema。所有接口的请求/响应体必须通过本文档中对应 Schema 的强校验。各模块在正式接口完成前，必须提供符合本文档规范的 Mock 接口。

## 通用字段规范

```json
{
  "uid": "string (required) - SHA256 hash，见 uid-specification.md",
  "metadata": {
    "title": "string (required) - 小说标题",
    "platform": "string (required) - 来源平台标识: qidian / zongheng / douban / tieba / xiaohongshu",
    "last_update": "string (required) - ISO 8601 时间戳"
  }
}
```

## 1. Trend Explorer — 趋势数据契约

### 输出 Schema: TrendData

```json
{
  "uid": "a1b2c3d4e5f6...",
  "metadata": {
    "title": "诡秘之主",
    "platform": "qidian",
    "last_update": "2026-06-03T12:00:00Z"
  },
  "trend_metrics": {
    "heat_score": "number [0.0, 1.0] - 综合热度分",
    "rank": "integer - 当前排名 (可为空)",
    "rank_change": "integer - 排名变化 (正=上升)",
    "tags": ["string[] - 核心标签，如 [\"克苏鲁\", \"蒸汽朋克\", \"序列\"]"],
    "trend_direction": "string - enum: rising | stable | declining",
    "history_7d": [
      {
        "date": "string - YYYY-MM-DD",
        "heat_score": "number"
      }
    ]
  }
}
```

### Mock 接口

- `GET /api/v1/trend/hot?limit=20` — 热门趋势榜单
- `GET /api/v1/trend/detail/{uid}` — 单书趋势详情
- `GET /api/v1/trend/tags/evolution?tag={tag}&period=30d` — 标签演变数据

## 2. Safe-Search Architect — 搜索数据契约

### 输入 Schema: SearchRequest

```json
{
  "query": "string (required) - 自然语言搜索语句",
  "filters": {
    "tags_include": ["string[] - 必须包含的标签"],
    "tags_exclude": ["string[] - 排除的标签"],
    "min_heat": "number - 最低热度阈值",
    "platforms": ["string[] - 限定平台"]
  },
  "safe_tags": ["string[] - 避雷标签，如 [\"严禁烂尾\", \"主角智商在线\"]"],
  "top_k": "integer - 返回结果数，默认 10"
}
```

### 输出 Schema: SearchResult

```json
{
  "results": [
    {
      "uid": "a1b2c3d4e5f6...",
      "metadata": {
        "title": "string",
        "platform": "string",
        "last_update": "string"
      },
      "relevance_score": "number [0.0, 1.0]",
      "match_reason": "string - 匹配理由简述",
      "safe_check": {
        "passed": "boolean",
        "warnings": ["string[] - 命中的避雷标签及原因"]
      }
    }
  ],
  "query_rewrite": "string - Agent 改写后的查询",
  "total_hits": "integer"
}
```

### Mock 接口

- `POST /api/v1/search/semantic` — 语义搜索
- `GET /api/v1/search/vector/health` — 向量库健康检查

## 3. Sentiment Critic — 舆情数据契约

### 输出 Schema: SentimentData

```json
{
  "uid": "a1b2c3d4e5f6...",
  "metadata": {
    "title": "string",
    "platform": "string",
    "last_update": "string"
  },
  "sentiment_scores": {
    "overall": "number [0.0, 10.0] - 综合评分",
    "style": "number [0.0, 10.0] - 文笔分数",
    "logic": "number [0.0, 10.0] - 逻辑分数",
    "character": "number [0.0, 10.0] - 人物塑造分数",
    "update_stability": "number [0.0, 10.0] - 更新稳定性分数",
    "toxicity_index": "number [0.0, 1.0] - 毒性指数 (越低越好)"
  },
  "critic_summary": {
    "one_liner": "string - 一句话毒舌点评",
    "pros": ["string[] - 入坑理由 (最多 3 条)"],
    "cons": ["string[] - 避雷点 (最多 3 条)"]
  },
  "review_stats": {
    "total_count": "integer",
    "positive_ratio": "number [0.0, 1.0]",
    "negative_ratio": "number [0.0, 1.0]",
    "source_breakdown": {
      "tieba": "integer",
      "douban": "integer",
      "xiaohongshu": "integer"
    }
  }
}
```

### Mock 接口

- `GET /api/v1/sentiment/detail/{uid}` — 单书舆情详情
- `GET /api/v1/sentiment/compare?uids={uid1,uid2,uid3}` — 多书对比

## 4. 统一聚合 Schema — 结果聚合契约

### System Integrator 聚合输出

```json
{
  "uid": "a1b2c3d4e5f6...",
  "metadata": {
    "title": "string",
    "platform": "string",
    "last_update": "string"
  },
  "trend_metrics": { "... 来自 Trend Explorer" },
  "sentiment_scores": { "... 来自 Sentiment Critic" },
  "search_info": { "... 来自 Safe-Search Architect (搜索场景下)" },
  "aggregated_at": "string - ISO 8601"
}
```

## 校验规则

1. 所有接口输出必须通过对应 JSON Schema 的**强校验**，额外字段将被丢弃
2. `uid` 字段在所有 Schema 中均为必填
3. 数值范围必须严格落在定义区间内，越界值替换为最近边界值
4. 枚举字段不接受未定义值，非法值替换为默认值
5. ISO 8601 时间戳统一使用 UTC 时区
