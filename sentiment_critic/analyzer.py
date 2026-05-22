from __future__ import annotations

from collections import Counter, defaultdict
from statistics import mean
from typing import Any
import json

from .agent_client import AgentClient
from .models import Review, ReviewAnalysis, coerce_score, coerce_sentiment, normalize_space


SYSTEM_PROMPT = """你是“舆情分析与深度评价专家 Sentiment Critic”。
你的任务是从小说深度书评里识别真实口碑，避免被单一评分带偏。
请只输出 JSON，不要输出 Markdown。
字段要求：
{
  "items": [
    {
      "review_id": "原 review_id",
      "sentiment": "positive|neutral|negative",
      "sentiment_score": -1 到 1,
      "writing_score": 0 到 10,
      "logic_score": 0 到 10,
      "update_speed_score": 0 到 10,
      "tags": ["最多 5 个中文短标签"],
      "one_liner": "一句话毒舌点评，负面/中性时更犀利，正面时也要克制",
      "entry_reason": "一句话入坑理由，说明适合什么读者",
      "evidence": "不超过 35 字的依据摘要"
    }
  ]
}
评分要看文本证据：文笔看表达和描写评价，逻辑看设定/伏笔/人物动机，更新速度看更新、拖更、断更相关信息；评论没提到的维度给 5 到 6 分，不要编造事实。
"""


POSITIVE_WORDS = {
    "好看": 2,
    "推荐": 2,
    "入坑": 2,
    "封神": 3,
    "惊艳": 3,
    "优秀": 2,
    "细腻": 2,
    "流畅": 2,
    "爽": 1,
    "上头": 2,
    "伏笔": 1,
    "合理": 2,
    "稳定": 1,
    "勤快": 2,
}


NEGATIVE_WORDS = {
    "烂": 3,
    "弃文": 3,
    "毒": 2,
    "尬": 2,
    "水": 2,
    "崩": 3,
    "降智": 3,
    "拖更": 3,
    "断更": 4,
    "套路": 1,
    "注水": 2,
    "逻辑硬伤": 3,
    "烂尾": 4,
}


TAG_KEYWORDS = {
    "文笔细腻": ("文笔", "细腻", "描写"),
    "逻辑硬伤": ("逻辑硬伤", "降智", "不合理"),
    "设定亮眼": ("设定", "世界观", "脑洞"),
    "节奏拖沓": ("拖沓", "水", "注水"),
    "更新不稳": ("拖更", "断更", "更新慢"),
    "角色鲜活": ("人物", "角色", "群像"),
    "爽点密集": ("爽", "上头", "燃"),
    "后期崩坏": ("后期", "崩", "烂尾"),
}


def analyze_reviews(
    reviews: list[Review],
    use_agent: bool = True,
    batch_size: int = 6,
    client: AgentClient | None = None,
) -> dict[str, Any]:
    client = client or AgentClient()
    analyses: list[ReviewAnalysis] = []
    for batch in chunked(reviews, batch_size):
        if use_agent and client.available:
            try:
                analyses.extend(analyze_batch_with_agent(batch, client))
                continue
            except Exception as exc:
                print(f"[warn] Agent analysis failed, using heuristic fallback: {exc}")
        analyses.extend(heuristic_analysis(review) for review in batch)
    return build_report(reviews, analyses, agent_used=use_agent and client.available)


def analyze_batch_with_agent(batch: list[Review], client: AgentClient) -> list[ReviewAnalysis]:
    payload = [
        {
            "review_id": review.review_id,
            "platform": review.platform,
            "title": review.title,
            "content": review.content[:1600],
        }
        for review in batch
    ]
    response = client.chat_json(SYSTEM_PROMPT, json.dumps({"reviews": payload}, ensure_ascii=False))
    items = response.get("items") or response.get("reviews") or []
    by_id = {review.review_id: review for review in batch}
    analyses: list[ReviewAnalysis] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        review = by_id.get(str(item.get("review_id")))
        if not review:
            continue
        analyses.append(complete_analysis(item, review))
        seen.add(review.review_id)
    for review in batch:
        if review.review_id not in seen:
            analyses.append(heuristic_analysis(review))
    return analyses


def complete_analysis(data: dict[str, Any], review: Review) -> ReviewAnalysis:
    data = dict(data)
    data.setdefault("platform", review.platform)
    data.setdefault("title", review.title)
    data.setdefault("source_url", review.source_url)
    if not data.get("one_liner") or not data.get("entry_reason"):
        fallback = heuristic_analysis(review)
        data.setdefault("one_liner", fallback.one_liner)
        data.setdefault("entry_reason", fallback.entry_reason)
    return ReviewAnalysis.from_dict(data, review=review)


