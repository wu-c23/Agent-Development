# router-agent-workflow · Router Agent 编排工作流设计文档

> 模块：系统集成与交互体验  
> 负责人：苗文昊（System Integrator & UI/UX）  
> 版本：v1.0  
> 技术栈：LangGraph (状态机) + LangChain (工具调用) + OpenAI Function Calling  
> 适用范围：AI Fiction Navigator 系统的中央编排层

---

## 一、设计思路说明

### 1.1 Router Agent 在系统中的定位

Router Agent 是整个 AI Fiction Navigator 的**大脑与神经中枢**。它不直接处理任何业务逻辑（爬虫、向量检索、舆情分析都由其他模块负责），而是承担以下四类职责：

- **意图理解**：将用户自然语言 query 分类到 `find_book` / `review` / `trend` / `chat` 四种意图
- **任务编排**：根据意图调用一个或多个下游模块的 API
- **结果聚合**：将多源数据合并、去重、排序，并通过 LLM 统一语调
- **可观测性**：全链路埋点（trace_id、token、latency），写入 `agent_session_logs` 与 `token_usage_logs`

### 1.2 为什么选择 LangGraph 而不是 LangChain Agent

LangChain 的传统 Agent（如 ReAct）采用"自由发挥"模式，让 LLM 自行决定调用哪个 Tool。但本系统有以下特殊需求：

- **可预测的成本**：每个用户请求的 Token 消耗必须可估算，不能让 LLM 反复 self-loop
- **可追溯的链路**：必须能在日志中清晰看到"用户问什么 → 走了哪个分支 → 调用了什么 → 返回了什么"
- **强降级保障**：任何下游模块故障时必须有明确兜底路径，不能让 Agent "卡死"

因此，本项目采用 **LangGraph 状态机模式**：所有节点与边显式定义，LLM 只在"意图分类"和"结果总结"两个固定节点参与，**避免 Agent 自由调用工具带来的不可控**。

### 1.3 核心设计原则

- **状态机优于自由 Agent**：用有限状态机约束 LLM 行为，保证可预测性
- **单次 LLM 调用预算**：一次 `/agent/chat` 请求最多触发 2 次 LLM 调用（意图分类 + 结果总结），杜绝失控
- **下游调用并行化**：当意图需要多个模块（如 `review` 同时需要舆情 + 趋势）时，并发调用以降低延迟
- **失败即兜底，不重试**：单一模块失败立即走降级分支，**不在 Agent 层做重试**（重试是各模块自己的责任）
- **全链路埋点**：每个节点进入/退出时打点，最终写入 `agent_session_logs`

### 1.4 与其他文档的关系

- 接口契约 → 参考《system-openapi-v1.0.md》第 6.1 节 `POST /api/v1/agent/chat`
- 数据落库 → 参考《unified-data-model-sql.md》第 2.7/2.8 节（会话日志与 Token 日志表）
- 运维监控 → 本文档输出的指标将被《ops-monthly-report-template.md》消费

---

## 二、状态机总体结构

### 2.1 节点（Node）定义

Router Agent 工作流由 **9 个核心节点** 构成：

- `START`：入口节点，接收用户请求
- `parse_input`：解析输入，加载用户画像与会话上下文
- `classify_intent`：LLM 意图分类（第 1 次 LLM 调用）
- `route_dispatch`：根据意图分发到下游分支
- `branch_find_book`：调用搜索模块（可能并发调用舆情模块补充评分）
- `branch_review`：调用舆情模块（可能并发调用趋势模块补充热度）
- `branch_trend`：调用趋势模块
- `branch_chat`：直接走 LLM 兜底闲聊
- `aggregate_and_summarize`：结果聚合 + LLM 语调统一（第 2 次 LLM 调用）
- `log_and_respond`：写入日志，返回响应
- `END`：结束节点
- `fallback`：兜底节点（任何下游失败时进入）

### 2.2 边（Edge）流转规则

- `START` → `parse_input`
- `parse_input` → `classify_intent`
- `classify_intent` → `route_dispatch`
- `route_dispatch` → 根据 `intent` 字段分发：
  - `intent = find_book` → `branch_find_book`
  - `intent = review` → `branch_review`
  - `intent = trend` → `branch_trend`
  - `intent = chat` → `branch_chat`
  - `intent = unknown` → `fallback`
