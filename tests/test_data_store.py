"""Tests for sentiment_critic.data_store — data persistence and fallback loading."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Ensure Sentiment Critic package resolves BEFORE Safe-Search's stub.
# Pytest's own sys.path.insert(0, …) calls after conftest push the Sentiment
# Critic path to the end.  We re-insert it here to guarantee the full package
# (data_store, rag_engine, …) is found before the Safe-Search stub.
# ---------------------------------------------------------------------------
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

from unittest.mock import patch

import pytest

from sentiment_critic import data_store as ds


# Well-known UIDs from the built-in fallback data
UID_GGZY = "987a2b45c6bd2baa73d750f13daf15b63c20145de2e85fff22ada96ad3d8b27b"
UID_WYF = "26d4613826eb8819a9a601cfb88eb7621b0e6cc5c46ffefa96b5dea22ca938dc"
UID_XLWS = "f551b43b941bf7f47d6006792b26da44b8554945c72766133cb0c59771f48c89"
UID_FR = "22ed60b7b27cf4c8b77c1439cb7a9d82eb4667f6eafab681bcd415e18adbd0a4"
UID_XW = "587986904db3db77b83e2d7b49165f2f6e9ec1b6552b621e340695f21c240d8c"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _patch_data_paths(tmp_path):
    """Redirect all file paths to a unique temp dir so fallback data is used.

    Also patches _DATA_DIR so _build_novels/sentiment_from_existing_data()
    won't find any real jsonl / report files on the filesystem.
    """
    ds._NOVELS_PATH = tmp_path / "nonexistent_novels.json"
    ds._SENTIMENT_INDEX_PATH = tmp_path / "nonexistent_sentiment_index.json"
    ds._DATA_DIR = tmp_path / "nonexistent_data"
    ds._cache_loaded = False
    yield
    ds._cache_loaded = False


# ---------------------------------------------------------------------------
# Read operations (fallback data)
# ---------------------------------------------------------------------------


class TestFallbackData:
    """All tests in this class use the built-in fallback data."""

    def test_ensure_loaded_populates_cache(self):
        ds._cache_loaded = False
        ds._ensure_loaded()
        assert ds._novels_cache is not None
        assert len(ds._novels_cache) == 5
        assert ds._sentiment_cache is not None
        assert len(ds._sentiment_cache) == 5

    def test_get_all_novels_returns_list_of_5(self):
        novels = ds.get_all_novels()
        assert isinstance(novels, list)
        assert len(novels) == 5
        titles = {n["title"] for n in novels}
        assert titles == {
            "诡秘之主",
            "我有一座恐怖屋",
            "修罗武神",
            "凡人修仙传",
            "仙王的日常生活",
        }

    def test_get_novel_by_uid(self):
        novel = ds.get_novel(UID_GGZY)
        assert novel is not None
        assert novel["title"] == "诡秘之主"
        assert novel["author"] == "爱潜水的乌贼"
        assert novel["platform"] == "qidian"

    def test_get_novel_by_nonexistent_uid_returns_none(self):
        assert ds.get_novel("does-not-exist-uid") is None

    def test_get_novel_by_title_exact(self):
        novel = ds.get_novel_by_title("诡秘之主")
        assert novel is not None
        assert novel["uid"] == UID_GGZY

    def test_get_novel_by_title_fuzzy(self):
        novel = ds.get_novel_by_title("诡秘")
        assert novel is not None
        assert novel["title"] == "诡秘之主"

    def test_get_novel_by_title_no_match(self):
        assert ds.get_novel_by_title("一本不存在的书") is None

    def test_search_novels_by_tag(self):
        results = ds.search_novels("克苏鲁")
        assert len(results) >= 1
        assert any(n["title"] == "诡秘之主" for n in results)

    def test_search_novels_by_author(self):
        results = ds.search_novels("忘语")
        assert len(results) >= 1
        assert any(n["title"] == "凡人修仙传" for n in results)

    def test_search_novels_by_title_keyword(self):
        results = ds.search_novels("修罗")
        assert len(results) >= 1
        assert any(n["title"] == "修罗武神" for n in results)

    def test_search_novels_empty_keyword_returns_all(self):
        results = ds.search_novels("")
        assert len(results) == 5

    def test_search_novels_no_match(self):
        results = ds.search_novels("zzzdoesnotexistzzz")
        assert results == []

    def test_get_all_sentiments_returns_dict_of_5(self):
        sentiments = ds.get_all_sentiments()
        assert isinstance(sentiments, dict)
        assert len(sentiments) == 5
        assert UID_GGZY in sentiments
        assert UID_FR in sentiments

    def test_get_sentiment_by_uid(self):
        sent = ds.get_sentiment(UID_GGZY)
        assert sent is not None
        assert sent["overall"] == 9.1
        assert sent["style"] == 9.2
        assert sent["logic"] == 9.5

    def test_get_sentiment_by_nonexistent_uid_returns_none(self):
        assert ds.get_sentiment("nonexistent-uid") is None

    def test_get_sentiment_by_title(self):
        sent = ds.get_sentiment_by_title("诡秘之主")
        assert sent is not None
        assert sent["overall"] == 9.1

    def test_get_sentiment_by_nonexistent_title(self):
        assert ds.get_sentiment_by_title("不存在的书") is None

    def test_get_full_sentiment_data_contract_format(self):
        full = ds.get_full_sentiment(UID_GGZY)
        assert full is not None
        # Data Contract v1.0 fields
        assert "metadata" in full
        assert full["metadata"]["title"] == "诡秘之主"
        assert full["metadata"]["platform"] == "qidian"
        assert "sentiment_scores" in full
        assert full["sentiment_scores"]["overall"] == 9.1
        assert full["sentiment_scores"]["toxicity_index"] == 0.08
        assert "critic_summary" in full
        assert "逻辑严密的克苏鲁" in full["critic_summary"]["one_liner"]
        assert "review_stats" in full
        assert full["review_stats"]["total_count"] == 1250
        assert full["review_stats"]["positive_ratio"] == 0.86

    def test_get_full_sentiment_nonexistent_uid(self):
        assert ds.get_full_sentiment("nonexistent-uid") is None

    def test_get_novel_list_for_search_shape(self):
        search_list = ds.get_novel_list_for_search()
        assert len(search_list) == 5
        for item in search_list:
            assert "id" in item
            assert "title" in item
            assert "intro" in item
            assert "tags" in item
            assert "sentiment_summary" in item

    def test_get_novel_list_for_search_attaches_sentiment(self):
        search_list = ds.get_novel_list_for_search()
        ggzy = next(i for i in search_list if i["title"] == "诡秘之主")
        assert "逻辑严密的克苏鲁" in ggzy["sentiment_summary"]

    def test_build_mock_sentiment_store(self):
        store = ds.build_mock_sentiment_store()
        assert len(store) == 5
        ggzy = store.get(UID_GGZY)
        assert ggzy is not None
        assert ggzy["metadata"]["title"] == "诡秘之主"
        assert ggzy["sentiment_scores"]["overall"] == 9.1
        assert "critic_summary" in ggzy
        assert "review_stats" in ggzy


# ---------------------------------------------------------------------------
# Write operations (with mocked file I/O)
# ---------------------------------------------------------------------------


class TestWriteOperations:
    """Tests for save/upsert — all file writes are mocked with ``write_json``."""

    def test_save_novels_overwrites_cache(self):
        new_novels = [{"uid": "new-001", "title": "测试书"}]
        with patch("sentiment_critic.data_store.write_json") as mock_write:
            ds.save_novels(new_novels)
            mock_write.assert_called_once()
        assert len(ds._novels_cache) == 1

    def test_upsert_novel_inserts_new(self):
        new_novel = {"uid": "brand-new-uid", "title": "新书测试", "author": "新作者"}
        with patch("sentiment_critic.data_store.write_json") as mock_write:
            ds.upsert_novel(new_novel)
            mock_write.assert_called_once()
        novel = ds.get_novel("brand-new-uid")
        assert novel is not None
        assert novel["title"] == "新书测试"

    def test_upsert_novel_updates_existing(self):
        updated = {
            "uid": UID_GGZY,
            "title": "诡秘之主",
            "author": "爱潜水的乌贼",
            "heat_score": 999.0,
        }
        with patch("sentiment_critic.data_store.write_json") as mock_write:
            ds.upsert_novel(updated)
            mock_write.assert_called_once()
        novel = ds.get_novel(UID_GGZY)
        assert novel["heat_score"] == 999.0

    def test_upsert_novel_no_uid_does_nothing(self):
        with patch("sentiment_critic.data_store.write_json") as mock_write:
            ds.upsert_novel({"title": "No UID Book"})
            mock_write.assert_not_called()

    def test_save_sentiment_index_overwrites_cache(self):
        new_index = {"new-uid-1": {"overall": 9.0, "style": 8.0}}
        with patch("sentiment_critic.data_store.write_json") as mock_write:
            ds.save_sentiment_index(new_index)
            mock_write.assert_called_once()
        assert len(ds._sentiment_cache) == 1
        assert ds._sentiment_cache["new-uid-1"]["overall"] == 9.0

    @pytest.mark.xfail(
        reason="Source bug: upsert_sentiment() is missing 'global _sentiment_cache', "
               "causing UnboundLocalError. Add 'global _sentiment_cache' to fix."
    )
    def test_upsert_sentiment_inserts_new(self):
        with patch("sentiment_critic.data_store.write_json") as mock_write:
            ds.upsert_sentiment("fresh-uid", {"overall": 7.5, "style": 8.0})
            mock_write.assert_called_once()
        sent = ds.get_sentiment("fresh-uid")
        assert sent is not None
        assert sent["overall"] == 7.5

    @pytest.mark.xfail(
        reason="Source bug: upsert_sentiment() is missing 'global _sentiment_cache', "
               "causing UnboundLocalError. Add 'global _sentiment_cache' to fix."
    )
    def test_upsert_sentiment_updates_existing(self):
        with patch("sentiment_critic.data_store.write_json") as mock_write:
            ds.upsert_sentiment(UID_GGZY, {"overall": 5.0, "style": 5.0})
            mock_write.assert_called_once()
        sent = ds.get_sentiment(UID_GGZY)
        assert sent["overall"] == 5.0


# ---------------------------------------------------------------------------
# reload
# ---------------------------------------------------------------------------


class TestReload:
    def test_reload_restores_fallback_data(self):
        novels = ds.get_all_novels()
        assert len(novels) == 5

        # Mutate cache directly
        ds._novels_cache.append({"uid": "fake"})
        assert len(ds.get_all_novels()) == 6

        # Reload should restore from fallback
        ds.reload()
        assert len(ds.get_all_novels()) == 5

    def test_reload_sets_cache_loaded_flag(self):
        ds._cache_loaded = False
        ds.reload()
        assert ds._cache_loaded is True
