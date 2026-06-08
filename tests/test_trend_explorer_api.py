"""Tests for mock_server.py — Trend Explorer Mock API endpoints.

Tests all Data Contract v1.0 endpoints:
    GET /api/v1/trend/health
    GET /api/v1/trend/hot
    GET /api/v1/trend/detail/{uid}
    GET /api/v1/trend/tags/evolution

mock_server.py has no external dependencies beyond FastAPI, so these tests
import the module directly and exercise its built-in mock data.
"""

import sys
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_UID = "987a2b45c6bd2baa73d750f13daf15b63c20145de2e85fff22ada96ad3d8b27b"
NOVEL_COUNT = 5


def _import_app():
    """Import (or reload) mock_server.app, clearing any cached import first.

    The conftest already inserts Trend Explorer/trend-api-spec into sys.path,
    so a plain ``import mock_server`` should work.
    """
    for mod in list(sys.modules.keys()):
        if "mock_server" in mod and mod != "mock_server":
            del sys.modules[mod]
    # Force a fresh import so test isolation is maintained
    if "mock_server" in sys.modules:
        import importlib

        import mock_server as ms
        importlib.reload(ms)
    else:
        import mock_server as ms
    return ms.app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="function")
def client():
    """TestClient backed by a freshly loaded mock_server module."""
    app = _import_app()
    with TestClient(app) as c:
        yield c


# ===================================================================
# GET /api/v1/trend/health
# ===================================================================


class TestHealthEndpoint:
    def test_returns_ok_status(self, client: TestClient):
        resp = client.get("/api/v1/trend/health")
        assert resp.status_code == 200

    def test_response_structure(self, client: TestClient):
        resp = client.get("/api/v1/trend/health")
        body = resp.json()
        assert body == {"status": "ok", "module": "trend-explorer", "mock": True}

    def test_has_mock_header(self, client: TestClient):
        resp = client.get("/api/v1/trend/health")
        assert resp.headers.get("X-Mock") == "true"

    def test_has_latency_header(self, client: TestClient):
        resp = client.get("/api/v1/trend/health")
        latency = resp.headers.get("X-Mock-Latency")
        assert latency is not None
        assert latency.endswith("s")


# ===================================================================
# GET /api/v1/trend/hot
# ===================================================================


class TestHotEndpoint:
    def test_returns_items_list(self, client: TestClient):
        resp = client.get("/api/v1/trend/hot")
        assert resp.status_code == 200

    def test_response_structure_contract(self, client: TestClient):
        """Verify Data Contract v1.0 shape: {"items": [...], "total": int}."""
        resp = client.get("/api/v1/trend/hot")
        body = resp.json()
        assert "items" in body
        assert "total" in body
        assert isinstance(body["items"], list)
        assert isinstance(body["total"], int)

    def test_returns_all_mock_novels_by_default(self, client: TestClient):
        resp = client.get("/api/v1/trend/hot")
        body = resp.json()
        assert len(body["items"]) == NOVEL_COUNT
        assert body["total"] == NOVEL_COUNT

    def test_limit_parameter(self, client: TestClient):
        resp = client.get("/api/v1/trend/hot?limit=3")
        body = resp.json()
        assert len(body["items"]) == 3
        assert body["total"] == NOVEL_COUNT  # total is always the full count

    def test_limit_1_returns_one(self, client: TestClient):
        resp = client.get("/api/v1/trend/hot?limit=1")
        body = resp.json()
        assert len(body["items"]) == 1

    def test_limit_100_returns_all(self, client: TestClient):
        resp = client.get("/api/v1/trend/hot?limit=100")
        body = resp.json()
        assert len(body["items"]) == NOVEL_COUNT

    def test_invalid_limit_negative_is_rejected(self, client: TestClient):
        resp = client.get("/api/v1/trend/hot?limit=0")
        assert resp.status_code == 422

    def test_first_item_structure(self, client: TestClient):
        """Each item must contain uid, metadata, and trend_metrics."""
        resp = client.get("/api/v1/trend/hot?limit=1")
        item = resp.json()["items"][0]
        assert "uid" in item
        assert "metadata" in item
        assert "trend_metrics" in item
        assert isinstance(item["uid"], str)
        assert len(item["uid"]) == 64  # SHA256 hex

    def test_trend_metrics_structure(self, client: TestClient):
        """trend_metrics must contain all required Data Contract fields."""
        resp = client.get("/api/v1/trend/hot?limit=1")
        tm = resp.json()["items"][0]["trend_metrics"]
        assert "heat_score" in tm
        assert "rank" in tm
        assert "rank_change" in tm
        assert "tags" in tm
        assert "trend_direction" in tm
        assert "history_7d" in tm
        assert isinstance(tm["heat_score"], float)
        assert isinstance(tm["rank"], int)
        assert isinstance(tm["rank_change"], int)
        assert isinstance(tm["tags"], list)
        assert isinstance(tm["trend_direction"], str)
        assert isinstance(tm["history_7d"], list)

    def test_history_7d_has_seven_entries(self, client: TestClient):
        resp = client.get("/api/v1/trend/hot?limit=1")
        history = resp.json()["items"][0]["trend_metrics"]["history_7d"]
        assert len(history) == 7
        for entry in history:
            assert "date" in entry
            assert "heat_score" in entry

    def test_items_are_in_rank_order(self, client: TestClient):
        """Items should be returned in the mock list order."""
        resp = client.get("/api/v1/trend/hot")
        items = resp.json()["items"]
        ranks = [item["trend_metrics"]["rank"] for item in items]
        assert ranks == sorted(ranks)  # already sorted ascending

    def test_trend_direction_is_valid(self, client: TestClient):
        resp = client.get("/api/v1/trend/hot")
        for item in resp.json()["items"]:
            assert item["trend_metrics"]["trend_direction"] in (
                "rising", "declining", "stable"
            )


