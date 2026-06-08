"""Tests for safe_search.intent.

IntentExtractor — extraction, search query building, metadata filtering,
and candidate scoring.
"""

from __future__ import annotations

import json
import sys
import pytest
from unittest.mock import MagicMock, patch, ANY

# ---------------------------------------------------------------------------
# Workaround: safe_search.__init__ eagerly imports engine.py, which tries to
# import sentiment_critic.critic.score_risks.  That module does not exist in
# the repo (critic.py is missing), so we stub it in sys.modules before any
# safe_search import triggers the chain.
# ---------------------------------------------------------------------------
_stub_critic = MagicMock()
_stub_critic.score_risks = MagicMock(return_value={
    "scores": {"violence": 0.0, "sexual": 0.0, "gambling": 0.0, "politics": 0.0, "morality": 0.0},
    "evidence": {"violence": [], "sexual": [], "gambling": [], "politics": [], "morality": []},
})
sys.modules["sentiment_critic"] = MagicMock()
sys.modules["sentiment_critic.critic"] = _stub_critic
# ---------------------------------------------------------------------------

from safe_search.intent import IntentExtractor, INTENT_SYSTEM_PROMPT
from safe_search.models import Book, IntentResult


# ---------------------------------------------------------------------------
# Sample book used by scoring tests
# ---------------------------------------------------------------------------

HAREM_BOOK = Book(
    id="qidian:x",
    title="修罗武神",
    intro="楚枫逆天改命",
    tags=["玄幻", "升级流", "后宫", "爽文"],
    platform="qidian",
    platform_id="qidian:x",
)


# ============================================================================
# IntentExtractor
# ============================================================================

@pytest.fixture
def mock_client() -> MagicMock:
    """Return a MagicMock OpenAI client pre-configured with a valid response.

    The response simulates the IntentExtractor calling chat.completions.create
    and receiving a valid JSON IntentResult payload.
    """
    client = MagicMock()
    chat_completion = MagicMock()
    chat_completion.choices = [MagicMock()]
    chat_completion.choices[0].message.content = json.dumps(
        {
            "summary": "想要修仙爽文",
            "topics": ["修仙", "玄幻"],
            "style": ["爽文"],
            "protagonist_traits": ["杀伐果断"],
            "mood": ["热血"],
            "constraints": ["no_harem"],
        }
    )
    client.chat.completions.create.return_value = chat_completion
    return client


