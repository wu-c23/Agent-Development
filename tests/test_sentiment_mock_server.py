"""Tests for sentiment_critic.mock_server — FastAPI mock for Sentiment Critic.

This module is entirely self-contained with built-in mock data and no
external dependencies, so it can be imported directly.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

# Ensure Sentiment Critic is first in sys.path regardless of conftest
# (pytest's own sys.path.insert(0, …) calls after conftest push it back).
_senti_path = str(Path(__file__).resolve().parents[1] / "Sentiment Critic")
if _senti_path in sys.path:
    sys.path.remove(_senti_path)
sys.path.insert(0, _senti_path)

# Unconditionally remove any pre-existing sentiment_critic (real or mock)
# from sys.modules so the full Sentiment Critic package is imported.
# The Safe-Search stub (critic.py) may have been loaded first by test_critic.py.
# Leave sentiment_critic.critic (and other sub-module mocks) intact —
# they don't exist in the Sentiment Critic package, and Safe-Search
# tests rely on them being MagicMock in sys.modules.
sys.modules.pop("sentiment_critic", None)

import pytest
from fastapi.testclient import TestClient

from sentiment_critic.mock_server import (
    MOCK_NOVELS,
    _UID_MAP,
    app,
)

SAMPLE_UID = "987a2b45c6bd2baa73d750f13daf15b63c20145de2e85fff22ada96ad3d8b27b"
SAMPLE_TITLE = "诡秘之主"
MISSING_UID = "0000000000000000000000000000000000000000000000000000000000000000"


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def client():
    """TestClient bound to the sentiment mock API."""
    yield TestClient(app)


# ===================================================================
# API: GET /api/v1/sentiment/health
# ===================================================================


class TestAPIHealth:
    def test_health_returns_healthy(self, client) -> None:
        resp = client.get("/api/v1/sentiment/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["version"] == "1.0.0"

    def test_health_returns_index_count(self, client) -> None:
        resp = client.get("/api/v1/sentiment/health")
        data = resp.json()
        assert data["index_count"] == len(MOCK_NOVELS)


# ===================================================================
# API: GET /api/v1/sentiment/detail/{uid}
# ===================================================================


class TestAPIDetail:
    def test_detail_existing_uid(self, client) -> None:
        resp = client.get(f"/api/v1/sentiment/detail/{SAMPLE_UID}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["uid"] == SAMPLE_UID
        assert data["metadata"]["title"] == SAMPLE_TITLE

    def test_detail_missing_uid_returns_404(self, client) -> None:
        resp = client.get(f"/api/v1/sentiment/detail/{MISSING_UID}")
        assert resp.status_code == 404

    def test_detail_response_structure(self, client) -> None:
        resp = client.get(f"/api/v1/sentiment/detail/{SAMPLE_UID}")
        data = resp.json()
        # Top-level fields
        assert "uid" in data
        assert "metadata" in data
        assert "sentiment_scores" in data
        assert "critic_summary" in data
        assert "review_stats" in data
        # Metadata
        assert "title" in data["metadata"]
        assert "platform" in data["metadata"]
        assert "last_update" in data["metadata"]
        # Sentiment scores
        scores = data["sentiment_scores"]
        for dim in ("overall", "style", "logic", "character", "update_stability", "toxicity_index"):
            assert dim in scores
        # Critic summary
        summary = data["critic_summary"]
        for field in ("one_liner", "pros", "cons"):
            assert field in summary
        # Review stats
        stats = data["review_stats"]
        for field in ("total_count", "positive_ratio", "negative_ratio", "source_breakdown"):
            assert field in stats


# ===================================================================
# API: GET /api/v1/sentiment/compare
# ===================================================================


class TestAPICompare:
    def test_compare_multiple_uids(self, client) -> None:
        """Comma-separated UIDs return a list of results."""
        uid2 = "26d4613826eb8819a9a601cfb88eb7621b0e6cc5c46ffefa96b5dea22ca938dc"
        resp = client.get(
            "/api/v1/sentiment/compare",
            params={"uids": f"{SAMPLE_UID},{uid2}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["uid"] == SAMPLE_UID
        assert data[1]["uid"] == uid2

    def test_compare_mixed_valid_and_invalid(self, client) -> None:
        """Valid UIDs return data; invalid ones return an error object."""
        resp = client.get(
            "/api/v1/sentiment/compare",
            params={"uids": f"{SAMPLE_UID},{MISSING_UID}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert "error" not in data[0]  # valid
        assert data[1]["error"] == "not_found"  # invalid

    def test_compare_single_uid(self, client) -> None:
        resp = client.get(
            "/api/v1/sentiment/compare",
            params={"uids": SAMPLE_UID},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["uid"] == SAMPLE_UID

    def test_compare_without_uids_returns_422(self, client) -> None:
        """The uids query parameter is required, so omitting it gives 422."""
        resp = client.get("/api/v1/sentiment/compare")
        assert resp.status_code == 422

    def test_compare_empty_uids_returns_400(self, client) -> None:
        """An empty uids parameter (after splitting) returns 400."""
        resp = client.get(
            "/api/v1/sentiment/compare",
            params={"uids": ""},
        )

        # FastAPI Query(required=True) will still get the param,
        # but after splitting an empty string we get [""].
        # The endpoint strips and filters empties: if none remain, 400.
        assert resp.status_code in (400, 422)


# ===================================================================
# API: POST /api/v1/sentiment/refresh
# ===================================================================


class TestAPIRefresh:
    def test_refresh_returns_status(self, client) -> None:
        resp = client.post("/api/v1/sentiment/refresh")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "refreshed"
        assert data["index_count"] == len(MOCK_NOVELS)


# ===================================================================
# API: mock data integrity
# ===================================================================


class TestMockDataIntegrity:
    def test_all_novels_have_uid(self) -> None:
        for novel in MOCK_NOVELS:
            assert novel["uid"], f"Missing uid in {novel['metadata']['title']}"

    def test_all_novels_have_required_fields(self) -> None:
        for novel in MOCK_NOVELS:
            assert "metadata" in novel
            assert "sentiment_scores" in novel
            assert "critic_summary" in novel
            assert "review_stats" in novel

    def test_uid_map_covers_all(self) -> None:
        assert len(_UID_MAP) == len(MOCK_NOVELS)
        for novel in MOCK_NOVELS:
            assert novel["uid"] in _UID_MAP
