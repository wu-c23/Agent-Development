"""集中数据访问层 — 所有模块统一从这里读写书籍数据。

数据文件位于 Sentiment Critic/data/:
  novels.json          — 小说元数据索引
  sentiment_index.json — 聚合舆情评分

当数据文件不存在时，自动回退到内置 Mock 数据（与旧 sentiment_api 兼容）。
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any

from .models import dedupe_reviews, normalize_space, read_json, read_jsonl, write_json

# ---------------------------------------------------------------------------
# 路径解析
# ---------------------------------------------------------------------------

_PACKAGE_DIR = Path(__file__).resolve().parent
_DATA_DIR = _PACKAGE_DIR.parent / "data"
_NOVELS_PATH = _DATA_DIR / "novels.json"
_SENTIMENT_INDEX_PATH = _DATA_DIR / "sentiment_index.json"


def _data_path(filename: str) -> Path:
    return _DATA_DIR / filename


# ---------------------------------------------------------------------------
# 内置 Mock 数据 (数据文件不存在时的 fallback，与旧 sentiment_api 保持一致)
# ---------------------------------------------------------------------------

_FALLBACK_NOVELS: list[dict[str, Any]] = [
    {
        "uid": "987a2b45c6bd2baa73d750f13daf15b63c20145de2e85fff22ada96ad3d8b27b",
        "title": "诡秘之主", "author": "爱潜水的乌贼",
        "platform": "qidian", "platform_id": "qidian:诡秘之主",
        "tags": ["克苏鲁", "蒸汽朋克", "悬疑", "西方奇幻"],
        "status": "completed", "intro": "值夜者克莱恩在蒸汽朋克世界中探索超凡力量的秘密...",
        "last_update": "2026-06-03T12:00:00Z", "heat_score": 998.0,
    },
    {
        "uid": "26d4613826eb8819a9a601cfb88eb7621b0e6cc5c46ffefa96b5dea22ca938dc",
        "title": "我有一座恐怖屋", "author": "我会修空调",
        "platform": "qidian", "platform_id": "qidian:我有一座恐怖屋",
        "tags": ["悬疑", "恐怖", "系统流", "轻松"],
        "status": "completed", "intro": "陈歌继承废弃鬼屋，获得恐怖屋经营系统...",
        "last_update": "2026-06-02T10:00:00Z", "heat_score": 850.0,
    },
    {
        "uid": "f551b43b941bf7f47d6006792b26da44b8554945c72766133cb0c59771f48c89",
        "title": "修罗武神", "author": "善良的蜜蜂",
        "platform": "qidian", "platform_id": "qidian:修罗武神",
        "tags": ["玄幻", "升级流", "后宫", "爽文"],
        "status": "ongoing", "intro": "楚枫遭人陷害沦为废物，获得修罗传承后逆天改命...",
        "last_update": "2026-06-03T08:00:00Z", "heat_score": 520.0,
    },
    {
        "uid": "22ed60b7b27cf4c8b77c1439cb7a9d82eb4667f6eafab681bcd415e18adbd0a4",
        "title": "凡人修仙传", "author": "忘语",
        "platform": "qidian", "platform_id": "qidian:凡人修仙传",
        "tags": ["修仙", "凡人流", "慢热", "完结"],
        "status": "completed", "intro": "山村少年韩立在修仙界步步为营...",
        "last_update": "2026-05-28T16:00:00Z", "heat_score": 830.0,
    },
    {
        "uid": "587986904db3db77b83e2d7b49165f2f6e9ec1b6552b621e340695f21c240d8c",
        "title": "仙王的日常生活", "author": "枯玄",
        "platform": "qidian", "platform_id": "qidian:仙王的日常生活",
        "tags": ["修仙", "日常", "搞笑", "轻松"],
        "status": "completed", "intro": "最强仙王隐藏实力体验高中日常...",
        "last_update": "2026-06-01T09:00:00Z", "heat_score": 780.0,
    },
]

_FALLBACK_SENTIMENT: dict[str, dict[str, Any]] = {
    "987a2b45c6bd2baa73d750f13daf15b63c20145de2e85fff22ada96ad3d8b27b": {
        "uid": "987a2b45c6bd2baa73d750f13daf15b63c20145de2e85fff22ada96ad3d8b27b",
        "overall": 9.1, "style": 9.2, "logic": 9.5,
        "character": 9.0, "update_stability": 8.8, "toxicity_index": 0.08,
        "one_liner": "逻辑严密的克苏鲁神作，但前200页像在读说明书。",
        "pros": ["世界观构建顶级", "伏笔回收大师级", "角色智商集体在线"],
        "cons": ["开头节奏偏慢", "对轻度读者门槛较高"],
        "review_count": 1250, "positive_ratio": 0.86, "negative_ratio": 0.05,
        "source_breakdown": {"douban": 620, "tieba": 430, "xiaohongshu": 200},
    },
    "26d4613826eb8819a9a601cfb88eb7621b0e6cc5c46ffefa96b5dea22ca938dc": {
        "uid": "26d4613826eb8819a9a601cfb88eb7621b0e6cc5c46ffefa96b5dea22ca938dc",
        "overall": 8.5, "style": 8.0, "logic": 8.2,
        "character": 8.8, "update_stability": 9.0, "toxicity_index": 0.05,
        "one_liner": "不吓人的恐怖小说才是好喜剧，陈歌把鬼屋经营成了迪士尼。",
        "pros": ["角色塑造鲜明", "恐怖与搞笑平衡出色", "更新稳定"],
        "cons": ["后期略有套路化", "部分副本节奏不均"],
        "review_count": 890, "positive_ratio": 0.82, "negative_ratio": 0.06,
        "source_breakdown": {"douban": 420, "tieba": 350, "xiaohongshu": 120},
    },
    "f551b43b941bf7f47d6006792b26da44b8554945c72766133cb0c59771f48c89": {
        "uid": "f551b43b941bf7f47d6006792b26da44b8554945c72766133cb0c59771f48c89",
        "overall": 5.2, "style": 5.0, "logic": 4.0,
        "character": 3.5, "update_stability": 6.0, "toxicity_index": 0.45,
        "one_liner": "爽是真的爽，水也是真的水，后宫像Pokemon收集图鉴。",
        "pros": ["爽点密集节奏快", "适合无脑放松"],
        "cons": ["后宫角色扁平化", "后期严重注水", "逻辑经不起推敲"],
        "review_count": 2100, "positive_ratio": 0.45, "negative_ratio": 0.35,
        "source_breakdown": {"douban": 300, "tieba": 1500, "xiaohongshu": 300},
    },
    "22ed60b7b27cf4c8b77c1439cb7a9d82eb4667f6eafab681bcd415e18adbd0a4": {
        "uid": "22ed60b7b27cf4c8b77c1439cb7a9d82eb4667f6eafab681bcd415e18adbd0a4",
        "overall": 8.3, "style": 7.5, "logic": 9.0,
        "character": 8.5, "update_stability": 9.5, "toxicity_index": 0.10,
        "one_liner": "凡人流教科书，韩立教你什么叫真正的'凡人'——连老婆都是分身上位的。",
        "pros": ["逻辑自洽的修仙体系", "主角智商长期在线", "完结稳定不烂尾"],
        "cons": ["前期节奏偏慢", "女主存在感薄弱"],
        "review_count": 3200, "positive_ratio": 0.80, "negative_ratio": 0.08,
        "source_breakdown": {"douban": 1800, "tieba": 1100, "xiaohongshu": 300},
    },
    "587986904db3db77b83e2d7b49165f2f6e9ec1b6552b621e340695f21c240d8c": {
        "uid": "587986904db3db77b83e2d7b49165f2f6e9ec1b6552b621e340695f21c240d8c",
        "overall": 7.8, "style": 7.2, "logic": 6.5,
        "character": 8.0, "update_stability": 8.5, "toxicity_index": 0.12,
        "one_liner": "仙王装高中生的日常，像拿核弹打蚊子——浪费但好笑。",
        "pros": ["轻松解压", "反套路设定有趣", "角色讨喜"],
        "cons": ["深度不足", "单元剧形式缺乏主线推进"],
        "review_count": 780, "positive_ratio": 0.78, "negative_ratio": 0.09,
        "source_breakdown": {"douban": 350, "tieba": 280, "xiaohongshu": 150},
    },
}


# ---------------------------------------------------------------------------
# 内部缓存 (避免重复读盘)
# ---------------------------------------------------------------------------

_novels_cache: list[dict[str, Any]] | None = None
_sentiment_cache: dict[str, dict[str, Any]] | None = None
_cache_loaded: bool = False


def _ensure_loaded() -> None:
    global _novels_cache, _sentiment_cache, _cache_loaded
    if _cache_loaded:
        return
    _novels_cache = _load_novels_from_disk()
    _sentiment_cache = _load_sentiment_from_disk()
    _cache_loaded = True


def reload() -> None:
    """强制重新从磁盘加载数据（用于数据刷新后）。"""
    global _novels_cache, _sentiment_cache, _cache_loaded
    _novels_cache = _load_novels_from_disk()
    _sentiment_cache = _load_sentiment_from_disk()
    _cache_loaded = True


def _load_novels_from_disk() -> list[dict[str, Any]]:
    print(f"[DEBUG _load_novels_from_disk] path={_NOVELS_PATH}, exists={_NOVELS_PATH.exists()}", flush=True)
    if _NOVELS_PATH.exists():
        try:
            data = read_json(str(_NOVELS_PATH))
            if isinstance(data, list) and len(data) > 0:
                print(f"[DEBUG _load_novels_from_disk] loaded {len(data)} novels from file", flush=True)
                return data
        except (json.JSONDecodeError, OSError, ValueError) as e:
            print(f"[DEBUG _load_novels_from_disk] error: {e}", flush=True)
    fb = _build_novels_from_existing_data()
    if fb:
        print(f"[DEBUG _load_novels_from_disk] fallback: built {len(fb)} from existing data", flush=True)
        return fb
    print(f"[DEBUG _load_novels_from_disk] fallback: using FALLBACK_NOVELS ({len(_FALLBACK_NOVELS)})", flush=True)
    return list(_FALLBACK_NOVELS)


def _load_sentiment_from_disk() -> dict[str, dict[str, Any]]:
    print(f"[DEBUG _load_sentiment_from_disk] path={_SENTIMENT_INDEX_PATH}, exists={_SENTIMENT_INDEX_PATH.exists()}", flush=True)
    if _SENTIMENT_INDEX_PATH.exists():
        try:
            data = read_json(str(_SENTIMENT_INDEX_PATH))
            if isinstance(data, dict) and len(data) > 0:
                print(f"[DEBUG _load_sentiment_from_disk] loaded {len(data)} entries from file", flush=True)
                return data
        except (json.JSONDecodeError, OSError, ValueError) as e:
            print(f"[DEBUG _load_sentiment_from_disk] error: {e}", flush=True)
    fb = _build_sentiment_from_existing_data()
    if fb:
        print(f"[DEBUG _load_sentiment_from_disk] fallback: built {len(fb)} from existing data", flush=True)
        return fb
    print(f"[DEBUG _load_sentiment_from_disk] fallback: using FALLBACK_SENTIMENT ({len(_FALLBACK_SENTIMENT)})", flush=True)
    return dict(_FALLBACK_SENTIMENT)


def _build_novels_from_existing_data() -> list[dict[str, Any]] | None:
    """尝试从已有评论数据中提取小说元数据。"""
    novels: dict[str, dict[str, Any]] = {}
    reviews_dir = _DATA_DIR

    for jsonl_file in sorted(reviews_dir.glob("*.jsonl")):
        try:
            reviews = read_jsonl(str(jsonl_file))
        except (ValueError, OSError):
            continue
        for review in reviews:
            title = normalize_space(review.book)
            if not title or len(title) < 2:
                continue
            if title not in novels:
                novels[title] = {
                    "uid": review.uid or "",
                    "title": title,
                    "author": review.author or "",
                    "platform": review.platform,
                    "platform_id": review.platform_id or f"{review.platform}:{title}",
                    "tags": [],
                    "status": "unknown",
                    "intro": "",
                    "last_update": review.collected_at or "",
                    "heat_score": 0.0,
                }
            if review.author and not novels[title]["author"]:
                novels[title]["author"] = review.author

    if novels:
        result = list(novels.values())
        _write_novels_safe(result)
        return result
    return None


def _build_sentiment_from_existing_data() -> dict[str, dict[str, Any]] | None:
    """尝试从已有分析报告构建舆情索引。"""
    outputs_dir = _PACKAGE_DIR.parent / "outputs" / "runs"
    if not outputs_dir.exists():
        return None

    merged: dict[str, dict[str, Any]] = {}
    for report_file in sorted(outputs_dir.rglob("analysis_report.json")):
        try:
            report = read_json(str(report_file))
        except (json.JSONDecodeError, OSError):
            continue
        book_title = report.get("book", "")
        avg = report.get("average_scores", {})
        ratio = report.get("ratio", {})
        platform_bd = report.get("platform_breakdown", {})

        uid = ""
        novels = _novels_cache if _novels_cache else _FALLBACK_NOVELS
        for novel in novels:
            if novel.get("title") == book_title:
                uid = novel["uid"]
                break

        if not uid:
            continue

        merged[uid] = {
            "uid": uid,
            "overall": avg.get("sentiment", 0),
            "style": avg.get("writing", 0),
            "logic": avg.get("logic", 0),
            "character": avg.get("character", 0),
            "update_stability": avg.get("update_speed", 0),
            "toxicity_index": avg.get("toxicity", 0),
            "one_liner": report.get("verdict", ""),
            "pros": [tag["tag"] for tag in report.get("top_tags", [])[:3] if tag.get("count", 0) > 1],
            "cons": [],
            "review_count": report.get("review_count", 0),
            "positive_ratio": ratio.get("positive", 0),
            "negative_ratio": ratio.get("negative", 0),
            "source_breakdown": {
                p: info.get("total", 0) for p, info in platform_bd.items()
            },
        }

    if merged:
        _write_sentiment_safe(merged)
        return merged
    return None


def _write_novels_safe(data: list[dict[str, Any]]) -> None:
    try:
        write_json(str(_NOVELS_PATH), data)
    except OSError:
        pass


def _write_sentiment_safe(data: dict[str, dict[str, Any]]) -> None:
    try:
        write_json(str(_SENTIMENT_INDEX_PATH), data)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# 公共读取 API
# ---------------------------------------------------------------------------


def get_all_novels() -> list[dict[str, Any]]:
    """返回所有小说的元数据列表。"""
    _ensure_loaded()
    return list(_novels_cache) if _novels_cache else []


def get_novel(uid: str) -> dict[str, Any] | None:
    """根据 UID 查询单本小说元数据。"""
    _ensure_loaded()
    for novel in _novels_cache or []:
        if novel.get("uid") == uid:
            return dict(novel)
    return None


def get_novel_by_title(title: str) -> dict[str, Any] | None:
    """根据书名模糊查询小说元数据。"""
    _ensure_loaded()
    key = normalize_space(title).lower()
    for novel in _novels_cache or []:
        if normalize_space(novel.get("title", "")).lower() == key:
            return dict(novel)
    # 模糊匹配
    for novel in _novels_cache or []:
        if key in normalize_space(novel.get("title", "")).lower():
            return dict(novel)
    return None


def search_novels(keyword: str) -> list[dict[str, Any]]:
    """关键词搜索小说（匹配书名、作者、标签）。"""
    _ensure_loaded()
    key = normalize_space(keyword).lower()
    if not key:
        return get_all_novels()
    results: list[dict[str, Any]] = []
    for novel in _novels_cache or []:
        title = normalize_space(novel.get("title", "")).lower()
        author = normalize_space(novel.get("author", "")).lower()
        tags = " ".join(novel.get("tags", [])).lower()
        if key in title or key in author or key in tags:
            results.append(dict(novel))
    return results


def get_all_sentiments() -> dict[str, dict[str, Any]]:
    """返回所有舆情评分索引。"""
    _ensure_loaded()
    return dict(_sentiment_cache) if _sentiment_cache else {}


def get_sentiment(uid: str) -> dict[str, Any] | None:
    """根据 UID 查询单本舆情评分。"""
    _ensure_loaded()
    data = (_sentiment_cache or {}).get(uid)
    return dict(data) if data else None


def get_sentiment_by_title(title: str) -> dict[str, Any] | None:
    """根据书名查询舆情评分。"""
    novel = get_novel_by_title(title)
    if novel:
        return get_sentiment(novel["uid"])
    return None


def get_full_sentiment(uid: str) -> dict[str, Any] | None:
    """返回符合 sentiment_api Data Contract 格式的完整舆情数据。"""
    novel = get_novel(uid)
    if novel is None:
        return None
    sentiment = get_sentiment(uid)
    if sentiment is None:
        return None
    return {
        "uid": novel["uid"],
        "metadata": {
            "title": novel["title"],
            "platform": novel["platform"],
            "last_update": novel.get("last_update", ""),
        },
        "sentiment_scores": {
            "overall": sentiment.get("overall", 0),
            "style": sentiment.get("style", 0),
            "logic": sentiment.get("logic", 0),
            "character": sentiment.get("character", 0),
            "update_stability": sentiment.get("update_stability", 0),
            "toxicity_index": sentiment.get("toxicity_index", 0),
        },
        "critic_summary": {
            "one_liner": sentiment.get("one_liner", ""),
            "pros": sentiment.get("pros", []),
            "cons": sentiment.get("cons", []),
        },
        "review_stats": {
            "total_count": sentiment.get("review_count", 0),
            "positive_ratio": sentiment.get("positive_ratio", 0),
            "negative_ratio": sentiment.get("negative_ratio", 0),
            "source_breakdown": sentiment.get("source_breakdown", {}),
        },
    }


def get_novel_list_for_search() -> list[dict[str, Any]]:
    """返回适合 Safe-Search 索引的小说列表格式。"""
    _ensure_loaded()
    results: list[dict[str, Any]] = []
    for novel in _novels_cache or []:
        sentiment = (_sentiment_cache or {}).get(novel["uid"], {})
        results.append({
            "id": novel["uid"],
            "title": novel["title"],
            "intro": novel.get("intro", ""),
            "tags": novel.get("tags", []),
            "platform": novel.get("platform", "unknown"),
            "platform_id": novel.get("platform_id", ""),
            "author": novel.get("author", ""),
            "status": novel.get("status"),
            "sentiment_summary": sentiment.get("one_liner", ""),
        })
    return results


# ---------------------------------------------------------------------------
# 公共写入 API
# ---------------------------------------------------------------------------


def save_novels(novels: list[dict[str, Any]]) -> None:
    """覆盖写入 novels.json 并刷新缓存。"""
    global _novels_cache
    _ensure_loaded()
    write_json(str(_NOVELS_PATH), novels)
    _novels_cache = list(novels)


def upsert_novel(novel: dict[str, Any]) -> None:
    """插入或更新单本小说元数据。"""
    _ensure_loaded()
    uid = novel.get("uid", "")
    if not uid:
        return
    for i, existing in enumerate(_novels_cache or []):
        if existing.get("uid") == uid:
            _novels_cache[i] = dict(novel)
            write_json(str(_NOVELS_PATH), _novels_cache)
            return
    _novels_cache.append(dict(novel))
    write_json(str(_NOVELS_PATH), _novels_cache)


def save_sentiment_index(index: dict[str, dict[str, Any]]) -> None:
    """覆盖写入 sentiment_index.json 并刷新缓存。"""
    global _sentiment_cache
    _ensure_loaded()
    write_json(str(_SENTIMENT_INDEX_PATH), index)
    _sentiment_cache = dict(index)


def upsert_sentiment(uid: str, data: dict[str, Any]) -> None:
    """插入或更新单条舆情评分。"""
    _ensure_loaded()
    if _sentiment_cache is None:
        _sentiment_cache = {}
    _sentiment_cache[uid] = dict(data)
    write_json(str(_SENTIMENT_INDEX_PATH), _sentiment_cache)


# ---------------------------------------------------------------------------
# 从评论数据构建舆情索引
# ---------------------------------------------------------------------------


def build_sentiment_from_analysis_reports(reports_dir: str | None = None) -> dict[str, dict[str, Any]]:
    """扫描分析报告目录，聚合为 sentiment_index 格式。"""
    if reports_dir is None:
        reports_dir = str(_PACKAGE_DIR.parent / "outputs" / "runs")
    reports_path = Path(reports_dir)
    if not reports_path.exists():
        return {}

    merged: dict[str, dict[str, Any]] = {}
    for report_file in sorted(reports_path.rglob("analysis_report.json")):
        try:
            report = read_json(str(report_file))
        except (json.JSONDecodeError, OSError):
            continue
        book_title = report.get("book", "")
        if not book_title:
            continue
        novel = get_novel_by_title(book_title)
        if not novel:
            continue
        uid = novel["uid"]
        avg = report.get("average_scores", {})
        ratio = report.get("ratio", {})
        platform_bd = report.get("platform_breakdown", {})
        merged[uid] = {
            "uid": uid,
            "overall": round(avg.get("sentiment", 0) * 5 + 5, 1),
            "style": round(avg.get("writing", 0), 1),
            "logic": round(avg.get("logic", 0), 1),
            "character": round(avg.get("character", 0), 1),
            "update_stability": round(avg.get("update_speed", 0), 1),
            "toxicity_index": round(avg.get("toxicity", 0), 2),
            "one_liner": report.get("verdict", ""),
            "pros": [t["tag"] for t in report.get("top_tags", [])[:3] if t.get("count", 0) > 1],
            "cons": [],
            "review_count": report.get("review_count", 0),
            "positive_ratio": ratio.get("positive", 0),
            "negative_ratio": ratio.get("negative", 0),
            "source_breakdown": {p: info.get("total", 0) for p, info in platform_bd.items()},
        }
    return merged


def build_novels_from_reviews_and_trends(
    reviews_dir: str | None = None,
    trend_items_dir: str | None = None,
) -> list[dict[str, Any]]:
    """扫描评论和榜单数据，提取小说元数据。"""
    novels: dict[str, dict[str, Any]] = {}

    # 从评论数据提取
    search_dirs = [Path(reviews_dir)] if reviews_dir else [_DATA_DIR]
    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        for jsonl_file in sorted(search_dir.glob("*.jsonl")):
            try:
                reviews = read_jsonl(str(jsonl_file))
            except (ValueError, OSError):
                continue
            for review in reviews:
                title = normalize_space(review.book)
                if not title or len(title) < 2:
                    continue
                if title not in novels:
                    novels[title] = {
                        "uid": review.uid or "",
                        "title": title,
                        "author": review.author or "",
                        "platform": review.platform,
                        "platform_id": review.platform_id or f"{review.platform}:{title}",
                        "tags": [],
                        "status": "unknown",
                        "intro": "",
                        "last_update": review.collected_at or "",
                        "heat_score": 0.0,
                    }
                existing = novels[title]
                if review.author and not existing["author"]:
                    existing["author"] = review.author
                if review.platform and existing["platform"] == "unknown":
                    existing["platform"] = review.platform

    # 从榜单数据补充热度 + 新建仅存在于榜单的小说
    if trend_items_dir:
        trend_path = Path(trend_items_dir)
    else:
        trend_path = _DATA_DIR / "trend_items"
    if trend_path.exists():
        for jsonl_file in sorted(trend_path.glob("*.jsonl")):
            try:
                with open(jsonl_file, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        item = json.loads(line)
                        title = normalize_space(item.get("title", ""))
                        if not title:
                            continue
                        if title in novels:
                            existing = novels[title]
                        else:
                            # 榜单小说新建条目
                            platform = item.get("platform", "unknown")
                            pid = item.get("detailUrl") or f"{platform}:{title}"
                            try:
                                from .models import generate_uid
                                uid = generate_uid(pid, title)
                            except Exception:
                                uid = ""
                            existing = novels[title] = {
                                "uid": uid,
                                "title": title,
                                "author": item.get("author") or "",
                                "platform": platform,
                                "platform_id": pid,
                                "tags": [],
                                "status": "unknown",
                                "intro": item.get("summary") or "",
                                "last_update": item.get("capturedAt") or "",
                                "heat_score": 0.0,
                            }
                        heat = item.get("heatScore", 0)
                        if heat and heat > existing.get("heat_score", 0):
                            existing["heat_score"] = float(heat)
                        if item.get("author") and not existing.get("author"):
                            existing["author"] = item["author"]
                        tags = item.get("tags", [])
                        if tags:
                            existing_tags = set(existing.get("tags", []))
                            for tag in tags:
                                tag = normalize_space(str(tag))
                                if tag and tag not in existing_tags:
                                    existing_tags.add(tag)
                            existing["tags"] = list(existing_tags)
            except (json.JSONDecodeError, OSError):
                continue

    return list(novels.values()) if novels else []


# ---------------------------------------------------------------------------
# 兼容旧 API 的 Mock 响应构建
# ---------------------------------------------------------------------------


def _match_sentiment_by_title(novel: dict[str, Any]) -> dict[str, Any] | None:
    """按书名匹配舆情数据（先精确 UID，再标题匹配 fallback）。"""
    uid = novel.get("uid", "")
    title = normalize_space(novel.get("title", "")).lower()

    # 优先 UID 精确匹配
    if uid and uid in (_sentiment_cache or {}):
        return _sentiment_cache[uid]
    if uid and uid in _FALLBACK_SENTIMENT:
        return _FALLBACK_SENTIMENT[uid]

    # 按标题匹配 fallback
    for fallback_uid, fallback_sent in _FALLBACK_SENTIMENT.items():
        fallback_novel = None
        for fn in _FALLBACK_NOVELS:
            if fn["uid"] == fallback_uid:
                fallback_novel = fn
                break
        if fallback_novel and normalize_space(fallback_novel.get("title", "")).lower() == title:
            return fallback_sent

    return None


def build_mock_sentiment_store() -> dict[str, dict[str, Any]]:
    """构建与旧 sentiment_api._SENTIMENT_STORE 兼容的内存数据结构。

    优先使用真实数据，缺失时按标题回退到 Mock，确保所有已知小说都有舆情数据。
    """
    _ensure_loaded()
    print(f"[DEBUG build_mock_sentiment_store] novels_cache={len(_novels_cache) if _novels_cache else 0}, "
          f"sentiment_cache={len(_sentiment_cache) if _sentiment_cache else 0}, "
          f"cache_loaded={_cache_loaded}", flush=True)
    store: dict[str, dict[str, Any]] = {}

    # 合并真实小说 + fallback 小说（去重按标题）
    all_novels: dict[str, dict[str, Any]] = {}
    for novel in _FALLBACK_NOVELS:
        key = normalize_space(novel.get("title", "")).lower()
        if key:
            all_novels[key] = dict(novel)
    for novel in _novels_cache or []:
        key = normalize_space(novel.get("title", "")).lower()
        if key:
            if key in all_novels:
                # 合并：保留真实数据中的字段，补充 fallback 中缺失的
                existing = all_novels[key]
                for field in ("uid", "author", "tags", "intro", "status"):
                    if novel.get(field) and not existing.get(field):
                        existing[field] = novel[field]
            else:
                all_novels[key] = dict(novel)

    for novel in all_novels.values():
        uid = novel.get("uid", "")
        if not uid:
            continue

        sentiment = _match_sentiment_by_title(novel)
        if sentiment is None:
            continue

        store[uid] = {
            "uid": uid,
            "metadata": {
                "title": novel["title"],
                "platform": novel.get("platform", "unknown"),
                "last_update": novel.get("last_update", ""),
            },
            "sentiment_scores": {
                "overall": sentiment.get("overall", 0),
                "style": sentiment.get("style", 0),
                "logic": sentiment.get("logic", 0),
                "character": sentiment.get("character", 0),
                "update_stability": sentiment.get("update_stability", 0),
                "toxicity_index": sentiment.get("toxicity_index", 0),
            },
            "critic_summary": {
                "one_liner": sentiment.get("one_liner", ""),
                "pros": sentiment.get("pros", []),
                "cons": sentiment.get("cons", []),
            },
            "review_stats": {
                "total_count": sentiment.get("review_count", 0),
                "positive_ratio": sentiment.get("positive_ratio", 0),
                "negative_ratio": sentiment.get("negative_ratio", 0),
                "source_breakdown": sentiment.get("source_breakdown", {}),
            },
        }

    print(f"[DEBUG build_mock_sentiment_store] all_novels={len(all_novels)}, store={len(store)}, "
          f"fallback only={len(store) <= 5}", flush=True)
    return store
