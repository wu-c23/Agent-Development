# Agent-Development

大作业"网络小说智能推荐与舆情分析系统"

## 项目概述

本项目旨在构建一套集"精准搜索、智能避雷、舆情分析"为一体的网络小说智能推荐系统。针对网文市场"书海寻珠难、评价水分重、搜索维度单一"的行业痛点，通过语义搜索、风险评分、舆情挖掘三个核心模块实现全链路智能化。

### 核心模块

| 模块 | 负责人 | 职责 |
|------|--------|------|
| SafeSearch | 吴宸 | 语义搜索 + 智能避雷（向量检索、意图解析、风险过滤） |
| Sentiment Critic | 武文杰 | 舆情分析与深度评价（多维度评分模型） |
| Review Critic | 武文杰 | 书评采集与舆情看板（多平台爬虫 + 情感分析 + Dashboard） |
| System Integrator | 苗文昊 | 系统集成与 AI 交互（Router Agent、全局 API） |

---

## 环境准备

### 1. 依赖安装

```bash
pip install -r requirements.txt
```

### 2. 环境变量配置

复制模板文件并填入真实配置：

```bash
cp .env.example .env
```

编辑 `.env`，必填项：

```ini
# 必填：DeepSeek API Key
DEEPSEEK_API_KEY=sk-your-real-key-here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_CHAT_MODEL=deepseek-v4-pro

# 嵌入模型：local（本地免费）或 api（调用远程 API）
EMBEDDING_PROVIDER=local
EMBEDDING_LOCAL_MODEL=BAAI/bge-small-zh-v1.5
```

> **说明**：`EMBEDDING_PROVIDER=local` 使用本地 sentence-transformers 模型（BAAI/bge-small-zh-v1.5，中文优化，~100MB），首次运行自动下载，无需额外 API 费用。如需使用远程嵌入 API，设为 `api` 并配置 `EMBEDDING_API_KEY` 等变量。

---

## 运行方式

### 方式一：快速演示（命令行）

直接运行演示脚本，体验完整的语义搜索 + 避雷流程：

```bash
python src/main.py
```

脚本内置 5 本中文网络小说作为测试数据，演示以下功能：
- 稠密向量 + BM25 混合检索
- LLM 意图解析（few-shot）
- 五维风险评分（虐主/烂尾/狗血/后宫/节奏慢）
- 避雷标签过滤
- 增量更新（删除书籍后重新搜索）

输出为结构化 JSON，包含 `query_intent`、`retrieval_candidates`、`risk_scores`、`filtered_results`、`blocked_results`、`data_gaps` 六个部分。

---

### 方式二：REST API 服务（推荐给集成端）

启动 FastAPI 服务器，提供标准 RESTful 接口供其他模块调用：

```bash
python -m src.safe_search --mode api --host 0.0.0.0 --port 8000
```

启动后访问：
- **Swagger 文档**：http://localhost:8000/docs
- **ReDoc 文档**：http://localhost:8000/redoc

#### API 端点一览

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/health` | 健康检查 + 索引统计 |
| `POST` | `/api/v1/search` | 语义搜索 + 避雷过滤 |
| `POST` | `/api/v1/books/index` | 批量添加/更新书籍索引 |
| `GET` | `/api/v1/books/{book_id}` | 查询单本书 + 实时风险评分 |
| `DELETE` | `/api/v1/books/{book_id}` | 从索引中删除书籍 |
| `GET` | `/api/v1/intent?query=...` | 意图解析（调试用） |

#### 使用示例

**1. 索引书籍：**

```bash
curl -X POST http://localhost:8000/api/v1/books/index \
  -H "Content-Type: application/json" \
  -d '{
    "books": [
      {
        "id": "uid_001",
        "title": "诡秘之主",
        "intro": "值夜者克莱恩在蒸汽朋克世界中探索超凡力量的秘密...",
        "tags": ["克苏鲁", "蒸汽朋克", "悬疑", "西方奇幻"],
        "status": "completed",
        "sentiment_summary": "读者普遍好评，夸赞逻辑严密、角色塑造出色。"
      },
      {
        "id": "uid_002",
        "title": "修罗武神",
        "intro": "楚枫遭人陷害沦为废物，意外获得修罗传承后逆天改命...",
        "tags": ["玄幻", "升级流", "后宫", "爽文"],
        "status": "ongoing",
        "sentiment_summary": "读者喜欢爽快感，但吐槽后期水字数、后宫角色扁平化。"
      }
    ]
  }'
```

**2. 语义搜索（带避雷）：**

```bash
curl -X POST http://localhost:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "类似诡秘之主但基调不那么压抑的",
    "avoid_tags": ["后宫", "虐主"],
    "top_k": 5
  }'
