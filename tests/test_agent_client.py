"""Tests for review_critic.agent_client — config, client, env parsing, JSON extraction."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from review_critic import agent_client as ac


# ===================================================================
# chat_completions_endpoint
# ===================================================================


class TestChatCompletionsEndpoint:
    def test_appends_chat_completions(self):
        assert ac.chat_completions_endpoint("https://api.deepseek.com") == "https://api.deepseek.com/chat/completions"

    def test_does_not_duplicate(self):
        assert (
            ac.chat_completions_endpoint("https://api.deepseek.com/chat/completions")
            == "https://api.deepseek.com/chat/completions"
        )

    def test_strips_trailing_slash(self):
        assert ac.chat_completions_endpoint("https://api.deepseek.com/") == "https://api.deepseek.com/chat/completions"


# ===================================================================
# is_placeholder_value
# ===================================================================


class TestIsPlaceholderValue:
    def test_known_placeholders(self):
        for val in ("", "your_key_here", "your-deepseek-api-key-here", "sk-your-deepseek-api-key-here", "你的 key", "your-api-key", "your_api_key"):
            assert ac.is_placeholder_value(val) is True

    def test_real_key_not_placeholder(self):
        assert ac.is_placeholder_value("sk-real-key-12345") is False

    def test_none_is_placeholder(self):
        assert ac.is_placeholder_value(None) is True


# ===================================================================
# strip_env_value
# ===================================================================


class TestStripEnvValue:
    def test_strips_double_quotes(self):
        assert ac.strip_env_value('"some_value"') == "some_value"

    def test_strips_single_quotes(self):
        assert ac.strip_env_value("'some_value'") == "some_value"

    def test_no_quotes(self):
        assert ac.strip_env_value("some_value") == "some_value"

    def test_unmatched_quote_unchanged(self):
        assert ac.strip_env_value('"unmatched') == '"unmatched'

    def test_single_char_unchanged(self):
        assert ac.strip_env_value('"') == '"'


# ===================================================================
# extract_json_object
# ===================================================================


class TestExtractJsonObject:
    def test_plain_json(self):
        assert ac.extract_json_object('{"key": "value"}') == {"key": "value"}

    def test_json_with_markdown_fence(self):
        text = '```json\n{"key": "value"}\n```'
        assert ac.extract_json_object(text) == {"key": "value"}

    def test_json_with_surrounding_text(self):
        text = 'Here is the result: {"result": "ok"} thank you'
        assert ac.extract_json_object(text) == {"result": "ok"}

    def test_extracts_embedded_json(self):
        text = 'Some text before {"nested": {"a": 1}} and after'
        assert ac.extract_json_object(text) == {"nested": {"a": 1}}

    def test_raises_on_no_json(self):
        with pytest.raises((json.JSONDecodeError, ValueError)):
            ac.extract_json_object("no json here")

    def test_raises_on_empty(self):
        with pytest.raises((json.JSONDecodeError, ValueError)):
            ac.extract_json_object("")


# ===================================================================
# retry_after_seconds
# ===================================================================


class TestRetryAfterSeconds:
    def test_exponential_backoff(self):
        with patch("urllib.error.HTTPError") as MockHTTPError:
            exc = MagicMock()
            exc.headers = {}
            # No Retry-After header, falls back to exponential
            r0 = ac.retry_after_seconds(None, 0)
            r1 = ac.retry_after_seconds(None, 1)
            r2 = ac.retry_after_seconds(None, 2)
            assert r0 <= r1 <= r2
            assert r0 > 0

    def test_uses_retry_after_header(self):
        exc = MagicMock()
        exc.headers = {"Retry-After": "5"}
        result = ac.retry_after_seconds(exc, 0)
        assert result == 5.0

    def test_clamps_retry_after(self):
        exc = MagicMock()
        exc.headers = {"Retry-After": "999"}
        result = ac.retry_after_seconds(exc, 0)
        assert result == 120.0  # clamped to 120

    def test_invalid_retry_after_falls_back(self):
        exc = MagicMock()
        exc.headers = {"Retry-After": "not-a-number"}
        result = ac.retry_after_seconds(exc, 0)
        assert 1.0 <= result <= 120.0


# ===================================================================
# parse_env_file
# ===================================================================


class TestParseEnvFile:
    def test_parses_key_value(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("KEY=value\nFOO=bar\n", encoding="utf-8")
        result = ac.parse_env_file(env_file)
        assert result == {"KEY": "value", "FOO": "bar"}

    def test_skips_comments_and_empty_lines(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("# comment\n\nKEY=val\n", encoding="utf-8")
        result = ac.parse_env_file(env_file)
        assert result == {"KEY": "val"}

    def test_skips_lines_without_equals(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("KEY=val\njust_a_line\n", encoding="utf-8")
        result = ac.parse_env_file(env_file)
        assert result == {"KEY": "val"}

    def test_strips_quotes_from_value(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text('KEY="quoted_val"\n', encoding="utf-8")
        result = ac.parse_env_file(env_file)
        assert result == {"KEY": "quoted_val"}

    def test_handles_equals_in_value(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("KEY=val=with=equals\n", encoding="utf-8")
        result = ac.parse_env_file(env_file)
        assert result == {"KEY": "val=with=equals"}


# ===================================================================
# AgentClientConfig
# ===================================================================


class TestAgentClientConfig:
    def test_from_env_loads_env_vars(self):
        with patch.object(ac, "load_env_files") as mock_load:
            config = ac.AgentClientConfig.from_env()
            mock_load.assert_called_once()

    def test_endpoint_property(self):
        config = ac.AgentClientConfig(base_url="https://api.deepseek.com")
        assert config.endpoint == "https://api.deepseek.com/chat/completions"

    def test_masked_api_key_placeholder(self):
        config = ac.AgentClientConfig(api_key="")
        assert config.masked_api_key == "<missing or placeholder>"

    def test_masked_api_key_short(self):
        config = ac.AgentClientConfig(api_key="short")
        assert config.masked_api_key == "***"

    def test_masked_api_key_shows_prefix_suffix(self):
        config = ac.AgentClientConfig(api_key="sk-abcdefghijklmnopqr1234567890")
        assert config.masked_api_key == "sk-a...7890"

    def test_validation_errors_no_key(self):
        config = ac.AgentClientConfig(api_key="your_key_here", base_url="https://x.com", model="m")
        errors = config.validation_errors()
        assert any("api_key" in e.lower() or "API_KEY" in e for e in errors)

    def test_validation_errors_no_base_url(self):
        config = ac.AgentClientConfig(api_key="sk-real-key", base_url="", model="m")
        errors = config.validation_errors()
        assert any("base_url" in e.lower() or "BASE_URL" in e for e in errors)

    def test_validation_errors_no_model(self):
        config = ac.AgentClientConfig(api_key="sk-real-key", base_url="https://x.com", model="")
        errors = config.validation_errors()
        assert any("model" in e.lower() or "MODEL" in e for e in errors)

    def test_validation_no_errors(self):
        config = ac.AgentClientConfig(
            api_key="sk-real-key", base_url="https://api.deepseek.com", model="deepseek-test"
        )
        assert config.validation_errors() == []


# ===================================================================
# AgentClient
# ===================================================================


class TestAgentClient:
    def test_available_with_valid_config(self):
        config = ac.AgentClientConfig(
            api_key="sk-real-key", base_url="https://api.deepseek.com", model="deepseek-test"
        )
        client = ac.AgentClient(config=config)
        assert client.available is True

    def test_not_available_with_placeholder_key(self):
        config = ac.AgentClientConfig(
            api_key="", base_url="https://api.deepseek.com", model="deepseek-test"
        )
        client = ac.AgentClient(config=config)
        assert client.available is False

    def test_chat_json_returns_parsed_content(self):
        # Build a realistic API response
        inner_content = json.dumps({"result": "ok", "score": 0.95})
        api_response = {
            "choices": [{"message": {"content": inner_content}, "finish_reason": "stop"}],
            "model": "test",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(api_response).encode("utf-8")
        mock_response.__enter__.return_value = mock_response
        mock_response.headers = {}

        config = ac.AgentClientConfig(
            api_key="sk-real-key", base_url="https://api.deepseek.com", model="deepseek-test"
        )
        client = ac.AgentClient(config=config)

        with patch("review_critic.agent_client.urlopen", return_value=mock_response):
            result = client.chat_json("system prompt", "user prompt")
            assert result == {"result": "ok", "score": 0.95}

    def test_chat_json_raises_when_not_available(self):
        config = ac.AgentClientConfig(api_key="", base_url="", model="")
        client = ac.AgentClient(config=config)
        with pytest.raises(RuntimeError, match="missing"):
            client.chat_json("system", "user")

    def test_chat_json_handles_response_format_retry(self):
        # First call raises RuntimeError with "response_format", second succeeds
        inner_content = json.dumps({"result": "ok"})
        api_response = {"choices": [{"message": {"content": inner_content}}]}
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(api_response).encode("utf-8")
        mock_response.__enter__.return_value = mock_response
        mock_response.headers = {}

        config = ac.AgentClientConfig(
            api_key="sk-real-key", base_url="https://api.deepseek.com", model="deepseek-test"
        )
        client = ac.AgentClient(config=config)

        real_post = client._post

        def side_effect(payload):
            if "response_format" in payload:
                raise RuntimeError("response_format not supported")
            return real_post(payload)

        with patch.object(client, "_post", side_effect=side_effect):
            with patch("review_critic.agent_client.urlopen", return_value=mock_response):
                result = client.chat_json("system", "user")
                assert result == {"result": "ok"}


# ===================================================================
# load_env_files
# ===================================================================


class TestLoadEnvFiles:
    def test_load_env_files_calls_unified_and_local(self, tmp_path):
        with patch.object(ac, "load_env_file") as mock_load:
            with patch.object(ac, "unified_env_path", return_value=tmp_path / "Safe-Search Architect" / ".env"):
                ac.load_env_files()
                assert mock_load.call_count == 2


# ===================================================================
# Diagnostic lines
# ===================================================================


class TestDiagnosticLines:
    def test_diagnostic_lines_contain_key_info(self):
        config = ac.AgentClientConfig(
            api_key="sk-test-key-1234",
            base_url="https://api.test.com",
            model="test-model",
            sources={"DEEPSEEK_API_KEY": "test.env", "DEEPSEEK_BASE_URL": "test.env", "DEEPSEEK_CHAT_MODEL": "test.env"},
        )
        lines = config.diagnostic_lines()
        assert any("DEEPSEEK_API_KEY" in line for line in lines)
        assert any("DEEPSEEK_BASE_URL" in line for line in lines)
        assert any("DEEPSEEK_CHAT_MODEL" in line for line in lines)
        assert any("endpoint" in line for line in lines)
