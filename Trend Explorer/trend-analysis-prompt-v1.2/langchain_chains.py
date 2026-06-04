from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping


PROMPT_DIR = Path(__file__).resolve().parent
JSON_OUTPUT_FIELDS = (
    "core_tags",
    "genre",
    "hot_elements",
    "reader_emotion_value",
    "trend_reason",
    "evolution_relation",
    "confidence",
)


try:
    from langchain_core.output_parsers import JsonOutputParser
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.runnables import Runnable, RunnableLambda
except ImportError:  # pragma: no cover - keeps the module importable before dependencies are installed.
    JsonOutputParser = None
    ChatPromptTemplate = None
    Runnable = Any
    RunnableLambda = None


class LangChainDependencyError(RuntimeError):
    """Raised when LangChain packages are not installed in the runtime."""


def ensure_langchain_installed() -> None:
    """Fail fast with an actionable message when LangChain is missing."""

    if ChatPromptTemplate is None or JsonOutputParser is None or RunnableLambda is None:
        raise LangChainDependencyError(
            "LangChain dependencies are missing. Install langchain-core and a model provider package, "
            "for example: pip install langchain-core langchain-openai"
        )


def load_prompt_template(filename: str) -> str:
    """Load a Markdown prompt template from this module directory."""

    path = PROMPT_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Prompt template not found: {path}")
    return path.read_text(encoding="utf-8")


def build_default_llm():
    """Create the default chat model using DeepSeek API (OpenAI-compatible).

    Reads from the unified .env at Safe-Search Architect/.env:
    - DEEPSEEK_API_KEY: required.
    - DEEPSEEK_BASE_URL: defaults to https://api.deepseek.com.
    - DEEPSEEK_CHAT_MODEL: defaults to deepseek-v4-pro.
    - NOVEL_TREND_LLM_TEMPERATURE: optional float, defaults to 0.2.

    If DeepSeek key is not set, falls back to OPENAI_API_KEY
    and langchain-openai defaults for backward compatibility.
    """

    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:  # pragma: no cover - optional provider.
        raise LangChainDependencyError(
            "Default LLM requires langchain-openai. Install it: pip install langchain-openai"
        ) from exc

    deepseek_key = os.getenv("DEEPSEEK_API_KEY", "")
    if deepseek_key and not deepseek_key.startswith("sk-your-"):
        base = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
        return ChatOpenAI(
            model=os.getenv("DEEPSEEK_CHAT_MODEL", "deepseek-v4-pro"),
            temperature=float(os.getenv("NOVEL_TREND_LLM_TEMPERATURE", "0.2")),
            openai_api_key=deepseek_key,
            openai_api_base=f"{base}/v1" if not base.endswith("/v1") else base,
        )

    # Fallback: use standard OpenAI env vars (OPENAI_API_KEY, etc.)
    return ChatOpenAI(
        model=os.getenv("NOVEL_TREND_LLM_MODEL", "gpt-4o-mini"),
        temperature=float(os.getenv("NOVEL_TREND_LLM_TEMPERATURE", "0.2")),
    )


def extract_tags_chain(llm: Any | None = None) -> Runnable:
    """Build the core tag extraction chain.

    Input:
        {
          "work_payload": {
            "title": "作品名",
            "author": "作者",
            "platform": "平台",
            "rank": 1,
            "rankChange": 5,
            "category": "玄幻",
            "tags": ["系统流"],
            "heatScore": 12345,
            "listType": "月票榜-2026年01月",
            "summary": "作品简介",
            "commentSummary": "评论摘要"
          }
        }

    Output:
        dict with JSON_OUTPUT_FIELDS, including core_tags, genre,
        hot_elements, reader_emotion_value, trend_reason,
        evolution_relation, and confidence.
    """

    return build_json_chain(
        llm=llm,
        task_prompt_file="tag_extraction_prompt.md",
        input_preparer=prepare_tag_input,
    )


def analyze_genre_evolution_chain(llm: Any | None = None) -> Runnable:
    """Build the genre evolution analysis chain.

    Input:
        {
          "trend_window": [current period or current month TrendItem-like records],
          "previous_window": [previous period, previous month, or comparison records],
          "target_elements": ["废土", "规则怪谈", "系统流"]
        }

    Output:
        dict with JSON_OUTPUT_FIELDS. evolution_relation explains the inferred
        migration from one element or genre to another. Use null from/to values
        when evidence is insufficient.
    """

    return build_json_chain(
        llm=llm,
        task_prompt_file="genre_evolution_prompt.md",
        input_preparer=prepare_evolution_input,
    )