class TestIntentExtractor:
    """Unit tests for IntentExtractor."""

    # -- constructor ---------------------------------------------------------

    def test_constructor_stores_client_and_model(self) -> None:
        """The constructor stores the client and model arguments."""
        client = MagicMock()
        extractor = IntentExtractor(client, "deepseek-chat")
        assert extractor._client is client
        assert extractor._model == "deepseek-chat"

    # -- extract -------------------------------------------------------------

    def test_extract_returns_parsed_intent(
        self, mock_client: MagicMock
    ) -> None:
        """extract() with a valid response returns a fully populated IntentResult."""
        extractor = IntentExtractor(mock_client, "deepseek-chat")
        result = extractor.extract("想看修仙爽文，不要后宫")

        assert isinstance(result, IntentResult)
        assert result.summary == "想要修仙爽文"
        assert "修仙" in result.topics
        assert "爽文" in result.style
        assert "杀伐果断" in result.protagonist_traits
        assert "热血" in result.mood
        assert "no_harem" in result.constraints

    def test_extract_uses_correct_api_parameters(
        self, mock_client: MagicMock
    ) -> None:
        """extract() calls the OpenAI API with the expected arguments."""
        extractor = IntentExtractor(mock_client, "deepseek-chat")
        extractor.extract("修仙爽文")

        mock_client.chat.completions.create.assert_called_once_with(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": ANY},
                {"role": "user", "content": ANY},
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
        )

    def test_extract_passes_prompt_containing_query(
        self, mock_client: MagicMock
    ) -> None:
        """The user message sent to the API includes the original query."""
        extractor = IntentExtractor(mock_client, "deepseek-chat")
        extractor.extract("不要后宫的修仙文")

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        messages = call_kwargs["messages"]
        user_msg = next(m for m in messages if m["role"] == "user")
        assert "不要后宫的修仙文" in user_msg["content"]

    def test_extract_replaces_query_placeholder_in_prompt(
        self, mock_client: MagicMock
    ) -> None:
        """extract() substitutes {query} in INTENT_SYSTEM_PROMPT with the query."""
        extractor = IntentExtractor(mock_client, "deepseek-chat")
        extractor.extract("test_query_string")

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        messages = call_kwargs["messages"]
        user_msg = next(m for m in messages if m["role"] == "user")
        # The placeholder must have been replaced
        assert "{query}" not in user_msg["content"]
        assert "test_query_string" in user_msg["content"]

    def test_extract_handles_json_decode_error(self) -> None:
        """When the LLM returns invalid JSON, extract() returns an IntentResult with summary=query."""
        client = MagicMock()
        chat_completion = MagicMock()
        chat_completion.choices = [MagicMock()]
        chat_completion.choices[0].message.content = "not valid json"
        client.chat.completions.create.return_value = chat_completion

        extractor = IntentExtractor(client, "test-model")
        result = extractor.extract("my raw query")

        assert isinstance(result, IntentResult)
        assert result.summary == "my raw query"
        assert result.topics == []
        assert result.style == []
        assert result.protagonist_traits == []
        assert result.mood == []
        assert result.constraints == []

    def test_extract_handles_api_exception(self) -> None:
        """When the API call raises, extract() gracefully returns IntentResult with summary=query."""
        client = MagicMock()
        client.chat.completions.create.side_effect = RuntimeError("API timeout")

        extractor = IntentExtractor(client, "test-model")
        result = extractor.extract("error query")

        assert isinstance(result, IntentResult)
        assert result.summary == "error query"

    def test_extract_handles_none_content(self) -> None:
        """When message.content is None, the method does not crash."""
        client = MagicMock()
        chat_completion = MagicMock()
        chat_completion.choices = [MagicMock()]
        chat_completion.choices[0].message.content = None
        client.chat.completions.create.return_value = chat_completion

        extractor = IntentExtractor(client, "test-model")
        result = extractor.extract("null content")
        assert result.summary == "null content"

    # -- build_search_query --------------------------------------------------

    def test_build_search_query_combines_raw_query_with_intent(
        self,
    ) -> None:
        """build_search_query appends intent fields to the raw query."""
        extractor = IntentExtractor(MagicMock(), "test-model")
        raw = "找本好看的修仙小说"
        intent = IntentResult(
            topics=["修仙", "玄幻"],
            style=["爽文"],
            mood=["热血"],
            protagonist_traits=["杀伐果断"],
        )
        result = extractor.build_search_query(raw, intent)
        assert raw in result
        assert "修仙" in result
        assert "玄幻" in result
        assert "爽文" in result
        assert "热血" in result
        assert "杀伐果断" in result

    def test_build_search_query_with_empty_intent(self) -> None:
        """When the intent has no extra fields, only the raw query is returned."""
        extractor = IntentExtractor(MagicMock(), "test-model")
        raw = "单纯的关键词"
        intent = IntentResult()
        result = extractor.build_search_query(raw, intent)
        assert result == raw

    # -- build_metadata_filter -----------------------------------------------

    @pytest.mark.parametrize(
        "constraint",
        ["must_be_completed", "prefer_completed"],
    )
    def test_build_metadata_filter_completion_constraint(
        self, constraint: str
    ) -> None:
        """Completion constraints produce a status filter."""
        extractor = IntentExtractor(MagicMock(), "test-model")
        intent = IntentResult(constraints=[constraint])
        assert extractor.build_metadata_filter(intent) == {"status": "completed"}

    @pytest.mark.parametrize(
        "constraints",
        [[], ["no_harem"], ["no_abuse_protagonist"], ["no_harem", "no_love_triangle"]],
    )
    def test_build_metadata_filter_no_completion_constraint(
        self, constraints: list
    ) -> None:
        """Constraints that are not completion-related return None."""
        extractor = IntentExtractor(MagicMock(), "test-model")
        intent = IntentResult(constraints=constraints)
        assert extractor.build_metadata_filter(intent) is None

    # -- score_candidate -----------------------------------------------------

    def test_score_candidate_empty_intent_neutral(self) -> None:
        """An empty intent (no preferences) yields 0.5 (neutral)."""
        extractor = IntentExtractor(MagicMock(), "test-model")
        book = Book(id="b1", title="t", intro="i", tags=[])
        intent = IntentResult()
        assert extractor.score_candidate(book, intent) == 0.5

    def test_score_candidate_positive_matches(self) -> None:
        """Matching topics and style contribute positive signals."""
        extractor = IntentExtractor(MagicMock(), "test-model")
        intent = IntentResult(
            topics=["玄幻"],  # appears in tags
            style=["爽文"],  # appears in tags
        )
        score = extractor.score_candidate(HAREM_BOOK, intent)
        # topics: [1.0], styles: [1.0] -> avg = 1.0
        assert score == 1.0

    def test_score_candidate_partial_match(self) -> None:
        """Some fields matching, others not, produces an intermediate score."""
        extractor = IntentExtractor(MagicMock(), "test-model")
        intent = IntentResult(
            topics=["修仙", "玄幻"],  # 0.0, 1.0
            style=["爽文"],           # 1.0
        )
        score = extractor.score_candidate(HAREM_BOOK, intent)
        # signals = [0.0, 1.0, 1.0], avg = 2.0 / 3 ≈ 0.6667
        assert score == pytest.approx(2.0 / 3.0)

    def test_score_candidate_penalizes_no_harem(self) -> None:
        """The no_harem constraint adds a -0.5 penalty when tags contain harem keywords."""
        extractor = IntentExtractor(MagicMock(), "test-model")
        intent = IntentResult(
            topics=["玄幻"],
            style=["爽文"],
            constraints=["no_harem"],  # "后宫" is in HAREM_BOOK.tags
        )
        score = extractor.score_candidate(HAREM_BOOK, intent)
        # signals = [1.0, 1.0, -0.5], avg = 1.5 / 3 = 0.5
        assert score == 0.5

    def test_score_candidate_bounded_below_zero(self) -> None:
        """Score is clamped to 0.0 even if penalties dominate."""
        extractor = IntentExtractor(MagicMock(), "test-model")
        # A book with no matching fields but violating a constraint
        book = Book(id="bad", title="x", intro="x", tags=["后宫"])
        intent = IntentResult(
            topics=["nonexistent"],
            constraints=["no_harem"],
        )
        score = extractor.score_candidate(book, intent)
        # signals = [0.0, -0.5], avg = -0.25, clamped to 0.0
        assert score == 0.0

    def test_score_candidate_unrecognised_constraint_no_penalty(self) -> None:
        """An unrecognised constraint string does not add any penalty."""
        extractor = IntentExtractor(MagicMock(), "test-model")
        intent = IntentResult(
            topics=["玄幻"],
            constraints=["some_unknown_constraint"],
        )
        score = extractor.score_candidate(HAREM_BOOK, intent)
        # signals = [1.0], avg = 1.0
        assert score == 1.0
