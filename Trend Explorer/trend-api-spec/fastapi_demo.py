from __future__ import annotations

import hashlib
import json
import math
import os
import re
import subprocess
import threading
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CRAWLER_DIR = Path(os.getenv("CRAWLER_DIR", PROJECT_ROOT / "crawler-engine-v1.0"))
DATA_DIR = Path(os.getenv("TREND_DATA_DIR", CRAWLER_DIR / "data"))
ALLOW_CRAWLER_RUN = os.getenv("ALLOW_CRAWLER_RUN", "true").strip().lower() in {"1", "true", "yes", "on"}
DEFAULT_RUN_MODE: Literal["docker", "local"] = os.getenv("CRAWLER_RUN_MODE", "docker").strip().lower()  # type: ignore[assignment]
CRAWLER_TIMEOUT_SECONDS = int(os.getenv("CRAWLER_TIMEOUT_SECONDS", "3600"))
TREND_READ_MODE = os.getenv("TREND_READ_MODE", "latest").strip().lower()
REQUIRED_MONTHLY_TICKET_MONTHS = [
    month.strip()
    for month in os.getenv("REQUIRED_MONTHLY_TICKET_MONTHS", "20261,20262,20263,20264,20265").split(",")
    if month.strip()
]

EXCLUDED_TAGS = {
    "已签约",
    "签约",
    "未签约",
    "连载中",
    "连载",
    "已完结",
    "完结",
    "已完成",
    "vip",
    "VIP",
}

MONTH_RE = re.compile(r"(20\d{2})年\s*(\d{1,2})月")
MONTH_PARAM_RE = re.compile(r"month=(20\d{2})(\d{1,2})")

FLOW_RULES = [
    ("传统升级流", "反套路群像流", ["传统玄幻", "升级流"], ["反套路", "群像"]),
    ("系统流", "轻量金手指", ["系统流"], ["轻量金手指", "金手指"]),
    ("废土生存", "规则怪谈", ["废土生存"], ["规则怪谈", "规则限制", "副本"]),
    ("单主角爽文", "家族崛起群像", ["爽文", "无敌流"], ["家族崛起", "群像"]),
    ("门派经营", "宗族势力经营", ["门派经营", "宗门经营"], ["宗族势力", "家族崛起"]),
    ("单线复仇", "权谋博弈", ["复仇"], ["权谋博弈", "权谋"]),
]

GENRE_RULES = [
    ("传统玄幻", ["玄幻奇幻", "传统玄幻", "剑道", "热血", "高燃"]),
    ("系统流", ["系统流", "金手指", "轻量金手指"]),
    ("家族群像流", ["家族崛起", "宗族势力", "群像"]),
    ("仙侠修真", ["武侠仙侠", "仙侠", "修真"]),
    ("都市爽文", ["都市", "爽文", "多女主"]),
    ("规则怪谈", ["规则怪谈", "规则限制", "副本", "诡异"]),
    ("废土生存", ["废土生存", "末世"]),
    ("权谋博弈", ["权谋", "博弈", "历史"]),
    ("女强逆袭", ["女强", "逆袭"]),
]


def generate_uid(platform_id: str, novel_title: str) -> str:
    """Generate SHA256 UID per System Integrator spec: SHA256(platform_id + "|" + novel_title)."""
    raw = f"{platform_id}|{novel_title.strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def record_uid(item: dict[str, Any]) -> str:
    """Derive a stable UID for a trend record, using detailUrl or title as platform_id."""
    platform = item.get("platform") or "unknown"
    title = item.get("title") or "unknown"
    platform_id = item.get("detailUrl") or f"{platform}:{title}"
    return generate_uid(platform_id, title)


def trend_direction_from_change(change: float) -> str:
    if change >= 5:
        return "rising"
    if change <= -5:
        return "declining"
    return "stable"


def heat_score_normalized(heat: float, max_heat: float) -> float:
    if max_heat <= 0:
        return 0.0
    return round(min(1.0, max(0.0, heat / max_heat)), 4)


app = FastAPI(title="Novel Trend Windvane API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_x_trend_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Module"] = "trend-explorer"
    return response


class CrawlRunRequest(BaseModel):
    target: Literal["zongheng", "all"] = "zongheng"
    mode: Literal["docker", "local"] | None = None


class CrawlJob(BaseModel):
    id: str
    target: Literal["zongheng", "all"]
    mode: Literal["docker", "local"]
    status: Literal["queued", "running", "succeeded", "failed"]
    startedAt: str | None = None
    finishedAt: str | None = None
    exitCode: int | None = None
    message: str | None = None
    stdoutTail: str | None = None
    stderrTail: str | None = None


