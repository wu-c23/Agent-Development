# system-openapi-v1.0 · 全局 API 接口定义文档

> 模块：系统集成与交互体验  
> 负责人：苗文昊（System Integrator & UI/UX）  
> 版本：v1.0  
> 规范：OpenAPI 3.0.3  
> 适用范围：AI Fiction Navigator 网络小说智能推荐系统全模块对外接口

---

## 一、设计思路说明

### 1.1 为什么需要全局 API 规范

本项目采用"全权负责制"，每位成员独立交付端到端模块。若各模块各自定义接口风格（命名、错误码、分页、版本号），将导致：

- Router Agent 编排时需为每个模块写专属适配器，违背"标准化数据契约"原则
- 前端组件无法复用统一的 HTTP 客户端
- 联调阶段出现"接口对不上"的扯皮，拖慢整体进度
- 故障定位时无法用统一的 trace_id 串联全链路日志

因此，集成端必须先行交付**全局 API 规范**，所有模块的 RESTful 接口与 Mock 接口都必须遵循此规范。本文档即为该规范的权威定义。

### 1.2 核心设计原则

- **RESTful 风格统一**  
  资源命名使用复数名词（`/novels`、`/reviews`），动词使用标准 HTTP 方法（GET/POST/PATCH/DELETE）。
- **URL 版本化前缀**  
  所有接口强制以 `/api/v1/` 开头，未来 V2 升级时新旧版本并存，符合文档"V1/V2 版本化管理"要求。
- **统一响应封装**  
  所有响应使用 `{code, message, data, trace_id}` 结构，便于 Router Agent 统一解析。
- **统一错误码**  
  采用三段式错误码 `MODULE_CATEGORY_DETAIL`（如 `SEARCH_VECTOR_TIMEOUT`），便于跨模块故障定位。
- **全链路 trace_id**  
  请求头强制携带 `X-Trace-Id`，由 Router Agent 生成，下游模块透传，对接 `agent_session_logs` 表。
- **Mock 优先**  
  各模块在正式接口未完成前，必须按本规范提供 Mock 接口，集成端可独立推进编排开发。
- **JSON Schema 强校验**  
  所有请求体与响应体必须符合附录 A 的 Schema 定义，校验不通过直接返回 `400`。

### 1.3 接口分组总览

- **趋势模块**（吴隐 · `/api/v1/trend/*`）
  - 获取实时热榜
  - 获取单本小说热度曲线
  - 获取流派演变分析
- **搜索模块**（吴宸 · `/api/v1/search/*`）
  - 语义搜索（含避雷过滤）
  - 相似书推荐
  - 避雷词管理
- **舆情模块**（武文杰 · `/api/v1/sentiment/*`）
  - 获取小说聚合评分
  - 获取毒舌点评
  - 获取原始评论列表
- **集成端**（苗文昊 · `/api/v1/agent/*` & `/api/v1/users/*` & `/api/v1/admin/*`）
  - AI 书友对话
  - 用户画像管理
  - 系统运维监控

### 1.4 模块间调用约定（无插件，纯列表表达）

- 前端请求路径
  - 用户聊天 → `POST /api/v1/agent/chat` → Router Agent
- Router Agent 内部分发
  - 意图 = find_book → `POST /api/v1/search/semantic`
  - 意图 = review → `GET /api/v1/sentiment/novels/{uid}`
  - 意图 = trend → `GET /api/v1/trend/hot`
  - 意图 = chat → 直接 LLM 响应，不调用下游模块
- 结果聚合
  - Router Agent → 整合数据 → 调用 LLM 统一语调 → 返回 `data.response`

---

## 二、全局规范

### 2.1 基础信息

```yaml
openapi: 3.0.3
info:
  title: AI Fiction Navigator System API
  description: 网络小说智能推荐系统全局接口定义
  version: 1.0.0
  contact:
    name: 苗文昊 (System Integrator)
servers:
  - url: https://api.fiction-navigator.local/api/v1
    description: 生产环境
  - url: http://localhost:8000/api/v1
    description: 本地开发环境
  - url: http://mock.fiction-navigator.local/api/v1
    description: Mock 环境（联调用）
```

