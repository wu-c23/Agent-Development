"""Tests for sentiment_critic.sentiment_api — FastAPI endpoints."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure Sentiment Critic package is first in sys.path and re-import
# the real package (test_critic.py may have loaded the Safe-Search stub).
_senti_path = str(Path(__file__).resolve().parents[1] / "Sentiment Critic")
if _senti_path in sys.path:
    sys.path.remove(_senti_path)
sys.path.insert(0, _senti_path)
sys.modules.pop("sentiment_critic", None)

import importlib

import pytest
from fastapi.testclient import TestClient


MOCK_STORE = {
    "uid-1": {
        "uid": "uid-1",
        "metadata": {
            "title": "诡秘之主",
            "platform": "qidian",
            "last_update": "2026-06-03T12:00:00Z",
        },
        "sentiment_scores": {
            "overall": 9.1,
            "style": 9.2,
            "logic": 9.5,
            "character": 9.0,
            "update_stability": 8.8,
            "toxicity_index": 0.08,
        },
        "critic_summary": {
            "one_liner": "逻辑严密的克苏鲁神作",
            "pros": ["世界观构建顶级", "伏笔回收大师级"],
            "cons": ["开头节奏偏慢"],
        },
        "review_stats": {
            "total_count": 1250,
            "positive_ratio": 0.86,
            "negative_ratio": 0.05,
            "source_breakdown": {"douban": 620, "tieba": 430, "xiaohongshu": 200},
        },
    },
    "uid-2": {
        "uid": "uid-2",
        "metadata": {
            "title": "凡人修仙传",
            "platform": "qidian",
            "last_update": "2026-05-28T16:00:00Z",
        },
        "sentiment_scores": {
            "overall": 8.3,
            "style": 7.5,
            "logic": 9.0,
            "character": 8.5,
            "update_stability": 9.5,
            "toxicity_index": 0.10,
        },
        "critic_summary": {
            "one_liner": "凡人流教科书",
            "pros": ["逻辑自洽的修仙体系", "主角智商长期在线"],
            "cons": ["前期节奏偏慢"],
        },
        "review_stats": {
            "total_count": 3200,
            "positive_ratio": 0.80,
            "negative_ratio": 0.08,
            "source_breakdown": {"douban": 1800, "tieba": 1100, "xiaohongshu": 300},
        },
    },
    "uid-3": {
        "uid": "uid-3",
        "metadata": {
            "title": "修罗武神",
            "platform": "qidian",
            "last_update": "2026-06-03T08:00:00Z",
        },
        "sentiment_scores": {
            "overall": 5.2,
            "style": 5.0,
            "logic": 4.0,
            "character": 3.5,
            "update_stability": 6.0,
            "toxicity_index": 0.45,
        },
        "critic_summary": {
            "one_liner": "爽是真的爽，水也是真的水",
            "pros": ["爽点密集节奏快"],
            "cons": ["后宫角色扁平化", "后期严重注水"],
        },
        "review_stats": {
            "total_count": 2100,
            "positive_ratio": 0.45,
            "negative_ratio": 0.35,
            "source_breakdown": {"douban": 300, "tieba": 1500, "xiaohongshu": 300},
        },
    },
}


# ---------------------------------------------------------------------------
# Fixture: reload the API module with a mocked sentiment store
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    """TestClient backed by a mocked _SENTIMENT_STORE.

    Removes any stale sentiment_critic modules from sys.modules (Safe-Search
    test files may have re-mocked them during collection), re-ensures the
    Sentiment Critic path, then imports with a patched data store.
    """
    # Ensure the real Sentiment Critic path is first
    _senti_path = str(Path(__file__).resolve().parents[1] / "Sentiment Critic")
    if _senti_path in sys.path:
        sys.path.remove(_senti_path)
    sys.path.insert(0, _senti_path)

    # Drop ALL stale sentiment_critic entries so the import is fresh
    for mod in list(sys.modules):
        if mod.startswith("sentiment_critic"):
            del sys.modules[mod]

    # Patch at the data_store level so _init_store() picks up the mock
    with patch(
        "sentiment_critic.data_store.build_mock_sentiment_store",
        return_value=dict(MOCK_STORE),
    ):
        import sentiment_critic.sentiment_api  # noqa: F811
        from sentiment_critic.sentiment_api import app

        yield TestClient(app)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class TestHealth:
    def test_health_returns_healthy(self, client):
        resp = client.get("/api/v1/sentiment/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"
        assert body["version"] == "1.0.0"
        assert body["index_count"] == len(MOCK_STORE)


# ---------------------------------------------------------------------------
# Detail
# ---------------------------------------------------------------------------


class TestDetail:
    def test_detail_existing_uid(self, client):
        resp = client.get("/api/v1/sentiment/detail/uid-1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["uid"] == "uid-1"
        assert body["metadata"]["title"] == "诡秘之主"
        assert body["sentiment_scores"]["overall"] == 9.1
        assert "critic_summary" in body
        assert "review_stats" in body

    def test_detail_missing_uid_returns_404(self, client):
        resp = client.get("/api/v1/sentiment/detail/nonexistent-uid")
        assert resp.status_code == 404
        body = resp.json()
        assert "detail" in body

    def test_detail_returns_all_data_contract_fields(self, client):
        resp = client.get("/api/v1/sentiment/detail/uid-1")
        body = resp.json()
        assert set(body.keys()) == {"uid", "metadata", "sentiment_scores", "critic_summary", "review_stats"}
        assert set(body["metadata"].keys()) == {"title", "platform", "last_update"}
        assert set(body["sentiment_scores"].keys()) == {
            "overall", "style", "logic", "character", "update_stability", "toxicity_index",
        }


# ---------------------------------------------------------------------------
# Compare
# ---------------------------------------------------------------------------


class TestCompare:
    def test_compare_two_uids(self, client):
        resp = client.get("/api/v1/sentiment/compare", params={"uids": "uid-1,uid-2"})
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) == 2
        assert body[0]["uid"] == "uid-1"
        assert body[1]["uid"] == "uid-2"

    def test_compare_with_missing_uid(self, client):
        resp = client.get("/api/v1/sentiment/compare", params={"uids": "uid-1,missing-uid"})
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2
        assert body[0]["uid"] == "uid-1"
        assert body[1]["uid"] == "missing-uid"
        assert "error" in body[1]
        assert body[1]["error"] == "not_found"

    def test_compare_without_uids_param_returns_422(self, client):
        resp = client.get("/api/v1/sentiment/compare")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Refresh
# ---------------------------------------------------------------------------


class TestRefresh:
    def test_refresh_returns_refreshed_status(self, client):
        resp = client.post("/api/v1/sentiment/refresh")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "refreshed"
        assert body["index_count"] == len(MOCK_STORE)


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------


class TestChat:
    def test_chat_returns_answer(self, client):
        with patch("sentiment_critic.rag_engine.get_rag_engine") as mock_get:
            mock_engine = MagicMock()
            mock_engine.answer.return_value = {
                "answer": "推荐《诡秘之主》，这是一本克苏鲁小说。",
                "sources": ["诡秘之主"],
                "method": "tfidf",
            }
            mock_get.return_value = mock_engine

            resp = client.post(
                "/api/v1/sentiment/chat",
                json={"query": "推荐克苏鲁小说", "top_k": 3},
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["query"] == "推荐克苏鲁小说"
            assert "诡秘之主" in body["answer"]
            assert body["sources"] == ["诡秘之主"]
            assert body["method"] == "tfidf"

    def test_chat_with_session_id(self, client):
        with patch("sentiment_critic.rag_engine.get_rag_engine") as mock_get:
            mock_engine = MagicMock()
            mock_engine.answer.return_value = {
                "answer": "推荐《凡人修仙传》。",
                "sources": ["凡人修仙传"],
                "method": "tfidf",
            }
            mock_get.return_value = mock_engine

            resp = client.post(
                "/api/v1/sentiment/chat",
                json={"query": "推荐修仙小说", "top_k": 5, "session_id": "session-1"},
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["query"] == "推荐修仙小说"
            assert "answer" in body

    def test_chat_minimal_request(self, client):
        with patch("sentiment_critic.rag_engine.get_rag_engine") as mock_get:
            mock_engine = MagicMock()
            mock_engine.answer.return_value = {
                "answer": "测试回答",
                "sources": [],
                "method": "tfidf",
            }
            mock_get.return_value = mock_engine

            resp = client.post(
                "/api/v1/sentiment/chat",
                json={"query": "测试"},
            )
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# KB Stats
# ---------------------------------------------------------------------------


class TestKBStats:
    def test_kb_stats_shape(self, client):
        with (
            patch("sentiment_critic.rag_engine.get_rag_engine") as mock_get_engine,
            patch("sentiment_critic.rag_engine.get_vector_store") as mock_get_vs,
        ):
            mock_engine = MagicMock()
            mock_engine.kb.total_chunks = 42
            mock_engine.use_agent = True
            mock_engine.retrieval_method = "tfidf"
            mock_get_engine.return_value = mock_engine

            mock_vs = MagicMock()
            mock_vs.ready = False
            mock_vs.total_chunks = 0
            mock_get_vs.return_value = mock_vs

            resp = client.get("/api/v1/sentiment/kb/stats")
            assert resp.status_code == 200
            body = resp.json()
            assert body["total_chunks"] == 42
            assert body["llm_available"] is True
            assert body["retrieval_method"] == "tfidf"
            assert body["vector_enabled"] is False
            assert body["vector_chunks"] == 0

    def test_kb_stats_with_vector_enabled(self, client):
        with (
            patch("sentiment_critic.rag_engine.get_rag_engine") as mock_get_engine,
            patch("sentiment_critic.rag_engine.get_vector_store") as mock_get_vs,
        ):
            mock_engine = MagicMock()
            mock_engine.kb.total_chunks = 100
            mock_engine.use_agent = True
            mock_engine.retrieval_method = "hybrid"
            mock_get_engine.return_value = mock_engine

            mock_vs = MagicMock()
            mock_vs.ready = True
            mock_vs.total_chunks = 100
            mock_get_vs.return_value = mock_vs

            resp = client.get("/api/v1/sentiment/kb/stats")
            body = resp.json()
            assert body["retrieval_method"] == "hybrid"
            assert body["vector_enabled"] is True
            assert body["vector_chunks"] == 100