```

响应结构：

```json
{
  "query_intent": {
    "summary": "想要类似诡秘之主但氛围更轻松的作品",
    "topics": ["克苏鲁", "蒸汽朋克", "悬疑"],
    "style": ["逻辑严密", "世界观宏大"],
    "protagonist_traits": ["冷静", "谨慎"],
    "mood": ["轻快", "不那么压抑"],
    "constraints": ["avoid_heavy_angst"]
  },
  "retrieval_candidates": [...],
  "risk_scores": [...],
  "filtered_results": [
    {
      "id": "uid_001",
      "title": "诡秘之主",
      "final_score": 0.85,
      "similarity_score": 0.92,
      "intent_match": 0.75,
      "risk_penalty": 0.09,
      "reasons_recommend": ["topics_matched:克苏鲁,悬疑", "style_matched:逻辑严密", "completed"],
      "reasons_risk": ["slow_pacing:0.30"]
    }
  ],
  "blocked_results": [
    {
      "id": "uid_002",
      "title": "修罗武神",
      "blocked_by": ["tag:后宫", "risk:melodrama>0.85", "risk:harem>0.95"]
    }
  ],
  "data_gaps": []
}
```

**3. 查看索引状态：**

```bash
curl http://localhost:8000/api/v1/health
# → {"status":"ok","version":"1.0.0","index_stats":{"book_count":2,"embedding_dim":512,"bm25_book_count":2}}
```

---

### 方式三：MCP 服务器（Claude Code 集成）

作为 Claude Code 的工具插件运行，通过 MCP 协议（Model Context Protocol）暴露搜索能力。配置已在 `.claude/mcp.json` 中预设：

```bash
python -m src.safe_search --mode mcp
```

**MCP 工具列表：**

| 工具名 | 说明 |
|--------|------|
| `index_books` | 将书籍添加到持久化向量索引 |
| `search_novels` | 语义搜索 + 自动避雷过滤 |
| `score_novel_risks` | 单本书五维风险评分 |
| `extract_search_intent` | 结构化意图解析 |

---

### 方式四：Python SDK 调用

在代码中直接使用 SafeSearch 模块：

```python
from safe_search import SafeSearchEngine, Book

engine = SafeSearchEngine()

# 索引书籍
books = [
    Book(
        id="uid_001",
        title="诡秘之主",
        intro="值夜者克莱恩在蒸汽朋克世界中探索超凡力量...",
        tags=["克苏鲁", "蒸汽朋克", "悬疑"],
        status="completed",
        sentiment_summary="读者普遍好评。",
    ),
]
engine.index_books(books)

# 语义搜索 + 避雷
result = engine.search(
    query="类似诡秘之主但基调轻快的",
    avoid_tags=["后宫", "虐主"],
    top_k=5,
)

# 意图解析（不需要搜索时）
intent = engine.extract_intent("想看已完结的轻松修仙文")

