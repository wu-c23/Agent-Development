"""Tests for sentiment_critic.critic — risk scoring, rule matching, LLM integration."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# IMPORT SETUP
# ---------------------------------------------------------------------------
# The critic module lives at Safe-Search Architect/src/sentiment_critic/critic.py
# and imports "from openai import OpenAI". We must mock openai before importing
# critic so the top-level import succeeds even when openai is not installed.

_MOCK_OPENAI = MagicMock()
sys.modules["openai"] = _MOCK_OPENAI

# Reorder sys.path so Safe-Search Architect/src/ comes before Sentiment Critic/.
# This ensures we import the correct sentiment_critic package (the one containing critic.py).
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SAFE_SEARCH_SRC = str(_PROJECT_ROOT / "Safe-Search Architect" / "src")
_SENTIMENT_DIR = str(_PROJECT_ROOT / "Sentiment Critic")

if _SAFE_SEARCH_SRC in sys.path:
    sys.path.remove(_SAFE_SEARCH_SRC)
sys.path.insert(0, _SAFE_SEARCH_SRC)
if _SENTIMENT_DIR in sys.path:
    sys.path.remove(_SENTIMENT_DIR)
sys.path.append(_SENTIMENT_DIR)

from sentiment_critic.critic import (
    RISK_DIMENSIONS,
    TAG_RULES,
    _parse_llm_payload,
    _rule_scores,
    score_risks,
)
# ---------------------------------------------------------------------------

import pytest


# ===================================================================
# RISK_DIMENSIONS
# ===================================================================


class TestRiskDimensions:
    def test_has_five_dimensions(self):
        assert len(RISK_DIMENSIONS) == 5

    def test_contains_expected_dims(self):
        expected = {"abuse_protagonist", "unfinished", "melodrama", "harem", "slow_pacing"}
        assert set(RISK_DIMENSIONS) == expected

    def test_dimensions_order_is_consistent(self):
        assert RISK_DIMENSIONS == [
            "abuse_protagonist",
            "unfinished",
            "melodrama",
            "harem",
            "slow_pacing",
        ]


# ===================================================================
# TAG_RULES
# ===================================================================


class TestTagRules:
    def test_each_dimension_has_keywords(self):
        for dim in RISK_DIMENSIONS:
            assert dim in TAG_RULES
            assert len(TAG_RULES[dim]) >= 1

    def test_harem_keywords(self):
        assert "后宫" in TAG_RULES["harem"]

    def test_abuse_keywords(self):
        assert "虐主" in TAG_RULES["abuse_protagonist"]


# ===================================================================
# _rule_scores
# ===================================================================


class TestRuleScores:
    def test_all_zero_when_no_tags_match(self):
        scores = _rule_scores(["玄幻", "升级流"])
        assert all(v == 0.0 for v in scores.values())

    def test_harem_tag_returns_high_score(self):
        scores = _rule_scores(["玄幻", "后宫"])
        assert scores["harem"] == 0.95

    def test_matches_by_substring(self):
        scores = _rule_scores(["虐主文"])  # contains "虐主"
        assert scores["abuse_protagonist"] == 0.95

    def test_multiple_tags_same_dimension(self):
        scores = _rule_scores(["后宫", "后宫爽文"])
        assert scores["harem"] == 0.95

    def test_case_insensitive_matching(self):
        scores = _rule_scores(["HAREM"])
        assert scores["harem"] == 0.95

    def test_returns_dict_with_all_dimensions(self):
        scores = _rule_scores(["后宫"])
        for dim in RISK_DIMENSIONS:
            assert dim in scores


# ===================================================================
# _parse_llm_payload
# ===================================================================


class TestParseLlmPayload:
    def test_parses_valid_json(self):
        payload = json.dumps({
            "abuse_protagonist": 0.1,
            "unfinished": 0.2,
            "melodrama": 0.3,
            "harem": 0.4,
            "slow_pacing": 0.5,
        })
        result = _parse_llm_payload(payload)
        assert result is not None
        assert result["abuse_protagonist"] == 0.1
        assert result["unfinished"] == 0.2
        assert result["slow_pacing"] == 0.5

    def test_returns_none_on_invalid_json(self):
        assert _parse_llm_payload("not valid json") is None

    def test_returns_none_on_empty_dict(self):
        assert _parse_llm_payload("{}") is None  # no valid keys

    def test_returns_none_on_wrong_keys(self):
        payload = json.dumps({"foo": 0.5, "bar": 0.3})
        assert _parse_llm_payload(payload) is None

    def test_partial_scores(self):
        payload = json.dumps({"harem": 0.9, "unknown_dim": 1.0})
        result = _parse_llm_payload(payload)
        assert result is not None
        assert result["harem"] == 0.9
        assert "abuse_protagonist" not in result


# ===================================================================
# score_risks
# ===================================================================


class TestScoreRisks:
    def test_returns_dict_with_scores_and_evidence(self):
        client = MagicMock()
        result = score_risks(
            client=client,
            model="test",
            title="修罗武神",
            intro="",
            tags=["玄幻", "后宫"],
            sentiment_summary="",
        )
        assert "scores" in result
        assert "evidence" in result

    def test_rule_only_when_no_intro_and_no_sentiment(self):
        """When both intro and sentiment_summary are empty, LLM is not called."""
        client = MagicMock()
        result = score_risks(
            client=client,
            model="test",
            title="修罗武神",
            intro="",
            tags=["后宫"],
            sentiment_summary="",
        )
        client.chat.completions.create.assert_not_called()
        assert result["scores"]["harem"] >= 0.9

    def test_harem_tag_matched(self):
        client = MagicMock()
        result = score_risks(
            client=client,
            model="test",
            title="修罗武神",
            intro="楚枫逆天改命...",
            tags=["玄幻", "后宫"],
            sentiment_summary="",
        )
        assert "scores" in result
        assert "evidence" in result
        assert result["scores"]["harem"] >= 0.9

    def test_rule_scores_appear_in_evidence(self):
        client = MagicMock()
        result = score_risks(
            client=client,
            model="test",
            title="修罗武神",
            intro="",
            tags=["后宫", "虐主", "烂尾"],
            sentiment_summary="",
        )
        evidence_dims = {e["value"] for e in result["evidence"]}
        assert "harem" in evidence_dims
        assert "abuse_protagonist" in evidence_dims
        assert "unfinished" in evidence_dims

    def test_llm_scores_merged_with_rule_scores(self):
        """When LLM returns scores, they are merged via max with rule scores."""
        client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "abuse_protagonist": 0.1,
            "unfinished": 0.2,
            "melodrama": 0.3,
            "harem": 0.4,
            "slow_pacing": 0.5,
        })
        client.chat.completions.create.return_value = mock_response

        result = score_risks(
            client=client,
            model="test",
            title="诡秘之主",
            intro="值夜者克莱恩探索超凡力量的故事",
            tags=["克苏鲁", "悬疑"],
            sentiment_summary="好评居多，逻辑严密",
        )
        # Rule scores all 0.0 for non-matching tags, so LLM scores should be used
        assert result["scores"]["harem"] == 0.4
        assert result["scores"]["slow_pacing"] == 0.5
        client.chat.completions.create.assert_called_once()

    def test_llm_score_overrides_rule_score_when_higher(self):
        """Max of rule and LLM: LLM score wins when higher."""
        client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        # LLM returns a high score even though tags don't match harem directly
        mock_response.choices[0].message.content = json.dumps({
            "abuse_protagonist": 0.1,
            "unfinished": 0.0,
            "melodrama": 0.1,
            "harem": 0.85,
            "slow_pacing": 0.2,
        })
        client.chat.completions.create.return_value = mock_response

        result = score_risks(
            client=client,
            model="test",
            title="某书",
            intro="一些介绍内容",
            tags=["玄幻"],  # no harem tag
            sentiment_summary="有读者提到感情线",
        )
        # LLM says 0.85, rule says 0.0 → merged = 0.85
        assert result["scores"]["harem"] == 0.85

    def test_falls_back_to_rules_when_llm_fails(self):
        """When LLM call raises an exception, fall back to rule scores."""
        client = MagicMock()
        client.chat.completions.create.side_effect = Exception("API unavailable")

        result = score_risks(
            client=client,
            model="test",
            title="修罗武神",
            intro="一些介绍",
            tags=["后宫", "虐主"],
            sentiment_summary="读者评价正面",
        )
        # Should still have rule-based scores
        assert result["scores"]["harem"] >= 0.9
        assert result["scores"]["abuse_protagonist"] >= 0.9

    def test_llm_called_when_sentiment_summary_provided(self):
        """LLM is called when sentiment_summary is truthy even without intro."""
        client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "abuse_protagonist": 0.0,
            "unfinished": 0.0,
            "melodrama": 0.0,
            "harem": 0.0,
            "slow_pacing": 0.0,
        })
        client.chat.completions.create.return_value = mock_response

        result = score_risks(
            client=client,
            model="test",
            title="某书",
            intro="",
            tags=[],
            sentiment_summary="一般般",
        )
        client.chat.completions.create.assert_called_once()

    def test_scores_are_between_zero_and_one(self):
        """All dimension scores are in [0.0, 1.0]."""
        client = MagicMock()
        result = score_risks(
            client=client,
            model="test",
            title="修罗武神",
            intro="",
            tags=["后宫", "虐主", "烂尾", "狗血"],
            sentiment_summary="",
        )
        for dim in RISK_DIMENSIONS:
            assert 0.0 <= result["scores"][dim] <= 1.0

    def test_scores_contains_all_five_dimensions(self):
        client = MagicMock()
        result = score_risks(
            client=client,
            model="test",
            title="test",
            intro="",
            tags=[],
            sentiment_summary="",
        )
        for dim in RISK_DIMENSIONS:
            assert dim in result["scores"]
