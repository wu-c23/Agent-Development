"""Tests for safe_search.vector_store.

BM25Index, _normalize_scores, and HybridVectorStore.
"""

from __future__ import annotations

import json
import sys
import pytest
from unittest.mock import MagicMock, patch, ANY

# ---------------------------------------------------------------------------
# Workaround: safe_search.__init__ eagerly imports engine.py, which tries to
# import sentiment_critic.critic.score_risks.  That module does not exist in
# the repo (critic.py is missing), so we stub it in sys.modules before any
# safe_search import triggers the chain.
# ---------------------------------------------------------------------------
_stub_critic = MagicMock()
_stub_critic.score_risks = MagicMock(return_value={
    "scores": {"violence": 0.0, "sexual": 0.0, "gambling": 0.0, "politics": 0.0, "morality": 0.0},
    "evidence": {"violence": [], "sexual": [], "gambling": [], "politics": [], "morality": []},
})
sys.modules["sentiment_critic"] = MagicMock()
sys.modules["sentiment_critic.critic"] = _stub_critic
# ---------------------------------------------------------------------------

from safe_search.vector_store import BM25Index, _normalize_scores, HybridVectorStore
from safe_search.models import Book


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_book(
    id: str,
    title: str = "测试书名",
    intro: str = "测试简介",
    tags: list | None = None,
    platform: str = "test",
    platform_id: str | None = None,
    status: str | None = None,
) -> Book:
    return Book(
        id=id,
        title=title,
        intro=intro,
        tags=tags or [],
        platform=platform,
        platform_id=platform_id or id,
        status=status,
    )


SIMPLE_BOOKS = [
    make_book("b1", "书一", "简介一", ["tag1", "tag2"]),
    make_book("b2", "书二", "简介二", ["tag3", "tag4"]),
]


# ============================================================================
# _normalize_scores
# ============================================================================

class TestNormalizeScores:
    """Unit tests for the _normalize_scores helper."""

    def test_ascending_values(self) -> None:
        """[1, 2, 3] -> [0.0, 0.5, 1.0]."""
        assert _normalize_scores([1, 2, 3]) == [0.0, 0.5, 1.0]

    def test_empty_list(self) -> None:
        """Empty input returns empty list."""
        assert _normalize_scores([]) == []

    def test_all_same_values(self) -> None:
        """When all values are equal, return all 1.0."""
        assert _normalize_scores([5, 5, 5]) == [1.0, 1.0, 1.0]

    def test_single_element(self) -> None:
        """Single element returns [1.0]."""
        assert _normalize_scores([3.14]) == [1.0]

    def test_negative_values(self) -> None:
        """Negative values normalize correctly."""
        assert _normalize_scores([-2, 0, 2]) == [0.0, 0.5, 1.0]

    def test_float_precision(self) -> None:
        """Float values with fractional components."""
        result = _normalize_scores([0.1, 0.5, 0.9])
        assert result[0] == 0.0
        assert result[-1] == 1.0


# ============================================================================
# BM25Index
# ============================================================================