# 增量管理
engine.index_books([new_book])  # 添加/更新
engine.remove_book("uid_001")   # 删除
```

> **注意**：`safe_search` 和 `sentiment_critic` 是 `src/` 下的兄弟包。代码中已通过 try/except 同时兼容绝对导入和相对导入。运行脚本时确保 `src/` 在 Python 路径中（如 `python src/main.py` 或 `PYTHONPATH=src python -c "..."`）。

---

### 方式五：Review Critic 模块（书评采集与舆情看板）

独立的书评采集与分析子系统，详细用法见下方。

#### 只抓豆瓣书评

最稳的方式是直接提供豆瓣图书页面的 subject id 或 URL：

```powershell
python scripts/collect_douban_reviews.py --book "诡秘之主" --subject-id "豆瓣subject数字ID" --pages 2 --output data/raw_reviews.jsonl
```

也可以给 subject URL：

```powershell
python scripts/collect_douban_reviews.py --book "诡秘之主" --subject-url "https://book.douban.com/subject/xxxx/" --pages 2
```

如果不提供 subject，脚本会尝试用豆瓣搜索找第一个匹配结果：

```powershell
python scripts/collect_douban_reviews.py --book "诡秘之主" --pages 1
```

先只检查自动搜索能找到哪些豆瓣条目：

```powershell
python scripts/collect_douban_reviews.py --book "诡秘之主" --search-only
```

成功抓取过一次后，脚本会把书名和 subject id 写入 `data/douban_subject_cache.json`；之后即使豆瓣搜索接口被 403，也可以直接按书名复用缓存。

豆瓣有反爬和登录态限制。如果遇到安全验证、403 或搜不到条目，可以设置自己的合法 Cookie：

```powershell
$env:DOUBAN_COOKIE="你的豆瓣 Cookie"
python scripts/collect_douban_reviews.py --book "诡秘之主" --subject-id "豆瓣subject数字ID" --pages 2
```

抓取本地保存的豆瓣书评 HTML：

```powershell
python scripts/collect_douban_reviews.py --book "诡秘之主" --input-html saved_review_page.html --output data/raw_reviews.jsonl
```

旧入口也接入了豆瓣专用采集逻辑：

```powershell
python scripts/collect_reviews.py --book "诡秘之主" --platform douban --subject-id "豆瓣subject数字ID" --max-pages 2
```

#### 分析与看板

先用本地规则跑通：

```powershell
python scripts/analyze_reviews.py --input data/raw_reviews.jsonl --output outputs/analysis_report.json --no-agent
python scripts/build_dashboard.py --report outputs/analysis_report.json --output outputs/sentiment_dashboard.html
```

使用 DeepSeek Agent 时，复制 `.env.example` 为 `.env` 并填写 API Key，然后运行：

```powershell
python scripts/analyze_reviews.py --input data/raw_reviews.jsonl --output outputs/analysis_report.json
```

确认一定调用模型而不是回退本地启发式规则：

```powershell
python scripts/analyze_reviews.py --input data/raw_reviews.jsonl --output outputs/analysis_report.json --require-agent
```

如果遇到 HTTP 429 限流，降低并发：

```powershell
python scripts/run_sentiment_pipeline.py --book "诡秘之主" --platform douban --max-pages 2 --batch-size 3 --batch-delay 15 --require-agent
```

一键全流程（采集 + 分析 + 看板）：

```powershell
python scripts/run_sentiment_pipeline.py --book "诡秘之主" --platform douban --subject-id "豆瓣subject数字ID" --max-pages 2 --no-agent
```

#### Review Critic 输出

- `data/raw_reviews.jsonl`：豆瓣书评原始数据
- `outputs/analysis_report.json`：结构化舆情分析结果
- `outputs/sentiment_dashboard.html`：小说详情页舆情看板

JSONL 字段示例：

```json
{"book":"小说名","platform":"douban","title":"书评标题","author":"作者","created_at":"2026-05-22","content":"书评正文","source_url":"https://book.douban.com/review/xxxx/"}
```

---

## 项目目录结构

```
Agent-Development/
├── .claude/
│   ├── mcp.json                        # MCP 服务器注册（Claude Code 集成）
│   └── skills/
│       └── safe-search.md              # SafeSearch 技能定义
├── .env                                # 环境变量（API Key 等，已 gitignore）
├── .env.example                        # 环境变量模板
├── requirements.txt                    # Python 依赖
├── README.md                           # 本文件
│
├── data/
│   └── chroma/                         # ChromaDB 向量存储持久化目录
│       └── chroma.sqlite3
│
├── docs/
│   ├── vector-db-schema.md             # 向量数据库 Schema 文档
│   └── index-lifecycle-policy.md       # 索引生命周期与增量更新手册
│
├── scripts/                            # CLI 入口脚本
│   ├── analyze_reviews.py              # 书评情感分析
│   ├── build_dashboard.py              # 生成舆情看板 HTML
│   ├── collect_douban_reviews.py       # 豆瓣书评采集
│   ├── collect_reviews.py              # 多平台书评采集
│   └── run_sentiment_pipeline.py       # 一键全流程
│
└── src/
    ├── __init__.py
    ├── main.py                         # 快速演示入口
    ├── safe_search/                    # 语义搜索与避雷模块
    │   ├── __init__.py                 # 公开 API 导出
    │   ├── __main__.py                 # 统一入口（--mode api|mcp）
    │   ├── api.py                      # FastAPI REST 服务
    │   ├── config.py                   # 配置（环境变量加载）
    │   ├── embeddings.py               # 嵌入提供者（local/API 双模式）
    │   ├── engine.py                   # SafeSearchEngine 核心引擎
    │   ├── intent.py                   # 意图提取 + Self-querying Retriever
    │   ├── mcp_server.py               # MCP 工具服务器
    │   ├── models.py                   # Book / IntentResult 数据模型
    │   └── vector_store.py             # HybridVectorStore (ChromaDB + BM25)
    ├── sentiment_critic/               # 风险评分模块
    │   ├── __init__.py
    │   └── critic.py                   # 五维风险评分（规则 + LLM）
    └── review_critic/                  # 书评采集与分析模块
        ├── __init__.py
        ├── agent_client.py             # OpenAI 兼容 HTTP 客户端
        ├── analyzer.py                 # 情感分析引擎
        ├── collectors.py               # 通用 HTML 采集器
        ├── dashboard.py                # 舆情看板 HTML 生成
        ├── douban.py                   # 豆瓣专用爬虫
        └── models.py                   # Review / ReviewAnalysis 数据模型
```

---

## 数据契约

全系统通过统一 UID 关联各模块数据：

```json
{
  "uid": "hash(Platform_ID + Novel_Title)",
  "metadata": {
    "title": "string",
    "platform": "string",
    "last_update": "timestamp"
  },
  "trend_metrics": {"heat_score": 0.95, "tags": ["废土", "规则怪谈"]},
  "sentiment_scores": {"logic": 8.5, "style": 7.0, "toxicity_index": 0.2},
  "vector_id": "string"
}
```

SafeSearch 模块中，`Book.id` 应使用此 UID 作为值，ChromaDB 的 document ID 与此一致，确保搜索结果可直接通过 UID 关联其他模块的舆情评分和趋势数据。
