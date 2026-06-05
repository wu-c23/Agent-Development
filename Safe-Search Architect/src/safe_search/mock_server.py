"""Safe-Search Mock API Server — 符合 Data Contract v1.0 规范。

从 Sentiment Critic/data/novels.json 集中数据源加载书籍，
提供符合 Data Contract 的 Mock 接口供集成端联调。

启动: uvicorn src.safe_search.mock_server:app --port 8002
"""

from __future__ import annotations

import hashlib
import json
import random
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(
    title="Safe-Search Mock API",
    description="网络小说语义搜索 Mock 服务 — Safe-Search Architect",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# 路径常量 — 指向集中数据目录
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).resolve().parents[3]  # 网络小说大作业/
_CENTRAL_NOVELS = _ROOT / "Sentiment Critic" / "data" / "novels.json"

# ---------------------------------------------------------------------------
# 原始 5 本精选 Mock（保留丰富元数据，不会被中央数据覆盖）
# ---------------------------------------------------------------------------

_ORIGINAL_MOCK_NOVELS: list[dict] = [
    {
        "uid": "987a2b45c6bd2baa73d750f13daf15b63c20145de2e85fff22ada96ad3d8b27b",
        "metadata": {
            "title": "诡秘之主",
            "platform": "qidian",
            "last_update": "2026-06-03T12:00:00Z",
        },
        "intro": "值夜者克莱恩在蒸汽朋克世界中探索超凡力量的秘密...",
        "tags": ["克苏鲁", "蒸汽朋克", "悬疑", "西方奇幻"],
        "status": "completed",
        "heat_score": 998.0,
        "relevance_score": 0.92,
        "match_reason": "topics_matched:克苏鲁,蒸汽朋克,悬疑",
        "safe_check": {"passed": True, "warnings": []},
        "risk_scores": {
            "abuse_protagonist": 0.10,
            "unfinished": 0.00,
            "melodrama": 0.05,
            "harem": 0.00,
            "slow_pacing": 0.30,
        },
    },
    {
        "uid": "26d4613826eb8819a9a601cfb88eb7621b0e6cc5c46ffefa96b5dea22ca938dc",
        "metadata": {
            "title": "我有一座恐怖屋",
            "platform": "qidian",
            "last_update": "2026-06-02T10:00:00Z",
        },
        "intro": "陈歌继承废弃鬼屋，获得恐怖屋经营系统...",
        "tags": ["悬疑", "恐怖", "系统流", "轻松"],
        "status": "completed",
        "heat_score": 850.0,
        "relevance_score": 0.85,
        "match_reason": "topics_matched:悬疑; style_matched:逻辑严密",
        "safe_check": {"passed": True, "warnings": []},
        "risk_scores": {
            "abuse_protagonist": 0.05,
            "unfinished": 0.00,
            "melodrama": 0.15,
            "harem": 0.00,
            "slow_pacing": 0.10,
        },
    },
    {
        "uid": "f551b43b941bf7f47d6006792b26da44b8554945c72766133cb0c59771f48c89",
        "metadata": {
            "title": "修罗武神",
            "platform": "qidian",
            "last_update": "2026-06-03T08:00:00Z",
        },
        "intro": "楚枫遭人陷害沦为废物，获得修罗传承后逆天改命...",
        "tags": ["玄幻", "升级流", "后宫", "爽文"],
        "status": "ongoing",
        "heat_score": 450.0,
        "relevance_score": 0.45,
        "match_reason": "semantic_match",
        "safe_check": {
            "passed": False,
            "warnings": ["tag:后宫", "risk:harem>0.95", "risk:melodrama>0.85"],
        },
        "risk_scores": {
            "abuse_protagonist": 0.20,
            "unfinished": 0.50,
            "melodrama": 0.85,
            "harem": 0.95,
            "slow_pacing": 0.70,
        },
    },
    {
        "uid": "22ed60b7b27cf4c8b77c1439cb7a9d82eb4667f6eafab681bcd415e18adbd0a4",
        "metadata": {
            "title": "凡人修仙传",
            "platform": "qidian",
            "last_update": "2026-05-28T16:00:00Z",
        },
        "intro": "山村少年韩立在修仙界步步为营...",
        "tags": ["修仙", "凡人流", "慢热", "完结"],
        "status": "completed",
        "heat_score": 780.0,
        "relevance_score": 0.78,
        "match_reason": "topics_matched:修仙; completed",
        "safe_check": {"passed": True, "warnings": ["slow_pacing:0.60"]},
        "risk_scores": {
            "abuse_protagonist": 0.15,
            "unfinished": 0.00,
            "melodrama": 0.10,
            "harem": 0.00,
            "slow_pacing": 0.60,
        },
    },
    {
        "uid": "587986904db3db77b83e2d7b49165f2f6e9ec1b6552b621e340695f21c240d8c",
        "metadata": {
            "title": "仙王的日常生活",
            "platform": "qidian",
            "last_update": "2026-06-01T09:00:00Z",
        },
        "intro": "最强仙王隐藏实力体验高中日常...",
        "tags": ["修仙", "日常", "搞笑", "轻松", "完结"],
        "status": "completed",
        "heat_score": 700.0,
        "relevance_score": 0.70,
        "match_reason": "style_matched:轻松; completed",
        "safe_check": {"passed": True, "warnings": []},
        "risk_scores": {
            "abuse_protagonist": 0.00,
            "unfinished": 0.00,
            "melodrama": 0.10,
            "harem": 0.05,
            "slow_pacing": 0.05,
        },
    },
]

