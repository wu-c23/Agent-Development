"""Tests for sentiment_critic.collectors — platform-agnostic helpers and
the extended collect_reviews function.

The shared functionality (ReviewHTMLParser, infer_platform, extract_reviews)
is tested implicitly through collect_reviews.  This file focuses on the
additional logic specific to the Sentiment Critic version:
  - balanced_limit_reviews — distributes a cap across platforms
  - collect_reviews with input_html — offline HTML parsing path
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

from unittest.mock import MagicMock, patch
from unittest.mock import MagicMock, patch

import pytest

from sentiment_critic.collectors import balanced_limit_reviews, collect_reviews
from sentiment_critic.models import Review


# ===================================================================
# balanced_limit_reviews
# ===================================================================


class TestBalancedLimitReviews:
    """balanced_limit_reviews distributes a cap evenly across platforms."""

    def _review(self, platform: str, content: str | None = None) -> Review:
        return Review(
            book="test",
            platform=platform,
            content=content or f"test review from {platform}",
        )

    def test_round_robin_across_platforms(self) -> None:
        """With 3 platforms and a limit of 3, one from each platform."""
        reviews = [
            self._review("douban"),
            self._review("douban"),
            self._review("tieba"),
            self._review("tieba"),
            self._review("xiaohongshu"),
        ]
        result = balanced_limit_reviews(reviews, 3)
        assert len(result) == 3
        platforms = [r.platform for r in result]
        assert "douban" in platforms
        assert "tieba" in platforms
        assert "xiaohongshu" in platforms

    def test_single_platform(self) -> None:
        """When all reviews come from one platform, a simple slice is taken."""
        reviews = [self._review("douban") for _ in range(5)]
        result = balanced_limit_reviews(reviews, 3)
        assert len(result) == 3
        assert all(r.platform == "douban" for r in result)

    def test_empty_list(self) -> None:
        assert balanced_limit_reviews([], 5) == []

    def test_limit_greater_than_list(self) -> None:
        """If limit exceeds the list length, the whole list is returned."""
        reviews = [self._review("douban"), self._review("tieba")]
        result = balanced_limit_reviews(reviews, 100)
        assert len(result) == 2

    def test_limit_zero(self) -> None:
        """Limit of 0 returns the whole list (early return)."""
        reviews = [self._review("douban")]
        result = balanced_limit_reviews(reviews, 0)
        assert len(result) == 1

    def test_preserves_order_within_platform(self) -> None:
        """Items from each platform keep their original relative order."""
        reviews = [
            self._review("douban", "first"),
            self._review("douban", "second"),
            self._review("tieba", "third"),
            self._review("tieba", "fourth"),
        ]
        result = balanced_limit_reviews(reviews, 3)
        assert len(result) == 3
        # douban should contribute at most the earlier items first
        douban_items = [r for r in result if r.platform == "douban"]
        assert len(douban_items) <= 2

    def test_uneven_distribution(self) -> None:
        """When limit is small, platforms get roughly equal share."""
        reviews = (
            [self._review("douban") for _ in range(10)]
            + [self._review("tieba") for _ in range(2)]
        )
        result = balanced_limit_reviews(reviews, 5)
        assert len(result) == 5
        # With round-robin, douban gets 3, tieba gets 2
        from collections import Counter

        counts = Counter(r.platform for r in result)
        assert counts["douban"] >= 2
        assert counts["tieba"] >= 1


# ===================================================================
# collect_reviews — input_html path (offline, no network calls)
# ===================================================================


class TestCollectReviewsWithInputHtml:
    """collect_reviews with ``input_html`` processes local HTML files through
    the generic parser without needing platform-specific crawlers."""

    LONG_REVIEW_TEXT = (
        "文笔细腻，推荐好看，逻辑严密，伏笔回收，角色鲜活，"
        "设定亮眼，世界观宏大，节奏紧凑，更新稳定，"
        "非常值得入坑，整体水平很高，强烈推荐这部小说，"
        "非常好看，值得一读，入坑不亏。"
    )

    @pytest.fixture
    def html_file(self, tmp_path: Path) -> Path:
        """A plain HTML page with a review-like paragraph."""
        f = tmp_path / "test_douban.html"
        f.write_text(
            "<html><body>"
            f"<p>{self.LONG_REVIEW_TEXT}</p>"
            "</body></html>",
            encoding="utf-8",
        )
        return f

    def test_collect_from_html_returns_reviews(self, html_file: Path) -> None:
        """Reading a local HTML file yields at least one Review."""
        results = collect_reviews(
            book="test_book",
            input_html=[str(html_file)],
        )
        assert len(results) >= 1
        r = results[0]
        assert r.book == "test_book"
        assert r.platform == "manual"
        assert "文笔" in r.content

    def test_collect_from_html_uses_source_url(self, html_file: Path) -> None:
        results = collect_reviews(
            book="test_book",
            input_html=[str(html_file)],
        )
        r = results[0]
        assert str(html_file) in r.source_url

    def test_collect_from_html_respects_limit(self, html_file: Path) -> None:
        results = collect_reviews(
            book="test_book",
            input_html=[str(html_file)],
            limit=1,
        )
        assert len(results) <= 1

    def test_collect_no_inputs_returns_empty(self) -> None:
        """With no inputs at all, collect_reviews returns []."""
        results = collect_reviews(book="test_book")
        assert results == []

    def test_collect_multiple_html_files(self, tmp_path: Path) -> None:
        """Multiple HTML files contribute reviews independently."""
        text1 = (
            "文笔细腻，推荐好看，逻辑严密，伏笔回收，角色鲜活，"
            "设定亮眼，世界观宏大，节奏紧凑，更新稳定，"
            "非常值得入坑，整体水平很高，强烈推荐这部小说，"
            "非常好看，值得一读，入坑不亏。"
        )
        text2 = (
            "逻辑严密，设定新颖，角色鲜活生动，文笔流畅自然，"
            "节奏紧凑不拖沓，更新稳定，伏笔巧妙，世界观宏大，"
            "非常好看的良心之作，值得推荐，入坑不亏，推荐阅读。"
        )
        f1 = tmp_path / "page1_douban.html"
        f1.write_text(
            f"<html><body><p>{text1}</p></body></html>",
            encoding="utf-8",
        )
        f2 = tmp_path / "page2_douban.html"
        f2.write_text(
            f"<html><body><p>{text2}</p></body></html>",
            encoding="utf-8",
        )
        results = collect_reviews(
            book="test_book",
            input_html=[str(f1), str(f2)],
        )
        assert len(results) >= 2


# ===================================================================
# collect_reviews — error handling
# ===================================================================


class TestCollectReviewsErrors:
    def test_nonexistent_html_file_raises(self) -> None:
        """A non-existent input_html path raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            collect_reviews(
                book="test",
                input_html=["/nonexistent/path.html"],
            )


# ===================================================================
# Data integrity
# ===================================================================


class TestModuleStructure:
    def test_balanced_limit_returns_list(self) -> None:
        """balanced_limit_reviews always returns a list."""
        assert isinstance(balanced_limit_reviews([], 5), list)
        assert isinstance(balanced_limit_reviews(
            [Review(book="a", platform="d", content="x")], 1
        ), list)
