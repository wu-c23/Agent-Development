"""Tests for review_critic.models — dataclasses, helpers, file I/O."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime

import pytest

from review_critic import models as m


# ---------------------------------------------------------------------------
# normalize_space
# ---------------------------------------------------------------------------


class TestNormalizeSpace:
    def test_collapses_multiple_spaces(self):
        assert m.normalize_space("  hello   world  ") == "hello world"

    def test_collapses_tabs_and_newlines(self):
        assert m.normalize_space("hello\n\tworld") == "hello world"

    def test_empty_string(self):
        assert m.normalize_space("") == ""

    def test_only_whitespace(self):
        assert m.normalize_space("   ") == ""

    def test_no_change_needed(self):
        assert m.normalize_space("hello world") == "hello world"

    def test_none_returns_empty(self):
        assert m.normalize_space(None) == ""


# ---------------------------------------------------------------------------
# now_iso
# ---------------------------------------------------------------------------


class TestNowIso:
    def test_returns_iso_format_string(self):
        result = m.now_iso()
        assert isinstance(result, str)
        assert len(result) >= 19  # YYYY-MM-DDTHH:MM:SS
        assert "+" in result or result.endswith("Z") or "-" in result[10:]
        # Verify format roughly: 2026-06-07T12:34:56+08:00
        assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", result)


# ---------------------------------------------------------------------------
# stable_review_id
# ---------------------------------------------------------------------------


class TestStableReviewId:
    def test_deterministic(self):
        id1 = m.stable_review_id("douban", "http://a.com", "好书")
        id2 = m.stable_review_id("douban", "http://a.com", "好书")
        assert id1 == id2

    def test_has_platform_prefix(self):
        result = m.stable_review_id("douban", "http://a.com", "好书")
        assert result.startswith("douban-")

    def test_has_correct_hash_length(self):
        result = m.stable_review_id("tieba", "http://b.com", "不错的书")
        prefix, hex_part = result.split("-", 1)
        assert prefix == "tieba"
        assert len(hex_part) == 12
        assert all(c in "0123456789abcdef" for c in hex_part)

    def test_different_inputs_different_ids(self):
        id1 = m.stable_review_id("douban", "http://a.com", "好书")
        id2 = m.stable_review_id("douban", "http://a.com", "差书")
        assert id1 != id2

    def test_different_platforms_different_ids(self):
        id1 = m.stable_review_id("douban", "http://a.com", "好书")
        id2 = m.stable_review_id("tieba", "http://a.com", "好书")
        assert id1 != id2


# ---------------------------------------------------------------------------
# generate_uid
# ---------------------------------------------------------------------------


class TestGenerateUid:
    def test_returns_sha256_hex(self):
        uid = m.generate_uid("user123", "诡秘之主")
        assert len(uid) == 64  # SHA256 hex length
        assert all(c in "0123456789abcdef" for c in uid)

    def test_deterministic(self):
        uid1 = m.generate_uid("user123", "诡秘之主")
        uid2 = m.generate_uid("user123", "诡秘之主")
        assert uid1 == uid2

    def test_different_inputs_different(self):
        uid1 = m.generate_uid("user123", "诡秘之主")
        uid2 = m.generate_uid("user456", "诡秘之主")
        assert uid1 != uid2

    def test_title_is_stripped(self):
        uid1 = m.generate_uid("user123", "  诡秘之主  ")
        uid2 = m.generate_uid("user123", "诡秘之主")
        assert uid1 == uid2


# ---------------------------------------------------------------------------
# coerce_score
# ---------------------------------------------------------------------------


class TestCoerceScore:
    def test_normal_value(self):
        assert m.coerce_score(5.0, 0.0, 10.0, 5.0) == 5.0

    def test_clamps_lower(self):
        assert m.coerce_score(-5.0, 0.0, 10.0, 5.0) == 0.0

    def test_clamps_upper(self):
        assert m.coerce_score(15.0, 0.0, 10.0, 5.0) == 10.0

    def test_none_returns_default(self):
        assert m.coerce_score(None, 0.0, 10.0, 5.0) == 5.0

    def test_invalid_string_returns_default(self):
        assert m.coerce_score("not_a_number", -1.0, 1.0, 0.0) == 0.0

    def test_int_value(self):
        assert m.coerce_score(3, 0.0, 10.0, 5.0) == 3.0

    def test_rounds_to_two_decimals(self):
        assert m.coerce_score(3.456, 0.0, 10.0, 5.0) == 3.46

    def test_sentiment_score_range(self):
        assert m.coerce_score(0.5, -1.0, 1.0, 0.0) == 0.5
        assert m.coerce_score(-2.0, -1.0, 1.0, 0.0) == -1.0
        assert m.coerce_score(2.0, -1.0, 1.0, 0.0) == 1.0


# ---------------------------------------------------------------------------
# coerce_sentiment
# ---------------------------------------------------------------------------


class TestCoerceSentiment:
    def test_positive_strings(self):
        for val in ("positive", "pos", "好评", "正面"):
            assert m.coerce_sentiment(val) == "positive"

    def test_negative_strings(self):
        for val in ("negative", "neg", "差评", "负面"):
            assert m.coerce_sentiment(val) == "negative"

    def test_neutral_strings(self):
        for val in ("neutral", "中评", "一般", "unknown", ""):
            assert m.coerce_sentiment(val) == "neutral"

    def test_none_returns_neutral(self):
        assert m.coerce_sentiment(None) == "neutral"

    def test_case_insensitive(self):
        assert m.coerce_sentiment("POSITIVE") == "positive"
        assert m.coerce_sentiment("Neg") == "negative"


# ---------------------------------------------------------------------------
# Review dataclass
# ---------------------------------------------------------------------------


class TestReview:
    def test_constructor_normalizes_strings(self):
        review = m.Review(
            book="  诡秘之主  ",
            platform="  DOUBAN  ",
            content="  好书！\n推荐  ",
            title="  标题  ",
            author="  作者  ",
        )
        assert review.book == "诡秘之主"
        assert review.platform == "douban"
        assert review.content == "好书！ 推荐"
        assert review.title == "标题"
        assert review.author == "作者"

    def test_empty_platform_defaults_to_unknown(self):
        review = m.Review(book="test", platform="", content="test")
        assert review.platform == "unknown"

    def test_auto_generates_review_id(self):
        review = m.Review(
            book="test", platform="douban", content="好书推荐", source_url="http://example.com"
        )
        assert review.review_id
        assert review.review_id.startswith("douban-")
        assert len(review.review_id) == len("douban-") + 12

    def test_review_id_deterministic(self):
        r1 = m.Review(book="test", platform="douban", content="好书推荐", source_url="http://example.com")
        r2 = m.Review(book="test", platform="douban", content="好书推荐", source_url="http://example.com")
        assert r1.review_id == r2.review_id

    def test_preserves_explicit_review_id(self):
        review = m.Review(
            book="test", platform="douban", content="好书",
            review_id="custom-id-123",
        )
        assert review.review_id == "custom-id-123"

    def test_auto_generates_uid_when_platform_id_and_book_provided(self):
        review = m.Review(
            book="诡秘之主", platform="douban", content="好书",
            platform_id="user_abc",
        )
        assert review.uid
        assert len(review.uid) == 64

    def test_uid_deterministic_from_platform_id_and_book(self):
        r1 = m.Review(
            book="诡秘之主", platform="douban", content="好书",
            platform_id="user_abc",
        )
        r2 = m.Review(
            book="诡秘之主", platform="douban", content="不同内容",
            platform_id="user_abc",
        )
        assert r1.uid == r2.uid  # uid based on platform_id + book, not content

    def test_no_uid_when_platform_id_missing(self):
        review = m.Review(book="诡秘之主", platform="douban", content="好书")
        assert review.uid == ""

    def test_no_uid_when_book_missing(self):
        review = m.Review(book="", platform="douban", content="好书", platform_id="user_abc")
        assert review.uid == ""

    def test_from_dict(self):
        data = {
            "book": "诡秘之主",
            "platform": "douban",
            "content": "好书推荐",
            "source_url": "http://example.com",
            "title": "精彩书评",
            "author": "读者A",
            "created_at": "2026-01-01",
            "review_id": "id-001",
            "uid": "uid-001",
            "platform_id": "user_abc",
            "extra": {"rating": 5},
        }
        review = m.Review.from_dict(data)
        assert review.book == "诡秘之主"
        assert review.platform == "douban"
        assert review.content == "好书推荐"
        assert review.title == "精彩书评"
        assert review.author == "读者A"
        assert review.review_id == "id-001"
        assert review.uid == "uid-001"
        assert review.extra == {"rating": 5}

    def test_from_dict_with_fallback_book(self):
        data = {"content": "好书", "platform": "douban"}
        review = m.Review.from_dict(data, fallback_book="默认书名")
        assert review.book == "默认书名"

    def test_from_dict_aliases_content_field(self):
        data = {"book": "B", "platform": "p", "text": "评论text"}
        review = m.Review.from_dict(data)
        assert review.content == "评论text"

    def test_from_dict_aliases_source_url_field(self):
        data = {"book": "B", "platform": "p", "content": "c", "url": "http://url"}
        review = m.Review.from_dict(data)
        assert review.source_url == "http://url"

    def test_from_dict_aliases_review_id_field(self):
        data = {"book": "B", "platform": "p", "content": "c", "id": "alt-id"}
        review = m.Review.from_dict(data)
        assert review.review_id == "alt-id"

    def test_from_dict_empty_content(self):
        data = {"book": "B", "platform": "p", "content": ""}
        review = m.Review.from_dict(data)
        assert review.content == ""

    def test_to_dict(self):
        review = m.Review(
            book="诡秘之主",
            platform="douban",
            content="好书推荐",
            source_url="http://example.com",
            title="书评",
        )
        d = review.to_dict()
        assert d["book"] == "诡秘之主"
        assert d["platform"] == "douban"
        assert d["content"] == "好书推荐"
        assert d["source_url"] == "http://example.com"
        assert d["title"] == "书评"
        assert "review_id" in d
        assert "collected_at" in d


# ---------------------------------------------------------------------------
# ReviewAnalysis dataclass
# ---------------------------------------------------------------------------


class TestReviewAnalysis:
    def test_from_dict_with_basic_fields(self):
        data = {
            "review_id": "r001",
            "platform": "douban",
            "title": "分析",
            "source_url": "http://a.com",
            "sentiment": "positive",
            "sentiment_score": 0.8,
            "writing_score": 8.5,
            "logic_score": 7.0,
            "update_speed_score": 6.0,
        }
        analysis = m.ReviewAnalysis.from_dict(data)
        assert analysis.review_id == "r001"
        assert analysis.sentiment == "positive"
        assert analysis.sentiment_score == 0.8
        assert analysis.writing_score == 8.5
        assert analysis.logic_score == 7.0

    def test_from_dict_coerces_scores(self):
        data = {
            "review_id": "r001",
            "platform": "douban",
            "title": "分析",
            "source_url": "http://a.com",
            "sentiment": "pos",
            "sentiment_score": 99.0,  # out of range
            "writing_score": -5.0,  # below 0
            "toxicity_index": "invalid",
        }
        analysis = m.ReviewAnalysis.from_dict(data)
        assert analysis.sentiment == "positive"
        assert analysis.sentiment_score == 1.0  # clamped to 1.0
        assert analysis.writing_score == 0.0  # clamped to 0.0
        assert analysis.toxicity_index == 0.0  # default from invalid

    def test_from_dict_with_review_fallback(self):
        review = m.Review(book="test", platform="tieba", content="好书", source_url="http://fallback.com")
        data = {"sentiment": "negative", "sentiment_score": -0.5}
        analysis = m.ReviewAnalysis.from_dict(data, review=review)
        assert analysis.platform == "tieba"
        assert analysis.source_url == "http://fallback.com"

    def test_from_dict_defaults(self):
        analysis = m.ReviewAnalysis.from_dict({})
        assert analysis.sentiment == "neutral"
        assert analysis.sentiment_score == 0.0
        assert analysis.writing_score == 5.0
        assert analysis.character_score == 5.0
        assert analysis.toxicity_index == 0.0
        assert analysis.tags == []

    def test_from_dict_strips_empty_tags(self):
        data = {
            "review_id": "r1", "platform": "p", "title": "t",
            "source_url": "u", "tags": ["good", "", "  ", "nice"],
        }
        analysis = m.ReviewAnalysis.from_dict(data)
        assert analysis.tags == ["good", "nice"]

    def test_to_dict(self):
        analysis = m.ReviewAnalysis(
            review_id="r001",
            platform="douban",
            title="分析标题",
            source_url="http://a.com",
            sentiment="positive",
            sentiment_score=0.75,
            writing_score=8.0,
            logic_score=7.5,
            update_speed_score=6.0,
            character_score=9.0,
            toxicity_index=0.05,
            one_liner="好书",
            entry_reason="质量高",
            tags=["文笔好", "逻辑强"],
            evidence="读者一致好评",
        )
        d = analysis.to_dict()
        assert d["review_id"] == "r001"
        assert d["sentiment"] == "positive"
        assert d["sentiment_score"] == 0.75
        assert d["tags"] == ["文笔好", "逻辑强"]
        assert d["evidence"] == "读者一致好评"


# ---------------------------------------------------------------------------
# dedupe_reviews
# ---------------------------------------------------------------------------


class TestDedupeReviews:
    def test_deduplicates_by_platform_and_content(self):
        r1 = m.Review(book="test", platform="douban", content="好书推荐 文笔很好 逻辑严密")
        r2 = m.Review(book="test", platform="douban", content="好书推荐 文笔很好 逻辑严密")
        r3 = m.Review(book="test", platform="douban", content="不同的内容")
        result = m.dedupe_reviews([r1, r2, r3])
        assert len(result) == 2
        assert result[0] is r1
        assert result[1] is r3

    def test_same_content_different_platforms_not_deduplicated(self):
        r1 = m.Review(book="test", platform="douban", content="好书")
        r2 = m.Review(book="test", platform="tieba", content="好书")
        result = m.dedupe_reviews([r1, r2])
        assert len(result) == 2

    def test_empty_list(self):
        assert m.dedupe_reviews([]) == []

    def test_preserves_order(self):
        reviews = [
            m.Review(book="B", platform="p1", content=f"review {i}") for i in range(5)
        ]
        result = m.dedupe_reviews(reviews)
        assert len(result) == 5
        assert [r.content for r in result] == [f"review {i}" for i in range(5)]


# ---------------------------------------------------------------------------
# JSONL / JSON file I/O
# ---------------------------------------------------------------------------


class TestJsonlIO:
    def test_write_then_read_roundtrip(self, tmp_path):
        reviews = [
            m.Review(book="诡秘之主", platform="douban", content="好书推荐", source_url="http://a.com"),
            m.Review(book="诡秘之主", platform="tieba", content="非常好看", source_url="http://b.com"),
        ]
        path = tmp_path / "reviews.jsonl"
        m.write_jsonl(path, reviews)
        assert path.exists()

        loaded = m.read_jsonl(str(path), fallback_book="诡秘之主")
        assert len(loaded) == 2
        assert loaded[0].content == "好书推荐"
        assert loaded[1].content == "非常好看"

    def test_read_nonexistent_file_returns_empty(self, tmp_path):
        path = tmp_path / "nonexistent.jsonl"
        result = m.read_jsonl(str(path))
        assert result == []

    def test_read_jsonl_handles_empty_lines(self, tmp_path):
        path = tmp_path / "mixed.jsonl"
        path.write_text(
            '{"content": "review1", "platform": "douban"}\n\n{"content": "review2", "platform": "tieba"}\n',
            encoding="utf-8",
        )
        loaded = m.read_jsonl(str(path), fallback_book="book")
        assert len(loaded) == 2

    def test_read_jsonl_skips_empty_content(self, tmp_path):
        path = tmp_path / "empty.jsonl"
        path.write_text('{"content": "", "platform": "douban"}\n', encoding="utf-8")
        loaded = m.read_jsonl(str(path), fallback_book="book")
        assert loaded == []

    def test_read_jsonl_raises_on_invalid_json(self, tmp_path):
        path = tmp_path / "bad.jsonl"
        path.write_text("not valid json\n", encoding="utf-8")
        with pytest.raises(ValueError, match="not valid JSONL"):
            m.read_jsonl(str(path))

    def test_write_jsonl_creates_parent_directory(self, tmp_path):
        reviews = [m.Review(book="b", platform="p", content="c")]
        path = tmp_path / "subdir" / "reviews.jsonl"
        m.write_jsonl(str(path), reviews)
        assert path.exists()


class TestJsonIO:
    def test_write_then_read_roundtrip(self, tmp_path):
        data = {"key": "value", "nested": {"a": 1, "b": [2, 3]}}
        path = tmp_path / "data.json"
        m.write_json(str(path), data)
        assert path.exists()

        loaded = m.read_json(str(path))
        assert loaded == data

    def test_write_creates_parent_directory(self, tmp_path):
        data = {"test": True}
        path = tmp_path / "nested" / "sub" / "data.json"
        m.write_json(str(path), data)
        assert path.exists()