# 精选书名集合，用于去重
_ORIGINAL_TITLES = {n["metadata"]["title"] for n in _ORIGINAL_MOCK_NOVELS}


def _generate_uid(platform_id: str, title: str) -> str:
    raw = f"{platform_id}|{title.strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _random_risk_scores() -> dict:
    """为中央数据的书籍生成随机的合理风险分数（大部分书是安全的）。"""
    return {
        "abuse_protagonist": round(random.uniform(0.0, 0.35), 2),
        "unfinished": round(random.uniform(0.0, 0.30), 2),
        "melodrama": round(random.uniform(0.0, 0.40), 2),
        "harem": round(random.uniform(0.0, 0.25), 2),
        "slow_pacing": round(random.uniform(0.0, 0.45), 2),
    }


def _build_mock_novels() -> list[dict]:
    """从集中数据 + 精选 Mock 构建完整小说列表。"""
    novels: list[dict] = []
    seen_titles: set[str] = set()
    seen_uids: set[str] = set()

    # 1. 先加载精选 Mock（保证高质量的搜索体验）
    for novel in _ORIGINAL_MOCK_NOVELS:
        novels.append(novel)
        seen_titles.add(novel["metadata"]["title"])
        seen_uids.add(novel["uid"])

    # 2. 从集中数据源加载
    if not _CENTRAL_NOVELS.exists():
        print(f"[mock_server] Central novels not found at {_CENTRAL_NOVELS}, using only {len(novels)} built-in books.")
        return novels

    try:
        with open(_CENTRAL_NOVELS, "r", encoding="utf-8") as f:
            central_data = json.load(f)
    except Exception as exc:
        print(f"[mock_server] Failed to load central novels: {exc}")
        return novels

    loaded_count = 0
    for item in central_data:
        title = item.get("title", "").strip()
        if not title or title in seen_titles:
            continue

        platform = item.get("platform", "qidian")
        platform_id = item.get("platform_id", f"{platform}:{title}")

        uid = item.get("uid", "").strip()
        if not uid:
            uid = _generate_uid(platform_id, title)
        if uid in seen_uids:
            continue

        heat = item.get("heat_score", 0) or 0
        tags = item.get("tags", []) or []
        intro = item.get("intro", "") or ""
        status = item.get("status", "unknown") or "unknown"
        author = item.get("author", "") or ""

        risk_scores = _random_risk_scores()

        # 只有极少数书有高危标签
        high_risk = False
        if any(t in ["后宫", "harem", "种马"] for t in tags):
            risk_scores["harem"] = round(random.uniform(0.85, 0.98), 2)
            high_risk = True
        if status == "ongoing" and heat < 10:
            risk_scores["unfinished"] = round(random.uniform(0.80, 0.95), 2)
            high_risk = True

        novels.append({
            "uid": uid,
            "metadata": {
                "title": title,
                "platform": platform,
                "last_update": item.get("last_update", "2026-06-01T00:00:00Z"),
                "author": author,
            },
            "intro": intro[:120] if intro else f"《{title}》- {author}" if author else f"《{title}》",
            "tags": tags,
            "status": status,
            "heat_score": heat,
            "relevance_score": 0.5,
            "match_reason": "from_central_index",
            "safe_check": {
                "passed": not high_risk,
                "warnings": [
                    f"risk:{dim}>{score:.2f}"
                    for dim, score in risk_scores.items()
                    if score >= 0.85
                ],
            },
            "risk_scores": risk_scores,
        })
        seen_titles.add(title)
        seen_uids.add(uid)
        loaded_count += 1

    print(f"[mock_server] Loaded {loaded_count} books from central data. Total: {len(novels)}")
    return novels


