import re
from typing import List, Tuple

import jieba
from rank_bm25 import BM25Okapi

from .models import Book


class BM25Index:
    def __init__(self) -> None:
        self._books: List[Book] = []
        self._bm25: BM25Okapi | None = None

    def build(self, books: List[Book]) -> None:
        self._books = books
        corpus = [self._tokenize(self._book_text(book)) for book in books]
        self._bm25 = BM25Okapi(corpus)

    def query(self, query: str, top_k: int) -> List[Tuple[Book, float]]:
        if not self._bm25:
            return []

        tokens = self._tokenize(query)
        scores = self._bm25.get_scores(tokens)
        ranked = sorted(enumerate(scores), key=lambda item: item[1], reverse=True)
        top = ranked[:top_k]
        normalized = self._normalize_scores([score for _, score in top])

        results: List[Tuple[Book, float]] = []
        for (idx, _), score in zip(top, normalized):
            results.append((self._books[idx], score))
        return results

    def _book_text(self, book: Book) -> str:
        return " ".join([book.title, book.intro, " ".join(book.tags)])

    def _tokenize(self, text: str) -> List[str]:
        text = text.lower()
        text = re.sub(r"\s+", " ", text)
        return [token for token in jieba.lcut(text) if token.strip()]

    def _normalize_scores(self, scores: List[float]) -> List[float]:
        if not scores:
            return []

        min_score = min(scores)
        max_score = max(scores)
        if max_score == min_score:
            return [1.0 for _ in scores]
        return [(score - min_score) / (max_score - min_score) for score in scores]