- 所有 `branch_*` → `aggregate_and_summarize`
- 任何节点抛错 → `fallback`
- `aggregate_and_summarize` → `log_and_respond`
- `fallback` → `log_and_respond`
- `log_and_respond` → `END`

### 2.3 状态机流转示意（纯列表表达，无插件）

```
[START]
  ↓
[parse_input] ── 加载 user_profiles / 会话上下文
  ↓
[classify_intent] ── LLM #1 调用：意图 + 槽位提取
  ↓
[route_dispatch] ── 根据 intent 字段路由
  ├─→ [branch_find_book]   → 调用 /search/semantic (+ /sentiment 补分)
  ├─→ [branch_review]      → 调用 /sentiment/novels/{uid} (+ /trend 补热度)
  ├─→ [branch_trend]       → 调用 /trend/hot
  ├─→ [branch_chat]        → 不调用下游，进入 fallback
  └─→ [fallback]           ── 兜底（任意失败都走这里）
  ↓
[aggregate_and_summarize] ── LLM #2 调用：统一语调
  ↓
[log_and_respond] ── 写入 agent_session_logs + token_usage_logs
  ↓
[END]
```

---

## 三、全局状态（State）定义

LangGraph 中所有节点共享同一个 `AgentState` 对象，结构如下：

```python
from typing import TypedDict, List, Optional, Literal

class AgentState(TypedDict):
    # ===== 输入字段 =====
    user_id: Optional[str]
    session_id: str
    user_message: str
    chat_history: List[dict]
    trace_id: str

    # ===== 上下文字段 =====
    user_profile: Optional[dict]
    avoid_tags: List[str]
    preferred_tags: List[str]

    # ===== 意图字段（classify_intent 输出）=====
    intent: Literal["find_book", "review", "trend", "chat", "unknown"]
    slots: dict
    confidence: float

    # ===== 下游结果字段 =====
    search_results: Optional[list]
    sentiment_results: Optional[dict]
    trend_results: Optional[list]
    
    # ===== 聚合输出字段 =====
    final_response: Optional[str]
    structured_results: Optional[list]
    
    # ===== 元信息字段 =====
    route_modules: List[str]
    latency_ms: dict
    token_usage: List[dict]
    errors: List[dict]
    status: Literal["success", "partial", "fallback", "failed"]
```

**字段说明：**

- `slots`：意图分类时提取的槽位，如 `{"reference_book": "诡秘之主", "mood_filter": "轻快"}`
- `route_modules`：实际调用了哪些下游模块，用于写入日志
- `latency_ms`：每个节点的耗时，结构如 `{"classify_intent": 320, "branch_find_book": 1280}`
- `token_usage`：每次 LLM 调用的 Token 消耗，用于审计
- `errors`：累积所有节点的错误信息，即使部分失败也保留
- `status`：最终状态——`success`（全成功）/ `partial`（部分模块失败但仍有结果）/ `fallback`（完全兜底）/ `failed`（整体失败）

---

## 四、节点详细设计

### 4.1 `parse_input` 节点

**职责：** 加载用户画像，拼接对话上下文。

**输入：** `user_id`, `session_id`, `user_message`, `chat_history`

**核心逻辑：**

- 若 `user_id` 存在，调用 `GET /api/v1/users/{user_id}` 加载画像
- 若 `user_id` 为空，生成临时游客 UUID
- 截断 `chat_history`，仅保留最近 6 轮（节省 Token）

**输出字段：** `user_profile`, `avoid_tags`, `preferred_tags`

**降级策略：** 画像加载失败时使用空画像继续，**不阻塞主流程**

**伪代码：**

```python
def parse_input(state: AgentState) -> AgentState:
    user_id = state.get("user_id") or f"guest-{uuid4()}"
    try:
        profile = http_get(f"/api/v1/users/{user_id}", timeout=500)
        state["user_profile"] = profile["data"]
        state["avoid_tags"] = profile["data"].get("avoid_tags", [])
        state["preferred_tags"] = profile["data"].get("preferred_tags", [])
    except Exception as e:
        state["errors"].append({"node": "parse_input", "msg": str(e)})
        state["avoid_tags"] = []
        state["preferred_tags"] = []
    
    state["chat_history"] = state["chat_history"][-6:]
    return state
```

---

### 4.2 `classify_intent` 节点（LLM 调用 #1）

**职责：** 调用 LLM 进行意图分类与槽位提取。

**输入：** `user_message`, `chat_history`, `preferred_tags`

**LLM Prompt 模板：**

