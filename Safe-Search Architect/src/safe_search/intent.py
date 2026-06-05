"""Intent extraction and self-querying retriever logic.

Parses natural-language queries into structured intent and uses it to:
  - Build enriched search queries
  - Construct ChromaDB metadata filters
  - Score candidates against the extracted preferences
"""

from __future__ import annotations

import json
from typing import List, Optional

from openai import OpenAI

from .models import Book, IntentResult


# ---------------------------------------------------------------------------
# Few-shot prompt
# ---------------------------------------------------------------------------

INTENT_SYSTEM_PROMPT = """You are a search intent analyzer for Chinese web novels.
Given a natural language query, extract structured intent as JSON.

## Output Schema
{
  "summary": "concise interpretation of what the user wants (Chinese)",
  "topics": ["genre/topic tags"],
  "style": ["writing style descriptors"],
  "protagonist_traits": ["main character personality/attributes"],
  "mood": ["emotional tone / atmosphere"],
  "constraints": ["hard constraints like 'must be completed'", "explicit avoid instructions"]
}

## Examples

Query: 类似《诡秘之主》但基调不那么压抑的
{
  "summary": "想要类似诡秘之主（克苏鲁、蒸汽朋克、悬疑）但氛围更轻松的作品",
  "topics": ["克苏鲁", "蒸汽朋克", "悬疑", "西方奇幻"],
  "style": ["逻辑严密", "世界观宏大"],
  "protagonist_traits": ["冷静", "谨慎", "智商在线"],
  "mood": ["轻快", "不那么压抑"],
  "constraints": ["avoid_heavy_angst"]
}

Query: 想看修仙爽文，不要后宫不要虐主
{
  "summary": "想要修仙题材的爽文，不能有后宫和虐主情节",
  "topics": ["修仙", "玄幻", "升级流"],
  "style": ["爽文", "节奏快"],
  "protagonist_traits": ["杀伐果断", "天赋异禀"],
  "mood": ["热血", "爽快"],
  "constraints": ["no_harem", "no_abuse_protagonist"]
}

Query: 求推荐完结的女频古代言情，男主专一
{
  "summary": "用户想要已完结的女频古代言情小说，男主感情专一",
  "topics": ["古代言情", "女频", "宫斗"],
  "style": ["文笔好", "感情细腻"],
  "protagonist_traits": ["男主专一", "女主聪慧"],
  "mood": ["甜宠", "温馨"],
  "constraints": ["must_be_completed", "no_love_triangle"]
}

Query: 最近书荒，来点无限流或者系统流，完本的优先
{
  "summary": "用户想看无限流或系统流的完结作品",
  "topics": ["无限流", "系统流", "诸天"],
  "style": ["脑洞大", "逻辑严密"],
  "protagonist_traits": ["机智", "冷静"],
  "mood": ["紧张", "刺激"],
  "constraints": ["prefer_completed"]
}

Now analyze: {query}"""


# ---------------------------------------------------------------------------
# IntentExtractor
# ---------------------------------------------------------------------------


class IntentExtractor:
    """Extract structured search intent and use it for retrieval refinement."""

    def __init__(self, client: OpenAI, model: str) -> None:
        self._client = client
        self._model = model

    def extract(self, query: str) -> IntentResult:
        """Parse a natural-language query into structured intent."""
        prompt = INTENT_SYSTEM_PROMPT.replace("{query}", query)

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": "You output only valid JSON. No markdown, no explanation."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content or ""
            data = json.loads(content)
        except (json.JSONDecodeError, Exception):
            return IntentResult(summary=query)

        return IntentResult(
            summary=data.get("summary", query),
            topics=data.get("topics", []),
            style=data.get("style", []),
            protagonist_traits=data.get("protagonist_traits", []),
            mood=data.get("mood", []),
            constraints=data.get("constraints", []),
        )

    def build_search_query(self, raw_query: str, intent: IntentResult) -> str:
        """Enrich the raw query with extracted intent fields for better retrieval."""
        parts = [raw_query]
        if intent.topics:
            parts.extend(intent.topics)
        if intent.style:
            parts.extend(intent.style)
        if intent.mood:
            parts.extend(intent.mood)
        if intent.protagonist_traits:
            parts.extend(intent.protagonist_traits)
        return " ".join(parts)

    def build_metadata_filter(self, intent: IntentResult) -> Optional[dict]:
        """Convert intent constraints into a ChromaDB where clause.

        Supported constraints:
          - must_be_completed / prefer_completed -> status == 'completed'
        """
        must_complete = any(
            c in ["must_be_completed", "prefer_completed"] for c in intent.constraints
        )
        if must_complete:
            return {"status": "completed"}
        return None

    def score_candidate(self, book: Book, intent: IntentResult) -> float:
        """Score how well a candidate matches the extracted intent (0-1).

        Positive signals come from matching topics/style/mood/traits.
        Negative signals come from violating constraints (e.g. no_harem).
        """
        if not intent.topics and not intent.style and not intent.mood and not intent.protagonist_traits and not intent.constraints:
            return 0.5  # neutral — no preference dimensions to match against

        signals: List[float] = []
        book_text = f"{book.intro} {' '.join(book.tags)}"

        for topic in intent.topics:
            signals.append(1.0 if topic in book_text else 0.0)

        for style in intent.style:
            signals.append(1.0 if style in book_text else 0.0)

        for mood_word in intent.mood:
            signals.append(1.0 if mood_word in book_text else 0.0)

        for trait in intent.protagonist_traits:
            signals.append(1.0 if trait in book_text else 0.0)

        # Penalize constraint violations
        _constraint_tag_map = {
            "no_harem": ["后宫", "harem", "种马"],
            "no_love_triangle": ["多角恋", "三角恋"],
            "no_abuse_protagonist": ["虐主"],
        }
        for constraint in intent.constraints:
            violation_tags = _constraint_tag_map.get(constraint, [])
            for vtag in violation_tags:
                if vtag in book.tags:
                    signals.append(-0.5)  # penalty for violating a hard constraint

        if not signals:
            return 0.5

        return max(0.0, sum(signals) / len(signals))
