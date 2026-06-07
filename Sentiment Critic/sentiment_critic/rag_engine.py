"""RAG (Retrieval-Augmented Generation) Engine — 基于外部知识库的智能问答。

从集中数据源构建文档索引，检索相关上下文，调用 LLM 生成可靠答案。

检索架构 (Hybrid):
  用户查询 → Dense (ChromaDB + bge-small-zh-v1.5 embedding) 语义检索
           → Sparse (jieba + TF-IDF) 关键词检索
           → 加权融合 (0.7 dense + 0.3 sparse) → Top-K Chunks
           → Prompt → DeepSeek → 自然语言回复

  当 embedding 模型不可用时，自动降级为纯 TF-IDF 检索。

文本切分: 500-1000 字符/chunk，相邻 chunk 重叠 ~100 字符。
"""

from __future__ import annotations

import json
import math
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# jieba 懒加载（词典较大，首次 import 较慢）

_ROOT = Path(__file__).resolve().parents[1]
_DATA_DIR = _ROOT / "data"

# ---------------------------------------------------------------------------
# 文本分块
# ---------------------------------------------------------------------------


@dataclass
class TextChunk:
    """知识库中的一个文档块。"""
    chunk_id: str
    text: str
    source_type: str  # "novel_meta", "novel_review", "mock_detail"
    source_title: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


