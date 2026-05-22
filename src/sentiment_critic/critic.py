import json
from typing import Dict, List, Optional

from openai import OpenAI

RISK_DIMENSIONS = [
    "abuse_protagonist",
    "unfinished",
    "melodrama",
    "harem",
    "slow_pacing",
]

TAG_RULES = {
    "abuse_protagonist": ["abuse", "angst", "虐主"],
    "unfinished": ["unfinished", "烂尾", "坑"],
    "melodrama": ["melodrama", "狗血"],
    "harem": ["harem", "后宫"],
    "slow_pacing": ["slow", "节奏慢", "拖沓"],
}


def _rule_scores(tags: List[str]) -> Dict[str, float]:
    lowered = [tag.lower() for tag in tags]
    scores = {key: 0.0 for key in RISK_DIMENSIONS}
    for dim, needles in TAG_RULES.items():
        for needle in needles:
            if any(needle in tag for tag in lowered):
                scores[dim] = max(scores[dim], 0.95)
    return scores


def _parse_llm_payload(payload: str) -> Optional[Dict[str, float]]:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return None

    scores: Dict[str, float] = {}
    for key in RISK_DIMENSIONS:
        value = data.get(key)
        if isinstance(value, (int, float)):
            scores[key] = float(value)
    return scores if scores else None


def score_risks(
    client: OpenAI,
    model: str,
    title: str,
    intro: str,
    tags: List[str],
    sentiment_summary: Optional[str],
) -> Dict[str, object]:
    rule_scores = _rule_scores(tags)

    prompt = (
        "You are a reviewer scoring risk dimensions for a web novel. "
        "Return a JSON object with numeric values between 0 and 1 for: "
        "abuse_protagonist, unfinished, melodrama, harem, slow_pacing. "
        "Use the inputs below.\n\n"
        f"Title: {title}\n"
        f"Intro: {intro}\n"
        f"Tags: {', '.join(tags)}\n"
        f"Sentiment summary: {sentiment_summary or ''}\n"
    )

    llm_scores: Dict[str, float] = {}
    evidence: List[Dict[str, str]] = []
    if sentiment_summary or intro:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You output only JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        content = response.choices[0].message.content or ""
        parsed = _parse_llm_payload(content)
        if parsed:
            llm_scores = parsed
            evidence.append({"type": "model", "value": "llm_scoring"})

    merged = {key: max(rule_scores.get(key, 0.0), llm_scores.get(key, 0.0)) for key in RISK_DIMENSIONS}

    for dim, score in rule_scores.items():
        if score >= 0.9:
            evidence.append({"type": "tag", "value": dim})

    return {
        "scores": merged,
        "evidence": evidence,
    }
