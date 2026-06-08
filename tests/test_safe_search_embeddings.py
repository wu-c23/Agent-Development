"""Tests for safe_search.embeddings — provider factory and API provider.

LocalEmbeddingProvider is tested only via the factory with a patched
sentence-transformers to avoid downloading models.  APIEmbeddingProvider
is tested with a mocked ``openai.OpenAI`` client so no real HTTP calls
are made.
"""

import sys
from unittest.mock import MagicMock, patch

import pytest

# Pre-register modules that engine.py depends on but aren't relevant to
# these tests. This avoids ImportError during safe_search package init.
sys.modules["sentiment_critic"] = MagicMock()
sys.modules["sentiment_critic.critic"] = MagicMock()

from safe_search.embeddings import (
    APIEmbeddingProvider,
    EmbeddingProvider,
    LocalEmbeddingProvider,
    create_embedding_provider,
)


# ===================================================================
# create_embedding_provider — factory function
# ===================================================================

class TestCreateEmbeddingProvider:
    """Coverage: factory dispatches to the correct provider class."""

    def test_type_api_returns_api_provider(self) -> None:
        """Factory with type='api' and a valid api_key returns an
        APIEmbeddingProvider."""
        with patch("openai.OpenAI"):
            provider = create_embedding_provider(
                provider_type="api", api_key="sk-valid"
            )
        assert isinstance(provider, APIEmbeddingProvider)
        assert isinstance(provider, EmbeddingProvider)

    def test_type_api_passes_arguments(self) -> None:
        """Arguments are forwarded to APIEmbeddingProvider."""
        with patch("openai.OpenAI") as mock_openai:
            provider = create_embedding_provider(
                provider_type="api",
                api_key="sk-custom",
                api_base_url="https://custom.example.com/v1",
                api_model="custom-model",
            )
        # After __init__, the provider should have the client and model set
        assert provider._model == "custom-model"
        # OpenAI should have been called with the correct args
        mock_openai.assert_called_once_with(
            api_key="sk-custom", base_url="https://custom.example.com/v1"
        )

    def test_type_api_uses_defaults(self) -> None:
        """When optional args are omitted, defaults are used."""
        with patch("openai.OpenAI") as mock_openai:
            provider = create_embedding_provider(
                provider_type="api", api_key="sk-key"
            )
        mock_openai.assert_called_once_with(
            api_key="sk-key", base_url="https://api.deepseek.com"
        )
        assert provider._model == "text-embedding-3-small"

    def test_type_api_raises_on_missing_key(self) -> None:
        """Factory must raise ValueError when api_key is None/empty."""
        with pytest.raises(ValueError, match="EMBEDDING_API_KEY is required"):
            create_embedding_provider(provider_type="api", api_key=None)

        with pytest.raises(ValueError, match="EMBEDDING_API_KEY is required"):
            create_embedding_provider(provider_type="api", api_key="")

    def test_type_local_returns_local_provider(self) -> None:
        """Factory with type='local' returns a LocalEmbeddingProvider."""
        with patch(
            "sentence_transformers.SentenceTransformer"
        ) as mock_st:
            mock_instance = mock_st.return_value
            mock_instance.get_sentence_embedding_dimension.return_value = 512

            provider = create_embedding_provider(provider_type="local")

        assert isinstance(provider, LocalEmbeddingProvider)
        assert isinstance(provider, EmbeddingProvider)

    def test_type_local_passes_model_name(self) -> None:
        """The local_model argument is forwarded to SentenceTransformer."""
        with patch(
            "sentence_transformers.SentenceTransformer"
        ) as mock_st:
            mock_instance = mock_st.return_value
            mock_instance.get_sentence_embedding_dimension.return_value = 512

            create_embedding_provider(
                provider_type="local",
                local_model="custom/model-name",
            )

        mock_st.assert_called_once_with("custom/model-name")

    def test_type_defaults_to_local(self) -> None:
        """Calling without provider_type defaults to local."""
        with patch(
            "sentence_transformers.SentenceTransformer"
        ) as mock_st:
            mock_instance = mock_st.return_value
            mock_instance.get_sentence_embedding_dimension.return_value = 512

            provider = create_embedding_provider()

        assert isinstance(provider, LocalEmbeddingProvider)


