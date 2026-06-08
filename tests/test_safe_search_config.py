"""Tests for safe_search.config — env-based configuration.

The conftest.py sets several env vars (DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL,
DEEPSEEK_CHAT_MODEL, EMBEDDING_PROVIDER, etc.).  These tests verify that the
config module reads the environment correctly and that hard-coded defaults
are applied when env vars are absent.
"""

import importlib
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Pre-register modules that engine.py depends on but aren't relevant to
# these tests. This avoids ImportError during safe_search package init.
sys.modules["sentiment_critic"] = MagicMock()
sys.modules["sentiment_critic.critic"] = MagicMock()

import safe_search.config as config


# ---------------------------------------------------------------------------
# Values sourced from environment (set by conftest)
# ---------------------------------------------------------------------------

class TestConfigFromEnv:
    """Values that should reflect what conftest placed in the environment."""

    def test_api_key_read_from_environment(self) -> None:
        """DEEPSEEK_API_KEY is set by conftest to a test value."""
        assert config.API_KEY == "sk-test-key-for-unit-tests"

    def test_deepseek_base_url_from_env(self) -> None:
        """DEEPSEEK_BASE_URL is set by conftest."""
        assert config.DEEPSEEK_BASE_URL == "https://api.deepseek.com"

    def test_chat_model_from_env(self) -> None:
        """DEEPSEEK_CHAT_MODEL is set by conftest (overrides default)."""
        assert config.CHAT_MODEL == "deepseek-test-model"

    def test_embedding_provider_from_env(self) -> None:
        """EMBEDDING_PROVIDER is set to 'api' by conftest."""
        assert config.EMBEDDING_PROVIDER == "api"


# ---------------------------------------------------------------------------
# Default values (when env var is not set)
# ---------------------------------------------------------------------------

class TestConfigDefaults:
    """Test module-level defaults by removing relevant env vars and reloading."""

    # Keys that influence config module values
    _CONFIG_ENV_KEYS = [
        "DEEPSEEK_BASE_URL",
        "DEEPSEEK_CHAT_MODEL",
        "DEEPSEEK_API_KEY",
        "EMBEDDING_PROVIDER",
        "EMBEDDING_LOCAL_MODEL",
        "EMBEDDING_API_KEY",
        "EMBEDDING_BASE_URL",
        "CHROMA_PERSIST_DIR",
        "HF_ENDPOINT",
    ]

    @pytest.fixture
    def reload_clean(self) -> None:
        """Remove *all* config-related env vars, reload config, yield.

        After the test, restore the original env and reload again so that
        subsequent tests see the conftest environment.
        """
        saved: dict[str, str] = {}
        for key in self._CONFIG_ENV_KEYS:
            if key in os.environ:
                saved[key] = os.environ.pop(key)

        # Patch dotenv.load_dotenv at the source so that during
        # importlib.reload the from-import re-binding also gets the mock.
        with patch("dotenv.load_dotenv"):
            importlib.reload(config)
        yield

        os.environ.update(saved)
        importlib.reload(config)

    def test_deepseek_base_url_default(self, reload_clean: None) -> None:
        assert config.DEEPSEEK_BASE_URL == "https://api.deepseek.com"

    def test_chat_model_default(self, reload_clean: None) -> None:
        assert config.CHAT_MODEL == "deepseek-v4-pro"

    def test_api_key_none_when_unset(self, reload_clean: None) -> None:
        """With DEEPSEEK_API_KEY absent, API_KEY must be None."""
        assert config.API_KEY is None

    def test_embedding_provider_defaults_to_local(self, reload_clean: None) -> None:
        assert config.EMBEDDING_PROVIDER == "local"

    def test_chroma_persist_dir_is_valid_path_string(
        self, reload_clean: None
    ) -> None:
        """CHROMA_PERSIST_DIR must be a non-empty string representing a path."""
        path = config.CHROMA_PERSIST_DIR
        assert isinstance(path, str)
        assert len(path) > 0
        # It should be an absolute or relative path with 'chroma' in it
        assert "chroma" in path

    def test_hf_endpoint_default(self, reload_clean: None) -> None:
        assert config.HF_ENDPOINT == "https://hf-mirror.com"

    def test_embedding_local_model_default(self, reload_clean: None) -> None:
        assert config.EMBEDDING_LOCAL_MODEL == "BAAI/bge-small-zh-v1.5"

    def test_embedding_api_key_falls_back_to_api_key(
        self, reload_clean: None
    ) -> None:
        """When EMBEDDING_API_KEY is not set, it falls back to API_KEY (which
        is also None in a clean env)."""
        assert config.EMBEDDING_API_KEY is None

    def test_embedding_base_url_falls_back_to_deepseek_base_url(
        self, reload_clean: None
    ) -> None:
        assert config.EMBEDDING_BASE_URL == "https://api.deepseek.com"

    def test_embedding_api_model_default(self, reload_clean: None) -> None:
        assert config.EMBEDDING_API_MODEL == "text-embedding-3-small"


# ---------------------------------------------------------------------------
# Typing
# ---------------------------------------------------------------------------

class TestConfigTypes:
    """All config values must be strings (or None for optional keys)."""

    def test_deepseek_base_url_is_str(self) -> None:
        assert isinstance(config.DEEPSEEK_BASE_URL, str)

    def test_chat_model_is_str(self) -> None:
        assert isinstance(config.CHAT_MODEL, str)

    def test_api_key_is_str_or_none(self) -> None:
        assert config.API_KEY is None or isinstance(config.API_KEY, str)

    def test_embedding_provider_is_str(self) -> None:
        assert isinstance(config.EMBEDDING_PROVIDER, str)

    def test_chroma_persist_dir_is_str(self) -> None:
        assert isinstance(config.CHROMA_PERSIST_DIR, str)

    def test_hf_endpoint_is_str(self) -> None:
        assert isinstance(config.HF_ENDPOINT, str)
