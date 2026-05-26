# 向量索引维护与增量更新手册 (index-lifecycle-policy)

## 索引构建

### 初始构建

通过 REST API 批量导入：

```bash
curl -X POST http://localhost:8000/api/v1/books/index \
  -H "Content-Type: application/json" \
  -d '{
    "books": [
      {"id": "uid_001", "title": "诡秘之主", "intro": "...", "tags": ["克苏鲁", "悬疑"], "status": "completed"},
      {"id": "uid_002", "title": "修罗武神", "intro": "...", "tags": ["玄幻", "后宫"], "status": "ongoing"}
    ]
  }'
```

或通过 MCP 工具：

```
index_books(books=[...])
```

### 构建策略
- 每条书籍生成 512 维稠密向量
- 同时更新 BM25 稀疏索引（全量 tokenize，O(N)）
- ChromaDB 自动持久化到 `data/chroma/`

## 增量更新

### 新增/更新单本书

```bash
curl -X POST http://localhost:8000/api/v1/books/index \
  -H "Content-Type: application/json" \
  -d '{"books": [{"id": "uid_003", "title": "新书", ...}]}'
```

ChromaDB 使用 **upsert** 语义：相同 `id` 覆盖旧记录。

### 删除单本书

```bash
curl -X DELETE http://localhost:8000/api/v1/books/{book_id}
```

### BM25 重建
每次增/删操作后，BM25 索引执行全量重建。对于 N < 10,000 的规模，重建耗时 < 50ms。

## 索引维护

### 查看索引状态

```bash
curl http://localhost:8000/api/v1/health
# → {"status": "ok", "index_stats": {"book_count": 150, "embedding_dim": 512, "bm25_book_count": 150}}
```

### 全量重建

适应以下场景：
- 更换嵌入模型（如从 bge-small 切换到 bge-large）
- 索引数据损坏
- Schema 迁移

操作步骤：
1. 删除 ChromaDB 持久化目录：`rm -rf data/chroma/`
2. 重新批量导入全部书籍：`POST /api/v1/books/index`

### 嵌入模型切换

1. 修改 `.env` 中的 `EMBEDDING_LOCAL_MODEL` 或切换 `EMBEDDING_PROVIDER=api`
2. 执行全量重建（旧向量与新模型维度可能不兼容）

## 性能参考

| 操作 | 规模 | 预期耗时 |
|------|------|---------|
| 嵌入生成（本地） | 100 本书 | ~2s（首次含模型加载） |
| 嵌入生成（API） | 100 本书 | ~3s（取决于网络） |
| BM25 重建 | 10,000 本书 | ~50ms |
| ChromaDB 查询 | 10,000 本书 | ~10ms |
| 混合检索 | 100 本书 | ~200ms（含嵌入） |

## 监控指标

- `book_count`：索引中的书籍总数
- `embedding_dim`：当前嵌入向量维度
- 磁盘使用：监控 `data/chroma/` 目录大小
- API 延迟：监控 `/api/v1/search` 响应时间

## 数据恢复

ChromaDB 数据存储在 `data/chroma/`，该目录已加入 `.gitignore`。建议：
- 定期备份 `data/chroma/` 目录
- 保留原始书籍数据源（JSON/数据库），以便重建索引
