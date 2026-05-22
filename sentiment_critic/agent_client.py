from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import json
import os


@dataclass
class AgentClientConfig:
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    timeout: int = 90

    @classmethod
    def from_env(cls) -> "AgentClientConfig":
        load_env_file()
        return cls(
            api_key=os.getenv("EASYCOMPUTE_API_KEY") or os.getenv("OPENAI_API_KEY", ""),
            base_url=os.getenv("EASYCOMPUTE_BASE_URL")
            or os.getenv("OPENAI_BASE_URL")
            or "https://easycompute.cs.tsinghua.edu.cn/v1",
            model=os.getenv("EASYCOMPUTE_MODEL") or os.getenv("OPENAI_MODEL") or "DeepSeek-V4-Pro",
            timeout=int(os.getenv("EASYCOMPUTE_TIMEOUT", "90")),
        )


class AgentClient:
    """Small OpenAI-compatible chat/completions client.

    EasyCompute course pages commonly expose the key, model, and base URL separately.
    Keeping the client environment-driven makes the script work even if the exact
    path differs from the default.
    """

    def __init__(self, config: AgentClientConfig | None = None) -> None:
        self.config = config or AgentClientConfig.from_env()

    @property
    def available(self) -> bool:
        return bool(self.config.api_key and self.config.base_url and self.config.model)

    def chat_json(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> dict[str, Any]:
        if not self.available:
            raise RuntimeError("Agent client is missing EASYCOMPUTE_API_KEY/base_url/model.")
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
        try:
            with urlopen(request, timeout=self.config.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"Agent HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise RuntimeError(f"Agent request failed: {exc}") from exc
        except (KeyError, json.JSONDecodeError) as exc:
            raise RuntimeError("Agent response is not an OpenAI-compatible JSON payload.") from exc


def chat_completions_endpoint(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/chat/completions"


def load_env_file(path: str | Path = ".env") -> None:
    target = Path(path)
    if not target.is_absolute():
        target = repo_root() / target
    if not target.exists():
        return
    for raw_line in target.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = strip_env_value(value.strip())
        if key and key not in os.environ:
            os.environ[key] = value


def strip_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


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