# ===================================================================
# GET /api/v1/trend/detail/{uid}
# ===================================================================


class TestDetailEndpoint:
    def test_returns_existing_novel(self, client: TestClient):
        resp = client.get(f"/api/v1/trend/detail/{SAMPLE_UID}")
        assert resp.status_code == 200

    def test_response_structure_contract(self, client: TestClient):
        """Verify Data Contract v1.0 shape for detail."""
        resp = client.get(f"/api/v1/trend/detail/{SAMPLE_UID}")
        body = resp.json()
        assert "uid" in body
        assert "metadata" in body
        assert "trend_metrics" in body

    def test_uid_matches_request(self, client: TestClient):
        resp = client.get(f"/api/v1/trend/detail/{SAMPLE_UID}")
        assert resp.json()["uid"] == SAMPLE_UID

    def test_metadata_has_title_and_platform(self, client: TestClient):
        resp = client.get(f"/api/v1/trend/detail/{SAMPLE_UID}")
        meta = resp.json()["metadata"]
        assert "title" in meta
        assert "platform" in meta
        assert "last_update" in meta
        assert meta["title"] == "诡秘之主"

    def test_trend_metrics_all_fields(self, client: TestClient):
        resp = client.get(f"/api/v1/trend/detail/{SAMPLE_UID}")
        tm = resp.json()["trend_metrics"]
        assert "heat_score" in tm
        assert "rank" in tm
        assert "rank_change" in tm
        assert "tags" in tm
        assert "trend_direction" in tm
        assert "history_7d" in tm

    def test_non_existent_uid_returns_404(self, client: TestClient):
        fake_uid = "0" * 64
        resp = client.get(f"/api/v1/trend/detail/{fake_uid}")
        assert resp.status_code == 404

    def test_404_detail_message(self, client: TestClient):
        fake_uid = "0" * 64
        resp = client.get(f"/api/v1/trend/detail/{fake_uid}")
        body = resp.json()
        assert "detail" in body
        assert fake_uid in body["detail"]

    def test_empty_uid_returns_404(self, client: TestClient):
        resp = client.get("/api/v1/trend/detail/")
        # FastAPI will not match the route; expect 404 (or 405)
        assert resp.status_code in (404, 405)

    def test_different_novel_has_different_uid(self, client: TestClient):
        doupo_uid = "5ee58c6e2a50c7b194ab73eaf787590384344a765ff1b682ec15d962daae2dee"
        resp = client.get(f"/api/v1/trend/detail/{doupo_uid}")
        assert resp.status_code == 200
        assert resp.json()["metadata"]["title"] == "斗破苍穹"

    def test_all_novels_accessible_by_uid(self, client: TestClient):
        resp = client.get("/api/v1/trend/hot")
        for item in resp.json()["items"]:
            uid = item["uid"]
            detail_resp = client.get(f"/api/v1/trend/detail/{uid}")
            assert detail_resp.status_code == 200
            assert detail_resp.json()["uid"] == uid


# ===================================================================
# GET /api/v1/trend/tags/evolution
# ===================================================================