# ---------------------------------------------------------------------------
# 构建全局小说列表
# ---------------------------------------------------------------------------

MOCK_NOVELS = _build_mock_novels()


def _reload_mock_novels() -> int:
    """重新从集中数据加载，返回当前总数。"""
    global MOCK_NOVELS
    # 重置随机种子以确保每次 reload 风险分数不同
    MOCK_NOVELS = _build_mock_novels()
    return len(MOCK_NOVELS)


# ---------------------------------------------------------------------------
# Request models (对齐 Data Contract)
# ---------------------------------------------------------------------------


class SearchRequest(BaseModel):
    query: str
    safe_tags: list[str] = Field(default_factory=list)
    top_k: int = Field(default=10, ge=1, le=50)
    session_id: str = Field(default="", max_length=128, description="会话ID，用于多轮对话指代解析")


# ---------------------------------------------------------------------------
# 会话存储 — 多轮对话上下文（进程内，重启后丢失）
# ---------------------------------------------------------------------------

_search_sessions: dict[str, list[str]] = {}  # session_id → 上一轮搜索的书名列表


def _resolve_session_references(query: str, session_id: str) -> str:
    """将会话上下文中的指代表达式（第一本/第二本/这本书）解析为具体书名。"""
    if not session_id or session_id not in _search_sessions:
        return query

    last_titles = _search_sessions[session_id]
    if not last_titles:
        return query

    cn_ordinals = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}

    def _replace_ordinal(match):
        num_str = match.group(1)
        if num_str.isdigit():
            n = int(num_str)
        else:
            n = cn_ordinals.get(num_str, 0)
        if 1 <= n <= len(last_titles):
            return "《" + last_titles[n - 1] + "》"
        return match.group(0)

    import re
    modified = re.sub(r"第\s*([一二三四五六七八九十\d]+)\s*[本个]", _replace_ordinal, query)
    modified = re.sub(r"这[本个]书|那[本个]书|这[本个](?!书)|那[本个](?!书)",
                      lambda m: "《" + last_titles[0] + "》" if last_titles else m.group(0),
                      modified)
    return modified


# ---------------------------------------------------------------------------
# Middleware: Mock 延迟
# ---------------------------------------------------------------------------


@app.middleware("http")
async def add_mock_latency(request, call_next):
    delay = random.uniform(0.05, 0.15)
    time.sleep(delay)
    response = await call_next(request)
    response.headers["X-Mock"] = "true"
    response.headers["X-Mock-Latency"] = f"{delay:.3f}s"
    return response


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/api/v1/search/vector/health")
async def vector_health():
    return {
        "status": "healthy",
        "version": "1.0.0",
        "index_count": len(MOCK_NOVELS),
        "last_updated": "2026-06-03T12:00:00Z",
    }


def _longest_common_substring(s1: str, s2: str) -> int:
    """返回两个字符串的最长公共子串长度。"""
    if not s1 or not s2:
        return 0
    m, n = len(s1), len(s2)
    dp = [[0] * (n + 1) for _ in range(2)]
    max_len = 0
    for i in range(1, m + 1):
        cur = i % 2
        prev = 1 - cur
        for j in range(1, n + 1):
            if s1[i - 1] == s2[j - 1]:
                dp[cur][j] = dp[prev][j - 1] + 1
                max_len = max(max_len, dp[cur][j])
            else:
                dp[cur][j] = 0
    return max_len


