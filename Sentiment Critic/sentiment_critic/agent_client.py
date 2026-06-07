"""Agent client for LLM-powered review analysis — 使用统一的 DeepSeek API.

从 ../Safe-Search Architect/.env 读取配置，所有模块共用同一套 API Key。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import json
import os
import socket
import time


ENV_SOURCES: dict[str, str] = {}
CONFIG_KEYS = (
    "DEEPSEEK_API_KEY",
    "DEEPSEEK_BASE_URL",
    "DEEPSEEK_CHAT_MODEL",
    "LLM_TIMEOUT",
    "LLM_RETRIES",
)
PLACEHOLDER_VALUES = {"", "your_key_here", "your-deepseek-api-key-here", "sk-your-deepseek-api-key-here", "你的 key", "your-api-key", "your_api_key"}


@dataclass
class AgentClientConfig:
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    timeout: int = 180
    retries: int = 2
    sources: dict[str, str] | None = None

    @classmethod
    def from_env(cls) -> "AgentClientConfig":
        load_env_files()
        return cls(
            api_key=os.getenv("DEEPSEEK_API_KEY", ""),
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            model=os.getenv("DEEPSEEK_CHAT_MODEL", "deepseek-v4-pro"),
            timeout=int(os.getenv("LLM_TIMEOUT", "180")),
            retries=int(os.getenv("LLM_RETRIES", "2")),
            sources=dict(ENV_SOURCES),
        )

    @property
    def endpoint(self) -> str:
        return chat_completions_endpoint(self.base_url)

    @property
    def masked_api_key(self) -> str:
        if is_placeholder_value(self.api_key):
            return "<missing or placeholder>"
        if len(self.api_key) <= 8:
            return "***"
        return f"{self.api_key[:4]}...{self.api_key[-4:]}"

    def validation_errors(self) -> list[str]:
        errors: list[str] = []
        if is_placeholder_value(self.api_key):
            errors.append("DEEPSEEK_API_KEY is missing or still a placeholder")
        if not self.base_url:
            errors.append("DEEPSEEK_BASE_URL is missing")
        if not self.model:
            errors.append("DEEPSEEK_CHAT_MODEL is missing")
        return errors

    def diagnostic_lines(self) -> list[str]:
        sources = self.sources or {}
        key_source = sources.get("DEEPSEEK_API_KEY", env_source_label("DEEPSEEK_API_KEY"))
        base_source = sources.get("DEEPSEEK_BASE_URL", env_source_label("DEEPSEEK_BASE_URL"))
        model_source = sources.get("DEEPSEEK_CHAT_MODEL", env_source_label("DEEPSEEK_CHAT_MODEL"))
        return [
            f"config DEEPSEEK_API_KEY={self.masked_api_key} ({key_source})",
            f"config DEEPSEEK_BASE_URL={self.base_url} ({base_source})",
            f"config DEEPSEEK_CHAT_MODEL={self.model} ({model_source})",
            f"config LLM_TIMEOUT={self.timeout}",
            f"config LLM_RETRIES={self.retries}",
            f"config endpoint={self.endpoint}",
        ]


class AgentClient:
    """OpenAI-compatible chat/completions client — 使用 DeepSeek API.

    从 Safe-Search Architect/.env 读取统一配置。
    """

    def __init__(self, config: AgentClientConfig | None = None) -> None:
        self.config = config or AgentClientConfig.from_env()

    @property
    def available(self) -> bool:
        return not self.config.validation_errors()

    def chat_json(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> dict[str, Any]:
        if not self.available:
            raise RuntimeError(
                "Agent client is missing DEEPSEEK_API_KEY/base_url/model. "
                "Fill Safe-Search Architect/.env with DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, and DEEPSEEK_CHAT_MODEL."
            )
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }
        try:
            raw = self._post(payload)
        except RuntimeError as exc:
            if "response_format" not in str(exc):
                raise
            payload.pop("response_format", None)
            raw = self._post(payload)
        content = raw["choices"][0]["message"]["content"]
        return extract_json_object(content)

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        endpoint = chat_completions_endpoint(self.config.base_url)
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}",
            "X-API-Key": self.config.api_key,
        }
        request = Request(endpoint, data=body, headers=headers, method="POST")
        last_error: Exception | None = None
        for attempt in range(self.config.retries + 1):
            try:
                with urlopen(request, timeout=self.config.timeout) as response:
                    return json.loads(response.read().decode("utf-8"))
            except HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="ignore")
                if exc.code in {429, 500, 502, 503, 504} and attempt < self.config.retries:
                    wait_seconds = retry_after_seconds(exc, attempt)
                    print(
                        f"[agent] HTTP {exc.code}; retry "
                        f"{attempt + 1}/{self.config.retries} after {wait_seconds:.1f}s"
                    )
                    time.sleep(wait_seconds)
                    last_error = RuntimeError(f"Agent HTTP {exc.code}: {detail}")
                    continue
                hint = ""
                if exc.code == 404:
                    hint = (
                        f" Endpoint not found: {endpoint}. "
                        "Check DEEPSEEK_BASE_URL in Safe-Search Architect/.env."
                    )
                raise RuntimeError(f"Agent HTTP {exc.code}:{hint} {detail}") from exc
            except (URLError, TimeoutError, socket.timeout) as exc:
                last_error = exc
                if attempt < self.config.retries:
                    wait_seconds = retry_after_seconds(None, attempt)
                    print(
                        f"[agent] request failed ({exc}); retry "
                        f"{attempt + 1}/{self.config.retries} after {wait_seconds:.1f}s"
                    )
                    time.sleep(wait_seconds)
                    continue
                raise RuntimeError(f"Agent request failed after retries: {exc}") from exc
            except (KeyError, json.JSONDecodeError) as exc:
                raise RuntimeError("Agent response is not an OpenAI-compatible JSON payload.") from exc
        raise RuntimeError(f"Agent request failed after retries: {last_error}")


def chat_completions_endpoint(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/chat/completions"


def load_env_files() -> None:
    """加载统一的 .env 文件 (Safe-Search Architect/.env)."""
    # 优先加载 Safe-Search Architect 下的统一 .env
    unified_env = unified_env_path()
    load_env_file(unified_env)
    # 兼容：也加载模块自身的 .env (优先级低于统一配置)
    load_env_file(".env")


def unified_env_path() -> Path:
    """返回统一 .env 路径: <项目根>/Safe-Search Architect/.env"""
    return project_root() / "Safe-Search Architect" / ".env"


def project_root() -> Path:
    """返回项目根目录 (网络小说大作业)."""
    return Path(__file__).resolve().parents[2]


def load_env_file(path: str | Path = ".env") -> None:
    target = Path(path)
    if not target.is_absolute():
        target = Path(__file__).resolve().parents[1] / target
    if not target.exists():
        return
    parsed = parse_env_file(target)
    for key, value in parsed.items():
        existing = os.environ.get(key)
        existing_source = ENV_SOURCES.get(key, env_source_label(key) if existing is not None else "")
        if should_set_env_value(key, existing, existing_source, value):
            os.environ[key] = value
            ENV_SOURCES[key] = str(target)


def parse_env_file(path: Path) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = strip_env_value(value.strip())
        if key:
            parsed[key] = value
    return parsed


def should_set_env_value(key: str, existing: str | None, existing_source: str, new_value: str) -> bool:
    if key not in CONFIG_KEYS:
        return existing is None
    if existing is None:
        return True
    if is_placeholder_value(existing) and not is_placeholder_value(new_value):
        return existing_source.endswith(".env") or existing_source == "environment"
    return False


def is_placeholder_value(value: str | None) -> bool:
    return (value or "").strip() in PLACEHOLDER_VALUES


def strip_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def env_source_label(key: str) -> str:
    return "environment" if key in os.environ else "default"


def retry_after_seconds(exc: HTTPError | None, attempt: int) -> float:
    if exc is not None:
        value = exc.headers.get("Retry-After")
        if value:
            try:
                return min(120.0, max(1.0, float(value)))
            except ValueError:
                pass
    return min(120.0, 8.0 * (2**attempt))


def extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(text[start : end + 1])