def generate_trend_summary_chain(llm: Any | None = None) -> Runnable:
    """Build the trend summary generation chain.

    Input:
        {
          "time_range": "2026年1月 至 2026年4月",
          "trend_items": [TrendItem records from crawlers or APIs],
          "platform_stats": {"纵横中文网": {"items": 200, "topTags": ["玄幻"]}},
          "summary_focus": "发现热门题材、平台差异和上升作品"
        }

    Output:
        dict with JSON_OUTPUT_FIELDS. trend_reason should contain a concise
        readable report suitable for /api/trends/summary.
    """

    return build_json_chain(
        llm=llm,
        task_prompt_file="trend_summary_prompt.md",
        input_preparer=prepare_summary_input,
    )


def build_json_chain(llm: Any | None, task_prompt_file: str, input_preparer) -> Runnable:
    """Compose input normalization, prompt, chat model, and JSON parser."""

    ensure_langchain_installed()
    model = llm or build_default_llm()
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", load_prompt_template("system_prompt.md")),
            ("user", load_prompt_template(task_prompt_file)),
        ]
    )
    return RunnableLambda(input_preparer) | prompt | model | JsonOutputParser()


def prepare_tag_input(inputs: Mapping[str, Any] | Any) -> dict[str, str]:
    """Normalize tag extraction input into prompt variables."""

    if isinstance(inputs, Mapping):
        payload = inputs.get("work_payload", inputs)
    else:
        payload = inputs
    return {"work_payload": to_json_text(payload)}


def prepare_evolution_input(inputs: Mapping[str, Any] | Any) -> dict[str, str]:
    """Normalize genre evolution input into prompt variables."""

    if not isinstance(inputs, Mapping):
        inputs = {"trend_window": inputs}
    return {
        "trend_window": to_json_text(inputs.get("trend_window", [])),
        "previous_window": to_json_text(inputs.get("previous_window", [])),
        "target_elements": to_json_text(inputs.get("target_elements", [])),
    }


def prepare_summary_input(inputs: Mapping[str, Any] | Any) -> dict[str, str]:
    """Normalize trend summary input into prompt variables."""

    if not isinstance(inputs, Mapping):
        inputs = {"trend_items": inputs}
    return {
        "time_range": str(inputs.get("time_range", "")),
        "trend_items": to_json_text(inputs.get("trend_items", [])),
        "platform_stats": to_json_text(inputs.get("platform_stats", {})),
        "summary_focus": str(
            inputs.get("summary_focus", "发现热门题材、识别上升作品、判断平台差异、分析流派迁移")
        ),
    }


def to_json_text(value: Any) -> str:
    """Serialize arbitrary input as readable JSON for prompt injection."""

    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def validate_analysis_json(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Lightweight validation helper for chain outputs.

    This does not replace formal Pydantic validation, but it ensures downstream
    API code receives the required top-level fields even when a model omits one.
    """

    result = dict(payload)
    result.setdefault("core_tags", [])
    result.setdefault("genre", "")
    result.setdefault("hot_elements", [])
    result.setdefault("reader_emotion_value", [])
    result.setdefault("trend_reason", "")
    result.setdefault("evolution_relation", {"from": None, "to": None, "logic": ""})
    result.setdefault("confidence", 0.0)
    if not isinstance(result.get("evolution_relation"), Mapping):
        result["evolution_relation"] = {"from": None, "to": None, "logic": str(result["evolution_relation"])}
    result["confidence"] = clamp_confidence(result.get("confidence"))
    return {field: result[field] for field in JSON_OUTPUT_FIELDS}


def clamp_confidence(value: Any) -> float:
    """Coerce confidence into the required [0, 1] range."""

    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return min(1.0, max(0.0, number))


if __name__ == "__main__":
    sample = {
        "title": "雾都规则档案",
        "platform": "示例平台",
        "rank": 3,
        "category": "悬疑",
        "tags": ["规则怪谈", "无限流"],
        "summary": "主角进入被规则支配的城市副本，在限制条件中寻找生路。",
    }
    print(to_json_text(prepare_tag_input({"work_payload": sample})))
