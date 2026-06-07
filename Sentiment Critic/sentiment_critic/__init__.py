"""Sentiment Critic — 舆情采集、分析与看板展示模块。

Provides:
  - Multi-platform review crawling (douban/tieba/xiaohongshu)
  - Zero-shot sentiment analysis via LLM + heuristic fallback
  - Multi-dimension scoring (style/logic/character/update/toxicity)
  - REST API for integration (port 8003)
  - Interactive HTML dashboard
"""

__all__ = [
    "agent_client",
    "analyzer",
    "artifacts",
    "collectors",
    "dashboard",
    "douban",
    "mock_server",
    "models",
    "rag_engine",
    "get_rag_engine",
    "get_vector_store",
    "get_knowledge_base",
    "sentiment_api",
    "tieba",
    "xiaohongshu",
]