class TestTagsEvolutionEndpoint:
    def test_returns_for_known_tag(self, client: TestClient):
        resp = client.get("/api/v1/trend/tags/evolution?tag=克苏鲁")
        assert resp.status_code == 200

    def test_response_contains_expected_fields(self, client: TestClient):
        resp = client.get("/api/v1/trend/tags/evolution?tag=克苏鲁")
        body = resp.json()
        assert "tag" in body
        assert "period" in body
        assert "evolution" in body
        assert "trend" in body
        assert "related_works" in body

    def test_tag_value_matches_request(self, client: TestClient):
        resp = client.get("/api/v1/trend/tags/evolution?tag=克苏鲁")
        assert resp.json()["tag"] == "克苏鲁"

    def test_default_period_is_30d(self, client: TestClient):
        resp = client.get("/api/v1/trend/tags/evolution?tag=克苏鲁")
        assert resp.json()["period"] == "30d"

    def test_evolution_has_periods(self, client: TestClient):
        resp = client.get("/api/v1/trend/tags/evolution?tag=克苏鲁")
        evo = resp.json()["evolution"]
        assert len(evo) > 0
        for entry in evo:
            assert "date" in entry
            assert "heat" in entry
            assert "label" in entry

    def test_period_7d_limits_to_fewer_entries(self, client: TestClient):
        resp_30d = client.get("/api/v1/trend/tags/evolution?tag=克苏鲁")
        resp_7d = client.get("/api/v1/trend/tags/evolution?tag=克苏鲁&period=7d")
        # 7d should return fewer evolution entries than 30d
        assert len(resp_7d.json()["evolution"]) < len(resp_30d.json()["evolution"])

    def test_period_7d_returns_two_entries(self, client: TestClient):
        resp = client.get("/api/v1/trend/tags/evolution?tag=克苏鲁&period=7d")
        assert len(resp.json()["evolution"]) == 2

    def test_trend_is_valid_string(self, client: TestClient):
        resp = client.get("/api/v1/trend/tags/evolution?tag=克苏鲁")
        assert resp.json()["trend"] in ("rising", "declining", "stable")

    def test_related_works_has_five_items(self, client: TestClient):
        resp = client.get("/api/v1/trend/tags/evolution?tag=克苏鲁")
        works = resp.json()["related_works"]
        assert len(works) == 5
        for work in works:
            assert "title" in work
            assert "heat" in work

    def test_non_existent_tag_returns_404(self, client: TestClient):
        resp = client.get("/api/v1/trend/tags/evolution?tag=NONEXISTENT")
        assert resp.status_code == 404

    def test_404_detail_message(self, client: TestClient):
        resp = client.get("/api/v1/trend/tags/evolution?tag=NONEXISTENT")
        assert "NONEXISTENT" in resp.json()["detail"]

    def test_tag_system_flow_rising_trend(self, client: TestClient):
        """系统流 is declining in the mock data; verify that."""
        resp = client.get("/api/v1/trend/tags/evolution?tag=系统流")
        assert resp.status_code == 200
        assert resp.json()["trend"] == "declining"

    def test_tag_missing_period_param_is_rejected(self, client: TestClient):
        resp = client.get("/api/v1/trend/tags/evolution")
        assert resp.status_code == 422  # tag is required

    def test_unknown_period_uses_default(self, client: TestClient):
        resp = client.get("/api/v1/trend/tags/evolution?tag=克苏鲁&period=999d")
        assert resp.status_code == 200
        # Falls back to default behaviour (5 entries for unrecognized period)
        assert len(resp.json()["evolution"]) == 5


# ===================================================================
# Cross-module consistency
# ===================================================================


class TestCrossModuleConsistency:
    """Ensure hot-list items match their detail endpoints."""

    def test_hot_item_uid_resolves_in_detail(self, client: TestClient):
        hot_resp = client.get("/api/v1/trend/hot?limit=1")
        hot_item = hot_resp.json()["items"][0]

        detail_resp = client.get(f"/api/v1/trend/detail/{hot_item['uid']}")
        detail = detail_resp.json()

        assert detail["metadata"]["title"] == hot_item["metadata"]["title"]
        assert detail["trend_metrics"]["rank"] == hot_item["trend_metrics"]["rank"]

    def test_all_hot_uids_are_valid_sha256(self, client: TestClient):
        resp = client.get("/api/v1/trend/hot")
        for item in resp.json()["items"]:
            uid = item["uid"]
            assert len(uid) == 64
            int(uid, 16)  # raises ValueError if not hex