```
你是一个网络小说推荐系统的意图分类器。请将用户的输入分类为以下四种意图之一：

1. find_book（找书）：用户想要寻找符合某种特征的小说
2. review（评价）：用户想了解某本具体小说的评价/口碑
3. trend（趋势）：用户想了解最近流行什么、什么书火
4. chat（闲聊）：与小说无关的对话

用户当前画像偏好：{preferred_tags}
最近对话历史：{chat_history}

用户输入："{user_message}"

请以 JSON 格式返回：
{
  "intent": "...",
  "confidence": 0.0~1.0,
  "slots": {
    "reference_book": "（若提到某本书则填写）",
    "category": "（若提到分类）",
    "mood_filter": "（如：轻快、压抑、治愈）",
    "uid": "（若用户明确指定 UID 则填写）"
  }
}
```

**模型选择：** `gpt-4o-mini`（成本敏感，意图分类无需强模型）

**输出字段：** `intent`, `slots`, `confidence`

**降级策略：**

- LLM 调用失败 → 降级为关键词匹配（命中"推荐/找书"→ `find_book`，命中"怎么样/评价"→ `review`，命中"最近/火/热门"→ `trend`，否则 `chat`）
- `confidence < 0.5` → 视为 `unknown`，进入 `fallback`

**伪代码：**

```python
def classify_intent(state: AgentState) -> AgentState:
    t0 = time.time()
    try:
        resp = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": PROMPT.format(...)}],
            response_format={"type": "json_object"},
            temperature=0.0
        )
        result = json.loads(resp.choices[0].message.content)
        state["intent"] = result["intent"]
        state["slots"] = result.get("slots", {})
        state["confidence"] = result.get("confidence", 0.0)
        
        state["token_usage"].append({
            "node": "classify_intent",
            "model": "gpt-4o-mini",
            "prompt_tokens": resp.usage.prompt_tokens,
            "completion_tokens": resp.usage.completion_tokens
        })
    except Exception as e:
        state["errors"].append({"node": "classify_intent", "msg": str(e)})
        state["intent"] = keyword_fallback(state["user_message"])
        state["confidence"] = 0.6
    
    state["latency_ms"]["classify_intent"] = int((time.time() - t0) * 1000)
    return state
```

---

### 4.3 `route_dispatch` 节点

**职责：** 纯路由逻辑，无业务处理。

**输入：** `intent`, `confidence`

**输出：** 返回下一个节点名（LangGraph 的条件边机制）

**伪代码：**

```python
def route_dispatch(state: AgentState) -> str:
    if state["confidence"] < 0.5:
        return "fallback"
    
    return {
        "find_book": "branch_find_book",
        "review": "branch_review",
        "trend": "branch_trend",
        "chat": "branch_chat"
    }.get(state["intent"], "fallback")
```

---

### 4.4 `branch_find_book` 节点

**职责：** 处理找书意图，调用搜索模块（必要时并发调用舆情补分）。

**输入：** `user_message`, `slots`, `avoid_tags`, `user_id`

**核心逻辑：**

1. 构造 `SemanticSearchRequest`：
   - `query` = `user_message`
   - `avoid_tags` = `state.avoid_tags`（自动合并用户画像中的避雷词）
   - `top_k` = 10
2. 调用 `POST /api/v1/search/semantic`
3. 拿到 top 10 结果后，**并发**调用 `GET /api/v1/sentiment/novels/{uid}` 补充评分
4. 将评分合并进 `search_results`

**降级策略：**

- 搜索模块失败 → 进入 `fallback`，因为找书没有搜索是无法工作的
- 舆情补分失败 → 继续返回搜索结果，但 `scores` 字段为 null，`status = partial`

**伪代码：**

```python
def branch_find_book(state: AgentState) -> AgentState:
    t0 = time.time()
    state["route_modules"].append("search")
    
    try:
        # Step 1: 语义搜索
        search_resp = http_post("/api/v1/search/semantic", {
            "query": state["user_message"],
            "avoid_tags": state["avoid_tags"],
            "top_k": 10,
            "user_id": state["user_id"]
        }, timeout=3000)
        
        items = search_resp["data"]["items"]
        
        # Step 2: 并发补分
        state["route_modules"].append("sentiment")
        uids = [item["uid"] for item in items]
        scores = parallel_fetch_sentiment(uids, timeout=1500)
        
        # Step 3: 合并
        for item in items:
            item["scores"] = scores.get(item["uid"])
        
        state["search_results"] = items
        state["status"] = "success" if all(scores.values()) else "partial"
        
    except SearchModuleError as e:
        state["errors"].append({"node": "branch_find_book", "msg": str(e)})
        state["status"] = "fallback"
        return "fallback"  # 直接跳转兜底
    
    state["latency_ms"]["branch_find_book"] = int((time.time() - t0) * 1000)
    return state
```