class TestBM25Index:
    """Unit tests for BM25Index sparse retrieval."""

    # -- build ---------------------------------------------------------------

    @patch("safe_search.vector_store.jieba.lcut", return_value=["test", "token"])
    def test_build_stores_books_and_builds_corpus(self, mock_lcut: MagicMock) -> None:
        """build() stores the book list and initialises BM25Okapi."""
        idx = BM25Index()
        assert idx._books == []
        assert idx._bm25 is None

        idx.build(SIMPLE_BOOKS)

        assert len(idx._books) == 2
        assert idx._bm25 is not None
        # One tokenize call per book
        assert mock_lcut.call_count == 2

    @patch("safe_search.vector_store.jieba.lcut", return_value=["a"])
    def test_build_empty_books_no_bm25(self, mock_lcut: MagicMock) -> None:
        """Building with an empty book list leaves _bm25 as None."""
        idx = BM25Index()
        idx.build([])
        assert idx._books == []
        assert idx._bm25 is None

    @patch("safe_search.vector_store.jieba.lcut", return_value=["test", "token"])
    def test_build_replaces_previous_state(self, mock_lcut: MagicMock) -> None:
        """Subsequent build() calls fully replace prior state."""
        idx = BM25Index()
        idx.build([make_book("old")])
        assert len(idx._books) == 1
        assert idx._books[0].id == "old"

        idx.build([make_book("new")])
        assert len(idx._books) == 1
        assert idx._books[0].id == "new"

    # -- query ---------------------------------------------------------------

    @patch("safe_search.vector_store.jieba.lcut", return_value=["test", "token"])
    def test_query_returns_sorted_book_score_tuples(self, mock_lcut: MagicMock) -> None:
        """query() returns (Book, float) tuples sorted descending by score."""
        idx = BM25Index()
        idx.build(SIMPLE_BOOKS)
        results = idx.query("some query", top_k=2)

        assert len(results) == 2
        for book, score in results:
            assert isinstance(book, Book)
            assert isinstance(score, float)
            assert 0.0 <= score <= 1.0
        assert results[0][1] >= results[1][1]

    @patch("safe_search.vector_store.jieba.lcut", return_value=["test", "token"])
    def test_query_empty_index(self, mock_lcut: MagicMock) -> None:
        """Querying an index that was never built returns []."""
        idx = BM25Index()
        assert idx.query("anything", top_k=5) == []

    @patch("safe_search.vector_store.jieba.lcut", return_value=["test", "token"])
    def test_query_respects_top_k(self, mock_lcut: MagicMock) -> None:
        """Only top_k results are returned."""
        many = [make_book(f"b{i}") for i in range(10)]
        idx = BM25Index()
        idx.build(many)
        assert len(idx.query("test", top_k=3)) == 3
        assert len(idx.query("test", top_k=7)) == 7

    @patch("safe_search.vector_store.jieba.lcut", return_value=["test", "token"])
    def test_query_top_k_larger_than_corpus(self, mock_lcut: MagicMock) -> None:
        """When top_k exceeds corpus size, all available results are returned."""
        idx = BM25Index()
        idx.build(SIMPLE_BOOKS)
        assert len(idx.query("test", top_k=100)) == 2

    @patch("safe_search.vector_store.jieba.lcut", return_value=["test", "token"])
    def test_query_top_k_zero_returns_empty(self, mock_lcut: MagicMock) -> None:
        """top_k=0 produces an empty result list."""
        idx = BM25Index()
        idx.build(SIMPLE_BOOKS)
        assert idx.query("test", top_k=0) == []


# ============================================================================
# HybridVectorStore
# ============================================================================

@pytest.fixture
def mock_chroma():
    """Patch chromadb.PersistentClient and return the mock collection.

    Tests can configure the returned mock_collection to control count(),
    query(), upsert(), delete(), get() etc.
    """
    with patch("chromadb.PersistentClient") as m:
        mock_collection = MagicMock()
        mock_collection.count.return_value = 0
        mock_collection.query.return_value = {
            "ids": [[]],
            "distances": [[]],
            "metadatas": [[]],
        }
        mock_collection.get.return_value = {"ids": [], "metadatas": []}
        m.return_value.get_or_create_collection.return_value = mock_collection
        yield mock_collection


@pytest.fixture
def mock_jieba():
    """Patch jieba.lcut for any test that triggers BM25 tokenisation."""
    with patch("safe_search.vector_store.jieba.lcut", return_value=["test", "token"]):
        yield