# ===================================================================
# APIEmbeddingProvider
# ===================================================================

class TestAPIEmbeddingProvider:
    """Coverage: embed returns list-of-lists, dim returns dimension."""

    def _make_provider(self, mock_openai_cls: MagicMock) -> APIEmbeddingProvider:
        """Helper — create an APIEmbeddingProvider with the given mock
        already installed as openai.OpenAI."""
        client = MagicMock()
        mock_openai_cls.return_value = client
        provider = APIEmbeddingProvider(
            base_url="https://api.test.com",
            api_key="sk-test",
            model="test-model",
        )
        # Attach the client mock to the provider so tests can configure
        # return values after construction.
        provider._client_mock = client
        return provider

    # -- embed -------------------------------------------------------

    def test_embed_returns_list_of_lists(self) -> None:
        """embed() must return a list where each element is a list of floats."""
        with patch("openai.OpenAI") as mock_openai_cls:
            provider = self._make_provider(mock_openai_cls)
            client = provider._client_mock

            # Configure the mock response
            item1 = MagicMock()
            item1.embedding = [0.1, 0.2, 0.3]
            item2 = MagicMock()
            item2.embedding = [0.4, 0.5, 0.6]
            client.embeddings.create.return_value = MagicMock(
                data=[item1, item2]
            )

            result = provider.embed(["text one", "text two"])

        assert isinstance(result, list)
        assert len(result) == 2
        for vec in result:
            assert isinstance(vec, list)
            for val in vec:
                assert isinstance(val, float)

    def test_embed_dimension_inferred(self) -> None:
        """After embed(), dim() returns the length of the first embedding."""
        with patch("openai.OpenAI") as mock_openai_cls:
            provider = self._make_provider(mock_openai_cls)
            client = provider._client_mock

            item = MagicMock()
            item.embedding = [0.0] * 768  # 768-dim
            client.embeddings.create.return_value = MagicMock(data=[item])

            assert provider._dim is None
            provider.embed(["probe"])
            assert provider.dim() == 768

    def test_embed_single_text(self) -> None:
        """embed works with a single text string in the list."""
        with patch("openai.OpenAI") as mock_openai_cls:
            provider = self._make_provider(mock_openai_cls)
            client = provider._client_mock

            item = MagicMock()
            item.embedding = [0.5, 0.5]
            client.embeddings.create.return_value = MagicMock(data=[item])

            result = provider.embed(["hello"])
            assert len(result) == 1
            assert result[0] == [0.5, 0.5]

    def test_embed_empty_list(self) -> None:
        """embed([]) returns an empty list safely."""
        with patch("openai.OpenAI") as mock_openai_cls:
            provider = self._make_provider(mock_openai_cls)
            client = provider._client_mock

            client.embeddings.create.return_value = MagicMock(data=[])

            result = provider.embed([])
            assert result == []

    # -- dim ---------------------------------------------------------

    def test_dim_after_construction_is_none(self) -> None:
        """Before any embedding call, _dim is None."""
        with patch("openai.OpenAI") as mock_openai_cls:
            provider = self._make_provider(mock_openai_cls)
            assert provider._dim is None

    def test_dim_triggers_embed_when_unset(self) -> None:
        """Calling dim() for the first time triggers an embed probe."""
        with patch("openai.OpenAI") as mock_openai_cls:
            provider = self._make_provider(mock_openai_cls)
            client = provider._client_mock

            item = MagicMock()
            item.embedding = [0.0] * 256
            client.embeddings.create.return_value = MagicMock(data=[item])

            dim = provider.dim()
            assert dim == 256
            # embed was called with ["dim probe"]
            client.embeddings.create.assert_called_with(
                model="test-model", input=["dim probe"]
            )

    def test_dim_returns_cached_value(self) -> None:
        """Once _dim is set, dim() returns it without calling embed again."""
        with patch("openai.OpenAI") as mock_openai_cls:
            provider = self._make_provider(mock_openai_cls)
            client = provider._client_mock

            item = MagicMock()
            item.embedding = [0.0] * 128
            client.embeddings.create.return_value = MagicMock(data=[item])

            # First call triggers embed
            assert provider.dim() == 128
            assert client.embeddings.create.call_count == 1

            # Second call should use cache, not call embed
            assert provider.dim() == 128
            assert client.embeddings.create.call_count == 1

    def test_dim_returns_zero_when_embed_fails(self) -> None:
        """If embed returns no data, dim() returns 0 (edge case)."""
        with patch("openai.OpenAI") as mock_openai_cls:
            provider = self._make_provider(mock_openai_cls)
            client = provider._client_mock

            # Embed with data that has no items
            client.embeddings.create.return_value = MagicMock(data=[])

            # dim() calls embed internally, but embed won't set _dim
            # because data is empty; _dim stays None, returns 0
            assert provider.dim() == 0


