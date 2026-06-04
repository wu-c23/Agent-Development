# Router Agent 工作流设计文档 v1.0

## 概述

Router Agent（"AI 书友"）是系统的核心调度中枢，负责接收用户自然语言输入，进行意图识别，分发到对应业务模块，最终聚合结果并统一语调返回用户。

## 技术方案

- **编排框架**: LangGraph (Stateful Agentic Workflow)
- **LLM**: GPT-4 / Claude 3.5
- **通信协议**: RESTful API (各模块独立服务)
- **服务注册**: 硬编码 + 健康检查 (MVP 阶段)

## 状态机定义

### State Schema

```python
from typing import TypedDict, List, Optional
from enum import Enum

class Intent(str, Enum):
    SEARCH    = "search"     # 找书
    SENTIMENT = "sentiment"  # 评价/口碑
    TREND     = "trend"      # 趋势/动态
    MIXED     = "mixed"      # 混合需求

class RouterState(TypedDict):
    user_input: str                          # 原始用户输入
    intent: Optional[Intent]                 # 识别出的意图
    confidence: float                        # 意图置信度 [0, 1]
    search_result: Optional[dict]            # 搜索模块结果
    sentiment_result: Optional[dict]         # 舆情模块结果
    trend_result: Optional[dict]             # 趋势模块结果
    aggregated_response: Optional[str]       # 最终聚合输出
    error_modules: List[str]                 # 调用失败的模块列表
    fallback_used: bool                      # 是否启用了降级策略
```

## 工作流节点

### Node 1: 意图识别 (Intent Classifier)

```
输入: user_input
处理:
  1. 调用 LLM 进行 Few-shot 分类
  2. 输出意图类别 + 置信度
  3. 提取关键实体 (书名 / 标签 / 平台)
输出: intent, confidence, extracted_entities
```

**Prompt 策略**:
- 提供 3-5 个 Few-shot 示例覆盖三种意图
- 要求 LLM 输出结构化 JSON，限定意图枚举值
- 置信度 < 0.6 时标记为 `mixed`，走全量查询

**意图分类标准**:

| 用户输入示例 | 意图 | 分发模块 |
|-------------|------|----------|
| "推荐几本类似《诡秘之主》的书" | search | Safe-Search |
| "最近什么类型比较火" | trend | Trend Explorer |
| "《大奉打更人》口碑怎么样" | sentiment | Sentiment Critic |
| "帮我找本克苏鲁风格的，不要烂尾" | mixed | search → sentiment |
| "最近有什么口碑好的玄幻新书" | mixed | trend → sentiment |

### Node 2: 任务分发 (Dispatcher)

```
输入: intent, user_input, extracted_entities
处理:
  1. 根据意图决定调用哪个/哪些模块
  2. 并行调用 (无依赖) 或 串行调用 (有依赖)
  3. 设置超时: 单模块 5s，全链路 15s
输出: module_results, error_modules
```

**分发路由表**:

| 意图 | 调用链路 | 模式 |
|------|---------|------|
| search | Safe-Search → (可选) Sentiment Critic | 串行 |
| sentiment | Sentiment Critic | 单模块 |
| trend | Trend Explorer | 单模块 |
| mixed | Safe-Search ∥ Trend Explorer → Sentiment Critic | 混合 |

### Node 3: 结果聚合 (Aggregator)

```
输入: module_results, intent, user_input
处理:
  1. 将各模块返回数据注入聚合 Prompt
  2. LLM 根据意图选择合适的回复语调
  3. 若某模块失败，标注 "该部分数据暂不可用"
输出: aggregated_response
```

**聚合 Prompt 模板**:

```
你是一个专业的网文推荐助手"AI 书友"。请根据以下数据回答用户问题。

用户问题: {user_input}
意图: {intent}

[趋势数据]
{trend_result or "无"}

[搜索匹配]
{search_result or "无"}

[口碑分析]
{sentiment_result or "无"}

要求:
1. 回复语气亲切但不油腻，专业但不冰冷
2. 如果某部分数据缺失，轻描淡写跳过，不要道歉
3. 如涉及评分，给出简短解释而非只报数字
4. 控制在 300 字以内
```

### Node 4: 降级策略 (Fallback)

```
触发条件:
  - 所有模块均调用失败
  - 意图识别置信度 < 0.3
  - 全链路超时

降级行为:
  1. 返回预置的通用推荐列表 (Top 10 热门)
  2. 提示用户 "目前系统繁忙，以下是当前热门推荐"
  3. 记录降级事件到 system_api_audit
```

## 完整工作流图

```
用户输入
    │
    ▼
┌──────────────┐    置信度 < 0.3    ┌────────────┐
│ 意图识别      │ ─────────────────▶ │  降级策略   │
│ Intent Class  │                    │  Fallback   │
└──────┬───────┘                    └─────┬──────┘
       │ 置信度 >= 0.3                    │
       ▼                                  │
┌──────────────┐                          │
│  任务分发     │                          │
│  Dispatcher  │                          │
└──────┬───────┘                          │
       │                                  │
  ┌────┼────┬────┐                        │
  ▼    ▼    ▼    ▼                        │
┌──┐ ┌──┐ ┌──┐  (超时)                    │
│搜│ │趋│ │舆│   │                        │
│索│ │势│ │情│   │                        │
└──┘ └──┘ └──┘   │                        │
  │    │    │     │                        │
  └────┼────┘     │                        │
       ▼          ▼                        ▼
┌──────────────┐                    ┌────────────┐
│  结果聚合     │ ─── 全失败 ──────▶ │  降级策略   │
│  Aggregator  │                    │  Fallback   │
└──────┬───────┘                    └──────┬──────┘
       │                                  │
       └────────────┬─────────────────────┘
                    ▼
              最终回复给用户
```

## 超时与容错

| 配置项 | 值 | 说明 |
|--------|-----|------|
| 单模块超时 | 5s | 单个子服务最大等待时间 |
| 全链路超时 | 15s | 整个请求的最大处理时间 |
| 重试次数 | 1 | 每个模块最多重试 1 次 |
| 熔断阈值 | 连续 5 次失败 | 熔断后 30s 恢复 |

## Mock 行为

Router Agent 在联调阶段提供以下 Mock 行为:
- 接收任意自然语言输入
- 返回预定义的聚合响应
- 从 Mock 数据池随机选择推荐结果
