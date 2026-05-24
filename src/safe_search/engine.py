import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Ensure src/ is importable regardless of how this module is loaded
_src = Path(__file__).resolve().parents[1]
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from openai import OpenAI

from sentiment_critic.critic import score_risks
from .config import API_KEY, CHAT_MODEL, DEEPSEEK_BASE_URL
from .models import Book
from .vector_store import BM25Index


class SafeSearchEngine:
    def __init__(self) -> None:
        if not API_KEY:
            raise RuntimeError("DEEPSEEK_API_KEY is not set")

        self._client = OpenAI(
            api_key=API_KEY,
            base_url=DEEPSEEK_BASE_URL,
        )
        self._index = BM25Index()

    def index_books(self, books: List[Book]) -> None:
        self._index.build(books)

    def _extract_intent(self, query: str) -> Dict[str, object]:
        prompt = (
            "Extract user intent from the query. "
            "Return JSON with fields: summary, topics, style, protagonist_traits, mood, constraints.\n\n"
            f"Query: {query}\n"
        )

        response = self._client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[
                {"role": "system", "content": "You output only JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        content = response.choices[0].message.content or ""
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {
                "summary": query,
                "topics": [],
                "style": [],
                "protagonist_traits": [],
                "mood": [],
                "constraints": [],
            }

    def search(
        self,
        query: str,
        avoid_tags: Optional[List[str]] = None,
        top_k: int = 10,
    ) -> Dict[str, object]:
        avoid_tags = avoid_tags or []
        ranked = self._index.query(query, top_k)
        candidates = [book for book, _ in ranked]

        retrieval_candidates = [
            {
                "id": book.id,
                "title": book.title,
                "similarity": score,
                "matched_fields": ["title", "intro", "tags"],
            }
            for book, score in ranked
        ]

        risk_scores = []
        filtered_results = []
        blocked_results = []
        data_gaps = []

        for book in candidates:
            risk = score_risks(
                client=self._client,
                model=CHAT_MODEL,
                title=book.title,
                intro=book.intro,
                tags=book.tags,
                sentiment_summary=book.sentiment_summary,
            )

            scores = risk["scores"]
            risk_scores.append(
                {
                    "id": book.id,
                    **scores,
                    "evidence": risk["evidence"],
                }
            )

            blocked_by = []
            for tag in avoid_tags:
                if tag in book.tags:
                    blocked_by.append(f"tag:{tag}")

            for dim, score in scores.items():
                if score >= 0.7:
                    blocked_by.append(f"risk:{dim}>{score:.2f}")

            if blocked_by:
                blocked_results.append(
                    {
                        "id": book.id,
                        "title": book.title,
                        "blocked_by": blocked_by,
                    }
                )
            else:
                risk_penalty = sum(score for score in scores.values()) / len(scores)
                filtered_results.append(
                    {
                        "id": book.id,
                        "title": book.title,
                        "final_score": max(0.0, 1.0 - risk_penalty),
                        "reasons_recommend": ["semantic_match"],
                        "reasons_risk": [f"{dim}:{score:.2f}" for dim, score in scores.items() if score >= 0.4],
                    }
                )

            missing = []
            if not book.status:
                missing.append("ending_status")
            if not book.sentiment_summary:
                missing.append("public_opinion_summary")
            if missing:
                data_gaps.append(
                    {
                        "id": book.id,
                        "missing": missing,
                        "suggestion": "add status or sentiment summary",
                    }
                )

        return {
            "query_intent": self._extract_intent(query),
            "retrieval_candidates": retrieval_candidates,
            "risk_scores": risk_scores,
            "filtered_results": filtered_results,
            "blocked_results": blocked_results,
            "data_gaps": data_gaps,
        }