def heuristic_analysis(review: Review) -> ReviewAnalysis:
    text = review.content
    positive = sum(weight for word, weight in POSITIVE_WORDS.items() if word in text)
    negative = sum(weight for word, weight in NEGATIVE_WORDS.items() if word in text)
    sentiment_score = (positive - negative) / max(positive + negative + 2, 2)
    sentiment_score = coerce_score(sentiment_score, -1.0, 1.0, 0.0)
    sentiment = "positive" if sentiment_score > 0.18 else "negative" if sentiment_score < -0.18 else "neutral"

    writing_score = dimension_score(text, ["文笔", "描写", "细腻", "流畅"], ["文笔差", "尬", "小白", "流水账"])
    logic_score = dimension_score(text, ["逻辑", "伏笔", "合理", "设定"], ["逻辑硬伤", "降智", "不合理", "崩"])
    update_speed_score = dimension_score(text, ["更新", "稳定", "日更", "勤快"], ["拖更", "断更", "更新慢"])
    tags = infer_tags(text, sentiment)
    one_liner = make_one_liner(sentiment, tags)
    entry_reason = make_entry_reason(sentiment, tags)
    evidence = make_evidence(text, tags)
    return ReviewAnalysis(
        review_id=review.review_id,
        platform=review.platform,
        title=review.title,
        source_url=review.source_url,
        sentiment=sentiment,
        sentiment_score=sentiment_score,
        writing_score=writing_score,
        logic_score=logic_score,
        update_speed_score=update_speed_score,
        one_liner=one_liner,
        entry_reason=entry_reason,
        tags=tags,
        evidence=evidence,
    )


def dimension_score(text: str, positive_terms: list[str], negative_terms: list[str]) -> float:
    score = 5.5
    for term in positive_terms:
        if term in text:
            score += 1.0
    for term in negative_terms:
        if term in text:
            score -= 1.3
    return coerce_score(score, 0.0, 10.0, 5.5)


def infer_tags(text: str, sentiment: str) -> list[str]:
    tags: list[str] = []
    for tag, keywords in TAG_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            tags.append(tag)
    if not tags:
        tags.append({"positive": "口碑偏正", "negative": "争议较大"}.get(sentiment, "评价分化"))
    return tags[:5]


def make_one_liner(sentiment: str, tags: list[str]) -> str:
    focus = "、".join(tags[:2])
    if sentiment == "positive":
        return f"不是无脑吹，核心优势确实落在{focus}上。"
    if sentiment == "negative":
        return f"雷点不藏着掖着，{focus}会直接劝退挑剔读者。"
    return f"优缺点都很明显，{focus}决定你会不会继续追。"


def make_entry_reason(sentiment: str, tags: list[str]) -> str:
    focus = "、".join(tags[:2])
    if sentiment == "negative":
        return f"只建议能接受{focus}争议、想亲自验毒的读者试读。"
    if sentiment == "positive":
        return f"适合想看{focus}、且愿意慢慢吃设定的读者入坑。"
    return f"适合先读前几十章确认{focus}是否合胃口。"


def make_evidence(text: str, tags: list[str]) -> str:
    for tag in tags:
        for keyword in TAG_KEYWORDS.get(tag, ()):
            index = text.find(keyword)
            if index >= 0:
                return normalize_space(text[max(0, index - 10) : index + 24])
    return normalize_space(text[:35])


def build_report(reviews: list[Review], analyses: list[ReviewAnalysis], agent_used: bool) -> dict[str, Any]:
    counts = Counter(item.sentiment for item in analyses)
    total = max(len(analyses), 1)
    platform_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for item in analyses:
        platform_counts[item.platform][item.sentiment] += 1

    score_fields = {
        "writing": [item.writing_score for item in analyses],
        "logic": [item.logic_score for item in analyses],
        "update_speed": [item.update_speed_score for item in analyses],
        "sentiment": [item.sentiment_score for item in analyses],
    }
    top_tags = Counter(tag for item in analyses for tag in item.tags).most_common(10)
    book = reviews[0].book if reviews else ""
    return {
        "book": book,
        "review_count": len(analyses),
        "agent_used": agent_used,
        "ratio": {
            "positive": round(counts["positive"] / total, 4),
            "neutral": round(counts["neutral"] / total, 4),
            "negative": round(counts["negative"] / total, 4),
        },
        "counts": dict(counts),
        "average_scores": {
            name: round(mean(values), 2) if values else 0 for name, values in score_fields.items()
        },
        "platform_breakdown": {
            platform: {
                "positive": counter["positive"],
                "neutral": counter["neutral"],
                "negative": counter["negative"],
                "total": sum(counter.values()),
            }
            for platform, counter in sorted(platform_counts.items())
        },
        "top_tags": [{"tag": tag, "count": count} for tag, count in top_tags],
        "verdict": make_verdict(counts, score_fields),
        "items": [item.to_dict() for item in analyses],
    }


def make_verdict(counts: Counter[str], score_fields: dict[str, list[float]]) -> str:
    total = max(sum(counts.values()), 1)
    positive_ratio = counts["positive"] / total
    negative_ratio = counts["negative"] / total
    logic_avg = mean(score_fields["logic"]) if score_fields["logic"] else 0
    writing_avg = mean(score_fields["writing"]) if score_fields["writing"] else 0
    if negative_ratio >= 0.45:
        return "负面声量偏高，建议重点核查低分评论里的共同雷点。"
    if positive_ratio >= 0.65 and logic_avg >= 6.5:
        return "真实口碑偏稳，设定和逻辑没有明显集中塌方信号。"
    if writing_avg >= 7 and logic_avg < 6:
        return "文笔认可度高于逻辑认可度，可能是氛围强但推演经不起细抠。"
    return "口碑分化明显，适合结合标签看自己能否接受主要争议。"


def chunked(values: list[Review], size: int) -> list[list[Review]]:
    return [values[index : index + size] for index in range(0, len(values), size)]