### 2.2 统一请求头

| 请求头          | 必填              | 说明                                                    |
| --------------- | ----------------- | ------------------------------------------------------- |
| `X-Trace-Id`    | 是                | 全链路追踪 ID，UUID v4 格式，由 Router Agent 或前端生成 |
| `X-User-Id`     | 否                | 当前用户 ID，未登录时可省略或传游客 UUID                |
| `Authorization` | 视接口而定        | `Bearer <token>`，管理端接口必填                        |
| `Content-Type`  | POST/PATCH 时必填 | 固定 `application/json`                                 |

### 2.3 统一响应结构

```json
{
  "code": 0,
  "message": "success",
  "data": { },
  "trace_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**字段说明：**

- `code`：业务状态码，`0` 表示成功，非零表示业务错误（与 HTTP 状态码独立）
- `message`：人类可读的错误描述
- `data`：实际业务数据，失败时可为 `null`
- `trace_id`：回传请求头中的 trace_id，便于客户端日志关联

### 2.4 统一错误码

| HTTP 状态 | 业务码（示例）               | 说明           |
| --------- | ---------------------------- | -------------- |
| 200       | `0`                          | 成功           |
| 400       | `COMMON_PARAM_INVALID`       | 请求参数非法   |
| 401       | `COMMON_AUTH_REQUIRED`       | 缺少认证信息   |
| 403       | `COMMON_PERMISSION_DENIED`   | 无权限         |
| 404       | `COMMON_RESOURCE_NOT_FOUND`  | 资源不存在     |
| 429       | `COMMON_RATE_LIMITED`        | 触发限流       |
| 500       | `COMMON_INTERNAL_ERROR`      | 服务内部错误   |
| 503       | `TREND_SERVICE_UNAVAILABLE`  | 趋势模块降级中 |
| 503       | `SEARCH_VECTOR_TIMEOUT`      | 向量检索超时   |
| 503       | `SENTIMENT_LLM_RATE_LIMITED` | 舆情 LLM 限流  |

错误码命名规则：`<模块>_<类别>_<具体原因>`，全大写下划线分隔。

### 2.5 统一分页参数

| 参数        | 类型 | 默认值 | 说明               |
| ----------- | ---- | ------ | ------------------ |
| `page`      | int  | 1      | 页码，从 1 开始    |
| `page_size` | int  | 20     | 每页条数，最大 100 |

分页响应：

```json
{
  "items": [],
  "total": 128,
  "page": 1,
  "page_size": 20,
  "has_next": true
}
```

---

## 三、趋势模块接口（吴隐 · `/api/v1/trend/*`）

### 3.1 获取实时热榜 `GET /api/v1/trend/hot`

**业务场景：** "全网风向标"大屏首页、Router Agent 处理"最近什么火"类意图。

**请求参数（Query）：**

| 参数       | 类型   | 必填 | 说明                                                 |
| ---------- | ------ | ---- | ---------------------------------------------------- |
| `platform` | string | 否   | 平台过滤，如 `qidian` / `zongheng`，省略则全平台聚合 |
| `category` | string | 否   | 分类过滤，如 `xuanhuan`                              |
| `limit`    | int    | 否   | 返回条数，默认 20，最大 50                           |

**响应示例：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "uid": "a3f5...e9c1",
        "title": "诡秘之主",
        "platform": "qidian",
        "author": "爱潜水的乌贼",
        "category": "xuanhuan",
        "heat_score": 0.9821,
        "rank_overall": 1,
        "tags": ["蒸汽朋克", "克苏鲁", "无敌流"],
        "trend_direction": "up"
      }
    ],
    "snapshot_at": "2024-11-20T10:00:00Z"
  },
  "trace_id": "..."
}
```

### 3.2 获取热度曲线 `GET /api/v1/trend/novels/{uid}/timeline`

**业务场景：** 小说详情页绘制热度趋势图。

**路径参数：** `uid` - 小说唯一标识

**Query 参数：**

| 参数          | 类型   | 必填 | 说明                                       |
| ------------- | ------ | ---- | ------------------------------------------ |
| `range`       | string | 否   | 时间范围：`7d` / `30d` / `90d`，默认 `30d` |
| `granularity` | string | 否   | 粒度：`hour` / `day`，默认 `day`           |

**响应示例：**

```json
{
  "code": 0,
  "data": {
    "uid": "a3f5...e9c1",
    "points": [
      { "snapshot_at": "2024-10-21T00:00:00Z", "heat_score": 0.9512 },
      { "snapshot_at": "2024-10-22T00:00:00Z", "heat_score": 0.9624 }
    ]
  }
}
```

### 3.3 获取流派演变分析 `GET /api/v1/trend/genres/evolution`

**业务场景：** 大屏展示"废土风 → 规则怪谈"等流派迁移分析。

**Query 参数：**

| 参数     | 类型   | 必填 | 说明                                          |
| -------- | ------ | ---- | --------------------------------------------- |
| `window` | string | 否   | 分析窗口：`weekly` / `monthly`，默认 `weekly` |

**响应示例：**

```json
{
  "code": 0,
  "data": {
    "transitions": [
      {
        "from_tag": "废土风",
        "to_tag": "规则怪谈",
        "strength": 0.76,
        "sample_novels": ["a3f5...e9c1", "b2c4...f8a3"]
      }
    ],
    "rising_tags": ["规则怪谈", "无限流", "异常生物管理局"],
    "declining_tags": ["重生流", "种田文"]
  }
}
```

---

## 四、搜索模块接口（吴宸 · `/api/v1/search/*`）

### 4.1 语义搜索 `POST /api/v1/search/semantic`

**业务场景：** Router Agent 处理"找书"意图的核心入口，支持自然语言 query。

**请求体：**

```json
{
  "query": "类似《诡秘之主》但基调轻快一些的小说",
  "filters": {
    "category": "xuanhuan",
    "min_heat_score": 0.5,
    "min_logic_score": 7.0
  },
  "avoid_tags": ["烂尾", "主角降智"],
  "top_k": 10,
  "user_id": "guest-uuid-xxx"
}
```

**字段说明：**

- `query`：自然语言查询，必填
- `filters`：结构化过滤条件，可选
- `avoid_tags`：避雷标签，若传入 `user_id` 则自动合并该用户 `user_profiles.avoid_tags`
- `top_k`：返回数量，默认 10，最大 50

**响应示例：**

```json
{
  "code": 0,
  "data": {
    "items": [
      {
        "uid": "b2c4...f8a3",
        "title": "宿命之环",
        "score": 0.8932,
        "match_reasons": ["克苏鲁元素", "升级体系明确", "基调相对轻松"],
        "filtered_by_avoid": false
      }
    ],
    "query_understanding": {
      "core_intent": "寻找类克苏鲁但轻松的玄幻小说",
      "extracted_tags": ["克苏鲁", "玄幻", "轻松"]
    }
  }
}
```

### 4.2 相似书推荐 `GET /api/v1/search/novels/{uid}/similar`

**业务场景：** 详情页"看了这本书的人还看了"模块。

**路径参数：** `uid`

**Query 参数：**

| 参数                 | 类型 | 必填 | 说明                       |
| -------------------- | ---- | ---- | -------------------------- |
| `top_k`              | int  | 否   | 默认 10                    |
| `same_category_only` | bool | 否   | 是否限定同分类，默认 false |

**响应示例：**

```json
{
  "code": 0,
  "data": {
    "anchor_uid": "a3f5...e9c1",
    "items": [
      { "uid": "b2c4...f8a3", "title": "宿命之环", "similarity": 0.91 }
    ]
  }
}
```

### 4.3 避雷词管理 `PATCH /api/v1/users/{user_id}/avoid-tags`

**业务场景：** 用户在前端管理个人避雷词，同时同步至搜索模块。

**请求体：**

```json
{
  "add": ["种马", "无脑爽文"],
  "remove": ["重生"]
}
```

**响应示例：**

```json
{
  "code": 0,
  "data": {
    "user_id": "guest-uuid-xxx",
    "avoid_tags": ["烂尾", "主角降智", "种马", "无脑爽文"]
  }
}
```

---

## 五、舆情模块接口（武文杰 · `/api/v1/sentiment/*`）

### 5.1 获取聚合评分 `GET /api/v1/sentiment/novels/{uid}`

**业务场景：** 详情页舆情看板组件、Router Agent 处理"这本书评价如何"意图。

**响应示例：**

```json
{
  "code": 0,
  "data": {
    "uid": "a3f5...e9c1",
    "scores": {
      "logic": 8.5,
      "style": 7.8,
      "update": 6.2,
      "character": 8.9
    },
    "toxicity_index": 0.18,
    "positive_ratio": 0.82,
    "review_count": 1283,
    "critic_summary": "文笔扎实，世界观炸裂，但更新慢得能逼疯读者。",
    "analyzed_at": "2024-11-20T08:00:00Z"
  }
}
```

### 5.2 获取毒舌点评 `GET /api/v1/sentiment/novels/{uid}/critic`

**业务场景：** 用户主动点击"看一句毒舌点评"按钮。

**Query 参数：**

| 参数    | 类型   | 必填 | 说明                                                   |
| ------- | ------ | ---- | ------------------------------------------------------ |
| `style` | string | 否   | 点评风格：`toxic` / `objective` / `hype`，默认 `toxic` |

**响应示例：**

```json
{
  "code": 0,
  "data": {
    "uid": "a3f5...e9c1",
    "style": "toxic",
    "summary": "这本书最大的缺点就是看完了，最大的优点也是看完了。",
    "entry_reason": "如果你能忍受作者龟速更新，那这是近五年最好的克苏鲁玄幻。"
  }
}
```

### 5.3 获取原始评论列表 `GET /api/v1/sentiment/novels/{uid}/reviews`

**业务场景：** 用户点击"查看真实书评"深度交互。

**Query 参数：**

| 参数              | 类型   | 必填 | 说明                                                |
| ----------------- | ------ | ---- | --------------------------------------------------- |
| `sentiment`       | string | 否   | 过滤标签：`positive` / `negative` / `controversial` |
| `source_platform` | string | 否   | 来源平台过滤                                        |
| `page`            | int    | 否   | 默认 1                                              |
| `page_size`       | int    | 否   | 默认 20                                             |

**响应示例：**

```json
{
  "code": 0,
  "data": {
    "items": [
      {
        "review_id": "rev_x3f9...",
        "source_platform": "douban",
        "author_name": "克总信徒",
        "content": "世界观铺垫太长，前 300 章劝退，但坚持下来是真的爽。",
        "sentiment_label": "controversial",
        "classified_tags": ["前期劝退", "后期高能"],
        "like_count": 421,
        "posted_at": "2024-09-15T12:30:00Z"
      }
    ],
    "total": 1283,
    "page": 1,
    "page_size": 20,
    "has_next": true
  }
}
```

---

## 六、集成端接口（苗文昊 · `/api/v1/agent/*` & `/api/v1/users/*` & `/api/v1/admin/*`）

### 6.1 AI 书友对话 `POST /api/v1/agent/chat`

**业务场景：** 前端聊天框入口，所有用户交互的统一入口。

**请求体：**

```json
{
  "user_id": "guest-uuid-xxx",
  "session_id": "sess_a1b2c3",
  "message": "最近有没有像《诡秘之主》的新书推荐？",
  "context": []
}
```

**字段说明：**

- `session_id`：会话 ID，新会话不传，由服务端生成并返回
- `context`：历史对话，可选，格式 `[{role, content}]`

**响应示例：**

```json
{
  "code": 0,
  "data": {
    "session_id": "sess_a1b2c3",
    "intent": "find_book",
    "route_modules": ["search", "sentiment"],
    "response": "基于你的口味，我推荐《宿命之环》……",
    "structured_results": [
      {
        "uid": "b2c4...f8a3",
        "title": "宿命之环",
        "match_reasons": ["克苏鲁元素", "升级体系明确"],
        "scores": { "logic": 8.2, "style": 8.0 }
      }
    ],
    "latency_ms": 1832
  }
}
```

### 6.2 获取用户画像 `GET /api/v1/users/{user_id}`

**响应示例：**

```json
{
  "code": 0,
  "data": {
    "user_id": "guest-uuid-xxx",
    "nickname": "匿名读者",
    "preferred_tags": ["克苏鲁", "无敌流"],
    "avoid_tags": ["烂尾", "种马"],
    "preferred_styles": ["硬核", "悬疑"],
    "interaction_stats": {
      "query_count": 42,
      "favorite_count": 8
    }
  }
}
```

### 6.3 更新用户画像 `PATCH /api/v1/users/{user_id}`

**请求体（所有字段均可选）：**

```json
{
  "nickname": "克总信徒",
  "preferred_tags": ["克苏鲁", "蒸汽朋克"],
  "preferred_styles": ["硬核"]
}
```

### 6.4 系统健康检查 `GET /api/v1/admin/health`

**业务场景：** 运维监控、模块降级判断。

**响应示例：**

```json
{
  "code": 0,
  "data": {
    "status": "healthy",
    "modules": {
      "trend":       { "status": "up",   "latency_ms": 45 },
      "search":      { "status": "up",   "latency_ms": 120 },
      "sentiment":   { "status": "degraded", "latency_ms": 890 },
      "integration": { "status": "up",   "latency_ms": 12 }
    },
    "checked_at": "2024-11-20T10:00:00Z"
  }
}
```

**状态枚举：** `up` / `degraded`（降级中，但仍可服务）/ `down`（不可用，已触发兜底）

### 6.5 Token 消耗查询 `GET /api/v1/admin/token-usage`

**业务场景：** 运维月报模板的数据源。

**Query 参数：**

| 参数         | 类型   | 必填 | 说明                                                |
| ------------ | ------ | ---- | --------------------------------------------------- |
| `start_date` | string | 是   | ISO 8601 日期，如 `2024-11-01`                      |
| `end_date`   | string | 是   | ISO 8601 日期                                       |
| `group_by`   | string | 否   | 聚合维度：`module` / `model` / `day`，默认 `module` |

**响应示例：**

```json
{
  "code": 0,
  "data": {
    "range": { "start": "2024-11-01", "end": "2024-11-20" },
    "group_by": "module",
    "items": [
      { "key": "search",      "total_tokens": 1283492, "cost_usd": 12.83 },
      { "key": "sentiment",   "total_tokens": 982143,  "cost_usd": 9.82 },
      { "key": "integration", "total_tokens": 421983,  "cost_usd": 4.21 },
      { "key": "trend",       "total_tokens": 132847,  "cost_usd": 1.32 }
    ],
    "total_cost_usd": 28.18
  }
}
```

---

## 七、限流与降级策略

### 7.1 限流规则

| 接口类型             | 限流阈值              | 触发后行为                       |
| -------------------- | --------------------- | -------------------------------- |
| 用户级（Agent Chat） | 60 次 / 分钟 / user   | 返回 429 + `COMMON_RATE_LIMITED` |
| 搜索类（语义检索）   | 30 次 / 分钟 / user   | 返回 429                         |
| 管理端               | 600 次 / 分钟 / token | 返回 429                         |
| Mock 接口            | 不限流                | -                                |

### 7.2 降级策略（呼应"架构解耦"禁令）

- **趋势模块故障** → Router Agent 跳过 `route_modules=trend` 分支，返回"趋势数据暂不可用"
- **舆情模块故障** → 详情页隐藏舆情卡片，但搜索与详情主功能可用
- **搜索模块故障** → 严重故障，触发兜底：返回热榜前 10 作为替代结果，并在响应中标记 `fallback: true`
- **集成端 LLM 故障** → 跳过"语调统一"步骤，直接返回结构化结果

**关键原则：** 任何单一模块的故障**不得**导致 `/api/v1/agent/chat` 完全不可用。

---

## 八、Mock 接口规范

### 8.1 Mock 服务要求

- 各模块必须在**正式接口完成前**提供 Mock 接口，部署于 `http://mock.fiction-navigator.local/api/v1`
- Mock 响应必须**完全符合**本规范定义的 JSON Schema
- Mock 数据建议固定 3-5 本"金标小说"（如《诡秘之主》《大奉打更人》），便于跨模块联调对齐
- Mock 接口应支持**故障注入**：在请求头加 `X-Mock-Fail: true` 时返回模拟错误，用于降级测试

### 8.2 Mock 数据约定

- 金标 UID 列表（建议各模块统一使用）：
  - `a3f5e9c1...` → 诡秘之主
  - `b2c4f8a3...` → 宿命之环
  - `c1d3a7b2...` → 大奉打更人
  - `d4e6b9c5...` → 道诡异仙
  - `e5f7c1d8...` → 我用奇书成圣师

---

## 九、附录 A：核心 JSON Schema 定义

### A.1 通用响应 Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "UnifiedResponse",
  "type": "object",
  "required": ["code", "message", "trace_id"],
  "properties": {
    "code":     { "type": ["integer", "string"] },
    "message":  { "type": "string" },
    "data":     { "type": ["object", "array", "null"] },
    "trace_id": { "type": "string", "format": "uuid" }
  }
}
```

### A.2 Novel 核心对象 Schema

```json
{
  "title": "Novel",
  "type": "object",
  "required": ["uid", "title", "platform"],
  "properties": {
    "uid":      { "type": "string", "pattern": "^[a-f0-9]{64}$" },
    "title":    { "type": "string", "maxLength": 255 },
    "platform": { "type": "string", "enum": ["qidian", "zongheng", "fanqie", "jjwxc"] },
    "author":   { "type": "string" },
    "category": { "type": "string" },
    "tags":     { "type": "array", "items": { "type": "string" } }
  }
}
```

### A.3 SemanticSearchRequest Schema

```json
{
  "title": "SemanticSearchRequest",
  "type": "object",
  "required": ["query"],
  "properties": {
    "query":       { "type": "string", "minLength": 1, "maxLength": 500 },
    "filters":     { "type": "object" },
    "avoid_tags":  { "type": "array", "items": { "type": "string" } },
    "top_k":       { "type": "integer", "minimum": 1, "maximum": 50, "default": 10 },
    "user_id":     { "type": "string" }
  }
}
```

### A.4 AgentChatRequest Schema

```json
{
  "title": "AgentChatRequest",
  "type": "object",
  "required": ["message"],
  "properties": {
    "user_id":    { "type": "string" },
    "session_id": { "type": "string" },
    "message":    { "type": "string", "minLength": 1, "maxLength": 1000 },
    "context": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "role":    { "type": "string", "enum": ["user", "assistant"] },
          "content": { "type": "string" }
        }
      }
    }
  }
}
```

---

## 十、附录 B：接口归属责任矩阵

| 接口路径                          | HTTP 方法   | 负责人             | 验收人 |
| --------------------------------- | ----------- | ------------------ | ------ |
| `/trend/hot`                      | GET         | 吴隐               | 苗文昊 |
| `/trend/novels/{uid}/timeline`    | GET         | 吴隐               | 苗文昊 |
| `/trend/genres/evolution`         | GET         | 吴隐               | 苗文昊 |
| `/search/semantic`                | POST        | 吴宸               | 苗文昊 |
| `/search/novels/{uid}/similar`    | GET         | 吴宸               | 苗文昊 |
| `/users/{user_id}/avoid-tags`     | PATCH       | 苗文昊（吴宸消费） | 吴宸   |
| `/sentiment/novels/{uid}`         | GET         | 武文杰             | 苗文昊 |
| `/sentiment/novels/{uid}/critic`  | GET         | 武文杰             | 苗文昊 |
| `/sentiment/novels/{uid}/reviews` | GET         | 武文杰             | 苗文昊 |
| `/agent/chat`                     | POST        | 苗文昊             | 全员   |
| `/users/{user_id}`                | GET / PATCH | 苗文昊             | 全员   |
| `/admin/health`                   | GET         | 苗文昊             | 苗文昊 |
| `/admin/token-usage`              | GET         | 苗文昊             | 苗文昊 |

---

## 十一、版本变更记录

| 版本 | 日期       | 变更说明                              | 作者   |
| ---- | ---------- | ------------------------------------- | ------ |
| v1.0 | 2024-XX-XX | 初版发布，覆盖 4 大模块 13 个核心接口 | 苗文昊 |