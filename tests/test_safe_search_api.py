"""Tests for the FastAPI REST application (safe_search.api)."""

import sys
from unittest.mock import MagicMock, patch

sys.modules["sentiment_critic"] = MagicMock()
sys.modules["sentiment_critic.critic"] = MagicMock()

import pytest
from fastapi.testclient import TestClient

from safe_search.models import IntentResult

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

SAMPLE_BOOK_UID = "987a2b45c6bd2baa73d750f13daf15b63c20145de2e85fff22ada96ad3d8b27b"


# ---------------------------------------------------------------------------
# Fixture: inject a mock engine into the lazy singleton
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    """Return a (TestClient, mock_engine) tuple.

    The mock engine is injected directly into the API module's ``_engine``
    global so that ``_get_engine()`` returns it without hitting any real
    dependencies.
    """
    mock_engine = MagicMock()
    # Default: book not found
    mock_engine.store.get_book.return_value = None
    mock_engine.store.get_index_stats.return_value = {
        "book_count": 42,
        "last_updated": "2024-06-01T00:00:00",
    }
    mock_engine.store.book_count.return_value = 42

    import safe_search.api

    safe_search.api._engine = mock_engine

    from safe_search.api import app

    test_client = TestClient(app)
    yield test_client, mock_engine


# ---------------------------------------------------------------------------
# Helper: build a mock Book object that the store can return
# ---------------------------------------------------------------------------


def _make_mock_book(
    uid: str = SAMPLE_BOOK_UID,
    title: str = "谎秘之主",
    platform: str = "qidian",
):
    book = MagicMock()
    book.id = uid
    book.title = title
    book.intro = "值夜者克莱恩..."
    book.tags = ["克苏鲁", "悬疑"]
    book.platform = platform
    book.status = "completed"
    book.sentiment_summary = "好评如潮"
    book.metadata = {
        "title": title,
        "platform": platform,
        "last_update": "2024-06-01T00:00:00",
    }
    return book


# ---------------------------------------------------------------------------
# GET /api/v1/search/vector/health
# ---------------------------------------------------------------------------


class TestHealth:
    def test_health_ok(self, client):
        test_client, mock_engine = client

        resp = test_client.get("/api/v1/search/vector/health")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["version"] == "1.0.0"
        assert data["index_count"] == 42
        mock_engine.store.get_index_stats.assert_called_once()


# ---------------------------------------------------------------------------
# POST /api/v1/search/semantic
# ---------------------------------------------------------------------------


class TestSemanticSearch:
    def test_semantic_search_valid(self, client):
        test_client, mock_engine = client

        mock_engine.search.return_value = {
            "query_intent": {
                "summary": "修仙小说",
                "topics": ["修仙"],
                "style": [],
                "protagonist_traits": [],
                "mood": [],
                "constraints": [],
            },
            "retrieval_candidates": [],
            "risk_scores": [],
            "filtered_results": [],
            "blocked_results": [],
            "data_gaps": [],
        }

        payload = {
            "query": "修仙",
            "filters": {
                "tags_include": [],
                "tags_exclude": [],
                "min_heat": None,
                "platforms": [],
            },
            "safe_tags": [],
            "top_k": 10,
        }

        resp = test_client.post("/api/v1/search/semantic", json=payload)

        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert "query_rewrite" in data
        assert "total_hits" in data
        assert data["query_rewrite"] == "修仙小说"
        assert data["total_hits"] == 0

        mock_engine.search.assert_called_once_with(
            query="修仙", avoid_tags=[], top_k=10
        )


# ---------------------------------------------------------------------------
# POST /api/v1/search/books/index
# ---------------------------------------------------------------------------


class TestIndexBooks:
    def test_index_books_valid(self, client):
        test_client, mock_engine = client

        payload = {
            "books": [
                {
                    "title": "谎秘之主",
                    "intro": "值夜者克莱恩...",
                    "tags": ["克苏鲁", "悬疑"],
                    "platform": "qidian",
                    "platform_id": "qidian:谎秘之主",
                }
            ]
        }

        resp = test_client.post("/api/v1/search/books/index", json=payload)

        assert resp.status_code == 200
        data = resp.json()
        assert data["indexed"] == 1
        assert data["total_in_index"] == 42

        mock_engine.index_books.assert_called_once()
        mock_engine.store.book_count.assert_called_once()


# ---------------------------------------------------------------------------
# GET /api/v1/search/books/{uid}
# ---------------------------------------------------------------------------