JOBS: dict[str, CrawlJob] = {}
JOBS_LOCK = threading.Lock()


def envelope(data: Any, message: str = "success") -> dict[str, Any]:
    return {
        "code": 0,
        "message": message,
        "data": data,
        "timestamp": now_iso(),
    }


@app.get("/api/health")
def health() -> dict[str, Any]:
    return envelope({"status": "ok", "dataDir": str(DATA_DIR), "crawlerDir": str(CRAWLER_DIR)})


@app.post("/api/crawler/run")
def run_crawler(request: CrawlRunRequest) -> dict[str, Any]:
    if not ALLOW_CRAWLER_RUN:
        raise HTTPException(status_code=403, detail="Crawler run is disabled by ALLOW_CRAWLER_RUN=false.")

    with JOBS_LOCK:
        for job in JOBS.values():
          if job.status in {"queued", "running"}:
              return envelope(job_dump(job), "crawler already running")

        job = CrawlJob(
            id=uuid.uuid4().hex,
            target=request.target,
            mode=request.mode or DEFAULT_RUN_MODE,
            status="queued",
        )
        JOBS[job.id] = job

    thread = threading.Thread(target=execute_crawler_job, args=(job.id,), daemon=True)
    thread.start()
    return envelope(job_dump(job), "crawler job created")


@app.get("/api/crawler/jobs/{job_id}")
def get_crawler_job(job_id: str) -> dict[str, Any]:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Crawler job not found.")
    return envelope(job_dump(job))


@app.get("/api/trends/dashboard")
def get_dashboard() -> dict[str, Any]:
    return envelope(build_dashboard())


@app.get("/api/trends/hot-tags")
def get_hot_tags() -> dict[str, Any]:
    return envelope(build_dashboard()["hotTags"])


@app.get("/api/trends/heat-curve")
def get_heat_curve() -> dict[str, Any]:
    return envelope(build_dashboard()["heatCurve"])


@app.get("/api/trends/platform-compare")
def get_platform_compare() -> dict[str, Any]:
    return envelope(build_dashboard()["platformCompare"])


@app.get("/api/trends/genre-migration")
def get_genre_migration() -> dict[str, Any]:
    return envelope(build_dashboard()["migration"])


@app.get("/api/trends/genre-migration-timeline")
def get_genre_migration_timeline() -> dict[str, Any]:
    return envelope(build_dashboard()["migrationTimeline"])


@app.get("/api/trends/genre-cloud-timeline")
def get_genre_cloud_timeline() -> dict[str, Any]:
    return envelope(build_dashboard()["genreCloudTimeline"])


@app.get("/api/trends/rising-works")
def get_rising_works() -> dict[str, Any]:
    return envelope(build_dashboard()["risingWorks"])


@app.get("/api/trends/summary")
def get_summary() -> dict[str, Any]:
    return envelope({"summary": build_dashboard()["summary"]})


@app.get("/api/debug/monthly-coverage")
def get_monthly_coverage() -> dict[str, Any]:
    records = load_records()
    monthly_records = [item for item in records if is_monthly_ticket_record(item)]
    return envelope(build_monthly_coverage(monthly_records))


# ============================================================
# Data Contract v1.0 端点 (跨模块通信)
# ============================================================

@app.get("/api/v1/trend/hot")
def get_trend_hot(limit: int = Query(20, ge=1, le=100)) -> dict[str, Any]:
    """热门趋势榜单 — 符合 Data Contract TrendData 结构."""
    records = load_records()
    if not records:
        return {"items": [], "total": 0}

    all_context = build_context(records)
    rising = build_rising_works(all_context)
    hot_tags = build_hot_tags(build_context([r for r in records if is_monthly_ticket_record(r)], score_mode="raw_heat"))
    max_heat = max((item.get("heatScore", 0) for item in records), default=1)

    items: list[dict[str, Any]] = []
    for work in rising[:limit]:
        uid = record_uid(work)
        heat = float(work.get("heatScore", 0))
        change = float(work.get("rankChange", 0))
        items.append({
            "uid": uid,
            "metadata": {
                "title": work.get("title", ""),
                "platform": work.get("platform", ""),
                "last_update": work.get("capturedAt") or now_iso(),
            },
            "trend_metrics": {
                "heat_score": heat_score_normalized(heat, max_heat),
                "rank": work.get("rank") or 0,
                "rank_change": work.get("rankChange") or 0,
                "tags": work.get("tags") or [],
                "trend_direction": trend_direction_from_change(change),
                "history_7d": _build_history_7d(work, records),
            },
        })
    return {"items": items, "total": len(rising)}


