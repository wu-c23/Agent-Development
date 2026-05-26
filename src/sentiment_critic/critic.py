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
    "abuse_protagonist": ["abuse", "angst", "虐主", "虐"],
    "unfinished": ["unfinished", "烂尾", "坑", "太监"],
    "melodrama": ["melodrama", "狗血"],
    "harem": ["harem", "后宫"],
    "slow_pacing": ["slow", "节奏慢", "拖沓", "水"],
}

RISK_SCORING_PROMPT = """You rate web novel risk dimensions on a 0-1 scale for Chinese novels.

## Scoring Rubric
- 0.00-0.20: No or negligible indication of this risk
- 0.21-0.50: Minor hints, most readers would not be bothered
- 0.51-0.80: Notable presence, would bother sensitive readers
- 0.81-1.00: Strong/defining characteristic, widely considered a problem

## Risk Dimensions
1. abuse_protagonist (虐主): Protagonist is excessively tortured, powerless, betrayed, or humiliated throughout
2. unfinished (烂尾/太监): Work is abandoned, has a rushed ending, or is known for being incomplete
3. melodrama (狗血): Over-the-top drama, contrived conflicts, excessive face-slapping, soap-opera twists
4. harem (后宫): Multiple shallow romantic interests, collecting female/male leads like trophies
5. slow_pacing (拖沓/水): Drawn-out plot, filler chapters, glacial progression, repetitive content

## Examples

Book: 《诡秘之主》
Intro: 值夜者克莱恩·莫雷蒂在蒸汽朋克世界中探索超凡力量的秘密，一步步成为真正的"愚者"...
Tags: ["克苏鲁", "蒸汽朋克", "悬疑", "西方奇幻"]
Status: completed
Sentiment: 读者普遍好评，夸赞逻辑严密、角色塑造出色，有读者反映开头节奏偏慢
{"abuse_protagonist": 0.10, "unfinished": 0.00, "melodrama": 0.05, "harem": 0.00, "slow_pacing": 0.30}

Book: 《修罗武神》
Intro: 楚枫遭人陷害沦为废物，意外获得修罗传承后一路碾压敌人，收服各色美女，逆天改命称霸天下！
Tags: ["玄幻", "升级流", "后宫", "爽文"]
Status: ongoing
Sentiment: 读者喜欢爽快感，但吐槽后期水字数和妹子太多像收菜
{"abuse_protagonist": 0.20, "unfinished": 0.50, "melodrama": 0.85, "harem": 0.95, "slow_pacing": 0.70}

Book: 《我有一座恐怖屋》
Intro: 陈歌继承了一家废弃的鬼屋，意外获得恐怖屋经营系统，需要用真实的恐怖场景来吓唬游客...
Tags: ["悬疑", "恐怖", "系统流", "轻松"]
Status: completed
Sentiment: 读者认为剧情新颖有趣、节奏感好，不吓人反而有点搞笑
{"abuse_protagonist": 0.05, "unfinished": 0.00, "melodrama": 0.15, "harem": 0.00, "slow_pacing": 0.10}

Now score this novel:
Title: {title}
Intro: {intro}
Tags: {tags}
Status: {status}
Sentiment: {sentiment}"""


def _rule_scores(tags: List[str]) -> Dict[str, float]:
    """Match tags against risk keyword dictionaries. Returns scores in [0, 1]."""
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
    """Score five risk dimensions using rule-based tags + LLM judgment.

    The final score per dimension = max(rule_score, llm_score).
    Evidence is collected from both sources.
    """
    rule_scores = _rule_scores(tags)
    llm_scores: Dict[str, float] = {}
    evidence: List[Dict[str, str]] = []

    # LLM scoring — only if there's meaningful content to analyze
    if sentiment_summary or intro:
        prompt = (
            RISK_SCORING_PROMPT
            .replace("{title}", title)
            .replace("{intro}", intro)
            .replace("{tags}", ", ".join(tags))
            .replace("{status}", "completed" if "completed" in [t.lower() for t in tags] else "unknown")
            .replace("{sentiment}", sentiment_summary or "")
        )
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You output only a JSON object. No markdown, no explanation."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content or ""
            parsed = _parse_llm_payload(content)
            if parsed:
                llm_scores = parsed
                evidence.append({"type": "model", "value": "llm_scoring"})
        except Exception:
            # LLM unavailable → fall back to rule scores only
            pass

    # Merge: max of rule and LLM per dimension
    merged = {
        key: max(rule_scores.get(key, 0.0), llm_scores.get(key, 0.0))
        for key in RISK_DIMENSIONS
    }

    for dim, score in rule_scores.items():
        if score >= 0.9:
            evidence.append({"type": "tag", "value": dim})

    return {
        "scores": merged,
        "evidence": evidence,
    }