class TestGetBook:
    def test_get_book_found(self, client):
        test_client, mock_engine = client

        mock_book = _make_mock_book()
        mock_engine.store.get_book.return_value = mock_book

        with patch("sentiment_critic.critic.score_risks") as mock_risk:
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

            resp = test_client.get(f"/api/v1/search/books/{SAMPLE_BOOK_UID}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["uid"] == SAMPLE_BOOK_UID
        assert data["metadata"]["title"] == "谎秘之主"
        assert data["metadata"]["platform"] == "qidian"
        assert data["tags"] == ["克苏鲁", "悬疑"]
        assert data["status"] == "completed"
        assert data["sentiment_summary"] == "好评如潮"
        assert "risk_scores" in data
        assert data["risk_scores"]["slow_pacing"] == 0.3
        assert "risk_evidence" in data

    def test_get_book_not_found(self, client):
        test_client, mock_engine = client

        mock_engine.store.get_book.return_value = None

        resp = test_client.get(f"/api/v1/search/books/{SAMPLE_BOOK_UID}")

        assert resp.status_code == 404
        data = resp.json()
        assert "detail" in data
        assert SAMPLE_BOOK_UID in data["detail"]


# ---------------------------------------------------------------------------
# DELETE /api/v1/search/books/{uid}
# ---------------------------------------------------------------------------


class TestDeleteBook:
    def test_delete_book_found(self, client):
        test_client, mock_engine = client

        mock_book = _make_mock_book()
        mock_engine.store.get_book.return_value = mock_book

        resp = test_client.delete(f"/api/v1/search/books/{SAMPLE_BOOK_UID}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["deleted"] == SAMPLE_BOOK_UID
        assert data["total_in_index"] == 42

        mock_engine.store.get_book.assert_called_with(SAMPLE_BOOK_UID)
        mock_engine.remove_book.assert_called_once_with(SAMPLE_BOOK_UID)

    def test_delete_book_not_found(self, client):
        test_client, mock_engine = client

        mock_engine.store.get_book.return_value = None

        resp = test_client.delete(f"/api/v1/search/books/{SAMPLE_BOOK_UID}")

        assert resp.status_code == 404
        data = resp.json()
        assert "detail" in data
        assert SAMPLE_BOOK_UID in data["detail"]

        mock_engine.remove_book.assert_not_called()


# ---------------------------------------------------------------------------
# GET /api/v1/search/intent
# ---------------------------------------------------------------------------


class TestExtractIntent:
    def test_extract_intent(self, client):
        test_client, mock_engine = client

        mock_engine.extract_intent.return_value = IntentResult(
            summary="修仙小说",
            topics=["修仙"],
            style=["爽文"],
            protagonist_traits=["杀伐果断"],
            mood=["热血"],
            constraints=["no_harem"],
        )

        resp = test_client.get("/api/v1/search/intent", params={"query": "修仙"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"] == "修仙小说"
        assert data["topics"] == ["修仙"]
        assert data["style"] == ["爽文"]
        assert data["protagonist_traits"] == ["杀伐果断"]
        assert data["mood"] == ["热血"]
        assert data["constraints"] == ["no_harem"]

        mock_engine.extract_intent.assert_called_once_with("修仙")


# ---------------------------------------------------------------------------
# POST /api/v1/search/books/sync-from-central
# ---------------------------------------------------------------------------


class TestSyncFromCentral:
    def test_sync_from_central_success(self, client):
        test_client, mock_engine = client

        with patch("safe_search.api._get_central_books") as mock_central:
            mock_central.return_value = [
                {
                    "id": "test-central-1",
                    "title": "Central Book",
                    "intro": "Central intro",
                    "tags": ["tag1"],
                    "platform": "qidian",
                    "platform_id": "cp1",
                    "author": "Author",
                    "status": "completed",
                    "sentiment_summary": "good",
                }
            ]

            resp = test_client.post("/api/v1/search/books/sync-from-central")

        assert resp.status_code == 200
        data = resp.json()
        assert data["indexed"] == 1
        assert data["total_in_index"] == 42
        assert "Sentiment Critic/data/novels.json" in data["source"]

        mock_engine.index_books.assert_called_once()

    def test_sync_from_central_no_data(self, client):
        test_client, mock_engine = client

        with patch("safe_search.api._get_central_books") as mock_central:
            mock_central.return_value = []

            resp = test_client.post("/api/v1/search/books/sync-from-central")

        assert resp.status_code == 404
        data = resp.json()
        assert "detail" in data

        mock_engine.index_books.assert_not_called()