@app.get("/api/v1/trend/detail/{uid}")
def get_trend_detail(uid: str) -> dict[str, Any]:
    """单书趋势详情 — 符合 Data Contract TrendData 结构."""
    records = load_records()
    max_heat = max((float(r.get("heatScore", 0)) for r in records), default=1)

    for record in records:
        if record_uid(record) == uid:
            heat = float(record.get("heatScore", 0))
            change = float(record.get("rankChange", 0))
            return {
                "uid": uid,
                "metadata": {
                    "title": record.get("title", ""),
                    "platform": record.get("platform", ""),
                    "last_update": record.get("capturedAt") or now_iso(),
                },
                "trend_metrics": {
                    "heat_score": heat_score_normalized(heat, max_heat),
                    "rank": record.get("rank") or 0,
                    "rank_change": record.get("rankChange") or 0,
                    "tags": record.get("tags") or [],
                    "trend_direction": trend_direction_from_change(change),
                    "history_7d": _build_history_7d(record, records),
                },
            }
    raise HTTPException(status_code=404, detail=f"UID not found: {uid}")


@app.get("/api/v1/trend/tags/evolution")
def get_tags_evolution(
    tag: str = Query(..., description="标签名称"),
    period: str = Query("30d", description="时间范围: 7d / 30d / 90d"),
) -> dict[str, Any]:
    """标签演变数据 — 返回标签在各时间段的 heat 变化."""
    records = load_records()
    monthly = [r for r in records if is_monthly_ticket_record(r)]
    context = build_context(monthly, score_mode="raw_heat")
    tag_period = context["tagPeriod"]
    periods = context["periods"]

    period_limit = {"7d": 1, "30d": 4, "90d": 12}.get(period, 4)

    evolution: list[dict[str, Any]] = []
    selected_periods = periods[-period_limit:] if len(periods) > period_limit else periods
    for period_key, period_label in selected_periods:
        heat = tag_period.get(tag, {}).get(period_key, 0)
        evolution.append({"date": period_key, "heat": round(heat, 2), "label": period_label})

    # Related works for this tag
    tag_works = context["tagWorks"].get(tag, {})
    related_works = sorted(tag_works.items(), key=lambda p: p[1], reverse=True)[:10]

    return {
        "tag": tag,
        "period": period,
        "evolution": evolution,
        "trend": trend_direction_from_change(
            calc_change(
                evolution[0]["heat"] if evolution else 0,
                evolution[-1]["heat"] if evolution else 0,
            )
        ),
        "related_works": [{"title": t, "heat": round(h, 2)} for t, h in related_works],
    }


