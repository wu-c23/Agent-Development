"""Tests for review_critic.analyzer — pure functions, heuristic analysis,
report building, and the high-level analyze_reviews orchestrator.

All tests avoid real LLM calls by passing ``client=MagicMock()`` or
setting ``use_agent=False``.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from review_critic.analyzer import (
    NEGATIVE_WORDS,
    POSITIVE_WORDS,
    TAG_KEYWORDS,
    analyze_reviews,
    build_report,
    chunked,
    complete_analysis,
    dimension_score,
    heuristic_analysis,
    infer_tags,
    is_retryable_agent_error,
    make_entry_reason,
    make_evidence,
    make_one_liner,
    make_verdict,
)
from review_critic.models import Review, ReviewAnalysis


# ===================================================================
# Pure function: chunked
# ===================================================================


class TestChunked:
    def test_normal_chunks(self) -> None:
        assert chunked([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]

    def test_empty_list(self) -> None:
        assert chunked([], 3) == []

    def test_single_chunk(self) -> None:
        assert chunked([1], 5) == [[1]]

    def test_exact_division(self) -> None:
        assert chunked([1, 2, 3, 4], 2) == [[1, 2], [3, 4]]

    def test_size_greater_than_list(self) -> None:
        assert chunked([1, 2], 10) == [[1, 2]]


# ===================================================================
# Pure function: dimension_score
# ===================================================================


class TestDimensionScore:
    def test_starts_at_5_5(self) -> None:
        """No matching terms leaves the score at 5.5."""
        assert dimension_score("无相关内容", ["文笔"], ["文笔差"]) == 5.5

    def test_positive_term_adds_1(self) -> None:
        """Each matching positive term adds 1.0."""
        score = dimension_score("文笔很好", ["文笔"], ["文笔差"])
        assert score == 6.5

    def test_negative_term_subtracts_1_3(self) -> None:
        """Each matching negative term subtracts 1.3."""
        score = dimension_score("文笔差", ["文笔"], ["文笔差"])
        assert score == 5.2  # 5.5 + 1.0 - 1.3

    def test_multiple_terms(self) -> None:
        text = "文笔细腻 文笔流畅"
        score = dimension_score(text, ["文笔", "描写", "细腻"], ["文笔差", "尬"])
        # "文笔" matches twice, but score is per-term, not per-occurrence
        # So: 5.5 + 1.0 (文笔) + 1.0 (细腻) = 7.5
        assert score == 7.5

    def test_clamped_to_10(self) -> None:
        score = dimension_score(
            "文笔 描写 细腻 流畅",
            ["文笔", "描写", "细腻", "流畅", "额外"],
            [],
        )
        # 5.5 + 5*1.0 = 10.5 -> clamped to 10.0
        assert score <= 10.0

    def test_clamped_to_0(self) -> None:
        score = dimension_score(
            "文笔差 尬",
            [],
            ["文笔差", "尬", "额外1", "额外2", "额外3"],
        )
        # 5.5 - 5*1.3 = -1.0 -> clamped to 0.0
        assert score >= 0.0


# ===================================================================
# Pure function: is_retryable_agent_error
# ===================================================================


class TestIsRetryableAgentError:
    def test_429_rate_limit(self) -> None:
        assert is_retryable_agent_error(Exception("429 rate limit")) is True

    def test_rate_limit_text(self) -> None:
        assert is_retryable_agent_error(Exception("ratelimit exceeded")) is True

    def test_timeout(self) -> None:
        assert is_retryable_agent_error(Exception("timed out")) is True

    def test_503(self) -> None:
        assert is_retryable_agent_error(Exception("503 service unavailable")) is True

    def test_504(self) -> None:
        assert is_retryable_agent_error(Exception("504 gateway timeout")) is True

    def test_non_retryable(self) -> None:
        assert is_retryable_agent_error(Exception("other error")) is False

    def test_empty_message(self) -> None:
        assert is_retryable_agent_error(Exception("")) is False


# ===================================================================
# Pure function: infer_tags
# ===================================================================


class TestInferTags:
    def test_writing_tag(self) -> None:
        text = "文笔细腻，描写生动"
        tags = infer_tags(text, "positive")
        assert "文笔细腻" in tags

    def test_logic_tag(self) -> None:
        text = "逻辑硬伤太多"
        tags = infer_tags(text, "negative")
        assert "逻辑硬伤" in tags

    def test_setting_tag(self) -> None:
        text = "世界观设定很宏大"
        tags = infer_tags(text, "positive")
        assert "设定亮眼" in tags

    def test_update_tag(self) -> None:
        text = "又拖更了"
        tags = infer_tags(text, "negative")
        assert "更新不稳" in tags

    def test_fallback_positive(self) -> None:
        """No keywords matched -> falls back to 口碑偏正."""
        tags = infer_tags("好看", "positive")
        assert tags == ["口碑偏正"]

    def test_fallback_negative(self) -> None:
        tags = infer_tags("不好看", "negative")
        assert tags == ["争议较大"]

    def test_fallback_neutral(self) -> None:
        tags = infer_tags("还行吧", "neutral")
        assert tags == ["评价分化"]

    def test_max_five_tags(self) -> None:
        text = "文笔细腻 逻辑硬伤 设定亮眼 节奏拖沓 更新不稳 角色鲜活 爽点密集"
        tags = infer_tags(text, "positive")
        assert len(tags) <= 5


# ===================================================================
# Pure function: make_one_liner
# ===================================================================


class TestMakeOneLiner:
    def test_positive(self) -> None:
        result = make_one_liner("positive", ["文笔细腻"])
        assert "不是无脑吹" in result

    def test_negative(self) -> None:
        result = make_one_liner("negative", ["逻辑硬伤"])
        assert "雷点" in result

    def test_neutral(self) -> None:
        result = make_one_liner("neutral", ["设定亮眼"])
        assert "优缺点都很明显" in result

    def test_uses_top_two_tags(self) -> None:
        result = make_one_liner("positive", ["文笔细腻", "设定亮眼"])
        assert "文笔细腻" in result
        assert "设定亮眼" in result


# ===================================================================
# Pure function: make_entry_reason
# ===================================================================


class TestMakeEntryReason:
    def test_positive(self) -> None:
        result = make_entry_reason("positive", ["文笔细腻"])
        assert "适合想看" in result

    def test_negative(self) -> None:
        result = make_entry_reason("negative", ["逻辑硬伤"])
        assert "只建议" in result

    def test_neutral(self) -> None:
        result = make_entry_reason("neutral", ["设定亮眼"])
        assert "适合先读" in result


# ===================================================================
# Pure function: make_evidence
# ===================================================================


class TestMakeEvidence:
    def test_extracts_around_keyword(self) -> None:
        text = "这本书的文笔确实细腻值得推荐"
        tags = ["文笔细腻"]
        result = make_evidence(text, tags)
        # Should find "文笔" in the text and extract context around it
        assert "文笔" in result
        assert len(result) <= 35

    def test_fallback_no_keyword(self) -> None:
        text = "这本书很好看值得推荐非常不错"
        tags = ["口碑偏正"]  # not in TAG_KEYWORDS
        result = make_evidence(text, tags)
        # Falls back to text[:35]
        assert result == text[:35]


# ===================================================================
# heuristic_analysis
# ===================================================================


class TestHeuristicAnalysis:
    def test_positive_review(self) -> None:
        """A review with multiple positive keywords yields positive sentiment."""
        content = (
            "文笔细腻，非常推荐这本书。伏笔设计精妙，逻辑严密，"
            "角色鲜活，世界观宏大。更新稳定，值得入坑。"
        )
        review = Review(book="test", platform="douban", content=content)
        analysis = heuristic_analysis(review)
        assert analysis.sentiment == "positive"
        assert analysis.writing_score > 5.5
        assert "文笔细腻" in analysis.tags

    def test_negative_review(self) -> None:
        """A review with strong negative keywords yields negative sentiment."""
        content = (
            "毒点太多，逻辑硬伤严重，主角降智，文笔小白，已经弃文了。"
            "还经常断更，拖更严重，后期崩得厉害。"
        )
        review = Review(book="test", platform="douban", content=content)
        analysis = heuristic_analysis(review)
        assert analysis.sentiment == "negative"
        assert analysis.writing_score < 5.5

    def test_neutral_review(self) -> None:
        """A review with balanced or no strong words yields neutral."""
        content = "还行吧，一般般，说不上好也说不上差。"
        review = Review(book="test", platform="douban", content=content)
        analysis = heuristic_analysis(review)
        assert analysis.sentiment == "neutral"
        # All scores should be near baseline
        assert 5.0 <= analysis.writing_score <= 6.0

    def test_all_analysis_fields_present(self) -> None:
        content = "文笔细腻 好看 推荐"
        review = Review(book="test", platform="douban", content=content)
        analysis = heuristic_analysis(review)
        assert analysis.review_id
        assert analysis.platform == "douban"
        assert analysis.sentiment in ("positive", "neutral", "negative")
        assert isinstance(analysis.sentiment_score, float)
        assert isinstance(analysis.writing_score, float)
        assert isinstance(analysis.logic_score, float)
        assert isinstance(analysis.update_speed_score, float)
        assert isinstance(analysis.tags, list)
        assert isinstance(analysis.one_liner, str)
        assert isinstance(analysis.entry_reason, str)
        assert isinstance(analysis.evidence, str)


# ===================================================================
# build_report
# ===================================================================


class TestBuildReport:
    def _make_analyses(self) -> tuple[list[Review], list[ReviewAnalysis]]:
        reviews = [
            Review(book="test_book", platform="douban", content=""),
            Review(book="test_book", platform="douban", content=""),
            Review(book="test_book", platform="tieba", content=""),
        ]
        analyses = [
            ReviewAnalysis(
                review_id="r1", platform="douban", title="", source_url="",
                sentiment="positive", sentiment_score=0.6,
                writing_score=8.0, logic_score=7.0, update_speed_score=5.0,
                tags=["文笔细腻", "设定亮眼"],
            ),
            ReviewAnalysis(
                review_id="r2", platform="douban", title="", source_url="",
                sentiment="negative", sentiment_score=-0.5,
                writing_score=3.0, logic_score=4.0, update_speed_score=5.0,
                tags=["逻辑硬伤"],
            ),
            ReviewAnalysis(
                review_id="r3", platform="tieba", title="", source_url="",
                sentiment="neutral", sentiment_score=0.0,
                writing_score=5.5, logic_score=5.5, update_speed_score=5.5,
                tags=["评价分化"],
            ),
        ]
        return reviews, analyses

    def test_report_contains_required_keys(self) -> None:
        reviews, analyses = self._make_analyses()
        report = build_report(reviews, analyses, agent_used=False)
        assert "book" in report
        assert "review_count" in report
        assert "ratio" in report
        assert "average_scores" in report
        assert "top_tags" in report
        assert "verdict" in report
        assert "items" in report
        assert "analysis_method" in report

    def test_report_book_and_count(self) -> None:
        reviews, analyses = self._make_analyses()
        report = build_report(reviews, analyses, agent_used=False)
        assert report["book"] == "test_book"
        assert report["review_count"] == 3

    def test_report_ratio(self) -> None:
        reviews, analyses = self._make_analyses()
        report = build_report(reviews, analyses, agent_used=False)
        assert report["ratio"]["positive"] == pytest.approx(1 / 3, abs=0.01)
        assert report["ratio"]["neutral"] == pytest.approx(1 / 3, abs=0.01)
        assert report["ratio"]["negative"] == pytest.approx(1 / 3, abs=0.01)

    def test_report_average_scores(self) -> None:
        reviews, analyses = self._make_analyses()
        report = build_report(reviews, analyses, agent_used=False)
        scores = report["average_scores"]
        assert "writing" in scores
        assert "logic" in scores
        assert "update_speed" in scores
        assert "sentiment" in scores

    def test_report_platform_breakdown(self) -> None:
        reviews, analyses = self._make_analyses()
        report = build_report(reviews, analyses, agent_used=False)
        pb = report["platform_breakdown"]
        assert "douban" in pb
        assert "tieba" in pb
        assert pb["douban"]["total"] == 2
        assert pb["tieba"]["total"] == 1


# ===================================================================
# make_verdict
# ===================================================================


class TestMakeVerdict:
    def test_high_negative_ratio(self) -> None:
        from collections import Counter

        counts = Counter({"positive": 1, "negative": 3, "neutral": 1})
        score_fields = {
            "logic": [5.0],
            "writing": [5.0],
        }
        verdict = make_verdict(counts, score_fields)
        assert "负面声量偏高" in verdict

    def test_high_positive_and_logic(self) -> None:
        from collections import Counter

        counts = Counter({"positive": 4, "negative": 1, "neutral": 1})
        score_fields = {
            "logic": [7.0, 6.5, 8.0, 7.5, 7.0, 6.0],
            "writing": [7.0],
        }
        verdict = make_verdict(counts, score_fields)
        assert "真实口碑偏稳" in verdict

    def test_high_writing_low_logic(self) -> None:
        from collections import Counter

        counts = Counter({"positive": 3, "negative": 2, "neutral": 1})
        score_fields = {
            "logic": [5.0, 5.5],
            "writing": [8.0, 7.5],
        }
        verdict = make_verdict(counts, score_fields)
        assert "文笔认可度高于逻辑认可度" in verdict

    def test_default_verdict(self) -> None:
        from collections import Counter

        counts = Counter({"positive": 2, "negative": 2, "neutral": 2})
        score_fields = {
            "logic": [5.0, 6.0],
            "writing": [6.0, 5.0],
        }
        verdict = make_verdict(counts, score_fields)
        assert "口碑分化明显" in verdict


# ===================================================================
# complete_analysis
# ===================================================================


class TestCompleteAnalysis:
    def test_merges_agent_data(self) -> None:
        review = Review(book="test", platform="douban", content="文笔非常好")
        data = {
            "review_id": review.review_id,
            "sentiment": "positive",
            "sentiment_score": 0.8,
            "writing_score": 9.0,
            "logic_score": 6.0,
            "update_speed_score": 5.5,
            "one_liner": "确实不错",
            "entry_reason": "适合喜欢好文笔的读者",
        }
        analysis = complete_analysis(data, review)
        assert analysis.sentiment == "positive"
        assert analysis.sentiment_score == 0.8

    def test_fills_missing_one_liner(self) -> None:
        """If one_liner/entry_reason are missing, heuristic fills them."""
        review = Review(book="test", platform="douban", content="文笔细腻 推荐")
        data = {
            "review_id": review.review_id,
            "sentiment": "positive",
            "sentiment_score": 0.5,
            "writing_score": 7.0,
            "logic_score": 6.0,
            "update_speed_score": 5.0,
        }
        analysis = complete_analysis(data, review)
        assert analysis.one_liner  # filled by heuristic fallback
        assert analysis.entry_reason  # filled by heuristic fallback


# ===================================================================
# analyze_reviews — orchestrator
# ===================================================================


class TestAnalyzeReviews:
    def test_heuristic_only(self) -> None:
        """With use_agent=False, all reviews go through heuristic analysis."""
        reviews = [
            Review(book="test_book", platform="douban", content="文笔细腻 推荐"),
        ]
        result = analyze_reviews(
            reviews,
            use_agent=False,
            client=MagicMock(),
        )
        assert result["book"] == "test_book"
        assert result["review_count"] == 1
        assert result["analysis_method"] == "heuristic"

    def test_heuristic_multiple_reviews(self) -> None:
        reviews = [
            Review(book="test_book", platform="douban", content="文笔细腻 推荐"),
            Review(book="test_book", platform="tieba", content="逻辑硬伤 弃文"),
        ]
        result = analyze_reviews(
            reviews,
            use_agent=False,
            client=MagicMock(),
        )
        assert result["review_count"] == 2
        assert result["analysis_method"] == "heuristic"

    def test_agent_fallback_to_heuristic(self) -> None:
        """When agent is unavailable (use_agent=True, but client says not
        available), the analysis falls back to heuristic."""
        mock_client = MagicMock()
        mock_client.available = False
        mock_client.config.diagnostic_lines.return_value = []
        mock_client.config.validation_errors.return_value = []

        reviews = [
            Review(book="test_book", platform="douban", content="文笔细腻 推荐"),
        ]
        result = analyze_reviews(
            reviews,
            use_agent=True,
            client=mock_client,
            require_agent=False,
        )
        # With no validation errors and agent not available,
        # the agent path is skipped and heuristic is used.
        assert result["analysis_method"] == "heuristic"
        assert result["review_count"] == 1

    def test_agent_fails_and_require_agent_raises(self) -> None:
        """If require_agent=True but agent is not available, an error is
        raised."""
        mock_client = MagicMock()
        mock_client.available = False
        mock_client.config.diagnostic_lines.return_value = []
        mock_client.config.validation_errors.return_value = ["no api key"]

        reviews = [
            Review(book="test_book", platform="douban", content="文笔细腻 推荐"),
        ]
        with pytest.raises(RuntimeError, match="Agent is required"):
            analyze_reviews(
                reviews,
                use_agent=True,
                client=mock_client,
                require_agent=True,
            )


# ===================================================================
# Edge cases and data integrity
# ===================================================================


class TestDataIntegrity:
    def test_positive_words_have_weights(self) -> None:
        for word, weight in POSITIVE_WORDS.items():
            assert isinstance(word, str)
            assert isinstance(weight, int)
            assert weight >= 1

    def test_negative_words_have_weights(self) -> None:
        for word, weight in NEGATIVE_WORDS.items():
            assert isinstance(word, str)
            assert isinstance(weight, int)
            assert weight >= 1

    def test_tag_keywords_structure(self) -> None:
        for tag, keywords in TAG_KEYWORDS.items():
            assert isinstance(tag, str)
            assert isinstance(keywords, tuple)
            assert len(keywords) >= 1
