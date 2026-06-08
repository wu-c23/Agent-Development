"""Shared fixtures and path configuration for all test files."""

import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure all source modules are importable
# ---------------------------------------------------------------------------
# IMPORTANT: sentiment_critic exists in both Safe-Search Architect/src/ and
# Sentiment Critic/. The latter has the full package (mock_server, data_store,
# rag_engine, etc.) while the former only has critic.py. Sentiment Critic/
# must be found FIRST so from sentiment_critic import * resolves correctly.
# Safe-Search test files must mock sentiment_critic.critic before importing.

_PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Safe-Search Architect — appended (lower priority for sentiment_critic)
_safe_search_src = _PROJECT_ROOT / "Safe-Search Architect" / "src"
_safe_search_src_str = str(_safe_search_src)
if _safe_search_src_str not in sys.path:
    sys.path.append(_safe_search_src_str)

# Sentiment Critic — inserted at front (takes priority for sentiment_critic)
_sentiment_dir = _PROJECT_ROOT / "Sentiment Critic"
_sentiment_dir_str = str(_sentiment_dir)
if _sentiment_dir_str not in sys.path:
    sys.path.insert(0, _sentiment_dir_str)

# Trend Explorer API — inserted at front too
_trend_api = _PROJECT_ROOT / "Trend Explorer" / "trend-api-spec"
_trend_api_str = str(_trend_api)
if _trend_api_str not in sys.path:
    sys.path.insert(0, _trend_api_str)

# ---------------------------------------------------------------------------
# Environment for tests (avoid loading real .env / hitting real APIs)
# ---------------------------------------------------------------------------

os.environ.setdefault("DEEPSEEK_API_KEY", "sk-test-key-for-unit-tests")
os.environ.setdefault("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
os.environ.setdefault("DEEPSEEK_CHAT_MODEL", "deepseek-test-model")
os.environ.setdefault("EMBEDDING_PROVIDER", "api")  # avoid downloading HF models
os.environ.setdefault("EMBEDDING_API_KEY", "sk-test-embed-key")
os.environ.setdefault("EMBEDDING_BASE_URL", "https://api.deepseek.com")
os.environ.setdefault("HF_ENDPOINT", "")
os.environ.setdefault("LLM_TIMEOUT", "10")
os.environ.setdefault("LLM_RETRIES", "1")
os.environ.setdefault("LLM_BATCH_DELAY", "0")

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

SAMPLE_BOOK_UID = "987a2b45c6bd2baa73d750f13daf15b63c20145de2e85fff22ada96ad3d8b27b"
SAMPLE_BOOK_TITLE = "诡秘之主"
SAMPLE_BOOK_AUTHOR = "爱潜水的乌贼"

SAMPLE_REVIEW_TEXT = (
    "这本书的文笔非常细腻，逻辑严密，伏笔回收做得很好。"
    "世界观构建顶级，角色智商在线。不过开头节奏偏慢，需要耐心。"
    "推荐给喜欢克苏鲁和悬疑的读者，入坑不亏。"
)

SAMPLE_SHORT_REVIEW = "好看推荐"


# ---------------------------------------------------------------------------
# Mock response helpers
# ---------------------------------------------------------------------------


def make_mock_chat_response(content: str) -> dict:
    """Create a fake OpenAI-compatible chat completions response."""
    return {
        "choices": [
            {
                "message": {"content": content},
                "finish_reason": "stop",
            }
        ],
        "model": "test-model",
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }


def make_mock_embedding_response(dim: int = 512) -> dict:
    """Create a fake OpenAI-compatible embeddings response."""
    return {
        "data": [{"embedding": [0.01] * dim, "index": 0}],
        "model": "test-embedding-model",
    }