def _build_history_7d(record: dict[str, Any], all_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build synthetic 7-day history from records of the same work."""
    work_title = record.get("title", "")
    work_platform = record.get("platform", "")
    matching = [
        r for r in all_records
        if r.get("title") == work_title and r.get("platform") == work_platform
    ]
    matching.sort(key=lambda r: r.get("capturedAt", ""))
    max_heat = max((float(r.get("heatScore", 0)) for r in matching), default=1)
    return [
        {
            "date": (r.get("capturedAt") or "")[:10],
            "heat_score": heat_score_normalized(float(r.get("heatScore", 0)), max_heat),
        }
        for r in matching[-7:]
    ]


def execute_crawler_job(job_id: str) -> None:
    with JOBS_LOCK:
        job = JOBS[job_id]
        job.status = "running"
        job.startedAt = now_iso()
        JOBS[job_id] = job

    command = build_crawler_command(job.target, job.mode)
    env = os.environ.copy()
    env.setdefault("ENABLE_QIDIAN", "false")

    try:
        result = subprocess.run(
            command,
            cwd=CRAWLER_DIR,
            env=env,
            capture_output=True,
            text=True,
            timeout=CRAWLER_TIMEOUT_SECONDS,
            check=False,
        )
        status = "succeeded" if result.returncode == 0 else "failed"
        message = "采集完成" if result.returncode == 0 else f"采集失败，退出码 {result.returncode}"
        update_job(
            job_id,
            status=status,
            finishedAt=now_iso(),
            exitCode=result.returncode,
            message=message,
            stdoutTail=tail(result.stdout),
            stderrTail=tail(result.stderr),
        )
    except Exception as exc:  # pragma: no cover - defensive runtime boundary
        update_job(
            job_id,
            status="failed",
            finishedAt=now_iso(),
            message=str(exc),
        )


def build_crawler_command(target: str, mode: str) -> list[str]:
    if mode == "docker":
        service = "crawler-zongheng" if target == "zongheng" else "crawler-all-once"
        return ["docker", "compose", "--profile", "manual", "run", "--build", "--rm", service]

    if target == "zongheng":
        return ["scrapy", "crawl", "zongheng_trends"]

    # Cross-platform: prefer PowerShell on Windows, bash on Linux
    if os.name == "nt":
        return ["powershell", "-ExecutionPolicy", "Bypass", "-File", "scripts\\run_all_once.ps1"]
    return ["bash", "scripts/run_all_once.sh"]


def update_job(job_id: str, **updates: Any) -> None:
    with JOBS_LOCK:
        job = JOBS[job_id]
        payload = job_dump(job)
        payload.update(updates)
        JOBS[job_id] = CrawlJob(**payload)


def job_dump(job: CrawlJob) -> dict[str, Any]:
    if hasattr(job, "model_dump"):
        return job.model_dump()
    return job.dict()


def build_dashboard() -> dict[str, Any]:
    records = load_records()
    generated_at = now_iso()
    if not records:
        return empty_dashboard(generated_at)

    monthly_records = [item for item in records if is_monthly_ticket_record(item)]
    all_context = build_context(records)
    monthly_context = build_context(monthly_records, score_mode="raw_heat")
    hot_tags = build_hot_tags(monthly_context)
    heat_curve = build_heat_curve(monthly_context, hot_tags)
    platform_compare = build_platform_compare(all_context)
    active_platform_count = sum(1 for item in platform_compare if item["status"] == "active")
    genre_cloud_timeline = build_genre_cloud_timeline(monthly_context)
    data_quality = build_monthly_coverage(monthly_records)
    migration, migration_timeline = build_migration(monthly_context)
    rising_works = build_rising_works(all_context)

    return {
        "generatedAt": generated_at,
        "summary": build_summary(records, monthly_records, hot_tags, platform_compare, genre_cloud_timeline),
        "metrics": [
            {
                "id": "hot-tags",
                "label": "细标签数",
                "value": str(len(hot_tags)),
                "delta": avg_change(hot_tags),
                "tone": "green",
            },
            {
                "id": "rising-works",
                "label": "上升作品",
                "value": str(len(rising_works)),
                "delta": avg_positive_rank_change(rising_works),
                "tone": "amber",
            },
            {
                "id": "platforms",
                "label": "监测平台",
                "value": str(active_platform_count),
                "deltaLabel": f"{active_platform_count} 个可用",
                "tone": "blue",
            },
            {
                "id": "migration",
                "label": "流派月份",
                "value": str(len(genre_cloud_timeline["clouds"])),
                "delta": genre_cloud_delta(genre_cloud_timeline),
                "tone": "rose",
            },
        ],
        "heatCurve": heat_curve,
        "hotTags": hot_tags,
        "platformCompare": platform_compare,
        "wordCloud": [{"name": item["tag"], "value": item["heat"]} for item in hot_tags[:24]],
        "migration": migration,
        "migrationTimeline": migration_timeline,
        "genreCloudTimeline": genre_cloud_timeline,
        "risingWorks": rising_works,
        "dataQuality": data_quality,
    }


def load_records() -> list[dict[str, Any]]:
    if not DATA_DIR.exists():
        return []

    deduped: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    files = select_jsonl_files()
    for path in files:
        with path.open("r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                normalize_record(item)
                period_key, _ = period_from_item(item)
                list_key = canonical_list_key(item)
                key = (
                    item.get("detailUrl") or item.get("title") or item.get("id") or "",
                    list_key,
                    item.get("platform") or "",
                    period_key,
                )
                deduped[key] = item
    return list(deduped.values())


def select_jsonl_files() -> list[Path]:
    files = sorted(DATA_DIR.glob("*.jsonl"), key=lambda path: path.stat().st_mtime)
    if not files:
        return []
    if TREND_READ_MODE == "all":
        return files
    return [files[-1]]


def canonical_list_key(item: dict[str, Any]) -> str:
    """Normalize list identity so repeated historical exports do not duplicate the same monthly rank."""

    if is_monthly_ticket_record(item):
        return "monthly-ticket"
    return item.get("listType") or ""


def normalize_record(item: dict[str, Any]) -> None:
    item["title"] = clean_text(item.get("title")) or "未知作品"
    item["platform"] = clean_text(item.get("platform")) or "未知平台"
    item["listType"] = clean_text(item.get("listType")) or "未知榜单"
    item["category"] = clean_text(item.get("category"))
    item["summary"] = clean_text(item.get("summary"))
    item["author"] = clean_text(item.get("author"))
    item["detailUrl"] = clean_text(item.get("detailUrl"))
    item["capturedAt"] = clean_text(item.get("capturedAt")) or now_iso()
    item["rank"] = to_int(item.get("rank"), 0)
    item["rankChange"] = to_int(item.get("rankChange"), 0)
    item["heatScore"] = to_float(item.get("heatScore"), 0)
    item["tags"] = normalize_tags(item.get("tags"), item.get("category"))


def build_context(records: list[dict[str, Any]], score_mode: Literal["weighted", "raw_heat"] = "weighted") -> dict[str, Any]:
    periods = build_periods(records)
    tag_total: defaultdict[str, float] = defaultdict(float)
    tag_period: defaultdict[str, defaultdict[str, float]] = defaultdict(lambda: defaultdict(float))
    tag_works: defaultdict[str, dict[str, float]] = defaultdict(dict)
    platform_total: defaultdict[str, float] = defaultdict(float)
    platform_tags: defaultdict[str, defaultdict[str, float]] = defaultdict(lambda: defaultdict(float))
    works_by_key: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)

    for item in records:
        score = monthly_heat_score(item) if score_mode == "raw_heat" else score_item(item)
        period_key = period_from_item(item)[0]
        work_key = item.get("detailUrl") or item["title"]
        works_by_key[work_key].append(item)
        platform_total[item["platform"]] += score

        for tag in item["tags"]:
            tag_total[tag] += score
            tag_period[tag][period_key] += score
            tag_works[tag][item["title"]] = max(tag_works[tag].get(item["title"], 0), score)
            platform_tags[item["platform"]][tag] += score

    return {
        "records": records,
        "scoreMode": score_mode,
        "periods": periods,
        "tagTotal": tag_total,
        "tagPeriod": tag_period,
        "tagWorks": tag_works,
        "platformTotal": platform_total,
        "platformTags": platform_tags,
        "worksByKey": works_by_key,
    }


def build_periods(records: list[dict[str, Any]]) -> list[tuple[str, str]]:
    periods: dict[str, str] = {}
    for item in records:
        key, label = period_from_item(item)
        periods[key] = label
    return sorted(periods.items(), key=lambda pair: pair[0])[-8:]


def build_hot_tags(context: dict[str, Any]) -> list[dict[str, Any]]:
    tag_total = context["tagTotal"]
    tag_period = context["tagPeriod"]
    tag_works = context["tagWorks"]
    periods = [key for key, _ in context["periods"]]
    max_score = max(tag_total.values(), default=1)

    rows = []
    for tag, score in sorted(tag_total.items(), key=lambda pair: pair[1], reverse=True):
        if not tag:
            continue
        heat = round(score / max_score * 100)
        first, last = first_last_values([tag_period[tag].get(period, 0) for period in periods])
        change = calc_change(first, last)
        works = sorted(tag_works[tag].items(), key=lambda pair: pair[1], reverse=True)
        rows.append(
            {
                "tag": tag,
                "heat": heat,
                "change": change,
                "group": tag_group(tag),
                "stage": tag_stage(change),
                "relatedWorks": [title for title, _ in works[:5]],
            }
        )
    return rows


def build_heat_curve(context: dict[str, Any], hot_tags: list[dict[str, Any]]) -> dict[str, Any]:
    periods = context["periods"]
    tag_period = context["tagPeriod"]
    selected_tags = [item["tag"] for item in hot_tags]
    series = []
    for tag in selected_tags:
        values = [to_k(tag_period[tag].get(period_key, 0)) for period_key, _ in periods]
        series.append(
            {
                "name": tag,
                "data": values,
                "description": f"{tag} 仅按历史月票榜统计，作品月票会同时贡献给该作品的所有细标签。",
            }
        )
    return {
        "dates": [label for _, label in periods],
        "series": series,
        "unit": "k",
        "source": "monthly-ticket",
        "valueLabel": "月票",
    }


def build_platform_compare(context: dict[str, Any]) -> list[dict[str, Any]]:
    platform_total = context["platformTotal"]
    platform_tags = context["platformTags"]
    max_score = max(platform_total.values(), default=1)
    rows = []
    for platform, score in sorted(platform_total.items(), key=lambda pair: pair[1], reverse=True):
        rows.append(
            {
                "platform": platform,
                "heat": round(score / max_score * 100),
                "works": sum(1 for item in context["records"] if item["platform"] == platform),
                "topTags": [tag for tag, _ in sorted(platform_tags[platform].items(), key=lambda pair: pair[1], reverse=True)[:6]],
                "status": "active",
            }
        )
    return rows


def build_genre_cloud_timeline(context: dict[str, Any]) -> dict[str, Any]:
    periods = context["periods"]
    genre_period: defaultdict[str, defaultdict[str, float]] = defaultdict(lambda: defaultdict(float))

    for item in context["records"]:
        period_key = period_from_item(item)[0]
        heat = monthly_heat_score(item)
        for genre in resolve_genres(item):
            genre_period[period_key][genre] += heat

    clouds = []
    for period_key, label in periods:
        genres = [
            {"name": genre, "value": to_k(score)}
            for genre, score in sorted(genre_period[period_key].items(), key=lambda pair: pair[1], reverse=True)
            if score > 0
        ]
        clouds.append({"period": label, "genres": genres[:18]})

    return {
        "periods": [label for _, label in periods],
        "unit": "k",
        "clouds": clouds,
        "summary": summarize_genre_clouds(clouds),
    }


def build_migration(context: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    tag_total = context["tagTotal"]
    tag_period = context["tagPeriod"]
    periods = context["periods"]
    raw_links = []

    for source, target, source_tags, target_tags in FLOW_RULES:
        source_score = sum_tag_scores(tag_total, source_tags)
        target_score = sum_tag_scores(tag_total, target_tags)
        raw_score = source_score * 0.35 + target_score
        if raw_score <= 0:
            continue

        period_values = []
        for period_key, _ in periods:
            value = (
                sum_tag_scores(tag_period, source_tags, period_key) * 0.35
                + sum_tag_scores(tag_period, target_tags, period_key)
            )
            period_values.append(value)
        first, last = first_last_values(period_values)
        raw_links.append((source, target, raw_score, calc_change(first, last), period_values))

    max_score = max((item[2] for item in raw_links), default=1)
    links = []
    timeline_flows = []
    for source, target, raw_score, change, period_values in raw_links:
        link_value = max(1, round(raw_score / max_score * 28))
        links.append(
            {
                "source": source,
                "target": target,
                "value": link_value,
                "change": change,
                "reason": migration_reason(source, target),
            }
        )
        max_period_value = max(period_values, default=1) or 1
        timeline_flows.append(
            {
                "id": f"{source}-{target}",
                "source": source,
                "target": target,
                "values": [max(1, round(value / max_period_value * link_value)) for value in period_values],
                "reason": migration_reason(source, target),
            }
        )

    nodes = sorted({name for link in links for name in (link["source"], link["target"])})
    return (
        {"nodes": [{"name": name} for name in nodes], "links": links},
        {"periods": [label for _, label in periods], "flows": timeline_flows},
    )


def build_rising_works(context: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for work_items in context["worksByKey"].values():
        sorted_items = sorted(work_items, key=lambda item: (period_from_item(item)[0], item.get("capturedAt", "")))
        latest = sorted_items[-1]
        rank_change = latest.get("rankChange") or derive_rank_change(sorted_items)
        rows.append(
            {
                "id": latest.get("id") or uuid.uuid5(uuid.NAMESPACE_URL, latest["title"]).hex,
                "title": latest["title"],
                "author": latest.get("author"),
                "platform": latest["platform"],
                "category": latest.get("category"),
                "tags": latest["tags"],
                "detailUrl": latest.get("detailUrl"),
                "rank": latest["rank"],
                "rankChange": rank_change,
                "heatScore": round(latest["heatScore"], 2),
                "listType": latest["listType"],
                "summary": latest.get("summary"),
                "capturedAt": latest.get("capturedAt"),
            }
        )
    return sorted(rows, key=lambda item: (item["rankChange"], item["heatScore"]), reverse=True)[:60]


def empty_dashboard(generated_at: str) -> dict[str, Any]:
    return {
        "generatedAt": generated_at,
        "summary": "尚未发现可用趋势数据，请先运行采集任务。",
        "metrics": [],
        "heatCurve": {"dates": [], "series": []},
        "hotTags": [],
        "platformCompare": [],
        "wordCloud": [],
        "migration": {"nodes": [], "links": []},
        "migrationTimeline": {"periods": [], "flows": []},
        "genreCloudTimeline": {"periods": [], "unit": "k", "clouds": [], "summary": "暂无历史月票榜流派数据。"},
        "risingWorks": [],
    }


def build_summary(
    records: list[dict[str, Any]],
    monthly_records: list[dict[str, Any]],
    hot_tags: list[dict[str, Any]],
    platforms: list[dict[str, Any]],
    genre_cloud_timeline: dict[str, Any],
) -> str:
    top_tags = "、".join(item["tag"] for item in hot_tags[:6]) or "暂无标签"
    active_platforms = "、".join(item["platform"] for item in platforms if item["status"] == "active") or "暂无平台"
    genre_summary = genre_cloud_timeline.get("summary") or ""
    return (
        f"本次共聚合 {len(records)} 条公开榜单记录，其中历史月票榜记录 {len(monthly_records)} 条。"
        f"全标签热度趋势只按月票榜统计，高热标签集中在 {top_tags}。"
        f"当前可用平台为 {active_platforms}。{genre_summary}"
    )


def period_from_item(item: dict[str, Any]) -> tuple[str, str]:
    text = f"{item.get('listType', '')} {item.get('sourceUrl', '')}"
    match = MONTH_PARAM_RE.search(text)
    if match:
        year, month = int(match.group(1)), int(match.group(2))
        return f"{year}-{month:02d}", f"{month:02d}月"
    match = MONTH_RE.search(text)
    if match:
        year, month = int(match.group(1)), int(match.group(2))
        return f"{year}-{month:02d}", f"{month:02d}月"
    captured = str(item.get("capturedAt") or "")
    if len(captured) >= 7:
        return captured[:7], captured[5:7] + "月"
    return "current", "当前"


def score_item(item: dict[str, Any]) -> float:
    heat = max(float(item.get("heatScore") or 0), 0)
    rank = max(int(item.get("rank") or 0), 0)
    rank_bonus = max(0, 120 - rank) / 3 if rank else 0
    return math.log1p(heat) * 10 + rank_bonus


def monthly_heat_score(item: dict[str, Any]) -> float:
    return max(float(item.get("heatScore") or 0), 0)


def is_monthly_ticket_record(item: dict[str, Any]) -> bool:
    text = f"{item.get('listType', '')} {item.get('sourceUrl', '')}"
    return ("月票" in text or "monthly-ticket" in text) and bool(month_token_from_item(item))


def month_token_from_item(item: dict[str, Any]) -> str | None:
    text = f"{item.get('listType', '')} {item.get('sourceUrl', '')}"
    match = MONTH_PARAM_RE.search(text)
    if match:
        return f"{match.group(1)}{int(match.group(2))}"
    match = MONTH_RE.search(text)
    if match:
        return f"{match.group(1)}{int(match.group(2))}"
    return None


def build_monthly_coverage(monthly_records: list[dict[str, Any]]) -> dict[str, Any]:
    by_month: dict[str, dict[str, Any]] = {
        month: {
            "month": month,
            "label": f"{month[:4]}年{int(month[4:]):02d}月",
            "records": 0,
            "uniqueWorks": 0,
            "tagCount": 0,
            "heatTotal": 0,
            "expectedRecords": 200,
            "complete": False,
        }
        for month in REQUIRED_MONTHLY_TICKET_MONTHS
    }
    work_sets: defaultdict[str, set[str]] = defaultdict(set)
    tag_sets: defaultdict[str, set[str]] = defaultdict(set)

    for item in monthly_records:
        month = month_token_from_item(item)
        if not month:
            continue
        by_month.setdefault(
            month,
            {
                "month": month,
                "label": f"{month[:4]}年{int(month[4:]):02d}月",
                "records": 0,
                "uniqueWorks": 0,
                "tagCount": 0,
                "heatTotal": 0,
                "expectedRecords": 200,
                "complete": False,
            },
        )
        by_month[month]["records"] += 1
        by_month[month]["heatTotal"] += monthly_heat_score(item)
        work_sets[month].add(item.get("detailUrl") or item.get("title") or item.get("id") or "")
        tag_sets[month].update(item.get("tags") or [])

    for month, row in by_month.items():
        row["uniqueWorks"] = len([value for value in work_sets[month] if value])
        row["tagCount"] = len(tag_sets[month])
        row["heatTotalK"] = to_k(row["heatTotal"])
        row["complete"] = row["records"] == row["expectedRecords"]

    rows = [by_month[month] for month in sorted(by_month)]
    missing = [row["month"] for row in rows if row["records"] == 0]
    incomplete = [row["month"] for row in rows if row["records"] and row["records"] != row["expectedRecords"]]
    return {
        "requiredMonths": REQUIRED_MONTHLY_TICKET_MONTHS,
        "months": rows,
        "missingMonths": missing,
        "incompleteMonths": incomplete,
        "isComplete": not missing and not incomplete,
        "note": "月票趋势仅使用 sourceUrl/listType 中带有 month=20261..20265 的月票榜记录，详情页只补标签。",
    }


def to_k(value: float) -> float:
    scaled = value / 1000
    if scaled >= 100:
        return round(scaled)
    if scaled >= 10:
        return round(scaled, 1)
    return round(scaled, 2)


def resolve_genres(item: dict[str, Any]) -> list[str]:
    text = " ".join([item.get("category") or "", *item.get("tags", [])])
    genres: list[str] = []
    for genre, keywords in GENRE_RULES:
        if any(keyword and keyword in text for keyword in keywords):
            genres.append(genre)
    if not genres and item.get("category"):
        genres.append(str(item["category"]))
    return unique_values(genres[:4])


def summarize_genre_clouds(clouds: list[dict[str, Any]]) -> str:
    if not clouds:
        return "暂无历史月票榜流派数据。"
    first = clouds[0]["genres"][:3]
    latest = clouds[-1]["genres"][:3]
    first_names = "、".join(item["name"] for item in first) or "暂无"
    latest_names = "、".join(item["name"] for item in latest) or "暂无"
    return f"月票榜流派热度从 {first_names} 逐步变化到 {latest_names}，可通过逐月词云观察题材重心迁移。"


def genre_cloud_delta(genre_cloud_timeline: dict[str, Any]) -> float:
    clouds = genre_cloud_timeline.get("clouds") or []
    if len(clouds) < 2:
        return 0
    first_total = sum(item["value"] for item in clouds[0].get("genres", []))
    latest_total = sum(item["value"] for item in clouds[-1].get("genres", []))
    return calc_change(first_total, latest_total)


def normalize_tags(value: Any, category: Any) -> list[str]:
    parts = value if isinstance(value, list) else [value]
    if category:
        parts = [category, *parts]

    seen = set()
    result = []
    for part in parts:
        if part is None:
            continue
        for raw in str(part).replace("/", ",").replace("|", ",").split(","):
            tag = clean_text(raw)
            if not tag or tag in EXCLUDED_TAGS or tag in seen:
                continue
            seen.add(tag)
            result.append(tag)
    return result


def unique_values(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        cleaned = clean_text(value)
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)
    return result


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).strip().split())
    return text or None


def first_last_values(values: list[float]) -> tuple[float, float]:
    non_zero = [value for value in values if value > 0]
    if not non_zero:
        return 0, 0
    return non_zero[0], non_zero[-1]


def calc_change(first: float, last: float) -> float:
    if first <= 0:
        return 0
    return round(max(-99, min(99, (last - first) / first * 100)), 1)


def tag_group(tag: str) -> str:
    if any(word in tag for word in ["玄幻", "仙侠", "都市", "悬疑", "废土", "规则怪谈"]):
        return "题材"
    if any(word in tag for word in ["热血", "高燃", "治愈", "爽文"]):
        return "情绪价值"
    if any(word in tag for word in ["剑道", "权谋", "副本", "系统", "金手指"]):
        return "元素机制"
    if any(word in tag for word in ["群像", "家族", "宗族", "成长", "少年"]):
        return "叙事人设"
    return "细标签"


def tag_stage(change: float) -> str:
    if change >= 12:
        return "rising"
    if change < 0:
        return "cooling"
    return "stable"


def sum_tag_scores(container: Any, tags: list[str], period_key: str | None = None) -> float:
    total = 0.0
    for tag, value in container.items():
        if any(target in tag for target in tags):
            if period_key is None:
                total += float(value)
            else:
                total += float(value.get(period_key, 0))
    return total


def migration_reason(source: str, target: str) -> str:
    return f"{source} 正向 {target} 迁移，说明读者兴趣正在从单点爽感转向更易形成讨论和留存的复合元素。"


def derive_rank_change(items: list[dict[str, Any]]) -> int:
    monthly = [item for item in items if period_from_item(item)[0] != "current"]
    if len(monthly) < 2:
        return 0
    monthly = sorted(monthly, key=lambda item: period_from_item(item)[0])
    return max(0, int(monthly[0]["rank"]) - int(monthly[-1]["rank"]))


def avg_change(hot_tags: list[dict[str, Any]]) -> float:
    values = [item["change"] for item in hot_tags[:10]]
    return round(sum(values) / len(values), 1) if values else 0


def avg_positive_rank_change(works: list[dict[str, Any]]) -> float:
    values = [item["rankChange"] for item in works if item["rankChange"] > 0]
    return round(sum(values) / len(values), 1) if values else 0


def avg_link_change(links: list[dict[str, Any]]) -> float:
    values = [item.get("change", 0) for item in links]
    return round(sum(values) / len(values), 1) if values else 0


def to_int(value: Any, default: int) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


def to_float(value: Any, default: float) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def tail(value: str, limit: int = 4000) -> str:
    return value[-limit:] if value else ""
