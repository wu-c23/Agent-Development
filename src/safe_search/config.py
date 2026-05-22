import os

DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
CHAT_MODEL = os.getenv("DEEPSEEK_CHAT_MODEL", "deepseek-v4-pro")
EMBEDDING_MODEL = os.getenv("DEEPSEEK_EMBEDDING_MODEL", "text-embedding-3-large")
API_KEY = os.getenv("DEEPSEEK_API_KEY")

CHROMA_PATH = os.getenv("CHROMA_PATH", "data/chroma")
COLLECTION_NAME = os.getenv("CHROMA_COLLECTION", "novels")
