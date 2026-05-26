import json
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import jieba
from rank_bm25 import BM25Okapi

from .embeddings import EmbeddingProvider
from .models import Book


# ---------------------------------------------------------------------------
# BM25Index — sparse / keyword retrieval
# ---------------------------------------------------------------------------


class BM25Index:
    """BM25 sparse retrieval with jieba Chinese tokenization."""

    def __init__(self) -> None:
        self._books: List[Book] = []
        self._bm25: BM25Okapi | None = None

    def build(self, books: List[Book]) -> None:
        self._books = list(books)
        corpus = [self._tokenize(self._book_text(book)) for book in books]
        self._bm25 = BM25Okapi(corpus) if corpus else None

    def query(self, query: str, top_k: int) -> List[Tuple[Book, float]]:
        if not self._bm25:
            return []
        tokens = self._tokenize(query)
        scores = self._bm25.get_scores(tokens)
        ranked = sorted(enumerate(scores), key=lambda item: item[1], reverse=True)
        top = ranked[:top_k]
        normalized = _normalize_scores([score for _, score in top])
        return [(self._books[idx], score) for (idx, _), score in zip(top, normalized)]

    def _book_text(self, book: Book) -> str:
        return " ".join([book.title, book.intro, " ".join(book.tags)])

    def _tokenize(self, text: str) -> List[str]:
        text = text.lower()
        text = re.sub(r"\s+", " ", text)
        return [token for token in jieba.lcut(text) if token.strip()]


def _normalize_scores(scores: List[float]) -> List[float]:
    if not scores:
        return []
    mn, mx = min(scores), max(scores)
    if mx == mn:
        return [1.0] * len(scores)
    return [(s - mn) / (mx - mn) for s in scores]


# ---------------------------------------------------------------------------
# HybridVectorStore — dense + sparse hybrid retrieval backed by ChromaDB
# ---------------------------------------------------------------------------


class HybridVectorStore:
    """Hybrid vector + BM25 retrieval with ChromaDB persistence.

    Dense embeddings are computed via the configured EmbeddingProvider.
    Sparse retrieval uses BM25 for keyword matching.
    Results are fused via weighted score combination.

    If embedding_provider is None, operates in sparse-only mode (BM25 only).
    """

    def __init__(
        self,
        persist_dir: str,
        embedding_provider: EmbeddingProvider | None,
        collection_name: str = "novels",
    ) -> None:
        import chromadb

        self._embedder = embedding_provider
        self._bm25 = BM25Index()
        self._books: Dict[str, Book] = {}

        self._chroma = chromadb.PersistentClient(path=persist_dir)
        self._collection = self._chroma.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    # -- Index management ---------------------------------------------------

    def add_books(self, books: List[Book]) -> None:
        """Add or update books. Existing books with the same id are replaced."""
        if not books:
            return

        for b in books:
            self._books[b.id] = b
        self._bm25.build(list(self._books.values()))

        if self._embedder is None:
            return  # sparse-only mode: skip ChromaDB

        texts = [_book_text(b) for b in books]
        embeddings = self._embedder.embed(texts)
        now = datetime.now(timezone.utc).isoformat()

        ids = [b.id for b in books]
        metadatas = [
            {
                "title": b.title,
                "tags": json.dumps(b.tags, ensure_ascii=False),
                "status": b.status or "",
                "intro_length": len(b.intro),
                "tag_count": len(b.tags),
                "last_indexed": now,
            }
            for b in books
        ]
        self._collection.upsert(ids=ids, embeddings=embeddings, metadatas=metadatas)

    def update_book(self, book: Book) -> None:
        """Update a single book."""
        self.add_books([book])

    def delete_book(self, book_id: str) -> None:
        """Remove a book from the index."""
        self._collection.delete(ids=[book_id])
        self._books.pop(book_id, None)
        self._bm25.build(list(self._books.values()))

    def get_book(self, book_id: str) -> Optional[Book]:
        """Retrieve a single book by id."""
        return self._books.get(book_id)

    def book_count(self) -> int:
        return self._collection.count()

    # -- Retrieval ----------------------------------------------------------

    def query_dense(self, query: str, top_k: int, where: dict | None = None) -> List[Tuple[Book, float]]:
        """Dense (semantic) vector search via ChromaDB."""
        if self._embedder is None or self._collection.count() == 0:
            return []
        query_embedding = self._embedder.embed([query])[0]
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, self._collection.count()),
            where=where,
            include=["distances", "metadatas"],
        )
        return self._parse_chroma_results(results)

    def query_sparse(self, query: str, top_k: int) -> List[Tuple[Book, float]]:
        """Sparse (keyword) BM25 search."""
        return self._bm25.query(query, top_k)

    def query_hybrid(
        self,
        query: str,
        top_k: int,
        dense_weight: float = 0.7,
        where: dict | None = None,
    ) -> List[Tuple[Book, float]]:
        """Hybrid search: weighted fusion of dense + sparse scores.

        dense_weight=0.7 means 70% semantic, 30% keyword matching.
        Falls back to sparse-only when no embedding provider is available.
        """
        if self._embedder is None:
            return self.query_sparse(query, top_k)

        dense_results = self.query_dense(query, top_k * 2, where=where)
        sparse_results = self.query_sparse(query, top_k * 2)

        dense_scores = {book.id: score for book, score in dense_results}
        sparse_scores = {book.id: score for book, score in sparse_results}

        all_ids = set(dense_scores.keys()) | set(sparse_scores.keys())
        fused: List[Tuple[Book, float]] = []
        for bid in all_ids:
            d_score = dense_scores.get(bid, 0.0)
            s_score = sparse_scores.get(bid, 0.0)
            combined = dense_weight * d_score + (1 - dense_weight) * s_score
            if bid in self._books:
                fused.append((self._books[bid], combined))

        fused.sort(key=lambda x: x[1], reverse=True)
        return fused[:top_k]

    # -- Helpers ------------------------------------------------------------

    def _parse_chroma_results(self, results: dict) -> List[Tuple[Book, float]]:
        """Convert ChromaDB query results to (Book, score) list."""
        out: List[Tuple[Book, float]] = []
        ids_list = results.get("ids", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for bid, dist in zip(ids_list, distances):
            book = self._books.get(bid)
            if book is None:
                continue
            # ChromaDB returns cosine distance. Convert to similarity: 1 - distance.
            score = 1.0 - min(dist, 1.0)
            out.append((book, score))

        # Re-normalize to [0, 1] range
        scores = [s for _, s in out]
        normalized = _normalize_scores(scores)
        return [(book, ns) for (book, _), ns in zip(out, normalized)]

    def get_index_stats(self) -> dict:
        return {
            "book_count": self._collection.count(),
            "embedding_dim": self._embedder.dim() if self._embedder else 0,
            "bm25_book_count": len(self._books),
            "dense_enabled": self._embedder is not None,
        }


def _book_text(book: Book) -> str:
    return " ".join([book.title, book.intro, " ".join(book.tags)])