class TestHybridVectorStore:
    """Unit tests for HybridVectorStore."""

    # -- init ----------------------------------------------------------------

    def test_init_sparse_only(self, mock_chroma: MagicMock) -> None:
        """Constructor with None embedder creates a sparse-only store."""
        vs = HybridVectorStore("/tmp/test", embedding_provider=None)
        assert vs is not None
        assert vs._embedder is None
        assert vs._bm25 is not None
        assert vs._books == {}
        # count() is NOT called during __init__ — it is only used in
        # query_dense / book_count / get_index_stats
        mock_chroma.count.assert_not_called()

    def test_init_with_embedder(self, mock_chroma: MagicMock) -> None:
        """Constructor stores the embedder reference when provided."""
        mock_embedder = MagicMock()
        vs = HybridVectorStore("/tmp/test", embedding_provider=mock_embedder)
        assert vs._embedder is mock_embedder

    # -- add_books -----------------------------------------------------------

    def test_add_books_calls_embedder(self, mock_chroma: MagicMock, mock_jieba: None) -> None:
        """add_books invokes embedder.embed and collection.upsert."""
        mock_embedder = MagicMock()
        mock_embedder.embed.return_value = [[0.1, 0.2], [0.3, 0.4]]

        vs = HybridVectorStore("/tmp/test", embedding_provider=mock_embedder)
        books = [make_book("b1"), make_book("b2")]
        vs.add_books(books)

        mock_embedder.embed.assert_called_once()
        mock_chroma.upsert.assert_called_once()
        call_kwargs = mock_chroma.upsert.call_args.kwargs
        assert call_kwargs["ids"] == ["b1", "b2"]
        assert len(call_kwargs["embeddings"]) == 2
        assert len(call_kwargs["metadatas"]) == 2
        # Verify metadata structure
        for meta in call_kwargs["metadatas"]:
            assert "title" in meta
            assert "platform" in meta
            assert "tags" in meta
            assert "last_indexed" in meta

    def test_add_books_sparse_only_skips_upsert(
        self, mock_chroma: MagicMock, mock_jieba: None
    ) -> None:
        """Without an embedder, add_books skips ChromaDB upsert."""
        vs = HybridVectorStore("/tmp/test", embedding_provider=None)
        vs.add_books(SIMPLE_BOOKS)
        mock_chroma.upsert.assert_not_called()
        assert len(vs._books) == 2

    def test_add_books_empty_list(self, mock_chroma: MagicMock) -> None:
        """add_books([]) is a no-op."""
        vs = HybridVectorStore("/tmp/test", embedding_provider=None)
        vs.add_books([])
        assert vs._books == {}
        mock_chroma.upsert.assert_not_called()

    # -- query_sparse / query_dense / query_hybrid ---------------------------

    def test_query_sparse_delegates_to_bm25(
        self, mock_chroma: MagicMock, mock_jieba: None
    ) -> None:
        """query_sparse returns BM25 results."""
        vs = HybridVectorStore("/tmp/test", embedding_provider=None)
        vs.add_books(SIMPLE_BOOKS)
        results = vs.query_sparse("test query", top_k=2)
        assert len(results) == 2
        for book, score in results:
            assert isinstance(book, Book)
            assert 0.0 <= score <= 1.0

    def test_query_dense_returns_empty_without_embedder(
        self, mock_chroma: MagicMock
    ) -> None:
        """query_dense returns [] when no embedder is configured."""
        vs = HybridVectorStore("/tmp/test", embedding_provider=None)
        assert vs.query_dense("test", top_k=5) == []

    def test_query_dense_returns_empty_when_count_zero(
        self, mock_chroma: MagicMock
    ) -> None:
        """query_dense returns [] when the collection is empty."""
        mock_embedder = MagicMock()
        vs = HybridVectorStore("/tmp/test", embedding_provider=mock_embedder)
        vs._books = {"b1": make_book("b1")}
        # collection.count is 0 (default from fixture)
        assert vs.query_dense("test", top_k=5) == []

    def test_query_hybrid_no_embedder_falls_back_to_sparse(
        self, mock_chroma: MagicMock, mock_jieba: None
    ) -> None:
        """query_hybrid falls back to sparse-only when there is no embedder."""
        vs = HybridVectorStore("/tmp/test", embedding_provider=None)
        vs.add_books(SIMPLE_BOOKS)
        results = vs.query_hybrid("test query", top_k=2)
        assert len(results) == 2

    def test_query_hybrid_with_embedder(
        self, mock_chroma: MagicMock, mock_jieba: None
    ) -> None:
        """query_hybrid fuses dense + sparse scores."""
        mock_embedder = MagicMock()
        # Return value for add_books
        mock_embedder.embed.return_value = [[0.1, 0.2, 0.3]]

        vs = HybridVectorStore("/tmp/test", embedding_provider=mock_embedder)
        book = make_book("hybrid1", "混", "合检索", ["测试"])
        vs.add_books([book])

        # Configure collection for query_dense
        mock_chroma.count.return_value = 1
        mock_chroma.query.return_value = {
            "ids": [["hybrid1"]],
            "distances": [[0.3]],
            "metadatas": [[{"title": "混"}]],
        }

        # Reset embedder call history (was called during add_books)
        mock_embedder.embed.reset_mock()
        mock_embedder.embed.return_value = [[0.1, 0.2, 0.3]]

        results = vs.query_hybrid("混合", top_k=1)
        assert len(results) == 1
        assert results[0][0].id == "hybrid1"
        assert 0.0 <= results[0][1] <= 1.0
        # Both dense and sparse were consulted
        mock_embedder.embed.assert_called_once()
        mock_chroma.query.assert_called_once()

    # -- get_book ------------------------------------------------------------

    def test_get_book_returns_stored_book(
        self, mock_chroma: MagicMock, mock_jieba: None
    ) -> None:
        """get_book retrieves a book by id."""
        vs = HybridVectorStore("/tmp/test", embedding_provider=None)
        book = make_book("find-me", "目标书")
        vs.add_books([book])
        retrieved = vs.get_book("find-me")
        assert retrieved is not None
        assert retrieved.id == "find-me"
        assert retrieved.title == "目标书"

    def test_get_book_returns_none_for_missing(self, mock_chroma: MagicMock) -> None:
        """get_book returns None when the id does not exist."""
        vs = HybridVectorStore("/tmp/test", embedding_provider=None)
        assert vs.get_book("nonexistent") is None

    # -- update_book / delete_book ------------------------------------------

    def test_update_book_delegates_to_add_books(
        self, mock_chroma: MagicMock, mock_jieba: None
    ) -> None:
        """update_book is a thin wrapper around add_books([book])."""
        mock_embedder = MagicMock()
        mock_embedder.embed.return_value = [[0.5, 0.5]]

        vs = HybridVectorStore("/tmp/test", embedding_provider=mock_embedder)
        book = make_book("upd1")
        with patch.object(vs, "add_books") as mock_add:
            vs.update_book(book)
            mock_add.assert_called_once_with([book])

    def test_delete_book_removes_book(
        self, mock_chroma: MagicMock, mock_jieba: None
    ) -> None:
        """delete_book removes the book from chroma and local dict."""
        vs = HybridVectorStore("/tmp/test", embedding_provider=None)
        book = make_book("del1")
        vs._books = {"del1": book}

        vs.delete_book("del1")
        assert "del1" not in vs._books
        mock_chroma.delete.assert_called_once_with(ids=["del1"])

    # -- book_count ----------------------------------------------------------

    def test_book_count(self, mock_chroma: MagicMock) -> None:
        """book_count delegates to the collection count."""
        mock_chroma.count.return_value = 42
        vs = HybridVectorStore("/tmp/test", embedding_provider=None)
        assert vs.book_count() == 42

    # -- get_index_stats -----------------------------------------------------

    def test_get_index_stats_with_embedder(
        self, mock_chroma: MagicMock
    ) -> None:
        """get_index_stats returns expected keys with an embedder."""
        mock_embedder = MagicMock()
        mock_embedder.dim.return_value = 768

        mock_chroma.count.return_value = 3
        mock_chroma.get.return_value = {
            "metadatas": [
                {"last_indexed": "2024-01-01T00:00:00"},
                {"last_indexed": "2025-06-15T12:00:00"},
                {"last_indexed": "2024-09-01T00:00:00"},
            ]
        }

        vs = HybridVectorStore("/tmp/test", embedding_provider=mock_embedder)
        vs._books = {
            "b1": make_book("b1"),
            "b2": make_book("b2"),
            "b3": make_book("b3"),
        }

        stats = vs.get_index_stats()
        assert stats["book_count"] == 3
        assert stats["embedding_dim"] == 768
        assert stats["bm25_book_count"] == 3
        assert stats["dense_enabled"] is True
        assert stats["last_updated"] == "2025-06-15T12:00:00"

    def test_get_index_stats_empty(self, mock_chroma: MagicMock) -> None:
        """get_index_stats returns zero / empty values for an empty store."""
        mock_chroma.count.return_value = 0
        vs = HybridVectorStore("/tmp/test", embedding_provider=None)
        stats = vs.get_index_stats()
        assert stats["book_count"] == 0
        assert stats["embedding_dim"] == 0
        assert stats["bm25_book_count"] == 0
        assert stats["dense_enabled"] is False
        assert stats["last_updated"] == ""

    # -- _parse_chroma_results -----------------------------------------------

    def test_parse_chroma_results_converts_distances(
        self, mock_chroma: MagicMock
    ) -> None:
        """Distances are converted to similarities and normalised."""
        vs = HybridVectorStore("/tmp/test", embedding_provider=None)
        vs._books = {
            "b1": make_book("b1"),
            "b2": make_book("b2"),
        }

        raw = {
            "ids": [["b1", "b2"]],
            "distances": [[0.2, 0.8]],
            "metadatas": [[{}, {}]],
        }
        parsed = vs._parse_chroma_results(raw)

        assert len(parsed) == 2
        # Distance 0.2 -> similarity 0.8; distance 0.8 -> similarity 0.2
        # Normalised: 0.8 -> 1.0, 0.2 -> 0.0
        assert parsed[0][0].id == "b1"
        assert parsed[0][1] == pytest.approx(1.0)
        assert parsed[1][0].id == "b2"
        assert parsed[1][1] == pytest.approx(0.0)

    def test_parse_chroma_results_skips_missing_books(
        self, mock_chroma: MagicMock
    ) -> None:
        """Books not present in _books are silently skipped."""
        vs = HybridVectorStore("/tmp/test", embedding_provider=None)
        vs._books = {"b1": make_book("b1")}

        raw = {
            "ids": [["b1", "ghost"]],
            "distances": [[0.3, 0.6]],
            "metadatas": [[{}, {}]],
        }
        parsed = vs._parse_chroma_results(raw)
        assert len(parsed) == 1
        assert parsed[0][0].id == "b1"

    def test_parse_chroma_results_clips_large_distances(
        self, mock_chroma: MagicMock
    ) -> None:
        """Distances > 1.0 are clipped to 1.0 before similarity conversion."""
        vs = HybridVectorStore("/tmp/test", embedding_provider=None)
        vs._books = {
            "b1": make_book("b1"),
            "b2": make_book("b2"),
        }

        raw = {
            "ids": [["b1", "b2"]],
            "distances": [[1.5, 0.3]],
            "metadatas": [[{}, {}]],
        }
        parsed = vs._parse_chroma_results(raw)

        assert len(parsed) == 2
        # Without clipping: 1.0-1.5 = -0.5 negative!
        # With clipping: 1.0-min(1.5,1.0) = 0.0; 1.0-min(0.3,1.0) = 0.7
        # Normalised: [0.0, 0.7] -> [0.0, 1.0]
        assert parsed[0][0].id == "b1"
        assert parsed[0][1] == pytest.approx(0.0)
        assert parsed[1][0].id == "b2"
        assert parsed[1][1] == pytest.approx(1.0)

    def test_parse_chroma_results_empty_ids(self, mock_chroma: MagicMock) -> None:
        """Empty ids / distances return an empty list."""
        vs = HybridVectorStore("/tmp/test", embedding_provider=None)
        raw = {
            "ids": [[]],
            "distances": [[]],
            "metadatas": [[]],
        }
        assert vs._parse_chroma_results(raw) == []
