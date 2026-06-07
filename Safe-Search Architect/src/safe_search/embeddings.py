"""Embedding provider abstraction for dense vector search.

Supports two backends:
  - LocalEmbeddingProvider: sentence-transformers, runs locally, no API cost
  - APIEmbeddingProvider: OpenAI-compatible /v1/embeddings endpoint
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List


class EmbeddingProvider(ABC):
    """Abstract embedding provider."""

    @abstractmethod
    def embed(self, texts: List[str]) -> List[List[float]]:
        """Return embeddings for each input text."""
        ...

    @abstractmethod
    def dim(self) -> int:
        """Return embedding dimension."""
        ...


class LocalEmbeddingProvider(EmbeddingProvider):
    """Local embeddings via sentence-transformers.

    Default model: BAAI/bge-small-zh-v1.5 — 512-dim, Chinese-optimized, ~100MB.

    Set HF_ENDPOINT env var to use a mirror, e.g. https://hf-mirror.com for China.
    """

    def __init__(self, model_name: str = "BAAI/bge-small-zh-v1.5") -> None:
        import os

        # Respect HF_ENDPOINT mirror (essential for users in China)
        hf_endpoint = os.environ.get("HF_ENDPOINT", "")
        if hf_endpoint:
            os.environ.setdefault("HF_ENDPOINT", hf_endpoint)

        from sentence_transformers import SentenceTransformer

        try:
            self._model = SentenceTransformer(model_name)
        except Exception as e:
            raise RuntimeError(
                f"Failed to download embedding model '{model_name}'.\n"
                f"  HuggingFace may be inaccessible from your network.\n"
                f"  Set HF_ENDPOINT=https://hf-mirror.com in .env to use a mirror.\n"
                f"  Or set EMBEDDING_PROVIDER=api to use a remote API instead.\n"
                f"  Original error: {e}"
            ) from e

        self._dim = self._model.get_sentence_embedding_dimension()

    def embed(self, texts: List[str]) -> List[List[float]]:
        embeddings = self._model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()

    def dim(self) -> int:
        return self._dim


class APIEmbeddingProvider(EmbeddingProvider):
    """OpenAI-compatible embeddings API (DeepSeek, OpenAI, etc.)."""

    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        # Infer dimension from first embedding call
        self._dim: int | None = None

    def embed(self, texts: List[str]) -> List[List[float]]:
        response = self._client.embeddings.create(model=self._model, input=texts)
        embeddings = [item.embedding for item in response.data]
        if self._dim is None and embeddings:
            self._dim = len(embeddings[0])
        return embeddings

    def dim(self) -> int:
        if self._dim is None:
            # Trigger a minimal embedding to infer dimension
            self.embed(["dim probe"])
        return self._dim or 0


def create_embedding_provider(
    provider_type: str = "local",
    local_model: str = "BAAI/bge-small-zh-v1.5",
    api_key: str | None = None,
    api_base_url: str | None = None,
    api_model: str | None = None,
) -> EmbeddingProvider:
    """Factory: create an embedding provider from configuration."""
    if provider_type == "api":
        if not api_key:
            raise ValueError("EMBEDDING_API_KEY is required for API embedding provider")
        return APIEmbeddingProvider(
            base_url=api_base_url or "https://api.deepseek.com",
            api_key=api_key,
            model=api_model or "text-embedding-3-small",
        )
    return LocalEmbeddingProvider(model_name=local_model)
