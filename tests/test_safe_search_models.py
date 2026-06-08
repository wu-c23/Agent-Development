"""Tests for safe_search.models — Book and IntentResult dataclasses."""

import sys
from datetime import datetime, timezone
from unittest.mock import ANY, MagicMock

# Pre-register modules that engine.py depends on but aren't relevant to
# these tests. This avoids ImportError during safe_search package init.
sys.modules["sentiment_critic"] = MagicMock()
sys.modules["sentiment_critic.critic"] = MagicMock()

from safe_search.models import Book, IntentResult
from safe_search.uid_utils import generate_uid


# ---------------------------------------------------------------------------
# Book
# ---------------------------------------------------------------------------

class TestBookAutoUid:
    """Coverage: UID auto-generation when id is empty."""

    def test_auto_generates_uid(self) -> None:
        """Book without explicit id generates UID from platform_id + title."""
        book = Book(
            title="诡秘之主", intro="", platform_id="qidian:123456"
        )
        expected_uid = generate_uid("qidian:123456", "诡秘之主")
        assert book.id == expected_uid
        assert len(book.id) == 64

    def test_with_explicit_id_keeps_id(self) -> None:
        """When id is provided, it must not be overwritten."""
        book = Book(
            title="诡秘之主",
            intro="",
            platform_id="qidian:123456",
            id="my-custom-id",
        )
        assert book.id == "my-custom-id"

    def test_explicit_id_does_not_depend_on_platform_id(self) -> None:
        """Providing id explicitly bypasses platform_id + title entirely."""
        book = Book(title="Any", intro="", platform_id="whatever", id="explicit")
        assert book.id == "explicit"

    def test_empty_platform_id_uses_platform_and_title(self) -> None:
        """When platform_id is empty, UID is generated from platform:title."""
        book = Book(
            title="凡人修仙传", intro="", platform="zongheng", platform_id=""
        )
        expected_uid = generate_uid("zongheng:凡人修仙传", "凡人修仙传")
        assert book.id == expected_uid

    def test_default_platform_unknown(self) -> None:
        """If no platform is given, it defaults to 'unknown'."""
        book = Book(title="Test", intro="", platform_id="")
        expected_uid = generate_uid("unknown:Test", "Test")
        assert book.id == expected_uid
        assert book.platform == "unknown"

    def test_empty_title_and_platform_id(self) -> None:
        """Edge case: both title and platform_id empty."""
        book = Book(title="", intro="", platform_id="")
        expected_uid = generate_uid("unknown:", "")
        assert book.id == expected_uid

    def test_title_whitespace_stripped_in_uid(self) -> None:
        """Book delegates whitespace stripping to generate_uid()."""
        book = Book(title="  雪中悍刀行  ", intro="", platform_id="zongheng:42")
        expected_uid = generate_uid("zongheng:42", "  雪中悍刀行  ")
        assert book.id == expected_uid
        # The UID matches the unstripped version since generate_uid strips
        assert book.id == generate_uid("zongheng:42", "雪中悍刀行")


class TestBookMetadata:
    """Coverage: .metadata property."""

    def test_metadata_contains_required_keys(self) -> None:
        """Metadata dict has title, platform, last_update."""
        book = Book(title="盗墓笔记", intro="", platform="douban")
        meta = book.metadata
        assert "title" in meta
        assert "platform" in meta
        assert "last_update" in meta

    def test_metadata_values(self) -> None:
        """Metadata values match the book's attributes."""
        book = Book(title="庆余年", intro="", platform="qidian")
        meta = book.metadata
        assert meta["title"] == "庆余年"
        assert meta["platform"] == "qidian"

    def test_metadata_last_update_is_isoformat(self) -> None:
        """last_update is a valid ISO-format datetime string."""
        book = Book(title="Test", intro="", platform="test")
        meta = book.metadata
        parsed = datetime.fromisoformat(meta["last_update"])
        assert parsed.tzinfo is not None

    def test_metadata_returns_new_dict_each_call(self) -> None:
        """Each call to .metadata returns a fresh dict."""
        book = Book(title="Test", intro="", platform="test")
        m1 = book.metadata
        m2 = book.metadata
        assert m1 is not m2