def chunk_text(
    text: str,
    source_type: str,
    source_title: str = "",
    chunk_size: int = 600,
    overlap: int = 120,
    metadata: dict[str, Any] | None = None,
) -> list[TextChunk]:
    """将长文本切分为有重叠的 chunk。"""
    if not text or not text.strip():
        return []

    text = text.strip()
    chunks: list[TextChunk] = []
    start = 0
    idx = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))
        # 尽量在句号/换行处断开
        if end < len(text):
            for sep in ["。", "\n", "！", "？", "；", ".", "!"]:
                pos = text.rfind(sep, start + chunk_size // 2, end)
                if pos > 0:
                    end = pos + 1
                    break

        chunk_text_val = text[start:end].strip()
        if chunk_text_val:
            chunk_id = f"{source_title}_{idx}" if source_title else f"chunk_{idx}"
            chunks.append(TextChunk(
                chunk_id=chunk_id,
                text=chunk_text_val,
                source_type=source_type,
                source_title=source_title,
                metadata=metadata or {},
            ))
            idx += 1

        start = end - overlap
        if start >= len(text):
            break
        # 防止无限循环
        if start <= 0:
            start = end

    return chunks


# ---------------------------------------------------------------------------
# TF-IDF 检索器
# ---------------------------------------------------------------------------

# 中文停用词
_STOP_WORDS = set(
    "的 了 在 是 我 有 和 就 不 人 都 一 一个 上 也 很 到 说 要 去 你 "
    "会 着 没有 看 好 自己 这 他 她 它 们 那 些 什么 怎么 哪个 为什么 "
    "可以 这个 那个 还 但 被 把 让 与 及 或 对 从 而 且 之 为 以 所 "
    "更 又 才 呢 吗 啊 吧 哦 嗯 哈 嘛 啦 呀 哇".split()
)


def _tokenize(text: str) -> list[str]:
    """快速分词：字符 2-gram（中文）+ 拆分英文数字。"""
    text = text.strip().lower()
    tokens = []

    # 提取连续中文字符段做 2-gram
    cn_buf = []
    for ch in text:
        if '一' <= ch <= '鿿' or '㐀' <= ch <= '䶿':
            cn_buf.append(ch)
        else:
            # 清空中文缓冲
            if len(cn_buf) >= 2:
                for i in range(len(cn_buf) - 1):
                    tokens.append(''.join(cn_buf[i:i+2]))
            elif len(cn_buf) == 1:
                tokens.append(cn_buf[0])
            cn_buf = []
            # 英文/数字词
            if ch.isalnum():
                tokens.append(ch)
    # 尾部处理
    if len(cn_buf) >= 2:
        for i in range(len(cn_buf) - 1):
            tokens.append(''.join(cn_buf[i:i+2]))
    elif len(cn_buf) == 1:
        tokens.append(cn_buf[0])

    # 去重 + 去停用词
    seen = set()
    result = []
    for t in tokens:
        if t not in seen and t not in _STOP_WORDS:
            seen.add(t)
            result.append(t)
    return result


def _tokenize_query(text: str) -> list[str]:
    """查询分词：使用 jieba（更精确的词级切分）+ 2-gram 补充召回。"""
    import jieba

    words = jieba.lcut(text.strip().lower())
    tokens = []
    seen = set()
    for w in words:
        w = w.strip()
        if len(w) >= 2 and w not in _STOP_WORDS and w not in seen:
            seen.add(w)
            tokens.append(w)
    # 同时补充 2-gram（提高召回）
    for t in _tokenize(text):
        if t not in seen:
            seen.add(t)
            tokens.append(t)
    return tokens


@dataclass
class KnowledgeBase:
    """基于 TF-IDF 的文档检索引擎。"""

    chunks: list[TextChunk] = field(default_factory=list)
    _chunk_tokens: list[list[str]] = field(default_factory=list)
    _df: dict[str, int] = field(default_factory=lambda: defaultdict(int))  # 文档频率
    _total_docs: int = 0

    def index_chunks(self, chunks: list[TextChunk]) -> None:
        """索引一批 chunk。"""
        for chunk in chunks:
            self.chunks.append(chunk)
            tokens = _tokenize(chunk.text)
            self._chunk_tokens.append(tokens)
            unique_tokens = set(tokens)
            for token in unique_tokens:
                self._df[token] += 1
            self._total_docs += 1

    def _tfidf_vector(self, tokens: list[str]) -> dict[str, float]:
        """计算 TF-IDF 向量。"""
        tf = defaultdict(float)
        total = max(len(tokens), 1)
        for t in tokens:
            tf[t] += 1.0 / total

        vec: dict[str, float] = {}
        for t, tf_val in tf.items():
            df = self._df.get(t, 0)
            if df == 0:
                continue
            idf = math.log((self._total_docs + 1) / (df + 1)) + 1.0
            vec[t] = tf_val * idf
        return vec

    def _cosine_similarity(self, v1: dict[str, float], v2: dict[str, float]) -> float:
        """计算两个稀疏向量的余弦相似度。"""
        if not v1 or not v2:
            return 0.0
        dot = sum(v1.get(k, 0) * v2.get(k, 0) for k in set(v1) | set(v2))
        norm1 = math.sqrt(sum(v * v for v in v1.values()))
        norm2 = math.sqrt(sum(v * v for v in v2.values()))
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot / (norm1 * norm2)

    def retrieve(self, query: str, top_k: int = 5) -> list[tuple[TextChunk, float]]:
        """检索与查询最相关的 top_k 个 chunk。"""
        query_tokens = _tokenize_query(query)
        if not query_tokens or self._total_docs == 0:
            return []

        query_vec = {}
        tf = defaultdict(float)
        total = max(len(query_tokens), 1)
        for t in query_tokens:
            tf[t] += 1.0 / total
        for t, tf_val in tf.items():
            df = self._df.get(t, 0)
            if df > 0:
                idf = math.log((self._total_docs + 1) / (df + 1)) + 1.0
                query_vec[t] = tf_val * idf

        if not query_vec:
            return []

        scored: list[tuple[TextChunk, float]] = []
        for i, doc_tokens in enumerate(self._chunk_tokens):
            doc_vec = self._tfidf_vector(doc_tokens)
            sim = self._cosine_similarity(query_vec, doc_vec)
            if sim > 0.05:
                scored.append((self.chunks[i], sim))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    @property
    def total_chunks(self) -> int:
        return self._total_docs


# ---------------------------------------------------------------------------
# VectorStore — ChromaDB 语义检索
# ---------------------------------------------------------------------------

# 尝试导入 ChromaDB 依赖（允许缺失，运行时降级到纯 TF-IDF）
_VECTOR_DEPS_AVAILABLE = False
_VECTOR_INIT_ERROR: str | None = None

try:
    import chromadb  # noqa: F401
    from sentence_transformers import SentenceTransformer  # noqa: F401

    _VECTOR_DEPS_AVAILABLE = True
except ImportError as _e:
    _VECTOR_INIT_ERROR = f"Missing dependency: {_e}"


class VectorStore:
    """ChromaDB 语义向量检索引擎。

    使用 bge-small-zh-v1.5 模型将文本编码为 512 维向量，
    存入 ChromaDB 持久化存储，支持余弦相似度语义搜索。

    当 sentence-transformers 或 chromadb 不可用、或 embedding 模型
    下载失败时，VectorStore 进入 degraded 模式（ready=False），
    上层自动回退到 TF-IDF 检索。
    """

    COLLECTION_NAME = "rag_knowledge_base"

    def __init__(self, persist_dir: str) -> None:
        self._ready = False
        self._embedder: Any = None
        self._chroma_client: Any = None
        self._collection: Any = None
        self._chunk_map: dict[str, TextChunk] = {}
        self._indexed_count = 0

        if not _VECTOR_DEPS_AVAILABLE:
            print(f"[rag] VectorStore unavailable: {_VECTOR_INIT_ERROR}")
            return

        try:
            self._init_embedder()
            self._init_chroma(persist_dir)
            self._ready = True
            existing = self._collection.count()
            print(f"[rag] VectorStore ready, embedding dim={self._embedder.get_sentence_embedding_dimension()}, "
                  f"chroma collection '{self.COLLECTION_NAME}' has {existing} chunks")
        except Exception as exc:
            print(f"[rag] VectorStore unavailable ({exc}), will use TF-IDF only")

    def _init_embedder(self) -> None:
        """初始化 embedding 模型，优先使用国内镜像。"""
        hf_endpoint = os.environ.get("HF_ENDPOINT", "")
        if hf_endpoint:
            os.environ.setdefault("HF_ENDPOINT", hf_endpoint)

        model_name = os.environ.get("EMBEDDING_LOCAL_MODEL", "BAAI/bge-small-zh-v1.5")
        self._embedder = SentenceTransformer(model_name)

    def _init_chroma(self, persist_dir: str) -> None:
        """初始化 ChromaDB 持久化客户端和 collection。"""
        Path(persist_dir).mkdir(parents=True, exist_ok=True)
        self._chroma_client = chromadb.PersistentClient(path=persist_dir)
        self._collection = self._chroma_client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    @property
    def ready(self) -> bool:
        return self._ready

    @property
    def total_chunks(self) -> int:
        return self._collection.count() if self._ready else 0

    def _load_chunk_map_from_cache(self, cache_path: str) -> None:
        """从 JSON 缓存恢复 chunk_map（用于已持久化的 ChromaDB 数据）。"""
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for item in data.get("chunks", []):
                chunk = TextChunk(
                    chunk_id=item["chunk_id"],
                    text=item["text"],
                    source_type=item["source_type"],
                    source_title=item.get("source_title", ""),
                    metadata=item.get("metadata", {}),
                )
                self._chunk_map[chunk.chunk_id] = chunk
        except Exception:
            pass

    def index_chunks(self, chunks: list[TextChunk]) -> None:
        """批量索引文本块到 ChromaDB（如果已有数据则跳过，避免重复计算）。"""
        if not self._ready or not chunks:
            return

        if self._collection.count() > 0:
            print(f"[rag] VectorStore already has {self._collection.count()} chunks, skipping re-index")
            return

        texts = [c.text for c in chunks]
        ids = [c.chunk_id for c in chunks]
        metadatas = [
            {
                "source_type": c.source_type,
                "source_title": c.source_title,
            }
            for c in chunks
        ]

        print(f"[rag] Computing embeddings for {len(chunks)} chunks (model: BAAI/bge-small-zh-v1.5)...")
        embeddings = self._embedder.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=True,
            batch_size=64,
        )

        batch_size = 500
        for i in range(0, len(chunks), batch_size):
            end = min(i + batch_size, len(chunks))
            self._collection.add(
                ids=ids[i:end],
                embeddings=embeddings[i:end].tolist(),
                metadatas=metadatas[i:end],
                documents=texts[i:end],
            )

        for c in chunks:
            self._chunk_map[c.chunk_id] = c
        self._indexed_count = len(chunks)
        print(f"[rag] VectorStore indexed {len(chunks)} chunks into ChromaDB")

    def rebuild(self, chunks: list[TextChunk]) -> None:
        """强制重建：清空已有数据并重新索引（用于数据更新后）。"""
        if not self._ready:
            return
        try:
            self._chroma_client.delete_collection(self.COLLECTION_NAME)
        except Exception:
            pass
        self._collection = self._chroma_client.create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        self._chunk_map.clear()
        self._indexed_count = 0
        self.index_chunks(chunks)

    def search(self, query: str, top_k: int = 5) -> list[tuple[TextChunk, float]]:
        """语义向量检索：embedding query → ChromaDB 余弦相似度查询。"""
        if not self._ready or self._collection.count() == 0:
            return []

        query_embedding = self._embedder.encode(
            [query], normalize_embeddings=True
        )[0]

        results = self._collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=min(top_k, self._collection.count()),
            include=["distances", "metadatas", "documents"],
        )

        out: list[tuple[TextChunk, float]] = []
        ids_list: list[str] = results.get("ids", [[]])[0]  # type: ignore[assignment]
        distances: list[float] = results.get("distances", [[]])[0]  # type: ignore[assignment]
        metadatas_list: list[dict] = results.get("metadatas", [[]])[0]  # type: ignore[assignment]
        documents_list: list[str] = results.get("documents", [[]])[0]  # type: ignore[assignment]

        for cid, dist, meta, doc in zip(ids_list, distances, metadatas_list, documents_list):
            score = 1.0 - min(dist, 1.0)  # cosine distance → similarity
            if cid in self._chunk_map:
                chunk = self._chunk_map[cid]
            else:
                chunk = TextChunk(
                    chunk_id=cid,
                    text=doc or meta.get("text", ""),
                    source_type=meta.get("source_type", ""),
                    source_title=meta.get("source_title", ""),
                )
            out.append((chunk, score))

        return out