def _calculate_relevance(novel: dict, query_lower: str) -> tuple[float, str, bool]:
    """计算一本书与查询的相关度。返回 (relevance, match_reason, is_title_match)。"""
    tags = novel.get("tags", [])
    title = novel["metadata"]["title"]
    title_lower = title.lower()
    intro = novel.get("intro", "").lower()
    author = novel.get("metadata", {}).get("author", "").lower()

    relevance = 0.45  # 基础分
    reasons = []
    is_title_match = False
    title_len = len(title_lower)

    # 1. 精确标题匹配（最高优先级）
    if title_lower in query_lower or query_lower in title_lower:
        relevance += 0.35
        is_title_match = True
        reasons.append("title_exact_match")
    else:
        # 2. 最长公共子串匹配（中文分词能力强）
        lcs = _longest_common_substring(title_lower, query_lower)
        if lcs >= 4:
            relevance += 0.32
            is_title_match = True
            reasons.append(f"title_lcs_{lcs}")
        elif lcs >= 3:
            relevance += 0.28
            is_title_match = True
            reasons.append(f"title_lcs_{lcs}")
        elif lcs >= 2:
            # 2字匹配：计算匹配覆盖率来区分
            match_ratio = lcs / title_len
            if match_ratio >= 0.5:
                relevance += 0.22
            else:
                relevance += 0.15
            is_title_match = True
            reasons.append(f"title_substring")

        # 3. 查询词在标题中出现
        if not is_title_match:
            query_words = [w for w in query_lower.replace("，", " ").replace("。", " ").replace("?", "").replace("？", "").split() if len(w) >= 2]
            matched_qwords = [w for w in query_words if w in title_lower]
            if matched_qwords:
                relevance += 0.18 * min(len(matched_qwords), 2)
                is_title_match = True
                reasons.append("query_in_title")

    # 4. 标签匹配
    matched_tags = [t for t in tags if t.lower() in query_lower]
    if matched_tags:
        relevance += 0.15 * min(len(matched_tags), 3)
        reasons.append(f"tags:{','.join(matched_tags[:3])}")

    # 5. 简介匹配
    if intro:
        lcs_intro = _longest_common_substring(intro, query_lower)
        if lcs_intro >= 4:
            relevance += 0.12
        elif lcs_intro >= 2:
            relevance += 0.06

    # 6. 作者匹配
    if author and author in query_lower:
        relevance += 0.20
        reasons.append("author_match")

    relevance = min(relevance, 1.0)
    reason = "; ".join(reasons) if reasons else "semantic_match"
    return relevance, reason, is_title_match


def _collect_known_tags() -> set[str]:
    """收集所有已知标签（用于排除匹配）。"""
    tags: set[str] = set()
    for novel in MOCK_NOVELS:
        for tag in novel.get("tags", []):
            t = tag.strip()
            if t:
                tags.add(t)
    return tags