---

### 4.5 `branch_review` 节点

**职责：** 处理"某本书评价如何"的意图。

**输入：** `slots.reference_book` 或 `slots.uid`

**核心逻辑：**

1. 若有 `uid` 直接用；否则用 `reference_book` 调用 `/search/semantic` top_k=1 反查 UID
2. 调用 `GET /api/v1/sentiment/novels/{uid}` 获取评分
3. 并发调用 `GET /api/v1/sentiment/novels/{uid}/critic` 获取毒舌点评
4. 并发调用 `GET /api/v1/trend/novels/{uid}/timeline?range=30d` 获取热度趋势

**降级策略：**

- 找不到 UID → 返回"未找到对应小说"
- 舆情模块失败 → 进入 `fallback`（核心功能依赖）
- 趋势模块失败 → 不影响主流程，热度字段为 null

---

### 4.6 `branch_trend` 节点

**职责：** 处理"最近什么火"类意图。

**核心逻辑：**

1. 调用 `GET /api/v1/trend/hot?limit=10`
2. 若用户输入包含分类关键词，从 `slots.category` 提取并加入 query
3. 可选：调用 `/trend/genres/evolution` 补充流派演变信息

**降级策略：**

- 趋势模块失败 → 进入 `fallback`，返回"趋势数据暂不可用"

---

### 4.7 `branch_chat` 节点

**职责：** 闲聊兜底，不调用任何业务模块。

**核心逻辑：** 直接将用户消息丢给 `aggregate_and_summarize` 节点的 LLM，由其自行回复（系统人设：友好的小说书友）。

**降级策略：** 无下游依赖，不会失败

---

### 4.8 `aggregate_and_summarize` 节点（LLM 调用 #2）

**职责：** 将各模块结构化结果转换为自然语言，统一"AI 书友"语调。

**LLM Prompt 模板：**

```
你是"AI 书友"，一个懂网络小说、说话有温度、偶尔毒舌的推荐助手。
请基于以下结构化数据，给用户一个自然、有趣、不超过 300 字的回复。

用户问题："{user_message}"
意图类型：{intent}
检索到的小说数据：{search_results}
舆情数据：{sentiment_results}
趋势数据：{trend_results}

回复要求：
- 用第一人称"我"，称呼用户"你"
- 推荐时给出 2-3 句具体理由，避免空泛
- 若数据有缺失（如舆情未获取到），用"暂时没拿到口碑数据"这类自然说法带过，**禁止暴露技术细节**
- 若是闲聊意图，可以轻松幽默地回应
```

**模型选择：** `gpt-4o`（用户最终看到的回复，需高质量）

**输出字段：** `final_response`, `structured_results`

**降级策略：** LLM 失败时，用模板拼接结构化数据返回（如"为你找到以下小说：1. xxx 2. yyy"）

---

### 4.9 `log_and_respond` 节点

**职责：** 全链路日志落库 + 返回响应给客户端。

**核心逻辑：**

1. 写入 `agent_session_logs`：
   - `session_id`, `user_id`, `intent`, `route_modules`, `user_query`, `final_response`, `latency_ms`（总耗时）, `status`, `error_message`
2. 写入 `token_usage_logs`：
   - 遍历 `state.token_usage`，每条插入一行
3. 构造响应：

```json
{
  "code": 0,
  "data": {
    "session_id": "...",
    "intent": "find_book",
    "route_modules": ["search", "sentiment"],
    "response": "...",
    "structured_results": [...],
    "latency_ms": 1832
  },
  "trace_id": "..."
}
```

---

### 4.10 `fallback` 节点

**职责：** 全局兜底节点，确保任何情况下用户都能拿到响应。

**触发条件：**

- 任何节点抛出未捕获异常
- `confidence < 0.5`
- 关键下游模块（找书时的搜索模块、评价时的舆情模块）完全不可用

**核心逻辑：**