# ---------------------------------------------------------------------------
# 知识库构建
# ---------------------------------------------------------------------------


def build_knowledge_base(
    novels_path: str | None = None,
    reviews_dir: str | None = None,
    sentiment_path: str | None = None,
    use_cache: bool = True,
) -> KnowledgeBase:
    """从集中数据构建知识库（自动缓存到 data/rag_kb_cache.json）。"""
    cache_path = _DATA_DIR / "rag_kb_cache.json"

    if use_cache and cache_path.exists():
        try:
            kb = _load_kb_from_cache(cache_path)
            if kb and kb.total_chunks > 0:
                print(f"[rag] KnowledgeBase loaded from cache: {kb.total_chunks} chunks")
                return kb
        except Exception:
            pass

    kb = KnowledgeBase()

    # 1. 小说元数据（热度前 300）
    novels_file = Path(novels_path) if novels_path else _DATA_DIR / "novels.json"
    if novels_file.exists():
        _index_novels(kb, novels_file)

    # 2. 评论数据（采样，最多 500 条）
    reviews_d = Path(reviews_dir) if reviews_dir else _DATA_DIR / "runs"
    if reviews_d.exists():
        _index_reviews(kb, reviews_d)

    # 3. 舆情评分
    sentiment_file = Path(sentiment_path) if sentiment_path else _DATA_DIR / "sentiment_index.json"
    if sentiment_file.exists():
        _index_sentiment(kb, sentiment_file)

    # 4. 内置精选数据
    _index_mock_data(kb)

    print(f"[rag] KnowledgeBase built: {kb.total_chunks} chunks indexed")

    # 写入缓存
    try:
        _save_kb_to_cache(kb, cache_path)
    except Exception:
        pass

    return kb