# ===================================================================
# LocalEmbeddingProvider (via factory, mocked)
# ===================================================================

class TestLocalEmbeddingProvider:
    """Coverage: factory creates LocalEmbeddingProvider with mocked ST."""

    def test_create_via_factory(self) -> None:
        with patch(
            "sentence_transformers.SentenceTransformer"
        ) as mock_st:
            mock_instance = mock_st.return_value
            mock_instance.get_sentence_embedding_dimension.return_value = 384

            provider = create_embedding_provider(provider_type="local")

        assert isinstance(provider, LocalEmbeddingProvider)
        assert provider.dim() == 384

    def test_create_directly(self) -> None:
        with patch(
            "sentence_transformers.SentenceTransformer"
        ) as mock_st:
            mock_instance = mock_st.return_value
            mock_instance.get_sentence_embedding_dimension.return_value = 512

            provider = LocalEmbeddingProvider(model_name="any/model")

        mock_st.assert_called_once_with("any/model")
        assert provider.dim() == 512

    def test_embed_with_mock(self) -> None:
        with patch(
            "sentence_transformers.SentenceTransformer"
        ) as mock_st:
            mock_instance = mock_st.return_value
            mock_instance.get_sentence_embedding_dimension.return_value = 4

            # Make encode() return an object with a .tolist() method
            fake_embeddings = MagicMock()
            fake_embeddings.tolist.return_value = [[0.1, 0.2, 0.3, 0.4]]
            mock_instance.encode.return_value = fake_embeddings

            provider = LocalEmbeddingProvider(model_name="test-model")
            result = provider.embed(["hello"])

        assert isinstance(result, list)
        assert len(result) == 1
        assert len(result[0]) == 4
        assert isinstance(result[0], list)
        assert all(isinstance(v, float) for v in result[0])


# ===================================================================
# Abstract base
# ===================================================================

class TestEmbeddingProviderABC:
    """Verify the ABC cannot be instantiated directly."""

    def test_cannot_instantiate_abstract(self) -> None:
        with pytest.raises(TypeError):
            EmbeddingProvider()  # type: ignore[abstract]

    def test_api_provider_concrete(self) -> None:
        """APIEmbeddingProvider is a concrete subclass."""
        with patch("openai.OpenAI"):
            provider = APIEmbeddingProvider(
                base_url="x", api_key="y", model="z"
            )
        assert isinstance(provider, EmbeddingProvider)

    def test_local_provider_concrete(self) -> None:
        """LocalEmbeddingProvider is a concrete subclass."""
        with patch("sentence_transformers.SentenceTransformer") as mock_st:
            mock_st.return_value.get_sentence_embedding_dimension.return_value = 1
            provider = LocalEmbeddingProvider("test")
        assert isinstance(provider, EmbeddingProvider)