1. 根据失败原因构造友好提示：
   - 搜索失败 → "搜索服务暂时繁忙，先帮你看看最近的热门书吧" + 调用 `/trend/hot` 兜底
   - 舆情失败 → "这本书的口碑数据暂时拿不到，要不先看看简介？"
   - LLM 失败 → "我有点累了，要不你换个问法试试？"
2. 设置 `state["status"] = "fallback"`
3. 流向 `log_and_respond`

---

## 五、并发与超时策略

### 5.1 节点级超时

| 节点                        | 超时阈值 | 超时后行为             |
| --------------------------- | -------- | ---------------------- |
| `parse_input`               | 500ms    | 使用空画像继续         |
| `classify_intent`           | 2000ms   | 降级为关键词匹配       |
| `branch_find_book` 主调用   | 3000ms   | 进入 fallback          |
| `branch_find_book` 补分调用 | 1500ms   | 跳过补分，标记 partial |
| `branch_review` 主调用      | 2000ms   | 进入 fallback          |
| `branch_trend`              | 1500ms   | 进入 fallback          |
| `aggregate_and_summarize`   | 5000ms   | 用模板拼接兜底         |

### 5.2 并发调用

需要并发的场景：

- `branch_find_book`：搜索返回 10 个 UID 后，并发请求 10 个 `/sentiment/novels/{uid}`
- `branch_review`：同时请求 `/sentiment/novels/{uid}` 与 `/trend/novels/{uid}/timeline`

并发实现建议：`asyncio.gather()` 或 `concurrent.futures.ThreadPoolExecutor`

### 5.3 端到端 SLA 目标

- **P50 延迟**：≤ 2000ms
- **P95 延迟**：≤ 5000ms
- **可用率**：≥ 99%（含降级响应）
- **完全失败率**（连 fallback 都失败）：< 0.1%

---

## 六、可观测性与日志埋点

### 6.1 必埋点字段

每次请求结束后，必须保证以下数据落库：

- `agent_session_logs` 表：1 条
- `token_usage_logs` 表：N 条（N = LLM 调用次数）

### 6.2 日志样例

```json
{
  "session_id": "sess_a1b2c3",
  "user_id": "guest-uuid-xxx",
  "trace_id": "550e8400-e29b-41d4-a716-446655440000",
  "intent": "find_book",
  "confidence": 0.92,
  "route_modules": ["search", "sentiment"],
  "user_query": "类似《诡秘之主》但基调轻快的",
  "final_response": "基于你的口味，我推荐《宿命之环》……",
  "latency_breakdown": {
    "parse_input": 45,
    "classify_intent": 380,
    "branch_find_book": 1240,
    "aggregate_and_summarize": 820,
    "log_and_respond": 12
  },
  "total_latency_ms": 2497,
  "status": "success",
  "errors": []
}
```

### 6.3 关键监控指标

集成端需对以下指标持续监控（对接交付物 4 的运维月报）：

- **意图分类准确率**：通过用户后续行为（是否点击结果、是否追问）反推
- **各分支调用频次**：`find_book` / `review` / `trend` / `chat` 各占比
- **下游模块失败率**：每个模块单独统计
- **Fallback 触发率**：超过 5% 需要告警
- **Token 单次消耗中位数**：用于成本预估

---

## 七、与下游模块的契约约定

### 7.1 调用约定

- 所有下游调用必须传递 `X-Trace-Id` 请求头
- 所有下游调用强制 `timeout`，禁止无限等待
- 所有下游返回必须符合《system-openapi-v1.0.md》定义的响应结构
- Router Agent **不解析**下游业务错误细节，仅根据 `code` 字段判断成功/失败

### 7.2 失败响应约定

下游模块返回非 `code=0` 时，Router Agent 视为该次调用失败，根据分支策略决定：

- 进入 `fallback` 还是
- 标记 `partial` 继续主流程

下游模块**不应**抛出 HTTP 500，所有业务错误应通过 `code` 字段表达。

---

## 八、LangGraph 工程实现示例

### 8.1 状态图构建代码骨架