def build_vector_store_from_kb(
    kb: KnowledgeBase,
    persist_dir: str | None = None,
) -> VectorStore:
    """从已构建的 KnowledgeBase 创建向量索引（ChromaDB 持久化）。

    首次调用时计算 embedding 并写入 ChromaDB，后续启动直接复用已有数据。
    """
    persist_dir = persist_dir or str(_DATA_DIR / "chroma")
    cache_path = str(_DATA_DIR / "rag_kb_cache.json")

    vs = VectorStore(persist_dir)
    if vs.ready:
        # 尝试从缓存恢复 chunk_map（用于从 ChromaDB 搜索结果重建 TextChunk）
        vs._load_chunk_map_from_cache(cache_path)
        vs.index_chunks(kb.chunks)
    return vs


def _save_kb_to_cache(kb: KnowledgeBase, path: Path) -> None:
    """将知识库序列化到 JSON 文件。"""
    data = {
        "chunks": [
            {
                "chunk_id": c.chunk_id,
                "text": c.text,
                "source_type": c.source_type,
                "source_title": c.source_title,
                "metadata": c.metadata,
            }
            for c in kb.chunks
        ],
        "total_docs": kb._total_docs,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    print(f"[rag] Cache saved: {path}")


def _load_kb_from_cache(path: Path) -> KnowledgeBase | None:
    """从缓存加载知识库。"""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    kb = KnowledgeBase()
    for item in data.get("chunks", []):
        chunk = TextChunk(
            chunk_id=item["chunk_id"],
            text=item["text"],
            source_type=item["source_type"],
            source_title=item.get("source_title", ""),
            metadata=item.get("metadata", {}),
        )
        kb.chunks.append(chunk)
        tokens = _tokenize(chunk.text)
        kb._chunk_tokens.append(tokens)
        for token in set(tokens):
            kb._df[token] += 1
    kb._total_docs = data.get("total_docs", len(kb.chunks))
    return kb


def _index_novels(kb: KnowledgeBase, path: Path) -> None:
    """索引小说元数据（仅索引热度前 300 本）。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            novels = json.load(f)
    except Exception:
        return

    # 按热度排序，只取前 300
    novels.sort(key=lambda n: n.get("heat_score", 0) or 0, reverse=True)
    novels = novels[:300]

    chunks: list[TextChunk] = []
    for novel in novels:
        title = novel.get("title", "")
        if not title:
            continue
        text_parts = [f"《{title}》"]
        author = novel.get("author", "")
        if author:
            text_parts.append(f"作者：{author}")
        tags = novel.get("tags", [])
        if tags:
            text_parts.append(f"标签：{', '.join(tags)}")
        platform = novel.get("platform", "")
        if platform:
            text_parts.append(f"平台：{platform}")
        status = novel.get("status", "unknown")
        status_map = {"completed": "已完结", "ongoing": "连载中", "unknown": "状态未知"}
        text_parts.append(f"状态：{status_map.get(status, status)}")
        intro = novel.get("intro", "")
        if intro:
            text_parts.append(f"简介：{intro[:200]}")
        heat = novel.get("heat_score", 0)
        if heat:
            text_parts.append(f"热度：{heat:.0f}")

        full_text = "\n".join(text_parts)
        chunks.extend(chunk_text(
            full_text,
            source_type="novel_meta",
            source_title=title,
            metadata={"title": title, "uid": novel.get("uid", ""), "platform": platform},
        ))

    kb.index_chunks(chunks)
    print(f"[rag] Indexed {len(chunks)} chunks from top {len(novels)} novels (by heat)")


def _index_reviews(kb: KnowledgeBase, dir_path: Path) -> None:
    """索引评论 JSONL 文件。"""
    chunks: list[TextChunk] = []
    processed = 0

    for jsonl_file in sorted(dir_path.glob("*.jsonl")):
        if jsonl_file.stat().st_size == 0:
            continue
        try:
            with open(jsonl_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception:
            continue

        book_title = ""
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                review = json.loads(line)
            except json.JSONDecodeError:
                continue

            title = review.get("title") or review.get("book") or ""
            if title and not book_title:
                book_title = title

            content = review.get("content") or review.get("text") or ""
            if len(content) < 30:
                continue

            author = review.get("author") or review.get("user") or "匿名"
            platform = review.get("platform", "")
            rating = review.get("rating") or review.get("score") or ""

            text = f"《{title}》的读者评论\n用户：{author}"
            if rating:
                text += f"\n评分：{rating}"
            if platform:
                text += f"\n来源：{platform}"
            text += f"\n内容：{content[:800]}"

            chunks.extend(chunk_text(
                text,
                source_type="novel_review",
                source_title=title or book_title,
                metadata={"title": title, "platform": platform},
            ))
            processed += 1

    kb.index_chunks(chunks)
    print(f"[rag] Indexed {len(chunks)} chunks from {processed} reviews")


def _index_sentiment(kb: KnowledgeBase, path: Path) -> None:
    """索引舆情评分数据。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            index = json.load(f)
    except Exception:
        return

    chunks: list[TextChunk] = []
    for uid, entry in index.items():
        if not isinstance(entry, dict):
            continue
        title = entry.get("title") or entry.get("metadata", {}).get("title", "")
        if not title:
            continue

        parts = [f"《{title}》舆情分析"]
        overall = entry.get("overall") or entry.get("sentiment_scores", {}).get("overall")
        if overall is not None:
            parts.append(f"综合评分：{overall}/10")

        for dim_name, dim_key in [("文笔", "style"), ("逻辑", "logic"), ("人物", "character"),
                                    ("更新稳定性", "update_stability"), ("毒性指数", "toxicity_index")]:
            val = entry.get(dim_key) or entry.get("sentiment_scores", {}).get(dim_key)
            if val is not None:
                parts.append(f"{dim_name}：{val}")

        one_liner = entry.get("one_liner") or entry.get("critic_summary", {}).get("one_liner")
        if one_liner:
            parts.append(f"毒舌点评：{one_liner}")

        pros = entry.get("pros") or entry.get("critic_summary", {}).get("pros", [])
        if pros:
            parts.append(f"优点：{', '.join(pros[:5])}")

        cons = entry.get("cons") or entry.get("critic_summary", {}).get("cons", [])
        if cons:
            parts.append(f"缺点：{', '.join(cons[:5])}")

        review_count = entry.get("review_count") or entry.get("review_stats", {}).get("total_count", 0)
        if review_count:
            pos = entry.get("positive_ratio") or entry.get("review_stats", {}).get("positive_ratio", 0)
            parts.append(f"共{review_count}条评论，好评率{pos * 100:.0f}%")

        text = "\n".join(parts)
        chunks.extend(chunk_text(
            text,
            source_type="sentiment",
            source_title=title,
            metadata={"title": title, "uid": uid},
        ))

    kb.index_chunks(chunks)
    print(f"[rag] Indexed {len(chunks)} chunks from sentiment index ({len(index)} entries)")


def _index_mock_data(kb: KnowledgeBase) -> None:
    """索引内置精选 mock 数据（丰富的书评和元数据）。"""
    # 与 mock_server 中的 5 本书保持一致
    mock_books = [
        {
            "title": "诡秘之主",
            "tags": ["克苏鲁", "蒸汽朋克", "悬疑", "西方奇幻"],
            "status": "completed",
            "intro": "值夜者克莱恩在蒸汽朋克世界中探索超凡力量的秘密，从序列9占卜家开始，一步步揭开世界的真相。融合克苏鲁神话、SCP基金会、维多利亚时代风貌。",
            "one_liner": "逻辑严密的克苏鲁神作，但前200页像在读说明书。",
            "pros": ["世界观构建顶级", "伏笔回收大师级", "角色智商集体在线", "力量体系精细", "悬疑氛围出色"],
            "cons": ["开头节奏偏慢", "对轻度读者门槛较高", "中期部分支线略冗长"],
            "overall": 9.1,
            "style": 9.2,
            "logic": 9.5,
            "character": 9.0,
            "update_stability": 8.8,
            "toxicity_index": 0.08,
            "review_count": 1250,
            "positive_ratio": 0.86,
        },
        {
            "title": "我有一座恐怖屋",
            "tags": ["悬疑", "恐怖", "系统流", "轻松"],
            "status": "completed",
            "intro": "陈歌继承废弃鬼屋，获得恐怖屋经营系统，每个恐怖场景都对应一个真实案件，在经营鬼屋的同时破解谜案。",
            "one_liner": "不吓人的恐怖小说才是好喜剧，陈歌把鬼屋经营成了迪士尼。",
            "pros": ["角色塑造鲜明", "恐怖与搞笑平衡出色", "更新稳定", "案件设计精巧"],
            "cons": ["后期略有套路化", "部分副本节奏不均"],
            "overall": 8.5,
            "style": 8.0,
            "logic": 8.2,
            "character": 8.8,
            "update_stability": 9.0,
            "toxicity_index": 0.05,
            "review_count": 890,
            "positive_ratio": 0.82,
        },
        {
            "title": "修罗武神",
            "tags": ["玄幻", "升级流", "后宫", "爽文"],
            "status": "ongoing",
            "intro": "楚枫遭人陷害沦为废物，获得修罗传承后逆天改命，踏上一段热血与美色交织的升级之路。",
            "one_liner": "爽是真的爽，水也是真的水，后宫像Pokemon收集图鉴。",
            "pros": ["爽点密集节奏快", "适合无脑放松"],
            "cons": ["后宫角色扁平化", "后期严重注水", "逻辑经不起推敲"],
            "overall": 5.2,
            "style": 5.0,
            "logic": 4.0,
            "character": 3.5,
            "update_stability": 6.0,
            "toxicity_index": 0.45,
            "review_count": 2100,
            "positive_ratio": 0.45,
        },
        {
            "title": "凡人修仙传",
            "tags": ["修仙", "凡人流", "慢热", "完结"],
            "status": "completed",
            "intro": "山村少年韩立在修仙界步步为营，以凡人之资，凭着谨慎、隐忍和一点点机缘，走出了一条属于自己的修仙大道。",
            "one_liner": "凡人流教科书，韩立教你什么叫真正的'凡人'——连老婆都是分身上位的。",
            "pros": ["逻辑自洽的修仙体系", "主角智商长期在线", "完结稳定不烂尾", "配角有血有肉"],
            "cons": ["前期节奏偏慢", "女主存在感薄弱", "部分战斗描写略冗长"],
            "overall": 8.3,
            "style": 7.5,
            "logic": 9.0,
            "character": 8.5,
            "update_stability": 9.5,
            "toxicity_index": 0.10,
            "review_count": 3200,
            "positive_ratio": 0.80,
        },
        {
            "title": "仙王的日常生活",
            "tags": ["修仙", "日常", "搞笑", "轻松", "完结"],
            "status": "completed",
            "intro": "最强仙王隐藏实力体验高中日常，装弱、装穷、装路人，一边应付同学一边顺手拯救世界。",
            "one_liner": "仙王装高中生的日常，像拿核弹打蚊子——浪费但好笑。",
            "pros": ["轻松解压", "反套路设定有趣", "角色讨喜"],
            "cons": ["深度不足", "单元剧形式缺乏主线推进"],
            "overall": 7.8,
            "style": 7.2,
            "logic": 6.5,
            "character": 8.0,
            "update_stability": 8.5,
            "toxicity_index": 0.12,
            "review_count": 780,
            "positive_ratio": 0.78,
        },
    ]

    chunks: list[TextChunk] = []
    for book in mock_books:
        parts = [
            f"《{book['title']}》详细信息",
            f"标签：{', '.join(book['tags'])}",
            f"状态：{'已完结' if book['status'] == 'completed' else '连载中'}",
            f"简介：{book['intro']}",
            f"综合评分：{book['overall']}/10",
            f"文笔：{book['style']} 逻辑：{book['logic']} 人物：{book['character']} 更新稳定性：{book['update_stability']}",
            f"毒舌点评：{book['one_liner']}",
            f"优点：{', '.join(book['pros'])}",
            f"缺点：{', '.join(book['cons'])}",
            f"共{book['review_count']}条评论，好评率{book['positive_ratio'] * 100:.0f}%",
        ]
        text = "\n".join(parts)
        chunks.extend(chunk_text(
            text,
            source_type="mock_detail",
            source_title=book["title"],
            metadata={"title": book["title"]},
        ))

    kb.index_chunks(chunks)
    print(f"[rag] Indexed {len(chunks)} chunks from {len(mock_books)} mock books")


# ---------------------------------------------------------------------------
# RAG 生成引擎
# ---------------------------------------------------------------------------


RAG_SYSTEM_PROMPT = """你是"网络小说智能推荐助手"，基于知识库中的真实数据回答用户问题。

重要规则：
1. 只基于下面提供的【参考资料】来回答，不要编造信息
2. 如果参考资料中没有相关信息，诚实告诉用户"目前知识库中没有这方面的信息"
3. 回答要自然、友好、有温度，像朋友聊天一样
4. 如果用户问的是推荐类问题，给出具体书名并简要说明理由
5. 如果用户问的是某本书的类型/评价/详情，直接回答
6. 如果用户闲聊（不是找书/问书），认真回答用户的问题
7. 回答长度：推荐类 4-6 句，询问单本书 3-5 句，闲聊 2-4 句
8. 用中文回答，不要用 Markdown 格式，所有提到的书名必须用《》包裹
9. 多轮对话时，注意结合对话历史理解用户的上下文引用（如"第一本"、"这本"、"它"等指代）——用户说的"第一本书"指的是你上一轮推荐的第一本书，不是书名里带"第一"的小说"""

# ---------------------------------------------------------------------------
# 会话管理 — 多轮对话记忆
# ---------------------------------------------------------------------------

@dataclass
class ConversationState:
    """单个会话的多轮对话状态。"""
    messages: list[dict[str, str]] = field(default_factory=list)
    last_recommended_titles: list[str] = field(default_factory=list)


# 会话存储（进程内，重启后丢失）
_sessions: dict[str, ConversationState] = {}

# 指代表达式模式
_REFERENCE_PATTERNS = [
    (re.compile(r"第\s*([一二三四五六七八九十\d]+)\s*[本个]"), lambda m, books: _nth_book(m, books)),
    (re.compile(r"第\s*最后\s*[本个]|最后\s*[一那]\s*[本个]"), lambda m, books: [books[-1]] if books else []),
    (re.compile(r"(?:这[本个]|那[本个]|[这那]本书|[这那]一部|[这那]篇)"), lambda m, books: [books[0]] if books else []),
]


def _parse_chinese_num(s: str) -> int:
    """将中文数字转换为一索引的整数。"""
    cn_nums = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
    if s in cn_nums:
        return cn_nums[s]
    return int(s)


def _nth_book(match, books: list[str]) -> list[str]:
    """获取第N本书（N从1开始）。"""
    n_str = match.group(1)
    try:
        n = _parse_chinese_num(n_str)
    except (ValueError, KeyError):
        return []
    idx = n - 1
    if 0 <= idx < len(books):
        return [books[idx]]
    return []


def _resolve_references(query: str, last_titles: list[str]) -> tuple[str, list[str]]:
    """检测并解析用户查询中的指代表达式。

    将"第一本书"、"这本"等替换为具体的书名，用于后续检索。
    返回 (解析后的查询, 被引用的书名列表)。
    """
    if not last_titles:
        return query, []

    resolved_titles: list[str] = []
    modified_query = query

    for pattern, resolver in _REFERENCE_PATTERNS:
        match = pattern.search(query)
        if match:
            titles = resolver(match, last_titles)
            if titles:
                resolved_titles.extend(titles)
                # 在查询末尾追加书名关键词以增强检索
                for t in titles:
                    if t not in modified_query:
                        modified_query += f" {t}"

    # 去重
    seen = set()
    unique_titles = []
    for t in resolved_titles:
        if t not in seen:
            seen.add(t)
            unique_titles.append(t)

    return modified_query, unique_titles


def get_or_create_session(session_id: str) -> ConversationState:
    """获取或创建会话状态。"""
    if session_id not in _sessions:
        _sessions[session_id] = ConversationState()
    return _sessions[session_id]


def _strip_session(session: ConversationState, max_history: int = 10) -> None:
    """限制会话历史长度，避免上下文过长。"""
    if len(session.messages) > max_history * 2:
        session.messages = session.messages[-(max_history * 2):]


def _extract_titles_from_answer(answer: str) -> list[str]:
    """从回答文本中提取被推荐的书名（用《》包裹的）。"""
    titles = re.findall(r"《([^》]+)》", answer)
    seen = set()
    unique = []
    for t in titles:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    return unique


@dataclass
class RAGEngine:
    """RAG 引擎：混合检索 (Dense Vector + Sparse TF-IDF) + LLM 生成。

    检索优先级:
      1. 若 vector_store 可用 → 混合检索 (0.7 dense + 0.3 sparse)
      2. 若 vector_store 不可用 → 纯 TF-IDF 检索
    """

    kb: KnowledgeBase
    vector_store: VectorStore | None = None
    use_agent: bool = True

    @property
    def retrieval_method(self) -> str:
        if self.vector_store and self.vector_store.ready:
            return "hybrid"
        return "tfidf"

    def answer(self, query: str, top_k: int = 5, session_id: str = "") -> dict[str, Any]:
        """根据用户查询，检索知识库并生成答案。

        支持多轮对话：通过 session_id 关联上下文，解析指代替换为具体书名。

        Returns:
            {"answer": str, "sources": [...], "method": "rag"|"hybrid"|"tfidf_heuristic"}
        """
        # 多轮对话：解析指代表达式
        session = get_or_create_session(session_id) if session_id else None
        enriched_query = query
        resolved_titles: list[str] = []
        if session and session.last_recommended_titles:
            enriched_query, resolved_titles = _resolve_references(query, session.last_recommended_titles)

        retrieved = self._retrieve(enriched_query, top_k)

        if retrieved:
            seen = set()
            unique_chunks = []
            for chunk, score in retrieved:
                key = chunk.text[:100]
                if key not in seen:
                    seen.add(key)
                    unique_chunks.append((chunk, score))
            retrieved = unique_chunks[:top_k]

            context_parts = []
            sources = []
            for i, (chunk, score) in enumerate(retrieved, 1):
                context_parts.append(f"[资料{i}] (来源:{chunk.source_title}, 相关度:{score:.2f})\n{chunk.text}")
                if chunk.source_title and chunk.source_title not in sources:
                    sources.append(chunk.source_title)
        else:
            context_parts = ["知识库中暂无相关信息。"]
            sources = []

        context = "\n\n---\n\n".join(context_parts)

        method = self.retrieval_method

        # 如果解析出了具体书名但检索没召回对应资料，强制注入已知书名信息到上下文
        if resolved_titles and not any(t in c.text for t in resolved_titles for c, _ in retrieved):
            title_hint = "\n".join(f"提示：用户提到的第{i+1}本书是《{t}》，请围绕《{t}》回答。" for i, t in enumerate(resolved_titles))
            context = title_hint + "\n\n---\n\n" + context

        if self.use_agent:
            try:
                answer = self._generate_with_llm(query, context, session)
                if session:
                    session.messages.append({"role": "user", "content": query})
                    session.messages.append({"role": "assistant", "content": answer})
                    session.last_recommended_titles = _extract_titles_from_answer(answer)
                    _strip_session(session)
                return {"answer": answer, "sources": sources[:5], "method": method}
            except Exception as exc:
                print(f"[rag] LLM generation failed: {exc}, falling back to heuristic")

        answer = self._generate_heuristic(query, retrieved)
        if session:
            session.messages.append({"role": "user", "content": query})
            session.messages.append({"role": "assistant", "content": answer})
            session.last_recommended_titles = _extract_titles_from_answer(answer)
            _strip_session(session)
        return {"answer": answer, "sources": sources[:5], "method": f"{method}_heuristic"}

    def _retrieve(self, query: str, top_k: int) -> list[tuple[TextChunk, float]]:
        """混合检索：向量语义 + TF-IDF 关键词，加权融合排序。"""
        if not (self.vector_store and self.vector_store.ready):
            return self.kb.retrieve(query, top_k=top_k)

        dense_results = self.vector_store.search(query, top_k=top_k * 2)
        sparse_results = self.kb.retrieve(query, top_k=top_k * 2)

        if not dense_results:
            return sparse_results[:top_k]
        if not sparse_results:
            return dense_results[:top_k]

        # 加权融合 (0.7 dense + 0.3 sparse)
        dense_scores: dict[str, tuple[TextChunk, float]] = {}
        for chunk, score in dense_results:
            dense_scores[chunk.chunk_id] = (chunk, score)

        sparse_scores: dict[str, tuple[TextChunk, float]] = {}
        for chunk, score in sparse_results:
            sparse_scores[chunk.chunk_id] = (chunk, score)

        all_ids = set(dense_scores.keys()) | set(sparse_scores.keys())
        fused: list[tuple[TextChunk, float]] = []
        for cid in all_ids:
            d_score = dense_scores.get(cid, (None, 0.0))[1]
            s_score = sparse_scores.get(cid, (None, 0.0))[1]
            combined = 0.7 * d_score + 0.3 * s_score
            chunk = dense_scores.get(cid, sparse_scores.get(cid))[0]
            fused.append((chunk, combined))

        fused.sort(key=lambda x: x[1], reverse=True)
        return fused[:top_k]

    def _generate_with_llm(self, query: str, context: str, session: ConversationState | None = None) -> str:
        """使用 DeepSeek LLM 生成答案，支持多轮对话历史。"""
        from .agent_client import AgentClient

        client = AgentClient()
        if not client.available:
            raise RuntimeError("LLM not available")

        user_prompt = f"""【参考资料】
{context}

【用户问题】
{query}

请基于以上参考资料回答用户问题。如果资料中没有相关信息，请诚实告知。"""

        # 获取对话历史（不含当前问题）
        history: list[dict[str, str]] = []
        if session and len(session.messages) >= 2:
            history = session.messages.copy()

        return self._call_llm_text(RAG_SYSTEM_PROMPT, user_prompt, history)

    def _call_llm_text(self, system_prompt: str, user_prompt: str, history: list[dict[str, str]] | None = None) -> str:
        """调用 LLM 获取纯文本回复，支持多轮对话历史。"""
        from .agent_client import AgentClient, AgentClientConfig

        config = AgentClientConfig.from_env()
        if config.validation_errors():
            raise RuntimeError("LLM config invalid")

        import json as _json
        from urllib.request import Request, urlopen

        messages = [{"role": "system", "content": system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_prompt})

        payload = {
            "model": config.model,
            "messages": messages,
            "temperature": 0.7,
        }
        body = _json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.api_key}",
            "X-API-Key": config.api_key,
        }
        request = Request(config.endpoint, data=body, headers=headers, method="POST")
        with urlopen(request, timeout=config.timeout) as response:
            raw = _json.loads(response.read().decode("utf-8"))
        return raw["choices"][0]["message"]["content"]

    def _generate_heuristic(
        self, query: str, retrieved: list[tuple[TextChunk, float]]
    ) -> str:
        """无 LLM 时的启发式回答。"""
        if not retrieved:
            return (
                "抱歉，我在知识库中没有找到与你的问题相关的信息。\n\n"
                "你可以试试问我：\n"
                "• 推荐悬疑小说\n"
                "• 诡秘之主好看吗\n"
                "• 有没有类似凡人修仙传的书"
            )

        # 提取检索到的书名
        books = []
        for chunk, score in retrieved:
            title = chunk.source_title
            if title and title not in books:
                books.append(title)

        query_lower = query.lower()

        # 判断意图
        is_recommend = any(w in query_lower for w in ["推荐", "找", "有没有", "书荒", "想看"])
        is_inquiry = any(w in query_lower for w in ["是什么", "好看吗", "怎么样", "评价", "完结", "类型", "讲讲", "讲一讲", "具体", "内容", "介绍", "聊一聊", "说说"])
        is_followup = any(w in query_lower for w in ["第一", "第二", "第三", "这本", "那本", "上一本", "刚才", "前面"])

        if (is_inquiry or is_followup) and books:
            top_book = books[0]
            # 从检索结果中提取信息
            info_parts = []
            for chunk, _ in retrieved:
                if chunk.source_title == top_book:
                    info_parts.append(chunk.text[:300])
            info = " ".join(info_parts)[:500]
            if info:
                return f"根据知识库中的信息，《{top_book}》的相关资料如下：\n\n{info}\n\n💡 如需更详细的评论分析，可以点击书名查看。"
            else:
                return f"关于《{top_book}》，我找到了以下相关信息。\n\n💡 如需更详细的评论分析，可以点击书名查看。"

        if is_recommend and books:
            book_list = "、".join(f"《{b}》" for b in books[:5])
            return f"根据你的偏好，我找到了这些可能感兴趣的小说：{book_list}\n\n这些都是知识库中匹配度较高的作品，你可以点击书名查看详细评价。想了解其中哪一本？"

        if books:
            book_list = "、".join(f"《{b}》" for b in books[:5])
            return f"关于你的问题，我找到了这些相关的小说：{book_list}\n\n想了解哪一本的详细信息呢？"

        return "抱歉，我没有完全理解你的问题。你可以试试：\n• 推荐XX类型的小说\n• 某本书好看吗\n• 有没有类似XX的书"


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_global_kb: KnowledgeBase | None = None
_global_vs: VectorStore | None = None
_global_engine: RAGEngine | None = None


def get_knowledge_base(reload: bool = False) -> KnowledgeBase:
    """获取全局知识库单例。"""
    global _global_kb
    if _global_kb is None or reload:
        _global_kb = build_knowledge_base()
    return _global_kb


def get_vector_store(reload: bool = False) -> VectorStore | None:
    """获取全局向量存储单例（可能为 None，表示 embedding 不可用）。"""
    global _global_vs, _global_kb
    if _global_vs is None or reload:
        kb = get_knowledge_base(reload)
        _global_vs = build_vector_store_from_kb(kb)
    return _global_vs if (_global_vs and _global_vs.ready) else None


def get_rag_engine(reload: bool = False) -> RAGEngine:
    """获取全局 RAG 引擎单例（自动选择最优检索方式）。"""
    global _global_engine, _global_vs
    if _global_engine is None or reload:
        kb = get_knowledge_base(reload)
        vs = get_vector_store(reload)
        _global_engine = RAGEngine(kb=kb, vector_store=vs)
    return _global_engine
