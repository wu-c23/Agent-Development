# 向量数据库 Schema (vector-db-schema-v2.0)

## 概述

SafeSearch 模块使用 **ChromaDB** 作为向量存储引擎，结合 **sentence-transformers** 本地嵌入模型，实现稠密语义搜索。同时保留 BM25 稀疏索引作为混合检索的补充。

## Collection: `novels`

### 基本信息

| 属性 | 值 |
|------|-----|
| Collection 名称 | `novels` |
| 距离度量 | cosine |
| HNSW M | 16（默认） |
| HNSW ef_construction | 100（默认） |
| 持久化路径 | `data/chroma/` |

### Document ID

使用 `Book.id` 作为唯一标识。相同 ID 的 upsert 操作会替换已有文档。

### Embedding 配置

| 属性 | 值 |
|------|-----|
| 默认模型 | `BAAI/bge-small-zh-v1.5` |
| 向量维度 | 512 |
| 归一化 | True（L2 归一化） |
| 嵌入文本 | `"{title} {intro} {' '.join(tags)}"` |

**备选方案**：设置 `EMBEDDING_PROVIDER=api` 可切换为 OpenAI 兼容的远程嵌入 API（如 text-embedding-3-small）。

### Metadata 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `title` | str | 小说标题 |
| `tags` | str | JSON 编码的标签列表，如 `"[\"玄幻\", \"升级流\"]"` |
| `status` | str | `"completed"` / `"ongoing"` / `""`（未知） |
| `intro_length` | int | 简介字符数 |
| `tag_count` | int | 标签数量 |
| `last_indexed` | str | ISO 8601 时间戳 |

### Metadata 过滤

ChromaDB 支持基于 metadata 字段的等值过滤。支持的过滤条件示例：

```python
# 仅搜索已完结作品
{"status": "completed"}

# 支持 $and / $or 组合
{"$and": [{"status": "completed"}, {"tag_count": {"$gte": 3}}]}
```

### 与系统 UID 的关联

根据项目数据契约，全系统统一 UID = `hash(Platform_ID + Novel_Title)`。在 SafeSearch 模块中：
- `Book.id` 字段应使用此 UID 作为值
- 向量索引的 ChromaDB document ID = Book.id = 系统 UID
- 这样搜索结果可直接通过 UID 与其他模块（舆情评分、趋势数据）关联

## 混合检索架构

```
用户查询 → IntentExtractor → 意图解析
                              │
                              ├→ enriched_query → ChromaDB 稠密检索 (cosine, 权重 0.7)
                              └→ raw_query → BM25 稀疏检索 (jieba, 权重 0.3)
                                                  │
                                                  ▼
                                         加权分数融合 (hybrid fusion)
                                                  │
                                                  ▼
                                         候选排序 + 意图重排
                                                  │
                                                  ▼
                                         风险评分 + 标签过滤
                                                  │
                                                  ▼
                                         最终推荐结果
```
