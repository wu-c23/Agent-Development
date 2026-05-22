import json
from typing import Dict, List, Optional

from openai import OpenAI

from sentiment_critic.critic import score_risks
from .config import API_KEY, CHAT_MODEL, DEEPSEEK_BASE_URL
from .embedding import embed_texts
from .models import Book
from .vector_store import get_collection, upsert_books


class SafeSearchEngine:
    def __init__(self) -> None:
        if not API_KEY:
            raise RuntimeError("DEEPSEEK_API_KEY is not set")

        self._client = OpenAI(
            api_key=API_KEY,
            base_url=DEEPSEEK_BASE_URL,
        )
        self._collection = get_collection()

    def index_books(self, books: List[Book]) -> None:
        embeddings = embed_texts(self._client, [book.intro for book in books])
        upsert_books(self._collection, books, embeddings)

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
        query_embedding = embed_texts(self._client, [query])

        raw = self._collection.query(
            query_embeddings=query_embedding,
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        candidates = []
        for idx, book_id in enumerate(raw["ids"][0]):
            metadata = raw["metadatas"][0][idx]
            distance = raw["distances"][0][idx]
            similarity = max(0.0, 1.0 - float(distance))
            tags = [tag for tag in metadata.get("tags", "").split(",") if tag]

            candidates.append(
                Book(
                    id=book_id,
                    title=metadata.get("title", ""),
                    intro=raw["documents"][0][idx],
                    tags=tags,
                    status=metadata.get("status") or None,
                    sentiment_summary=metadata.get("sentiment_summary") or None,
                )
            )

        retrieval_candidates = [
            {
                "id": book.id,
                "title": book.title,
                "similarity": similarity,
                "matched_fields": ["intro", "tags"],
            }
            for book, similarity in zip(candidates, [max(0.0, 1.0 - float(d)) for d in raw["distances"][0]])
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