```python
from langgraph.graph import StateGraph, END

# 构建图
workflow = StateGraph(AgentState)

# 注册节点
workflow.add_node("parse_input", parse_input)
workflow.add_node("classify_intent", classify_intent)
workflow.add_node("branch_find_book", branch_find_book)
workflow.add_node("branch_review", branch_review)
workflow.add_node("branch_trend", branch_trend)
workflow.add_node("branch_chat", branch_chat)
workflow.add_node("aggregate_and_summarize", aggregate_and_summarize)
workflow.add_node("log_and_respond", log_and_respond)
workflow.add_node("fallback", fallback)

# 设置入口
workflow.set_entry_point("parse_input")

# 线性边
workflow.add_edge("parse_input", "classify_intent")

# 条件边：根据意图分发
workflow.add_conditional_edges(
    "classify_intent",
    route_dispatch,
    {
        "branch_find_book": "branch_find_book",
        "branch_review": "branch_review",
        "branch_trend": "branch_trend",
        "branch_chat": "branch_chat",
        "fallback": "fallback"
    }
)

# 汇聚边
for branch in ["branch_find_book", "branch_review", "branch_trend", "branch_chat"]:
    workflow.add_edge(branch, "aggregate_and_summarize")

workflow.add_edge("aggregate_and_summarize", "log_and_respond")
workflow.add_edge("fallback", "log_and_respond")
workflow.add_edge("log_and_respond", END)

# 编译
app = workflow.compile()
```

### 8.2 调用示例

```python
result = await app.ainvoke({
    "user_id": "guest-uuid-xxx",
    "session_id": "sess_a1b2c3",
    "user_message": "类似《诡秘之主》但基调轻快的",
    "chat_history": [],
    "trace_id": str(uuid4()),
    "route_modules": [],
    "latency_ms": {},
    "token_usage": [],
    "errors": [],
    "status": "success"
})
```

---

## 九、典型场景流转案例

### 9.1 案例 1：用户问"类似《诡秘之主》但轻快的"

- `parse_input` → 加载到避雷词 `["烂尾", "种马"]`
- `classify_intent` → `intent=find_book`, `slots={reference_book: "诡秘之主", mood_filter: "轻快"}`, `confidence=0.94`
- `route_dispatch` → 进入 `branch_find_book`
- `branch_find_book` → 调用 `/search/semantic`，返回 10 本候选；并发补分成功
- `aggregate_and_summarize` → LLM 生成"为你找到《宿命之环》……"
- `log_and_respond` → 写入日志，`status=success`，总耗时 1840ms

### 9.2 案例 2：用户问"《大奉打更人》评价怎么样"

- `parse_input` → 正常加载
- `classify_intent` → `intent=review`, `slots={reference_book: "大奉打更人"}`
- `route_dispatch` → `branch_review`
- `branch_review` → 反查 UID → 并发调用 `/sentiment/novels/{uid}` + `/trend/novels/{uid}/timeline`
- 假设 `/trend` 超时 → 标记 `partial`，热度字段为 null
- `aggregate_and_summarize` → "整体口碑不错，但更新慢……热度数据暂时拿不到"
- `status=partial`

### 9.3 案例 3：搜索模块完全宕机

- `branch_find_book` → 调用 `/search/semantic` 抛 503
- 直接进入 `fallback`
- `fallback` → 调用 `/trend/hot` 兜底，返回"搜索服务繁忙，给你看看最近热门吧"
- `status=fallback`，总耗时 1200ms

### 9.4 案例 4：用户说"你今天心情怎样"

- `classify_intent` → `intent=chat`, `confidence=0.88`
- `route_dispatch` → `branch_chat`
- `branch_chat` → 无下游调用
- `aggregate_and_summarize` → LLM 直接生成"今天的心情和好书的更新速度一样不稳定哈哈"
- `status=success`，仅消耗 1 次 LLM Token（意图分类）+ 1 次 LLM Token（回复）

---

## 十、设计权衡与未来演进

### 10.1 当前版本的妥协

- **未使用 ReAct 自由 Agent**：牺牲灵活性换取可预测性，符合教学项目"可控可解释"的需求
- **意图分类固定 4 种**：未来若需扩展（如"加书架"、"作者查询"），需重构 `route_dispatch`
- **单次会话无状态**：当前不维护跨会话长期记忆，仅依赖 `user_profiles` 表

### 10.2 V2 升级方向

- 引入 Memory（如 LangGraph 的 Checkpointer），支持多轮上下文追问
- 增加 `branch_compare`（小说对比意图）等新分支
- 引入 LLM 自动重写 query，提升搜索召回率
- 接入 Streaming 响应，提升前端体验

---

## 十一、版本变更记录

| 版本 | 日期       | 变更说明                                   | 作者   |
| ---- | ---------- | ------------------------------------------ | ------ |
| v1.0 | 2024-XX-XX | 初版发布，覆盖 9 个核心节点 + 4 个意图分支 | 苗文昊 |