def _parse_exclusions(query: str) -> tuple[str, set[str], set[str]]:
    """从查询中解析排除条件。返回 (清理后的查询, 排除的书名集合, 排除的标签集合)。

    识别模式:
      - 书名排除: 不要X, 除了X, 不包括X, 去掉X, 排除X, 别推X
      - 标签排除: 不TAG, 不要TAG, 非TAG, 不看TAG (TAG 匹配已知标签)
    """
    import re

    exclude_phrases = [
        r"注意[：:]?\s*不要\S+",
        r"注意[：:]?\s*别\S+",
        r"不要推荐\S+",
        r"不要\S+",
        r"别推荐\S+",
        r"别推\S+",
        r"除了\S+(?:以外|之外)?",
        r"不包括\S+",
        r"去掉\S+",
        r"排除\S+",
        r"不看\S+",
    ]

    excluded_titles: set[str] = set()
    excluded_tags: set[str] = set()
    cleaned = query

    # 构建已知书名查找表 + 已知标签集合
    title_set: set[str] = set()
    known_tags = _collect_known_tags()
    for novel in MOCK_NOVELS:
        t = novel["metadata"]["title"]
        title_set.add(t)

    # --- 标签排除: 检测 不TAG / 非TAG / 不要TAG 模式 ---
    # 按标签长度降序排列，优先匹配长标签（避免 "后宫" 误匹配 "后宫言情" 的一部分）
    for tag in sorted(known_tags, key=len, reverse=True):
        for prefix in ["不要", "不看", "别推", "不推荐", "不", "非"]:
            negation = prefix + tag
            if negation in cleaned:
                excluded_tags.add(tag)
                cleaned = cleaned.replace(negation, " ")
                break

    # --- 书名排除 ---
    for pattern in exclude_phrases:
        for match in re.finditer(pattern, cleaned):
            matched_text = match.group()
            # 尝试从匹配文本中提取书名
            # 去掉排除前缀
            for prefix in ["注意：不要", "注意:不要", "注意不要", "注意：别", "注意:别",
                          "注意别", "不要推荐", "不要", "别推荐", "别推", "除了",
                          "不包括", "去掉", "排除", "不看"]:
                if matched_text.startswith(prefix):
                    candidate = matched_text[len(prefix):]
                    break
            else:
                candidate = matched_text

            if not candidate:
                continue

            # 清理尾部：去掉"以外"、"之外"、标点
            candidate = candidate.rstrip("以外之外，,。.！!？?；;：:、的了吧吗呢啊")
            if not candidate:
                continue

            # 在已知书名中做 LCS 匹配
            best_match = ""
            best_len = 0
            for title in title_set:
                lcs = _longest_common_substring(candidate, title)
                # 要求至少匹配 2 字且覆盖 candidate 的 50% 以上
                if lcs >= 2 and lcs >= len(candidate) * 0.5 and lcs > best_len:
                    best_match = title
                    best_len = lcs

            if best_match and best_match not in excluded_titles:
                excluded_titles.add(best_match)

    # 清理查询：移除排除短语
    for phrase in exclude_phrases:
        cleaned = re.sub(phrase, "", cleaned)

    # 清理多余空格和标点
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = re.sub(r"[，,]+$", "", cleaned).strip()

    return cleaned, excluded_titles, excluded_tags


