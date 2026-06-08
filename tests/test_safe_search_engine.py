"""Tests for SafeSearchEngine -- semantic search with risk-avoidance filtering."""

import sys
from unittest.mock import MagicMock, patch

sys.modules["sentiment_critic"] = MagicMock()
sys.modules["sentiment_critic.critic"] = MagicMock()

import pytest

from safe_search.engine import SafeSearchEngine
from safe_search.models import Book, IntentResult

# ---------------------------------------------------------------------------
# Sample test data
# ---------------------------------------------------------------------------

BOOK = Book(
    title="谎秘之主",
    intro="值夜者克莱恩...",
    tags=["克苏鲁", "悬疑"],
    platform="qidian",
    platform_id="qidian:谎秘之主",
    id="test-uid-123",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def engine():
    """Create SafeSearchEngine with all external dependencies mocked.

    Yields (engine, mock_openai, store_instance, mock_intent_class, store_class)
    where store_class is the HybridVectorStore class mock (for ``call_args``)
    and store_instance is ``store_class.return_value``.
    """
    with (
        patch("safe_search.engine.OpenAI") as mock_openai,
        patch("safe_search.engine.create_embedding_provider") as mock_embed,
        patch("safe_search.engine.HybridVectorStore") as mock_store,
        patch("safe_search.engine.IntentExtractor") as mock_intent,
    ):
        mock_store_instance = MagicMock()
        mock_store.return_value = mock_store_instance
        e = SafeSearchEngine()
        yield e, mock_openai, mock_store_instance, mock_intent, mock_store


@pytest.fixture
def engine_sparse():
    """Create engine where dense embedding fails -- triggers sparse fallback."""
    with (
        patch("safe_search.engine.OpenAI") as mock_openai,
        patch(
            "safe_search.engine.create_embedding_provider",
            side_effect=Exception("HF blocked"),
        ),
        patch("safe_search.engine.HybridVectorStore") as mock_store,
        patch("safe_search.engine.IntentExtractor") as mock_intent,
    ):
        mock_store_instance = MagicMock()
        mock_store.return_value = mock_store_instance
        e = SafeSearchEngine()
        yield e, mock_openai, mock_store_instance, mock_intent, mock_store


# ---------------------------------------------------------------------------
# Constructor tests
# ---------------------------------------------------------------------------


class TestConstructor:
    def test_success(self, engine):
        """Constructor succeeds when all dependencies are available."""
        e, mock_openai, mock_store_instance, mock_intent, mock_store_cls = engine
        assert e._dense_enabled is True
        mock_openai.assert_called_once()
        # Store should have been created with an embedding provider
        call_kwargs = mock_store_cls.call_args[1]
        assert call_kwargs["embedding_provider"] is not None

    def test_missing_api_key(self):
        """Constructor raises RuntimeError when DEEPSEEK_API_KEY is not set."""
        with patch("safe_search.engine.API_KEY", ""):
            with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
                SafeSearchEngine()

    def test_sparse_fallback(self, engine_sparse):
        """Constructor falls back to sparse-only mode when embedding fails."""
        e, _, _, _, mock_store_cls = engine_sparse
        assert e._dense_enabled is False
        # Store should have been created with embedding_provider=None
        call_kwargs = mock_store_cls.call_args[1]
        assert call_kwargs["embedding_provider"] is None


# ---------------------------------------------------------------------------
# Index management
# ---------------------------------------------------------------------------


class TestIndexManagement:
    def test_index_books(self, engine):
        """index_books delegates to store.add_books."""
        e, _, mock_store, _, _ = engine
        e.index_books([BOOK])
        mock_store.add_books.assert_called_once_with([BOOK])

    def test_remove_book(self, engine):
        """remove_book delegates to store.delete_book."""
        e, _, mock_store, _, _ = engine
        e.remove_book("test-uid-123")
        mock_store.delete_book.assert_called_once_with("test-uid-123")

    def test_store_property(self, engine):
        """store property returns the HybridVectorStore instance."""
        e, _, mock_store, _, _ = engine
        assert e.store is mock_store


# ---------------------------------------------------------------------------
# Intent extraction
# ---------------------------------------------------------------------------


class TestIntentExtraction:
    def test_extract_intent(self, engine):
        """extract_intent delegates to IntentExtractor.extract."""
        e, _, _, mock_intent, _ = engine
        mock_intent_instance = mock_intent.return_value
        expected = IntentResult(summary="修仙小说")
        mock_intent_instance.extract.return_value = expected

        result = e.extract_intent("修仙")
        mock_intent_instance.extract.assert_called_once_with("修仙")
        assert result.summary == "修仙小说"


# ---------------------------------------------------------------------------
# Full pipeline search
# ---------------------------------------------------------------------------


class TestSearch:
    """Full pipeline search tests with mocked internals."""

    def test_full_pipeline(self, engine):
        """search returns dict with all expected keys and proper structure."""
        e, _, mock_store, mock_intent, _ = engine
        mock_intent_instance = mock_intent.return_value

        # --- mock intent layer ---
        intent = IntentResult(
            summary="修仙小说",
            topics=["修仙"],
            style=["爽文"],
            protagonist_traits=[],
            mood=["热血"],
            constraints=["no_harem"],
        )
        mock_intent_instance.extract.return_value = intent
        mock_intent_instance.build_search_query.return_value = "修仙 爽文"
        mock_intent_instance.build_metadata_filter.return_value = None
        mock_intent_instance.score_candidate.return_value = 0.8

        # --- mock retrieval ---
        mock_store.query_hybrid.return_value = [(BOOK, 0.9)]

        # --- mock risk scoring ---
        with patch("safe_search.engine.score_risks") as mock_risk:
            mock_risk.return_value = {
                "scores": {
                    "abuse_protagonist": 0.1,
                    "unfinished": 0.0,
                    "melodrama": 0.05,
                    "harem": 0.0,
                    "slow_pacing": 0.3,
                },
                "evidence": [{"type": "model", "value": "mock"}],
            }

            result = e.search("修仙")

        # --- verify top-level structure ---
        assert "query_intent" in result
        assert "retrieval_candidates" in result
        assert "risk_scores" in result
        assert "filtered_results" in result
        assert "blocked_results" in result
        assert "data_gaps" in result

        # --- query_intent ---
        assert result["query_intent"]["summary"] == "修仙小说"
        assert result["query_intent"]["topics"] == ["修仙"]
        assert result["query_intent"]["constraints"] == ["no_harem"]

        # --- retrieval_candidates ---
        assert len(result["retrieval_candidates"]) == 1
        rc = result["retrieval_candidates"][0]
        assert rc["id"] == "test-uid-123"
        assert rc["title"] == "谎秘之主"
        assert rc["similarity"] == 0.9
        assert rc["matched_fields"] == ["title", "intro", "tags"]

        # --- risk_scores ---
        assert len(result["risk_scores"]) == 1
        rs = result["risk_scores"][0]
        assert rs["id"] == "test-uid-123"
        assert rs["abuse_protagonist"] == 0.1
        assert rs["slow_pacing"] == 0.3
        assert rs["evidence"] == [{"type": "model", "value": "mock"}]

        # --- filtered_results (book passes all checks => in filtered) ---
        assert len(result["filtered_results"]) == 1
        fr = result["filtered_results"][0]
        assert fr["id"] == "test-uid-123"
        assert 0.0 <= fr["final_score"] <= 1.0
        assert "reasons_recommend" in fr
        assert "reasons_risk" in fr

        # --- blocked_results (no avoid_tags, so empty) ---
        assert len(result["blocked_results"]) == 0

        # --- data_gaps (BOOK has status=None and sentiment_summary=None) ---
        assert len(result["data_gaps"]) == 1
        dg = result["data_gaps"][0]
        assert "ending_status" in dg["missing"]
        assert "public_opinion_summary" in dg["missing"]

        # --- verify internal calls ---
        mock_intent_instance.extract.assert_called_once_with("修仙")
        mock_intent_instance.build_search_query.assert_called_once()
        mock_intent_instance.build_metadata_filter.assert_called_once()
        mock_intent_instance.score_candidate.assert_called_once_with(BOOK, intent)

    def test_with_avoid_tags(self, engine):
        """search blocks books whose tags match avoid_tags."""
        e, _, mock_store, mock_intent, _ = engine
        mock_intent_instance = mock_intent.return_value

        # A book that ought to be blocked
        harem_book = Book(
            title="后宫文",
            intro="后宫争斗",
            tags=["后宫", "宫斗"],
            platform="qidian",
            platform_id="qidian:后宫文",
            id="test-harem-uid",
            status="ongoing",
            sentiment_summary="popular",
        )

        mock_intent_instance.extract.return_value = IntentResult(
            summary="宫斗小说",
            topics=["宫斗"],
        )
        mock_intent_instance.build_search_query.return_value = "宫斗"
        mock_intent_instance.build_metadata_filter.return_value = None
        mock_intent_instance.score_candidate.return_value = 0.5

        mock_store.query_hybrid.return_value = [(harem_book, 0.9)]

        with patch("safe_search.engine.score_risks") as mock_risk:
            mock_risk.return_value = {
                "scores": {
                    dim: 0.0
                    for dim in [
                        "abuse_protagonist",
                        "unfinished",
                        "melodrama",
                        "harem",
                        "slow_pacing",
                    ]
                },
                "evidence": [],
            }

            result = e.search("宫斗", avoid_tags=["后宫"])

        assert len(result["blocked_results"]) == 1
        br = result["blocked_results"][0]
        assert br["id"] == "test-harem-uid"
        assert any("tag:后宫" in reason for reason in br["blocked_by"])

        # filtered_results should be empty since the only candidate was blocked
        assert len(result["filtered_results"]) == 0

    def test_with_books_param(self, engine):
        """search indexes provided books before querying."""
        e, _, mock_store, mock_intent, _ = engine
        mock_intent_instance = mock_intent.return_value

        mock_intent_instance.extract.return_value = IntentResult(summary="test")
        mock_intent_instance.build_search_query.return_value = "test query"
        mock_intent_instance.build_metadata_filter.return_value = None
        mock_intent_instance.score_candidate.return_value = 0.5
        mock_store.query_hybrid.return_value = [(BOOK, 0.9)]

        with patch("safe_search.engine.score_risks") as mock_risk:
            mock_risk.return_value = {
                "scores": {
                    dim: 0.0
                    for dim in [
                        "abuse_protagonist",
                        "unfinished",
                        "melodrama",
                        "harem",
                        "slow_pacing",
                    ]
                },
                "evidence": [],
            }

            e.search("test", books=[BOOK])

        # store.add_books should have been called with the provided books
        mock_store.add_books.assert_any_call([BOOK])
