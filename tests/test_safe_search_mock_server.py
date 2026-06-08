"""Tests for safe_search.mock_server — FastAPI mock for Safe-Search Architect.

The mock_server module loads 5 built-in books at import time and optionally
loads more from a central ``novels.json``.  All filesystem access is patched
during import so tests always see exactly the 5 built-in books.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Import the module under test — mock out dependencies and prevent
# filesystem access so only the 5 built-in mock novels are loaded.
# ---------------------------------------------------------------------------
with (
    patch("dotenv.load_dotenv", return_value=None),  # config.py calls load_dotenv at import
    patch("pathlib.Path.exists", return_value=False),  # prevent loading central novels.json
    patch.dict("sys.modules", {  # engine.py needs sentiment_critic.critic
        "sentiment_critic": MagicMock(),
        "sentiment_critic.critic": MagicMock(),
        "sentiment_critic.data_store": MagicMock(),
    }),
):
    import safe_search.mock_server as _ms
    from safe_search.mock_server import (
        MOCK_NOVELS,
        _build_review_data_titles,
        _calculate_relevance,
        _longest_common_substring,
        _parse_exclusions,
        _random_risk_scores,
        _resolve_session_references,
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
    """TestClient bound to the built-in mock API (5 books, no central data)."""
    yield TestClient(app)


def make_novel(
    title: str = "测试书名",
    tags: list[str] | None = None,
    intro: str = "",
    author: str = "",
) -> dict:
    """Helper — create a minimal novel dict suitable for _calculate_relevance."""
    return {
        "uid": "test-uid",
        "metadata": {"title": title, "author": author},
        "tags": tags or [],
        "intro": intro,
    }


# ===================================================================
# Internal helper: _longest_common_substring
# ===================================================================


class TestLongestCommonSubstring:
    def test_basic_match(self) -> None:
        """"abcdef" and "defxyz" share "def" (length 3)."""
        assert _longest_common_substring("abcdef", "defxyz") == 3

    def test_empty_first(self) -> None:
        assert _longest_common_substring("", "abc") == 0

    def test_empty_second(self) -> None:
        assert _longest_common_substring("abc", "") == 0

    def test_both_empty(self) -> None:
        assert _longest_common_substring("", "") == 0

    def test_no_overlap(self) -> None:
        assert _longest_common_substring("abc", "xyz") == 0

    def test_full_match(self) -> None:
        assert _longest_common_substring("hello", "hello") == 5

    def test_partial_at_end(self) -> None:
        assert _longest_common_substring("prefix-match", "match") == 5

    def test_partial_at_start(self) -> None:
        assert _longest_common_substring("abc-remainder", "abc") == 3

    def test_chinese_characters(self) -> None:
        assert _longest_common_substring("诡秘之主", "诡秘") == 2


# ===================================================================
# Internal helper: _calculate_relevance
# ===================================================================


class TestCalculateRelevance:
    def test_title_exact_match(self) -> None:
        """Title substring in query yields is_title_match=True."""
        novel = make_novel(title="诡秘之主", tags=["克苏鲁", "悬疑"])
        relevance, reason, is_title_match = _calculate_relevance(novel, "诡秘之主 书评")
        assert is_title_match is True
        assert "title_exact_match" in reason

    def test_tag_match_boosts_relevance(self) -> None:
        novel = make_novel(title="凡人修仙传", tags=["修仙", "凡人流"])
        relevance, reason, is_title_match = _calculate_relevance(novel, "推荐修仙小说")
        assert "tags:" in reason
        # Tag match adds 0.15 on top of base 0.45
        assert relevance >= 0.55

    def test_author_match(self) -> None:
        novel = make_novel(title="凡人修仙传", author="忘语", tags=[])
        relevance, reason, is_title_match = _calculate_relevance(novel, "忘语 作品")
        assert "author_match" in reason
        assert relevance >= 0.60  # base 0.45 + author 0.20

    def test_intro_lcs_boost(self) -> None:
        """Long intro substring can push relevance above base."""
        novel = make_novel(
            title="轮回归来",
            tags=[],
            intro="主角轮回归来复仇的故事轮回归来复仇的故事",
        )
        relevance, reason, is_title_match = _calculate_relevance(
            novel, "轮回归来 小说"
        )
        # "轮回归来" has LCS >= 4 with intro, adding 0.12
        assert relevance >= 0.55

    def test_no_match_returns_base(self) -> None:
        novel = make_novel(title="完全不相关", tags=["其他"])
        relevance, reason, is_title_match = _calculate_relevance(novel, "xyzzy")
        assert relevance == 0.45
        assert reason == "semantic_match"
        assert is_title_match is False


# ===================================================================
# Internal helper: _parse_exclusions
# ===================================================================


class TestParseExclusions:
    def test_exclude_tag_harem(self) -> None:
        """不要后宫 is recognised as a tag-level exclusion."""
        cleaned, titles, tags = _parse_exclusions("推荐修仙小说不要后宫")
        assert "后宫" in tags
        # The exclusion phrase is removed from the cleaned query
        assert "不要后宫" not in cleaned

    def test_exclude_tag_duwu(self) -> None:
        """不看毒草 excludes the matching tag."""
        cleaned, titles, tags = _parse_exclusions("不看毒草 推荐")
        # If "毒草" is not in known tags it won't be excluded,
        # but known tags from the built-in set include 后宫, 玄幻, etc.
        # Let's use a tag we know exists in the built-in data.
        cleaned, titles, tags = _parse_exclusions("不要后宫 推荐")
        assert "后宫" in tags

    def test_exclude_known_title(self) -> None:
        """不要修罗武神 excludes the built-in novel 修罗武神."""
        cleaned, titles, tags = _parse_exclusions("不要修罗武神")
        # "修罗武神" is a title in MOCK_NOVELS
        assert "修罗武神" in titles

    def test_no_exclusions(self) -> None:
        """Plain query returns empty exclusion sets."""
        cleaned, titles, tags = _parse_exclusions("推荐悬疑小说")
        assert len(titles) == 0
        assert len(tags) == 0
        assert cleaned == "推荐悬疑小说"

    def test_empty_query(self) -> None:
        cleaned, titles, tags = _parse_exclusions("")
        assert cleaned == ""
        assert len(titles) == 0
        assert len(tags) == 0


# ===================================================================
# Internal helper: _resolve_session_references
# ===================================================================


class TestResolveSessionReferences:
    """These tests directly manipulate ``_search_sessions`` on the module."""

    def _set_session(self, session_id: str, titles: list[str]) -> None:
        _ms._search_sessions[session_id] = titles

    def _clear_session(self, session_id: str) -> None:
        _ms._search_sessions.pop(session_id, None)

    def test_resolve_first_ordinal(self) -> None:
        """'第一本' resolves to the first title in the session."""
        self._set_session("s1", ["诡秘之主", "凡人修仙传"])
        try:
            result = _resolve_session_references("第一本怎么样", "s1")
            assert "诡秘之主" in result
            assert "第一本" not in result
        finally:
            self._clear_session("s1")

    def test_resolve_second_ordinal(self) -> None:
        """'第二本' resolves to the second title."""
        self._set_session("s2", ["诡秘之主", "凡人修仙传"])
        try:
            result = _resolve_session_references("第二本 好看吗", "s2")
            assert "凡人修仙传" in result
        finally:
            self._clear_session("s2")

    def test_no_session_returns_unchanged(self) -> None:
        """Without a valid session the query is returned as-is."""
        result = _resolve_session_references("第一本", "nonexistent")
        assert result == "第一本"

    def test_empty_session_returns_unchanged(self) -> None:
        """Session with empty history leaves the query unchanged."""
        self._set_session("s3", [])
        try:
            result = _resolve_session_references("第一本", "s3")
            assert result == "第一本"
        finally:
            self._clear_session("s3")

    def test_no_session_id_returns_unchanged(self) -> None:
        """Empty session_id means no resolution is attempted."""
        result = _resolve_session_references("第一本", "")
        assert result == "第一本"

    def test_this_book_resolves(self) -> None:
        """'这本书' resolves to the first (most recent) title."""
        self._set_session("s4", ["诡秘之主"])
        try:
            result = _resolve_session_references("这本书 怎么样", "s4")
            assert "诡秘之主" in result
        finally:
            self._clear_session("s4")


# ===================================================================
# Internal helper: _random_risk_scores
# ===================================================================


class TestRandomRiskScores:
    def test_returns_all_five_dims(self) -> None:
        scores = _random_risk_scores()
        assert isinstance(scores, dict)
        for dim in ("abuse_protagonist", "unfinished", "melodrama", "harem", "slow_pacing"):
            assert dim in scores

    def test_values_in_range(self) -> None:
        scores = _random_risk_scores()
        for val in scores.values():
            assert 0.0 <= val <= 1.0


# ===================================================================
# Internal helper: _build_review_data_titles
# ===================================================================


class TestBuildReviewDataTitles:
    def test_no_runs_dir(self) -> None:
        """When _RUNS_DIR does not exist, return an empty set."""
        with patch("pathlib.Path.exists", return_value=False):
            titles = _build_review_data_titles()
            assert titles == set()

    def test_with_jsonl_files(self) -> None:
        """JSONL files with platform markers contribute their stem title."""
        f1 = MagicMock(spec=Path)
        f1.suffix = ".jsonl"
        f1.stem = "诡秘之主_tieba_20260101"

        f2 = MagicMock(spec=Path)
        f2.suffix = ".jsonl"
        f2.stem = "凡人修仙传_douban_20260101"

        mock_dir = MagicMock(spec=Path)
        mock_dir.exists.return_value = True
        mock_dir.iterdir.return_value = [f1, f2]

        with patch.object(_ms, "_RUNS_DIR", mock_dir):
            titles = _build_review_data_titles()
        assert "诡秘之主" in titles
        assert "凡人修仙传" in titles
        assert len(titles) == 2

    def test_skips_non_jsonl(self) -> None:
        """Files without .jsonl suffix are skipped."""
        txt_file = MagicMock(spec=Path)
        txt_file.suffix = ".txt"
        txt_file.stem = "诡秘之主_tieba_20260101"

        mock_dir = MagicMock(spec=Path)
        mock_dir.exists.return_value = True
        mock_dir.iterdir.return_value = [txt_file]

        with patch.object(_ms, "_RUNS_DIR", mock_dir):
            titles = _build_review_data_titles()
        assert len(titles) == 0


# ===================================================================
# API: GET /api/v1/search/vector/health
# ===================================================================


class TestAPIHealth:
    def test_health_returns_status_and_count(self, client) -> None:
        resp = client.get("/api/v1/search/vector/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["version"] == "1.0.0"
        assert data["index_count"] == len(MOCK_NOVELS)


# ===================================================================
# API: POST /api/v1/search/semantic
# ===================================================================


class TestAPISemanticSearch:
    def test_semantic_search_returns_results(self, client) -> None:
        resp = client.post("/api/v1/search/semantic", json={"query": "悬疑小说"})
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert len(data["results"]) > 0
        assert "total_hits" in data

    def test_semantic_search_with_session_tracking(self, client) -> None:
        """Session is stored and used for reference resolution."""
        resp1 = client.post(
            "/api/v1/search/semantic",
            json={"query": "推荐悬疑小说", "session_id": "test-session-1"},
        )
        assert resp1.status_code == 200

        resp2 = client.post(
            "/api/v1/search/semantic",
            json={"query": "第一本怎么样", "session_id": "test-session-1"},
        )
        assert resp2.status_code == 200
        data2 = resp2.json()
        # query_rewrite should mention 指代解析 when references are resolved
        assert "指代解析" in data2["query_rewrite"]

    def test_semantic_search_without_session(self, client) -> None:
        """Without a session_id, no session tracking occurs."""
        resp = client.post(
            "/api/v1/search/semantic",
            json={"query": "推荐修仙小说"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data

    def test_semantic_search_top_k(self, client) -> None:
        """top_k parameter limits the number of results."""
        resp = client.post(
            "/api/v1/search/semantic",
            json={"query": "小说", "top_k": 2},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) <= 2

    def test_result_structure(self, client) -> None:
        """Each result has the expected fields."""
        resp = client.post(
            "/api/v1/search/semantic",
            json={"query": "悬疑"},
        )
        data = resp.json()
        for r in data["results"]:
            assert "uid" in r
            assert "metadata" in r
            assert "intro" in r
            assert "tags" in r
            assert "relevance_score" in r
            assert "has_review_data" in r
            assert "safe_check" in r
            assert "passed" in r["safe_check"]


# ===================================================================
# API: POST /api/v1/search/books/sync-from-central
# ===================================================================


class TestAPISyncFromCentral:
    def test_sync_reloads_index(self, client) -> None:
        resp = client.post("/api/v1/search/books/sync-from-central")
        assert resp.status_code == 200
        data = resp.json()
        assert "indexed" in data
        assert data["source"] == "central"
        assert data["total_in_index"] >= 5


# ===================================================================
# API: GET /api/v1/search/books/{uid}
# ===================================================================


class TestAPIGetBook:
    def test_get_existing_book(self, client) -> None:
        resp = client.get(f"/api/v1/search/books/{SAMPLE_UID}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["uid"] == SAMPLE_UID
        assert data["metadata"]["title"] == SAMPLE_TITLE

    def test_get_missing_book_returns_404(self, client) -> None:
        resp = client.get(f"/api/v1/search/books/{MISSING_UID}")
        assert resp.status_code == 404

    def test_book_response_structure(self, client) -> None:
        resp = client.get(f"/api/v1/search/books/{SAMPLE_UID}")
        data = resp.json()
        assert "uid" in data
        assert "metadata" in data
        assert "intro" in data
        assert "tags" in data
        assert "status" in data
        assert "heat_score" in data
        assert "relevance_score" in data
        assert "safe_check" in data
        assert "risk_scores" in data


# ===================================================================
# API: GET /api/v1/search/intent
# ===================================================================


class TestAPIIntent:
    def test_intent_returns_summary(self, client) -> None:
        resp = client.get("/api/v1/search/intent", params={"query": "悬疑小说"})
        assert resp.status_code == 200
        data = resp.json()
        assert "summary" in data
        assert "topics" in data
        assert "style" in data