class TestBookDefaults:
    """Coverage: default field values."""

    def test_intro_is_required(self) -> None:
        """intro has no default and must be provided."""
        book = Book(title="Test", intro="some intro", platform_id="p:1")
        assert book.intro == "some intro"

    def test_tags_defaults_to_empty_list(self) -> None:
        book = Book(title="Test", intro="", platform_id="p:1")
        assert book.tags == []

    def test_author_defaults_to_empty(self) -> None:
        book = Book(title="Test", intro="", platform_id="p:1")
        assert book.author == ""

    def test_status_defaults_to_none(self) -> None:
        book = Book(title="Test", intro="", platform_id="p:1")
        assert book.status is None

    def test_sentiment_summary_defaults_to_none(self) -> None:
        book = Book(title="Test", intro="", platform_id="p:1")
        assert book.sentiment_summary is None

    def test_all_optional_fields_can_be_set(self) -> None:
        book = Book(
            title="Test",
            platform_id="p:1",
            intro="Great story",
            tags=["fantasy", "adventure"],
            author="Author Name",
            status="completed",
            sentiment_summary="Positive",
        )
        assert book.intro == "Great story"
        assert book.tags == ["fantasy", "adventure"]
        assert book.author == "Author Name"
        assert book.status == "completed"
        assert book.sentiment_summary == "Positive"

    def test_tags_is_independent_copy(self) -> None:
        """Default factory ensures each Book gets its own list."""
        book_a = Book(title="A", intro="", platform_id="p:1")
        book_b = Book(title="B", intro="", platform_id="p:2")
        book_a.tags.append("x")
        assert "x" in book_a.tags
        assert "x" not in book_b.tags


class TestBookRoundTrip:
    """Verify that Book fields survive creation and access."""

    def test_repr(self) -> None:
        """Book has a useful repr (inherited from dataclass)."""
        book = Book(title="测试", intro="some intro", platform_id="p:1")
        r = repr(book)
        assert "Book(" in r
        assert "测试" in r

    def test_equality(self) -> None:
        """Two Books with same fields are equal (dataclass default)."""
        b1 = Book(title="Same", intro="", platform_id="p:1")
        b2 = Book(title="Same", intro="", platform_id="p:1")
        assert b1 == b2

    def test_inequality(self) -> None:
        """Books with different fields are not equal."""
        b1 = Book(title="A", intro="", platform_id="p:1")
        b2 = Book(title="B", intro="", platform_id="p:1")
        assert b1 != b2


# ---------------------------------------------------------------------------
# IntentResult
# ---------------------------------------------------------------------------

class TestIntentResultDefaults:
    """Coverage: IntentResult has empty defaults for every field."""

    def test_summary_defaults_to_empty_string(self) -> None:
        result = IntentResult()
        assert result.summary == ""

    def test_topics_defaults_to_empty_list(self) -> None:
        result = IntentResult()
        assert result.topics == []

    def test_style_defaults_to_empty_list(self) -> None:
        result = IntentResult()
        assert result.style == []

    def test_protagonist_traits_defaults_to_empty_list(self) -> None:
        result = IntentResult()
        assert result.protagonist_traits == []

    def test_mood_defaults_to_empty_list(self) -> None:
        result = IntentResult()
        assert result.mood == []

    def test_constraints_defaults_to_empty_list(self) -> None:
        result = IntentResult()
        assert result.constraints == []


class TestIntentResultPopulated:
    """Coverage: IntentResult with all fields populated."""

    def test_all_fields_set(self) -> None:
        result = IntentResult(
            summary="A thrilling adventure",
            topics=["magic", "cultivation"],
            style=["descriptive", "fast-paced"],
            protagonist_traits=["brave", "curious"],
            mood=["suspenseful"],
            constraints=["no gore"],
        )
        assert result.summary == "A thrilling adventure"
        assert result.topics == ["magic", "cultivation"]
        assert result.style == ["descriptive", "fast-paced"]
        assert result.protagonist_traits == ["brave", "curious"]
        assert result.mood == ["suspenseful"]
        assert result.constraints == ["no gore"]

    def test_partial_fields(self) -> None:
        """Only providing some fields leaves others as defaults."""
        result = IntentResult(summary="Only summary")
        assert result.summary == "Only summary"
        assert result.topics == []
        assert result.style == []
        assert result.protagonist_traits == []
        assert result.mood == []
        assert result.constraints == []

    def test_list_independence(self) -> None:
        """Each list field has its own identity (default factory)."""
        r1 = IntentResult()
        r2 = IntentResult()
        r1.topics.append("unique")
        assert "unique" in r1.topics
        assert "unique" not in r2.topics

    def test_equality(self) -> None:
        """Two IntentResults with same values are equal."""
        r1 = IntentResult(summary="S")
        r2 = IntentResult(summary="S")
        assert r1 == r2

    def test_inequality(self) -> None:
        r1 = IntentResult(summary="A")
        r2 = IntentResult(summary="B")
        assert r1 != r2
