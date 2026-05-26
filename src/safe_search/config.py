import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
_env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(_env_path)

# DeepSeek API
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
CHAT_MODEL = os.getenv("DEEPSEEK_CHAT_MODEL", "deepseek-v4-pro")
API_KEY = os.getenv("DEEPSEEK_API_KEY")

# Embedding provider: "local" (sentence-transformers) or "api" (OpenAI-compatible)
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "local")

# Local embedding settings
EMBEDDING_LOCAL_MODEL = os.getenv("EMBEDDING_LOCAL_MODEL", "BAAI/bge-small-zh-v1.5")

# API embedding settings (used when EMBEDDING_PROVIDER == "api")
EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY", API_KEY)
EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL", DEEPSEEK_BASE_URL)
EMBEDDING_API_MODEL = os.getenv("EMBEDDING_API_MODEL", "text-embedding-3-small")

# ChromaDB persistence
CHROMA_PERSIST_DIR = os.getenv(
    "CHROMA_PERSIST_DIR",
    str(Path(__file__).resolve().parents[2] / "data" / "chroma"),
)

# HuggingFace mirror (for users in China)
HF_ENDPOINT = os.getenv("HF_ENDPOINT", "https://hf-mirror.com")