@app.post("/api/v1/search/semantic")
async def semantic_search(request: SearchRequest):
    """语义搜索 + 避雷过滤 (Mock)，支持多轮对话指代解析。"""
    # 多轮对话：解析指代表达式（第一本→具体书名）
    resolved_query = _resolve_session_references(request.query, request.session_id)
    query_lower = resolved_query.lower()
    safe_tags_lower = [t.lower() for t in request.safe_tags]

    # 解析用户期望的推荐数量（排除"第X本"序数指代）
    _cn_num = {"一":1,"二":2,"两":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9,"十":10}
    effective_top_k = request.top_k
    import re as _re
    for m in _re.finditer(r"(?:^|[^第])([一二两三四五六七八九十\d]+)\s*[本部门篇个]", query_lower):
        ns = m.group(1)
        if ns.isdigit():
            n = int(ns)
        else:
            n = _cn_num.get(ns, 0)
        if n >= 1:
            effective_top_k = min(n, request.top_k)
            break

    # 解析排除条件
    cleaned_query, excluded_titles, excluded_tags = _parse_exclusions(query_lower)
    if excluded_titles:
        print(f"[semantic_search] Excluded titles: {excluded_titles}")
    if excluded_tags:
        print(f"[semantic_search] Excluded tags: {excluded_tags}")

    # 检查是否为泛查询（无明确主题关键词）
    generic_patterns = [
        "还有没有", "还有什么", "其他的", "别的书", "有没有别的",
        "再推荐", "换一批", "推荐一些", "有什么书", "随便推荐",
        "再来", "换一换", "更多", "还有哪些", "有哪些",
    ]
    is_generic = any(p in query_lower for p in generic_patterns)

    # 检测是否为特定书籍询问（而非推荐请求）
    inquiry_patterns = [
        "是什么", "怎么样", "好看吗", "好不好看", "评价", "介绍",
        "是什么类型", "讲什么", "什么类型", "好看不", "值得看",
        "完结了吗", "还在连载", "作者是谁", "谁写的", "多少章",
    ]
    is_inquiry = any(p in query_lower for p in inquiry_patterns)

    results = []
    for novel in MOCK_NOVELS:
        title = novel["metadata"]["title"]

        # 跳过被排除的书
        if title in excluded_titles:
            continue

        tags_str = " ".join(novel.get("tags", [])).lower()
        novel_tags = [t.lower() for t in novel.get("tags", [])]

        # 跳过包含排除标签的书
        tag_blocked = False
        for extag in excluded_tags:
            if extag.lower() in novel_tags:
                tag_blocked = True
                break
        if tag_blocked:
            continue

        heat = novel.get("heat_score", 0)

        # 用清理后的查询计算相关度
        relevance, match_reason, is_title_match = _calculate_relevance(novel, cleaned_query)

        # 泛查询时：用热度 + 随机作为排序依据（但标题匹配的书不随机）
        if is_generic and not is_title_match and relevance <= 0.50:
            heat_boost = min(heat / 50000, 0.30)
            random_boost = random.uniform(0.0, 0.20)
            relevance = 0.45 + heat_boost + random_boost

        # 书籍询问模式：大幅提升标题匹配的权重
        if is_inquiry and is_title_match:
            relevance = min(relevance + 0.15, 1.0)

        relevance = min(relevance, 1.0)

        # 避雷检查
        passed = True
        warnings = []
        for safe_tag in safe_tags_lower:
            if safe_tag in tags_str:
                passed = False
                warnings.append(f"tag:{safe_tag}")
        for dim, score in novel["risk_scores"].items():
            if score >= 0.85:
                dim_map = {
                    "harem": "后宫",
                    "melodrama": "狗血",
                    "slow_pacing": "节奏慢",
                    "abuse_protagonist": "虐主",
                    "unfinished": "烂尾",
                }
                cn_name = dim_map.get(dim, dim)
                if any(t in safe_tags_lower for t in [dim, cn_name]):
                    passed = False
                    warnings.append(f"risk:{dim}>{score:.2f}")

        # 高危书籍在泛查询中降权
        if is_generic and not novel["safe_check"]["passed"]:
            relevance = max(relevance - 0.25, 0.0)

        results.append({
            "uid": novel["uid"],
            "metadata": novel["metadata"],
            "intro": novel.get("intro", ""),
            "tags": novel.get("tags", []),
            "status": novel.get("status", "unknown"),
            "relevance_score": round(relevance, 4) if passed else 0.0,
            "match_reason": match_reason,
            "safe_check": {
                "passed": passed,
                "warnings": novel["safe_check"]["warnings"] if not passed else warnings,
            },
        })

    # 按相关度降序
    results.sort(key=lambda r: r["relevance_score"], reverse=True)
    results = results[:effective_top_k]

    # 保存本次搜索的书名到会话，供下一轮指代解析
    if request.session_id:
        _search_sessions[request.session_id] = [
            r["metadata"]["title"] for r in results if r["metadata"].get("title")
        ]

    # 构建查询改写，体现数量限制和指代解析
    rewrite_parts = [f"解析后的查询意图: {request.query}"]
    if resolved_query != request.query:
        rewrite_parts.append(f"(指代解析: {resolved_query})")
    if effective_top_k != request.top_k:
        rewrite_parts.append(f"(已识别数量限制: {effective_top_k}本)")

    return {
        "results": results,
        "query_rewrite": " ".join(rewrite_parts),
        "total_hits": len(results),
    }


@app.post("/api/v1/search/books/sync-from-central")
async def sync_from_central():
    """从集中数据源 (novels.json) 重新加载书籍索引。"""
    count = _reload_mock_novels()
    return {"indexed": count, "total_in_index": count, "source": "central"}


@app.get("/api/v1/search/books/{uid}")
async def get_book(uid: str):
    for novel in MOCK_NOVELS:
        if novel["uid"] == uid:
            return novel
    raise HTTPException(status_code=404, detail=f"Book '{uid}' not found")


@app.get("/api/v1/search/intent")
async def extract_intent(query: str):
    return {
        "summary": f"用户想要查找与'{query}'相关的网络小说",
        "topics": ["悬疑", "奇幻"],
        "style": ["逻辑严密"],
        "protagonist_traits": ["冷静", "谨慎"],
        "mood": ["轻快"],
        "constraints": [],
    }
