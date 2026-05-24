import os

DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
CHAT_MODEL = os.getenv("DEEPSEEK_CHAT_MODEL", "deepseek-v4-pro")
API_KEY = os.getenv("DEEPSEEK_API_KEY")
