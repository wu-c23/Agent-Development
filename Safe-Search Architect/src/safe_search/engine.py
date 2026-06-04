import os
import sys
from typing import Dict, List, Optional

from openai import OpenAI

try:
    from ..sentiment_critic.critic import score_risks
except ImportError:
    from sentiment_critic.critic import score_risks
from .config import (
    API_KEY,
    CHAT_MODEL,
    CHROMA_PERSIST_DIR,
    DEEPSEEK_BASE_URL,
    EMBEDDING_API_KEY,
    EMBEDDING_API_MODEL,
    EMBEDDING_BASE_URL,
    EMBEDDING_LOCAL_MODEL,
    EMBEDDING_PROVIDER,
    HF_ENDPOINT,
)
from .embeddings import create_embedding_provider
from .intent import IntentExtractor, IntentResult
from .models import Book
from .vector_store import HybridVectorStore


class SafeSearchEngine:
    """Semantic search engine with risk-avoidance filtering.

    Combines:
      - Dense + sparse hybrid retrieval (ChromaDB + BM25)
      - LLM intent extraction with few-shot prompting
      - 5-dimension risk scoring (rules + LLM)
      - Avoid-tag and risk-threshold filtering

    If the embedding model cannot be downloaded (e.g. HuggingFace blocked),
    the engine falls back to BM25-only sparse retrieval automatically.
    """

    def __init__(self) -> None:
        if not API_KEY:
            raise RuntimeError(
                "DEEPSEEK_API_KEY is not set. Copy .env.example to .env and fill in your key."
            )

        self._client = OpenAI(api_key=API_KEY, base_url=DEEPSEEK_BASE_URL)
        self._dense_enabled = True

        # Set HF mirror before importing sentence-transformers
        if HF_ENDPOINT:
            os.environ.setdefault("HF_ENDPOINT", HF_ENDPOINT)

        try:
            embedding = create_embedding_provider(
                provider_type=EMBEDDING_PROVIDER,
                local_model=EMBEDDING_LOCAL_MODEL,
                api_key=EMBEDDING_API_KEY,
                api_base_url=EMBEDDING_BASE_URL,
                api_model=EMBEDDING_API_MODEL,
            )
            self._store = HybridVectorStore(
                persist_dir=CHROMA_PERSIST_DIR,
                embedding_provider=embedding,
            )
        except Exception as e:
            print(
                f"[SafeSearch] Dense embedding unavailable: {e}\n"
                f"  Falling back to BM25 keyword search only.\n"
                f"  Set HF_ENDPOINT=https://hf-mirror.com in .env and retry.",
                file=sys.stderr,
            )
            self._dense_enabled = False
            # Create store without embedding — will use sparse-only retrieval
            self._store = HybridVectorStore(
                persist_dir=CHROMA_PERSIST_DIR,
                embedding_provider=None,  # type: ignore[arg-type]
            )

        self._intent = IntentExtractor(client=self._client, model=CHAT_MODEL)

    # -- Index management ---------------------------------------------------

    def index_books(self, books: List[Book]) -> None:
        """Add or update books in the persistent index."""
        self._store.add_books(books)

    def remove_book(self, book_id: str) -> None:
        self._store.delete_book(book_id)

    @property
    def store(self) -> HybridVectorStore:
        return self._store

    # -- Intent extraction --------------------------------------------------

    def extract_intent(self, query: str) -> IntentResult:
        """Extract structured search intent from a natural-language query."""
        return self._intent.extract(query)

    # -- Search -------------------------------------------------------------

    def search(
        self,
        query: str,
        avoid_tags: Optional[List[str]] = None,
        top_k: int = 10,
        books: Optional[List[Book]] = None,
    ) -> Dict[str, object]:
        """Full search pipeline: intent → retrieval → risk scoring → filtering.

        If `books` is provided, they are indexed before searching (ad-hoc mode).
        Otherwise, the persistent index is used.

        Returns a dict with keys:
          - query_intent: structured IntentResult as dict
          - retrieval_candidates: top-K raw results before filtering
          - risk_scores: per-candidate risk dimension scores
          - filtered_results: safe recommendations with final scores
          - blocked_results: blocked books with reasons
          - data_gaps: books with missing metadata
        """
        avoid_tags = avoid_tags or []

        # Ad-hoc mode: temporary index from provided books
        if books is not None:
            self._store.add_books(books)

        # Step 1: Extract intent
        intent = self._intent.extract(query)

        # Step 2: Build enriched query and metadata filter from intent
        enriched_query = self._intent.build_search_query(query, intent)
        metadata_filter = self._intent.build_metadata_filter(intent)

        # Step 3: Hybrid retrieval (or sparse-only fallback)
        retrieval_top_k = max(top_k * 2, 20)
        if self._dense_enabled:
            ranked = self._store.query_hybrid(
                enriched_query, retrieval_top_k, dense_weight=0.7, where=metadata_filter
            )
            if not ranked:
                ranked = self._store.query_hybrid(
                    enriched_query, retrieval_top_k, dense_weight=0.7
                )
        else:
            ranked = self._store.query_sparse(enriched_query, retrieval_top_k)
            if not ranked:
                ranked = self._store.query_sparse(query, retrieval_top_k)

        candidates = [book for book, _ in ranked]

        # Build retrieval_candidates output
        retrieval_candidates = [
            {
                "id": book.id,
                "title": book.title,
                "similarity": round(score, 4),
                "matched_fields": ["title", "intro", "tags"],
            }
            for book, score in ranked
        ]

        # Step 4: Intent-aware reranking
        intent_scores = {
            book.id: self._intent.score_candidate(book, intent)
            for book in candidates
        }

        # Step 5: Risk scoring + filtering
        risk_scores: List[dict] = []
        filtered_results: List[dict] = []
        blocked_results: List[dict] = []
        data_gaps: List[dict] = []

        for i, book in enumerate(candidates):
            # Risk scoring
            risk = score_risks(
                client=self._client,
                model=CHAT_MODEL,
                title=book.title,
                intro=book.intro,
                tags=book.tags,
                sentiment_summary=book.sentiment_summary,
            )
            scores = risk["scores"]
            risk_scores.append({
                "id": book.id,
                **scores,
                "evidence": risk["evidence"],
            })

            # Determine blocking reasons
            blocked_by: List[str] = []
            for tag in avoid_tags:
                if tag.lower() in [t.lower() for t in book.tags]:
                    blocked_by.append(f"tag:{tag}")

            for dim, score in scores.items():
                if score >= 0.7:
                    blocked_by.append(f"risk:{dim}>{score:.2f}")

            if blocked_by:
                blocked_results.append({
                    "id": book.id,
                    "title": book.title,
                    "blocked_by": blocked_by,
                })
            else:
                # Combine similarity, intent match, and risk penalty
                sim_score = ranked[i][1] if i < len(ranked) else 0.0
                intent_score = intent_scores.get(book.id, 0.5)
                risk_penalty = sum(scores.values()) / len(scores)
                final_score = round(
                    max(0.0, 0.4 * sim_score + 0.3 * intent_score + 0.3 * (1.0 - risk_penalty)),
                    4,
                )
                filtered_results.append({
                    "id": book.id,
                    "title": book.title,
                    "final_score": final_score,
                    "similarity_score": round(sim_score, 4),
                    "intent_match": round(intent_score, 4),
                    "risk_penalty": round(risk_penalty, 4),
                    "reasons_recommend": self._build_recommend_reasons(intent, book),
                    "reasons_risk": [
                        f"{dim}:{score:.2f}"
                        for dim, score in scores.items()
                        if score >= 0.4
                    ],
                })

            # Data gaps
            missing: List[str] = []
            if not book.status:
                missing.append("ending_status")
            if not book.sentiment_summary:
                missing.append("public_opinion_summary")
            if missing:
                data_gaps.append({
                    "id": book.id,
                    "missing": missing,
                    "suggestion": "add status or sentiment summary for better filtering",
                })

        # Sort filtered results by final_score descending
        filtered_results.sort(key=lambda r: r["final_score"], reverse=True)
        filtered_results = filtered_results[:top_k]

        return {
            "query_intent": {
                "summary": intent.summary,
                "topics": intent.topics,
                "style": intent.style,
                "protagonist_traits": intent.protagonist_traits,
                "mood": intent.mood,
                "constraints": intent.constraints,
            },
            "retrieval_candidates": retrieval_candidates,
            "risk_scores": risk_scores,
            "filtered_results": filtered_results,
            "blocked_results": blocked_results,
            "data_gaps": data_gaps,
        }

    def _build_recommend_reasons(
        self, intent: IntentResult, book: Book
    ) -> List[str]:
        """Generate recommendation reasons based on intent match."""
        reasons: List[str] = []
        book_text = f"{book.intro} {' '.join(book.tags)}"

        matched_topics = [t for t in intent.topics if t in book.tags or t in book_text]
        if matched_topics:
            reasons.append(f"topics_matched:{','.join(matched_topics[:3])}")

        if intent.style:
            matched_style = [s for s in intent.style if s in book_text]
            if matched_style:
                reasons.append(f"style_matched:{','.join(matched_style[:2])}")

        if book.status == "completed":
            reasons.append("completed")

        if not reasons:
            reasons.append("semantic_match")
        return reasons
