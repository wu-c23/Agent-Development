"""
统一大屏生成器 — 纯 Python, 无需 Node.js.

生成自包含 HTML 文件，集成三个模块:
  Tab 1: 趋势大屏 (Trend Explorer, 端口 8001)
  Tab 2: 小说评论 (Sentiment Critic, 端口 8003)
  Tab 3: AI 推荐 (Safe-Search Architect, 端口 8002)

用法:
    python unified_dashboard.py                        # 内置 Mock 数据
    python unified_dashboard.py --api http://127.0.0.1:8001  # 连接真实 API
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ============================================================
# UID 工具
# ============================================================

def gen_uid(platform_id: str, title: str) -> str:
    return hashlib.sha256(f"{platform_id}|{title.strip()}".encode("utf-8")).hexdigest()


# ============================================================
# 已知小说 UID 映射 (跨模块一致)
# ============================================================

KNOWN_UIDS: dict[str, str] = {
    "诡秘之主": "987a2b45c6bd2baa73d750f13daf15b63c20145de2e85fff22ada96ad3d8b27b",
    "我有一座恐怖屋": "26d4613826eb8819a9a601cfb88eb7621b0e6cc5c46ffefa96b5dea22ca938dc",
    "修罗武神": "f551b43b941bf7f47d6006792b26da44b8554945c72766133cb0c59771f48c89",
    "凡人修仙传": "22ed60b7b27cf4c8b77c1439cb7a9d82eb4667f6eafab681bcd415e18adbd0a4",
    "仙王的日常生活": "587986904db3db77b83e2d7b49165f2f6e9ec1b6552b621e340695f21c240d8c",
    "斗破苍穹": "5ee58c6e2a50c7b194ab73eaf787590384344a765ff1b682ec15d962daae2dee",
    "剑来": "8c2c257caf7438c0c5561c5584200deea9b11dd91283958002968646deeeec2b",
    "全职高手": "261d26f98be24a9423afba401b0fef88373220a3212166615613ad83b726d7fa",
}


def lookup_uid(title: str) -> str:
    if title in KNOWN_UIDS:
        return KNOWN_UIDS[title]
    return gen_uid("zongheng", title)


# ============================================================
# 内置 Mock 数据 (与 dashboard.py 一致)
# ============================================================

MOCK_DASHBOARD: dict[str, Any] = {
    "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    "summary": "全标签热度趋势仅统计历史月票榜，并按作品月票总数贡献到该作品的所有标签。当前展示数据来自纵横中文网 2026年1-5月月票榜，起点暂不纳入自动采集。",
    "metrics": [
        {"id": "hot-tags", "label": "细标签数", "value": "52", "delta": 18.4, "tone": "green"},
        {"id": "rising-works", "label": "上升作品", "value": "168", "delta": 21.7, "tone": "amber"},
        {"id": "platforms", "label": "监测平台", "value": "1", "deltaLabel": "纵横中文网", "tone": "blue"},
        {"id": "migration", "label": "流派月份", "value": "5", "delta": 9.1, "tone": "rose"},
    ],
    "dataQuality": {
        "requiredMonths": ["20261", "20262", "20263", "20264", "20265"],
        "missingMonths": [],
        "incompleteMonths": [],
        "isComplete": True,
        "note": "月票趋势仅使用带 month 参数的历史月票榜记录。",
        "months": [
            {"month": "20261", "label": "2026年01月", "records": 200, "uniqueWorks": 200, "tagCount": 160, "heatTotal": 980000, "heatTotalK": 980, "expectedRecords": 200, "complete": True},
            {"month": "20262", "label": "2026年02月", "records": 200, "uniqueWorks": 200, "tagCount": 160, "heatTotal": 1025000, "heatTotalK": 1025, "expectedRecords": 200, "complete": True},
            {"month": "20263", "label": "2026年03月", "records": 200, "uniqueWorks": 200, "tagCount": 160, "heatTotal": 1102000, "heatTotalK": 1102, "expectedRecords": 200, "complete": True},
            {"month": "20264", "label": "2026年04月", "records": 200, "uniqueWorks": 200, "tagCount": 160, "heatTotal": 1188000, "heatTotalK": 1188, "expectedRecords": 200, "complete": True},
            {"month": "20265", "label": "2026年05月", "records": 200, "uniqueWorks": 200, "tagCount": 160, "heatTotal": 1240000, "heatTotalK": 1240, "expectedRecords": 200, "complete": True},
        ],
    },
    "heatCurve": {
        "dates": ["01月", "02月", "03月", "04月", "05月"],
        "unit": "k",
        "valueLabel": "月票",
        "source": "monthly-ticket",
        "series": [
            {"name": "传统玄幻", "data": [72, 78, 84, 91, 96], "description": "纵横月票榜中长期基本盘，强设定、升级体系和高燃战斗仍是主轴。"},
            {"name": "家族崛起", "data": [38, 46, 59, 77, 92], "description": "从单主角爽点转向宗族、血脉、群像共振，近期上升速度最快。"},
            {"name": "热血", "data": [68, 71, 77, 84, 92], "description": "常与传统玄幻、剑道、少年成长并存。"},
            {"name": "剑道", "data": [54, 62, 70, 82, 90], "description": "兼具成长线、战斗爽点和辨识度。"},
            {"name": "群像", "data": [42, 49, 58, 74, 88], "description": "读者对多角色并肩、家族团队和势力成长的接受度提升。"},
            {"name": "轻量金手指", "data": [30, 35, 44, 56, 72], "description": "相比传统系统流，限制型金手指更受现阶段读者青睐。"},
            {"name": "规则怪谈", "data": [12, 18, 29, 45, 68], "description": "从废土生存向规则怪谈的迁移趋势明显。"},
        ],
    },
    "hotTags": [
        {"tag": "传统玄幻", "heat": 96, "change": 33.3, "group": "题材", "stage": "rising",
         "relatedWorks": ["剑道独尊", "万古神帝", "一剑独尊", "完美世界", "斗破苍穹"]},
        {"tag": "热血", "heat": 92, "change": 35.3, "group": "情绪价值", "stage": "rising",
         "relatedWorks": ["斗破苍穹", "完美世界", "剑来", "遮天", "大主宰"]},
        {"tag": "家族崛起", "heat": 92, "change": 142.1, "group": "叙事人设", "stage": "rising",
         "relatedWorks": ["家族修仙：从种植开始", "修仙家族不能飘", "青莲之巅"]},
        {"tag": "剑道", "heat": 90, "change": 66.7, "group": "元素机制", "stage": "rising",
         "relatedWorks": ["剑来", "一剑独尊", "剑道独尊", "仗剑走天涯", "剑仙之路"]},
        {"tag": "群像", "heat": 88, "change": 109.5, "group": "叙事人设", "stage": "rising",
         "relatedWorks": ["剑来", "诡秘之主", "全职高手", "将夜", "雪中悍刀行"]},
        {"tag": "轻量金手指", "heat": 72, "change": 140.0, "group": "元素机制", "stage": "rising",
         "relatedWorks": ["我的模拟长生路", "苟在妖武乱世修仙", "我在修仙界长命百岁"]},
        {"tag": "升级流", "heat": 70, "change": -5.4, "group": "题材", "stage": "stable",
         "relatedWorks": ["斗破苍穹", "修罗武神", "武动乾坤", "大主宰"]},
        {"tag": "规则怪谈", "heat": 68, "change": 466.7, "group": "题材", "stage": "rising",
         "relatedWorks": ["规则怪谈：我能完美利用规则", "雾都规则档案", "全球规则化"]},
        {"tag": "废土生存", "heat": 42, "change": -12.5, "group": "题材", "stage": "cooling",
         "relatedWorks": ["全球废土：开局一座城", "废土生存指南", "废土之上"]},
        {"tag": "凡人流", "heat": 38, "change": 8.6, "group": "题材", "stage": "stable",
         "relatedWorks": ["凡人修仙传", "凡人修仙记", "修真世界"]},
        {"tag": "金手指", "heat": 35, "change": -25.5, "group": "元素机制", "stage": "cooling",
         "relatedWorks": ["系统赋我长生", "神话版三国", "我能提取熟练度"]},
        {"tag": "系统流", "heat": 30, "change": -42.3, "group": "题材", "stage": "cooling",
         "relatedWorks": ["系统赋我长生", "神话版三国", "超级神基因"]},
    ],
    "platformCompare": [
        {"platform": "纵横中文网", "heat": 100, "works": 200, "topTags": ["传统玄幻", "热血", "家族崛起", "剑道", "群像", "轻量金手指"], "status": "active"},
    ],
    "wordCloud": [
        {"name": "传统玄幻", "value": 96}, {"name": "热血", "value": 92}, {"name": "家族崛起", "value": 92},
        {"name": "剑道", "value": 90}, {"name": "群像", "value": 88}, {"name": "轻量金手指", "value": 72},
        {"name": "升级流", "value": 70}, {"name": "规则怪谈", "value": 68}, {"name": "少年成长", "value": 55},
        {"name": "废土生存", "value": 42}, {"name": "凡人流", "value": 38}, {"name": "金手指", "value": 35},
    ],
    "migration": {
        "nodes": [
            {"name": "传统升级流"}, {"name": "反套路群像流"}, {"name": "系统流"}, {"name": "轻量金手指"},
            {"name": "废土生存"}, {"name": "规则怪谈"}, {"name": "单主角爽文"}, {"name": "家族崛起群像"},
            {"name": "门派经营"}, {"name": "宗族势力经营"}, {"name": "单线复仇"}, {"name": "权谋博弈"},
        ],
        "links": [
            {"source": "传统升级流", "target": "反套路群像流", "value": 28, "change": 35.2},
            {"source": "系统流", "target": "轻量金手指", "value": 22, "change": 78.6},
            {"source": "废土生存", "target": "规则怪谈", "value": 18, "change": 466.7},
            {"source": "单主角爽文", "target": "家族崛起群像", "value": 15, "change": 112.3},
            {"source": "门派经营", "target": "宗族势力经营", "value": 10, "change": 45.6},
            {"source": "单线复仇", "target": "权谋博弈", "value": 8, "change": 22.1},
        ],
    },
    "migrationTimeline": {
        "periods": ["01月", "02月", "03月", "04月", "05月"],
        "flows": [
            {"id": "传统升级流-反套路群像流", "source": "传统升级流", "target": "反套路群像流", "values": [12, 15, 18, 24, 28]},
            {"id": "系统流-轻量金手指", "source": "系统流", "target": "轻量金手指", "values": [8, 10, 12, 17, 22]},
            {"id": "废土生存-规则怪谈", "source": "废土生存", "target": "规则怪谈", "values": [2, 4, 7, 12, 18]},
            {"id": "单主角爽文-家族崛起群像", "source": "单主角爽文", "target": "家族崛起群像", "values": [5, 7, 9, 12, 15]},
        ],
    },
    "genreCloudTimeline": {
        "periods": ["01月", "02月", "03月", "04月", "05月"],
        "unit": "k",
        "summary": "月票榜流派热度从传统玄幻、系统流、热血逐步变化到家族崛起、规则怪谈、群像。",
        "clouds": [
            {"period": "01月", "genres": [{"name": "传统玄幻", "value": 72}, {"name": "热血", "value": 68}, {"name": "剑道", "value": 54}, {"name": "系统流", "value": 52}, {"name": "群像", "value": 42}, {"name": "家族崛起", "value": 38}]},
            {"period": "02月", "genres": [{"name": "传统玄幻", "value": 78}, {"name": "热血", "value": 71}, {"name": "剑道", "value": 62}, {"name": "系统流", "value": 49}, {"name": "家族崛起", "value": 46}, {"name": "群像", "value": 49}]},
            {"period": "03月", "genres": [{"name": "传统玄幻", "value": 84}, {"name": "热血", "value": 77}, {"name": "剑道", "value": 70}, {"name": "家族崛起", "value": 59}, {"name": "群像", "value": 58}, {"name": "轻量金手指", "value": 44}]},
            {"period": "04月", "genres": [{"name": "传统玄幻", "value": 91}, {"name": "热血", "value": 84}, {"name": "剑道", "value": 82}, {"name": "家族崛起", "value": 77}, {"name": "群像", "value": 74}, {"name": "轻量金手指", "value": 56}]},
            {"period": "05月", "genres": [{"name": "传统玄幻", "value": 96}, {"name": "热血", "value": 92}, {"name": "家族崛起", "value": 92}, {"name": "剑道", "value": 90}, {"name": "群像", "value": 88}, {"name": "轻量金手指", "value": 72}]},
        ],
    },
    "risingWorks": [
        {"id": "r1", "title": "剑来", "author": "烽火戏诸侯", "platform": "纵横中文网", "rank": 12, "rankChange": 28, "heatScore": 28500, "listType": "月票榜-2026年05月", "tags": ["剑道", "群像", "文青", "权谋"]},
        {"id": "r2", "title": "家族修仙：从种植开始", "author": "青云子", "platform": "纵横中文网", "rank": 35, "rankChange": 52, "heatScore": 18200, "listType": "月票榜-2026年05月", "tags": ["家族崛起", "修仙", "种田流"]},
        {"id": "r3", "title": "规则怪谈：我能完美利用规则", "author": "夜不语", "platform": "纵横中文网", "rank": 8, "rankChange": 64, "heatScore": 45200, "listType": "月票榜-2026年05月", "tags": ["规则怪谈", "无限流", "悬疑"]},
        {"id": "r4", "title": "我的模拟长生路", "author": "愤怒的香蕉", "platform": "纵横中文网", "rank": 22, "rankChange": 41, "heatScore": 24500, "listType": "月票榜-2026年05月", "tags": ["轻量金手指", "修仙", "模拟器"]},
        {"id": "r5", "title": "苟在妖武乱世修仙", "author": "文抄公", "platform": "纵横中文网", "rank": 18, "rankChange": 33, "heatScore": 27600, "listType": "月票榜-2026年05月", "tags": ["轻量金手指", "妖武", "苟道"]},
        {"id": "r6", "title": "斗破苍穹", "author": "天蚕土豆", "platform": "纵横中文网", "rank": 5, "rankChange": 3, "heatScore": 58000, "listType": "月票榜-2026年05月", "tags": ["传统玄幻", "爽文", "热血"]},
        {"id": "r7", "title": "修仙家族不能飘", "author": "青衫仗剑", "platform": "纵横中文网", "rank": 40, "rankChange": 48, "heatScore": 16200, "listType": "月票榜-2026年05月", "tags": ["家族崛起", "修仙", "经营"]},
        {"id": "r8", "title": "全球规则化", "author": "黑山老鬼", "platform": "纵横中文网", "rank": 15, "rankChange": 57, "heatScore": 31500, "listType": "月票榜-2026年05月", "tags": ["规则怪谈", "末世", "进化"]},
    ],
}


def fetch_dashboard(api_base: str) -> dict[str, Any] | None:
    try:
        import urllib.request
        url = f"{api_base.rstrip('/')}/api/trends/dashboard"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            if isinstance(payload, dict) and "data" in payload:
                return payload["data"]
            if isinstance(payload, dict) and "heatCurve" in payload:
                return payload
            return None
    except Exception as exc:
        print(f"Warning: Could not fetch from API ({exc}), using mock data.")
        return None


# ============================================================
# HTML 生成 (统一三 Tab 大屏)
# ============================================================

def build_unified_html(data: dict[str, Any]) -> str:
    json_data = json.dumps(data, ensure_ascii=False, default=str)
    known_uids_json = json.dumps(KNOWN_UIDS, ensure_ascii=False)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>网络小说智能推荐与舆情分析系统</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.1/dist/echarts.min.js"></script>
<style>
:root {{ --bg: #f5f6fa; --card-bg: #fff; --text: #1a1a2e; --text2: #6b7280;
  --border: #e5e7eb; --green: #10b981; --amber: #f59e0b; --blue: #3b82f6;
  --rose: #f43f5e; --purple: #8b5cf6; --shadow: 0 1px 3px rgba(0,0,0,.08);
  --accent: #3b82f6; --accent-light: #dbeafe; }}
[data-theme="dark"] {{ --bg: #0f172a; --card-bg: #1e293b; --text: #f1f5f9;
  --text2: #94a3b8; --border: #334155; --shadow: 0 1px 3px rgba(0,0,0,.3);
  --accent-light: #1e3a5f; }}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Microsoft YaHei', sans-serif;
  background: var(--bg); color: var(--text); min-height: 100vh; }}

/* ---- Tab 导航栏 ---- */
.tab-nav {{ background: var(--card-bg); border-bottom: 2px solid var(--border);
  padding: 0 24px; display: flex; align-items: center; justify-content: space-between;
  position: sticky; top: 0; z-index: 200; box-shadow: var(--shadow); }}
.tab-nav .brand {{ font-size: 18px; font-weight: 700; white-space: nowrap; }}
.tab-nav .tabs {{ display: flex; gap: 4px; }}
.tab-nav .tabs button {{ padding: 14px 20px; border: none; background: transparent;
  color: var(--text2); cursor: pointer; font-size: 14px; font-weight: 500;
  border-bottom: 3px solid transparent; transition: all .2s; white-space: nowrap; }}
.tab-nav .tabs button:hover {{ color: var(--text); background: var(--bg); }}
.tab-nav .tabs button.active {{ color: var(--accent); border-bottom-color: var(--accent);
  font-weight: 700; }}
.tab-nav .toolbar {{ display: flex; gap: 8px; align-items: center; }}
.tab-nav .toolbar button {{ padding: 6px 12px; border: 1px solid var(--border);
  border-radius: 6px; background: var(--card-bg); color: var(--text); cursor: pointer;
  font-size: 13px; }}
.tab-nav .toolbar button:hover {{ background: var(--border); }}

/* ---- Tab 内容区 ---- */
.tab-content {{ display: none; }}
.tab-content.active {{ display: block; }}
.container {{ max-width: 1440px; margin: 0 auto; padding: 20px 24px; }}

/* ---- 通用 Panel ---- */
.metrics {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 20px; }}
.metric-card {{ background: var(--card-bg); border-radius: 10px; padding: 18px 20px;
  box-shadow: var(--shadow); border: 1px solid var(--border); }}
.metric-card .label {{ font-size: 13px; color: var(--text2); }}
.metric-card .value {{ font-size: 28px; font-weight: 700; margin: 4px 0; }}
.metric-card .delta {{ font-size: 13px; }}
.metric-card .delta.up {{ color: var(--green); }}
.metric-card .delta.down {{ color: var(--rose); }}
.metric-card .delta.neutral {{ color: var(--text2); }}
.summary {{ background: var(--card-bg); border-radius: 10px; padding: 16px 20px;
  margin-bottom: 20px; box-shadow: var(--shadow); border: 1px solid var(--border);
  font-size: 14px; line-height: 1.6; color: var(--text2); }}
.grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }}
.grid3 {{ display: grid; grid-template-columns: 2fr 1fr; gap: 16px; margin-bottom: 16px; }}
.panel {{ background: var(--card-bg); border-radius: 10px; padding: 16px;
  box-shadow: var(--shadow); border: 1px solid var(--border); }}
.panel h2 {{ font-size: 16px; font-weight: 600; margin-bottom: 12px;
  display: flex; align-items: center; gap: 8px; }}
.chart {{ width: 100%; height: 380px; }}
.chart-sm {{ width: 100%; height: 320px; }}
.chart-lg {{ width: 100%; height: 480px; }}
.full-width {{ grid-column: 1 / -1; }}
.mb16 {{ margin-bottom: 16px; }}

/* ---- 表格 ---- */
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid var(--border); }}
th {{ color: var(--text2); font-weight: 500; font-size: 12px; }}
.tag-chip {{ display: inline-block; padding: 2px 8px; border-radius: 4px;
  font-size: 11px; margin: 1px 2px; background: #e0e7ff; color: #3730a3; }}
[data-theme="dark"] .tag-chip {{ background: #312e81; color: #c7d2fe; }}
.stage {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; }}
.stage.rising {{ background: #d1fae5; color: #065f46; }}
.stage.stable {{ background: #fef3c7; color: #92400e; }}
.stage.cooling {{ background: #fee2e2; color: #991b1b; }}
[data-theme="dark"] .stage.rising {{ background: #064e3b; color: #a7f3d0; }}
[data-theme="dark"] .stage.stable {{ background: #78350f; color: #fde68a; }}
[data-theme="dark"] .stage.cooling {{ background: #7f1d1d; color: #fecaca; }}
.coverage {{ display: flex; gap: 12px; flex-wrap: wrap; }}
.coverage .month {{ text-align: center; padding: 8px 14px; border-radius: 8px;
  border: 1px solid var(--border); font-size: 13px; }}
.coverage .month.complete {{ background: #d1fae5; border-color: #10b981; }}

/* ---- 小说名按钮 ---- */
.novel-btn {{ background: none; border: none; color: var(--accent); cursor: pointer;
  font-weight: 600; font-size: inherit; text-decoration: underline; text-underline-offset: 3px;
  padding: 0; text-align: left; }}
.novel-btn:hover {{ color: #1d4ed8; }}

/* ---- Tab 2: 评论视图 ---- */
.back-btn {{ padding: 8px 16px; border: 1px solid var(--border); border-radius: 6px;
  background: var(--card-bg); color: var(--text); cursor: pointer; font-size: 13px;
  margin-bottom: 16px; }}
.back-btn:hover {{ background: var(--border); }}
.review-header {{ display: flex; align-items: center; gap: 16px; margin-bottom: 20px; }}
.review-header h2 {{ font-size: 24px; }}
.review-header .platform-badge {{ padding: 4px 12px; border-radius: 999px;
  background: var(--accent-light); color: var(--accent); font-size: 12px; font-weight: 600; }}
.score-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; margin-bottom: 16px; }}
.score-card {{ background: var(--bg); border-radius: 8px; padding: 14px; text-align: center;
  border: 1px solid var(--border); }}
.score-card .dim {{ font-size: 12px; color: var(--text2); }}
.score-card .val {{ font-size: 28px; font-weight: 700; margin: 4px 0; }}
.score-bar {{ height: 6px; border-radius: 3px; background: var(--border); margin-top: 6px; overflow: hidden; }}
.score-bar-fill {{ height: 100%; border-radius: 3px; }}
.pro-con {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }}
.pro-con h3 {{ font-size: 14px; margin-bottom: 8px; }}
.pro-con ul {{ padding-left: 18px; font-size: 13px; line-height: 1.8; color: var(--text2); }}
.one-liner {{ background: var(--bg); border-radius: 8px; padding: 16px; font-size: 15px;
  line-height: 1.7; border-left: 4px solid var(--accent); margin-bottom: 16px; }}
.no-data {{ text-align: center; padding: 60px 20px; color: var(--text2); }}
.no-data .icon {{ font-size: 48px; margin-bottom: 12px; }}

/* ---- Tab 3: AI 对话 ---- */
.chat-container {{ display: flex; flex-direction: column; height: calc(100vh - 120px); max-width: 900px; margin: 0 auto; }}
.chat-messages {{ flex: 1; overflow-y: auto; padding: 16px 0; display: flex; flex-direction: column; gap: 16px; }}
.chat-msg {{ display: flex; gap: 10px; max-width: 85%; }}
.chat-msg.user {{ align-self: flex-end; flex-direction: row-reverse; }}
.chat-msg.assistant {{ align-self: flex-start; }}
.chat-msg .avatar {{ width: 36px; height: 36px; border-radius: 50%; display: flex;
  align-items: center; justify-content: center; font-size: 18px; flex-shrink: 0; }}
.chat-msg.user .avatar {{ background: var(--accent); }}
.chat-msg.assistant .avatar {{ background: var(--purple); }}
.chat-msg .bubble {{ background: var(--card-bg); border: 1px solid var(--border);
  border-radius: 12px; padding: 12px 16px; font-size: 14px; line-height: 1.6; }}
.chat-msg.user .bubble {{ background: var(--accent); color: #fff; border-color: var(--accent); }}
.result-cards {{ display: grid; gap: 12px; margin-top: 10px; }}
.result-card {{ background: var(--bg); border: 1px solid var(--border); border-radius: 8px;
  padding: 12px 16px; cursor: pointer; transition: all .2s; }}
.result-card:hover {{ border-color: var(--accent); box-shadow: 0 2px 8px rgba(0,0,0,.1); }}
.result-card .title {{ font-weight: 700; font-size: 15px; color: var(--accent); }}
.result-card .meta {{ font-size: 12px; color: var(--text2); margin-top: 4px; }}
.result-card .reason {{ font-size: 13px; margin-top: 6px; }}
.result-card .warning {{ color: var(--rose); font-size: 12px; }}
.chat-input-area {{ display: flex; gap: 10px; padding: 16px 0; border-top: 1px solid var(--border); }}
.chat-input-area input {{ flex: 1; padding: 10px 14px; border: 1px solid var(--border);
  border-radius: 8px; font-size: 14px; background: var(--card-bg); color: var(--text);
  outline: none; }}
.chat-input-area input:focus {{ border-color: var(--accent); }}
.chat-input-area button {{ padding: 10px 20px; background: var(--accent); color: #fff;
  border: none; border-radius: 8px; cursor: pointer; font-size: 14px; font-weight: 600; }}
.chat-input-area button:hover {{ opacity: 0.9; }}
.chat-input-area button:disabled {{ opacity: 0.5; cursor: not-allowed; }}
.avoid-tags {{ display: flex; flex-wrap: wrap; gap: 6px; padding: 8px 0; }}
.avoid-tag {{ padding: 4px 10px; border: 1px solid var(--border); border-radius: 999px;
  font-size: 12px; cursor: pointer; background: var(--card-bg); color: var(--text2);
  user-select: none; }}
.avoid-tag.selected {{ background: #fee2e2; border-color: var(--rose); color: var(--rose); }}
[data-theme="dark"] .avoid-tag.selected {{ background: #7f1d1d; color: #fecaca; }}

/* ---- Footer ---- */
.footer {{ text-align: center; padding: 20px; font-size: 12px; color: var(--text2); }}

/* ---- Loading ---- */
.loading {{ text-align: center; padding: 40px; color: var(--text2); }}
.spinner {{ display: inline-block; width: 24px; height: 24px; border: 3px solid var(--border);
  border-top-color: var(--accent); border-radius: 50%; animation: spin .8s linear infinite; }}
@keyframes spin {{ to {{ transform: rotate(360deg); }} }}

/* ---- Responsive ---- */
@media (max-width: 960px) {{
  .metrics {{ grid-template-columns: repeat(2, 1fr); }}
  .grid2, .grid3, .pro-con {{ grid-template-columns: 1fr; }}
  .tab-nav {{ flex-wrap: wrap; padding: 8px 12px; }}
  .tab-nav .brand {{ font-size: 15px; }}
  .tab-nav .tabs button {{ padding: 10px 12px; font-size: 13px; }}
}}
@media (max-width: 640px) {{
  .metrics {{ grid-template-columns: 1fr; }}
  .tab-nav .tabs button {{ padding: 8px 10px; font-size: 12px; }}
}}
</style>
</head>
<body data-theme="light">

<!-- ============ Tab 导航栏 ============ -->
<nav class="tab-nav">
  <div class="brand">📚 网络小说智能推荐与舆情分析系统</div>
  <div class="tabs">
    <button class="active" data-tab="trend" onclick="switchTab('trend')">📊 趋势大屏</button>
    <button data-tab="review" onclick="switchTab('review')">📝 小说评论</button>
    <button data-tab="chat" onclick="switchTab('chat')">🤖 AI 推荐</button>
	    <button data-tab="character" onclick="switchTab('character');loadCharacterList()">🎭 角色对话</button>
  </div>
  <div class="toolbar">
    <button onclick="toggleTheme()" title="切换明暗主题">🌓 主题</button>
  </div>
</nav>

<!-- ============ Tab 1: 趋势大屏 ============ -->
<div class="tab-content active" id="tab-trend">
<div class="container">

  <div class="summary" id="summary"></div>
  <div class="metrics" id="metrics"></div>

  <div class="panel full-width mb16">
    <h2>📅 历史月票榜覆盖</h2>
    <div class="coverage" id="coverage"></div>
  </div>

  <div class="grid3">
    <div class="panel"><h2>🔥 标签热度趋势曲线</h2><div class="chart" id="heatCurve"></div></div>
    <div class="panel"><h2>🏷️ 热门标签 Top 12</h2><div class="chart-sm" id="hotTagsBar"></div></div>
  </div>

  <div class="grid2">
    <div class="panel"><h2>☁️ 标签词云</h2><div class="chart" id="wordCloud"></div></div>
    <div class="panel"><h2>📱 平台热度对比</h2><div class="chart-sm" id="platformCompare"></div></div>
  </div>

  <div class="panel full-width mb16">
    <h2>🔀 流派迁移关系</h2>
    <div class="chart-lg" id="migrationSankey"></div>
  </div>

  <div class="panel full-width mb16">
    <h2>📈 流派迁移时间线</h2>
    <div class="chart-lg" id="migrationTimeline"></div>
  </div>

  <div class="panel full-width mb16">
    <h2>🚀 上升作品 <span style="font-weight:400;font-size:12px;color:var(--text2)">(点击书名查看评论)</span></h2>
    <div style="overflow-x:auto" id="risingWorksTable"></div>
  </div>

</div>
</div>

<!-- ============ Tab 2: 小说评论 ============ -->
<div class="tab-content" id="tab-review">
<div class="container">
  <button class="back-btn" onclick="switchTab('trend')">← 返回排行榜</button>
  <div id="reviewContent"><div class="no-data"><div class="icon">📝</div><p>请从排行榜或 AI 推荐中点击小说名查看评论分析</p></div></div>
</div>
</div>

<!-- ============ Tab 3: AI 推荐 ============ -->
<div class="tab-content" id="tab-chat">
<div class="container">
  <div class="chat-container">
    <div class="avoid-tags" id="avoidTags" style="display:none;">
      <span style="font-size:12px;color:var(--text2);margin-right:4px;">避雷标签:</span>
    </div>
    <div class="chat-messages" id="chatMessages">
      <div class="chat-msg assistant">
        <div class="avatar">🤖</div>
        <div class="bubble">
          你好！我是小说闲聊助手。<br>
          我可以帮你做这些事：<br>
          • 推荐小说 — "推荐悬疑小说"<br>
          • 查询书的信息 — "诡秘之主好看吗"<br>
          • 闲聊小说话题 — 和我聊聊你喜欢的角色<br><br>
          试试看吧！
        </div>
      </div>
    </div>
    <div class="chat-input-area">
      <input type="text" id="chatInput" placeholder="推荐悬疑小说、诡秘之主好看吗..." onkeydown="if(event.key==='Enter')sendMessage()">
      <button id="sendBtn" onclick="sendMessage()">发送</button>
    </div>
  </div>
</div>
</div>

<!-- ============ Tab 4: 角色对话 ============ -->
<div class="tab-content" id="tab-character">
<div class="container">
  <div class="chat-container">
    <!-- 角色选择器 -->
    <div style="padding: 12px 0; border-bottom: 1px solid var(--border); margin-bottom: 8px;">
      <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;" id="characterSelector">
        <span style="font-size:13px; color:var(--text2);">选择角色:</span>
        <div id="characterLoading" class="loading" style="padding:8px"><div class="spinner"></div></div>
      </div>
      <div id="charModeBadge" style="margin-top:6px; display:flex; gap:8px; align-items:center;">
        <span id="charModeLabel" style="font-size:11px; padding:2px 8px; border-radius:4px; background:#f0f0f0; color:#999;">
          ⏳ 检测中...
        </span>
      </div>
      <div id="characterInfo" style="display:none; margin-top:8px; padding:8px 12px; background:var(--bg); border-radius:8px; border:1px solid var(--border);">
        <div style="font-size:13px; color:var(--text2);">
          <span id="charAvatar" style="font-size:24px; margin-right:8px;"></span>
          <strong id="charName"></strong> · 《<span id="charNovel"></span>》
          <span id="charPersonality" style="margin-left:8px;"></span>
        </div>
      </div>
    </div>

    <!-- 自定义角色输入 -->
    <div style="margin-top:8px; padding:8px 0 4px; border-top:1px dashed var(--border);">
      <div style="font-size:12px; color:var(--text2); margin-bottom:6px;">或者指定任意角色：</div>
      <div style="display:flex; gap:6px; flex-wrap:wrap; align-items:center;">
        <input type="text" id="customCharName" placeholder="角色名" style="padding:5px 10px;border:1px solid var(--border);border-radius:6px;background:var(--card-bg);color:var(--text);font-size:13px;width:100px;">
        <span style="color:var(--text2);font-size:13px;">出自</span>
        <input type="text" id="customCharNovel" placeholder="小说名" style="padding:5px 10px;border:1px solid var(--border);border-radius:6px;background:var(--card-bg);color:var(--text);font-size:13px;width:130px;">
        <button onclick="startCustomCharacter()" style="padding:5px 14px;border:1px solid var(--accent);border-radius:6px;background:var(--accent);color:#fff;cursor:pointer;font-size:13px;white-space:nowrap;">开始对话</button>
        <span id="customCharError" style="font-size:12px;color:var(--rose);display:none;"></span>
      </div>
    </div>

    <div class="chat-messages" id="characterChatMessages">
      <div class="chat-msg assistant">
        <div class="avatar">🎭</div>
        <div class="bubble">
          你好！我是角色扮演助手。<br>
          请先在顶部选择一个小说角色，然后就可以和他们对话了！<br>
          · 选择「克莱恩」聊聊诡秘之主的世界<br>
          · 选择「韩立」探讨修仙之道<br>
          · 选择「陈歌」体验恐怖屋的日常<br>
          · 选择「王令」感受仙王的日常<br>
          · 选择「萧炎」点燃热血斗志
        </div>
      </div>
    </div>
    <div class="chat-input-area">
      <input type="text" id="characterChatInput" placeholder="和角色对话..." onkeydown="if(event.key==='Enter')sendCharacterMessage()" disabled>
      <button id="charSendBtn" onclick="sendCharacterMessage()" disabled>发送</button>
    </div>
  </div>
</div>
</div>

<div class="footer">
  网络小说智能推荐与舆情分析系统 — 统一大屏 · 纯 Python 生成，无需 Node.js
</div>

<script>
// ============================================================
// 全局状态
// ============================================================
const DATA = {json_data};
const KNOWN_UIDS = {known_uids_json};
const API = {{
  trend: 'http://127.0.0.1:8001',
  search: 'http://127.0.0.1:8002',
  sentiment: 'http://127.0.0.1:8003',
}};
let currentNovelUid = null;
let currentNovelTitle = null;
const CHARTS = {{}};
const AVOID_TAGS = ['后宫', '烂尾', '虐主', '狗血', '节奏慢'];
let _msgSeq = 0;

// ============================================================
// 主题
// ============================================================
function toggleTheme() {{
  const el = document.documentElement;
  const next = el.dataset.theme === 'dark' ? 'light' : 'dark';
  el.dataset.theme = next;
  localStorage.setItem('unified-theme', next);
  Object.values(CHARTS).forEach(c => c?.resize && c.resize());
}}
(function() {{
  const saved = localStorage.getItem('unified-theme');
  if (saved) document.documentElement.dataset.theme = saved;
}})();

// ============================================================
// Tab 切换
// ============================================================
function switchTab(name) {{
  document.querySelectorAll('.tab-nav .tabs button').forEach(b => b.classList.remove('active'));
  document.querySelector(`[data-tab="${{name}}"]`).classList.add('active');
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  if (name === 'trend') setTimeout(resizeAllCharts, 150);
  if (name === 'chat') {{
    document.getElementById('chatInput').focus();
    scrollChatBottom();
  }}
}}

// ============================================================
// UID 工具
// ============================================================
function getUid(title) {{
  if (KNOWN_UIDS[title]) return KNOWN_UIDS[title];
  // fallback: hash locally (async sha256)
  return null;
}}

// ============================================================
// 跨 Tab 跳转：打开评论视图
// ============================================================
async function openReview(uid, title) {{
  currentNovelUid = uid;
  currentNovelTitle = title;
  switchTab('review');
  const container = document.getElementById('reviewContent');
  container.innerHTML = '<div class="loading"><div class="spinner"></div><p>正在加载评论数据...</p></div>';

  try {{
    const resp = await fetch(`${{API.sentiment}}/api/v1/sentiment/detail/${{uid}}`);
    if (!resp.ok) throw new Error('not_found');
    const data = await resp.json();
    renderReview(data, container);
  }} catch (e) {{
    container.innerHTML = renderNoReviewData(title, uid);
  }}
}}

function renderNoReviewData(title, uid) {{
  return `<div class="no-data">
    <div class="icon">📭</div>
    <h3>${{title || '未知小说'}}</h3>
    <p style="margin-top:8px">暂无评论数据</p>
    <p style="font-size:12px;margin-top:4px;color:var(--text2)">UID: ${{uid}}</p>
    <p style="font-size:12px;margin-top:4px;color:var(--text2)">
      Sentiment Critic 服务 (端口 8003) 可能未启动，或该小说尚未采集评论数据。
    </p>
  </div>`;
}}

function renderReview(data, container) {{
  const m = data.metadata || {{}};
  const s = data.sentiment_scores || {{}};
  const c = data.critic_summary || {{}};
  const r = data.review_stats || {{}};
  const sources = r.source_breakdown || {{}};

  let html = `<div class="review-header">
    <h2>${{m.title || '未知小说'}}</h2>
    <span class="platform-badge">${{m.platform || '未知平台'}}</span>
  </div>`;

  // 毒舌点评
  if (c.one_liner) html += `<div class="one-liner">💬 ${{c.one_liner}}</div>`;

  // 评分卡片
  html += '<div class="score-grid">';
  const dims = [
    {{key:'overall', label:'综合评分', max:10, color:'var(--blue)'}},
    {{key:'style', label:'文笔', max:10, color:'var(--purple)'}},
    {{key:'logic', label:'逻辑', max:10, color:'var(--green)'}},
    {{key:'character', label:'人物塑造', max:10, color:'var(--amber)'}},
    {{key:'update_stability', label:'更新稳定性', max:10, color:'#06b6d4'}},
    {{key:'toxicity_index', label:'毒性指数', max:1, color:'var(--rose)', invert:true}},
  ];
  dims.forEach(d => {{
    const val = s[d.key] || 0;
    const pct = d.invert ? (1 - val) * 100 : val / d.max * 100;
    html += `<div class="score-card">
      <div class="dim">${{d.label}}</div>
      <div class="val" style="color:${{d.color}}">${{typeof val === 'number' ? val.toFixed(1) : val}}</div>
      <div class="score-bar"><div class="score-bar-fill" style="width:${{Math.round(pct)}}%;background:${{d.color}}"></div></div>
    </div>`;
  }});
  html += '</div>';

  // 优缺点
  html += '<div class="pro-con">';
  html += '<div><h3>👍 优点</h3><ul>' + (c.pros || []).map(p => `<li>${{p}}</li>`).join('') + '</ul></div>';
  html += '<div><h3>👎 缺点</h3><ul>' + (c.cons || []).map(p => `<li>${{p}}</li>`).join('') + '</ul></div>';
  html += '</div>';

  // 评论统计
  html += '<div class="panel"><h2>📊 评论统计</h2>';
  html += `<p style="font-size:14px">评论总数: <strong>${{r.total_count || 0}}</strong> &nbsp;|&nbsp;
    好评率: <strong style="color:var(--green)">${{((r.positive_ratio || 0) * 100).toFixed(1)}}%</strong> &nbsp;|&nbsp;
    差评率: <strong style="color:var(--rose)">${{((r.negative_ratio || 0) * 100).toFixed(1)}}%</strong></p>`;
  html += '<div style="margin-top:12px;display:flex;gap:16px;flex-wrap:wrap;">';
  const srcLabels = {{douban:'豆瓣', tieba:'贴吧', xiaohongshu:'小红书'}};
  Object.entries(sources).forEach(([k, v]) => {{
    html += `<span style="font-size:13px;color:var(--text2)">${{srcLabels[k] || k}}: <strong>${{v}}</strong> 条</span>`;
  }});
  html += '</div></div>';

  container.innerHTML = html;
}}

// ============================================================
// Tab 1: 趋势大屏渲染
// ============================================================
function initChart(id) {{
  const dom = document.getElementById(id);
  if (!dom) return null;
  if (CHARTS[id]) CHARTS[id].dispose();
  const inst = echarts.init(dom, document.documentElement.dataset.theme === 'dark' ? 'dark' : null);
  CHARTS[id] = inst;
  return inst;
}}

function resizeAllCharts() {{ Object.values(CHARTS).forEach(c => c?.resize?.()); }}

function renderTrendDashboard() {{
  document.getElementById('summary').textContent = DATA.summary || '';

  // KPI
  const tones = {{ green: 'up', amber: 'up', rose: 'up', blue: 'neutral' }};
  document.getElementById('metrics').innerHTML = (DATA.metrics || []).map(m =>
    `<div class="metric-card">
      <div class="label">${{m.label}}</div>
      <div class="value">${{m.value}}</div>
      <div class="delta ${{tones[m.tone] || 'neutral'}}">${{m.deltaLabel || (m.delta != null ? (m.delta > 0 ? '↑' : '↓') + Math.abs(m.delta).toFixed(1) + '%' : '')}}</div>
    </div>`
  ).join('');

  // 月票覆盖
  const dq = DATA.dataQuality || {{}};
  document.getElementById('coverage').innerHTML = (dq.months || []).map(m =>
    `<div class="month ${{m.complete ? 'complete' : ''}}">
      <div><strong>${{m.label}}</strong></div>
      <div style="font-size:11px">${{m.records}}/${{m.expectedRecords}} 条</div>
      <div style="font-size:11px">${{m.uniqueWorks}} 作品</div>
    </div>`
  ).join('');

  // 热度曲线
  (function() {{
    const chart = initChart('heatCurve');
    if (!chart) return;
    const hc = DATA.heatCurve || {{}};
    chart.setOption({{
      tooltip: {{ trigger: 'axis' }},
      legend: {{ type: 'scroll', bottom: 0, textStyle: {{ fontSize: 11 }} }},
      grid: {{ left: 50, right: 20, top: 20, bottom: 40 }},
      xAxis: {{ type: 'category', data: hc.dates || [], axisLabel: {{ fontSize: 11 }} }},
      yAxis: {{ type: 'value', name: hc.unit ? '热度(' + hc.unit + ')' : '热度', axisLabel: {{ fontSize: 11 }} }},
      series: (hc.series || []).map(s => ({{ name: s.name, type: 'line', data: s.data, smooth: true, symbol: 'circle', symbolSize: 6 }}))
    }});
  }})();

  // 热门标签柱状图
  (function() {{
    const chart = initChart('hotTagsBar');
    if (!chart) return;
    const tags = (DATA.hotTags || []).slice(0, 12);
    chart.setOption({{
      tooltip: {{ trigger: 'axis', axisPointer: {{ type: 'shadow' }} }},
      grid: {{ left: 80, right: 40, top: 10, bottom: 20 }},
      xAxis: {{ type: 'value', axisLabel: {{ fontSize: 11 }} }},
      yAxis: {{ type: 'category', data: tags.map(t => t.tag).reverse(), axisLabel: {{ fontSize: 11 }} }},
      series: [{{ type: 'bar', data: tags.map(t => t.heat).reverse(),
        itemStyle: {{ color: e => ['#10b981','#f59e0b','#3b82f6','#8b5cf6','#f43f5e','#06b6d4'][e.dataIndex % 6] }},
        label: {{ show: true, position: 'right', fontSize: 11 }} }}]
    }});
  }})();

  // 词云 (散点模拟)
  (function() {{
    const chart = initChart('wordCloud');
    if (!chart) return;
    const words = DATA.wordCloud || [];
    const maxV = Math.max(...words.map(w => w.value), 1);
    chart.setOption({{
      tooltip: {{ formatter: p => p.name + ': ' + p.value }},
      grid: {{ left: 10, right: 10, top: 10, bottom: 10 }},
      xAxis: {{ show: false, min: 0, max: 100 }},
      yAxis: {{ show: false, min: 0, max: 100 }},
      series: [{{ type: 'scatter',
        symbolSize: d => Math.max(14, d[2] / maxV * 64),
        data: words.map((w, i) => {{
          const angle = i / words.length * Math.PI * 2;
          const r = 20 + (i % 3) * 18 + Math.sin(i * 3.7) * 8;
          return [50 + Math.cos(angle) * r, 50 + Math.sin(angle) * r, w.value, w.name];
        }}),
        label: {{ show: true, formatter: p => p.data[3], fontSize: d => Math.max(10, d[2] / maxV * 16) }},
        itemStyle: {{ color: e => ['#10b981','#3b82f6','#f59e0b','#8b5cf5','#f43f5e','#06b6d4','#84cc16','#ec4899'][e.dataIndex % 8] }},
        emphasis: {{ scale: 1.3 }}
      }}]
    }});
  }})();

  // 平台对比
  (function() {{
    const chart = initChart('platformCompare');
    if (!chart) return;
    const pc = DATA.platformCompare || [];
    chart.setOption({{
      tooltip: {{ trigger: 'axis', axisPointer: {{ type: 'shadow' }} }},
      grid: {{ left: 100, right: 30, top: 10, bottom: 20 }},
      xAxis: {{ type: 'value', name: '热度', axisLabel: {{ fontSize: 11 }} }},
      yAxis: {{ type: 'category', data: pc.map(p => p.platform), axisLabel: {{ fontSize: 12 }} }},
      series: [{{ type: 'bar', data: pc.map(p => p.heat),
        itemStyle: {{ color: p => p.data.status === 'active' ? '#10b981' : '#9ca3af' }},
        label: {{ show: true, position: 'right', fontSize: 11,
          formatter: p => p.data.status === 'active' ? p.value + ' (活跃)' : p.value + ' (待接入)' }} }}]
    }});
  }})();

  // 桑基图
  (function() {{
    const chart = initChart('migrationSankey');
    if (!chart) return;
    const mig = DATA.migration || {{}};
    chart.setOption({{
      tooltip: {{ trigger: 'item', triggerOn: 'mousemove' }},
      series: [{{ type: 'sankey', layout: 'none', emphasis: {{ focus: 'adjacency' }},
        data: (mig.nodes || []).map(n => ({{ name: n.name }})),
        links: (mig.links || []).map(l => ({{ source: l.source, target: l.target, value: l.value }})),
        label: {{ fontSize: 12 }},
        lineStyle: {{ color: 'gradient', curveness: 0.5 }} }}]
    }});
  }})();

  // 迁移时间线
  (function() {{
    const chart = initChart('migrationTimeline');
    if (!chart) return;
    const mt = DATA.migrationTimeline || {{}};
    const flows = mt.flows || [];
    const periods = mt.periods || [];
    chart.setOption({{
      tooltip: {{ trigger: 'item' }},
      legend: {{ type: 'scroll', bottom: 0, textStyle: {{ fontSize: 11 }} }},
      grid: {{ left: 50, right: 20, top: 20, bottom: 50 }},
      xAxis: {{ type: 'category', data: periods, axisLabel: {{ fontSize: 11 }} }},
      yAxis: {{ type: 'value', axisLabel: {{ fontSize: 11 }} }},
      series: flows.map(f => ({{ name: f.id, type: 'line', data: f.values || [], smooth: true, symbol: 'circle', symbolSize: 8 }}))
    }});
  }})();

  // 上升作品表 (小说名可点击)
  (function() {{
    const works = DATA.risingWorks || [];
    document.getElementById('risingWorksTable').innerHTML =
      '<table><thead><tr><th>#</th><th>作品</th><th>作者</th><th>平台</th><th>榜单</th><th>排名变化</th><th>热度</th><th>标签</th></tr></thead><tbody>' +
      works.map((w, i) =>
        `<tr>
          <td>${{i + 1}}</td>
          <td><button class="novel-btn" onclick="openReview('${{getUid(w.title) || ''}}', '${{w.title}}')" title="查看评论">${{w.title || '-'}}</button></td>
          <td>${{w.author || '-'}}</td>
          <td>${{w.platform || '-'}}</td>
          <td>${{w.listType || '-'}}</td>
          <td>${{w.rankChange > 0 ? '🔺 +'+w.rankChange : w.rankChange < 0 ? '🔻 '+w.rankChange : '➖ 0'}}</td>
          <td>${{(w.heatScore || 0).toLocaleString()}}</td>
          <td>${{(w.tags || []).slice(0,4).map(t => '<span class="tag-chip">'+t+'</span>').join('')}}</td>
        </tr>`
      ).join('') + '</tbody></table>';
  }})();
}}

// ============================================================
// Tab 3: AI 推荐
// ============================================================
function initAvoidTags() {{
  // 避雷标签已移至 RAG 引擎上下文处理
  const container = document.getElementById('avoidTags');
  if (container) container.style.display = 'none';
}}

function getSelectedAvoidTags() {{
  return Array.from(document.querySelectorAll('.avoid-tag.selected')).map(s => s.textContent);
}}

async function sendMessage() {{
  const input = document.getElementById('chatInput');
  const query = input.value.trim();
  if (!query) return;

  const btn = document.getElementById('sendBtn');
  input.disabled = true;
  btn.disabled = true;

  // 添加用户消息
  appendMessage('user', query);
  input.value = '';

  // 添加 AI 加载消息
  const loadingId = appendMessage('assistant', '<div class="spinner"></div> 正在搜索...');

  const avoidTags = getSelectedAvoidTags();

  try {{
    const resp = await fetch(`http://127.0.0.1:8003/api/v1/sentiment/chat`, {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ query, top_k: 5, session_id: 'dashboard-ai-' + Date.now() }})
    }});
    if (!resp.ok) throw new Error('API error: ' + resp.status);
    const result = await resp.json();

    // 显示 LLM 生成的回复
    let html = `<div style="line-height:1.7">${{result.answer.replace(/\\n/g, '<br>')}}</div>`;
    if (result.sources && result.sources.length > 0) {{
      html += `<div style="font-size:11px;color:var(--text2);margin-top:8px;padding-top:6px;border-top:1px solid var(--border)">`;
      html += `📚 参考来源: ${{result.sources.join('、')}}`;
      html += `</div>`;
    }}
    updateMessage(loadingId, html);
  }} catch (e) {{
    updateMessage(loadingId, `<p>⚠️ AI 推荐服务不可用 (端口 8003)</p>
      <p style="font-size:12px;color:var(--text2)">请先启动 Sentiment Critic 服务：<br>
      <code>cd "Sentiment Critic" && uvicorn sentiment_critic.sentiment_api:app --port 8003</code></p>`);
  }}

  input.disabled = false;
  btn.disabled = false;
  setTimeout(() => input.focus(), 100);
}}

function appendMessage(role, html) {{
  const container = document.getElementById('chatMessages');
  const div = document.createElement('div');
  div.className = 'chat-msg ' + role;
  div.innerHTML = `<div class="avatar">${{role === 'user' ? '👤' : '🤖'}}</div><div class="bubble">${{html}}</div>`;
  div.id = 'msg-' + (++_msgSeq);
  container.appendChild(div);
  scrollChatBottom();
  return div.id;
}}

function updateMessage(id, html) {{
  const div = document.getElementById(id);
  if (div) {{
    div.querySelector('.bubble').innerHTML = html;
    scrollChatBottom();
  }}
}}

function scrollChatBottom() {{
  const container = document.getElementById('chatMessages');
  if (container) container.scrollTop = container.scrollHeight;
  const charContainer = document.getElementById('characterChatMessages');
  if (charContainer) charContainer.scrollTop = charContainer.scrollHeight;
}}

// ============================================================
// Tab 4: 角色对话
// ============================================================
let CURRENT_CHARACTER = null;
let IS_CUSTOM_CHARACTER = false;
let CUSTOM_CHARACTER = null;

function scrollCharacterChatBottom() {{
  const container = document.getElementById('characterChatMessages');
  if (container) container.scrollTop = container.scrollHeight;
}}

async function loadCharacterList() {{
  const container = document.getElementById('characterSelector');
  const loading = document.getElementById('characterLoading');
  const info = document.getElementById('characterInfo');

  if (container.querySelectorAll('.char-btn').length > 0) return;

  loading.style.display = 'block';
  try {{
    const resp = await fetch(`${{API.sentiment}}/api/v1/sentiment/character/list`);
    if (!resp.ok) throw new Error('API error');
    const data = await resp.json();
    loading.style.display = 'none';

    const chars = data.characters || [];
    chars.forEach(c => {{
      const btn = document.createElement('button');
      btn.className = 'char-btn';
      btn.innerHTML = `${{c.avatar_emoji || '🎭'}} ${{c.name}}`;
      btn.dataset.id = c.id;
      btn.title = `出自《${{c.novel}}》 - ${{(c.personality || []).join('、')}}`;
      btn.onclick = () => selectCharacter(c.id, chars);
      container.appendChild(btn);
    }});

    if (!document.getElementById('charBtnStyle')) {{
      const style = document.createElement('style');
      style.id = 'charBtnStyle';
      style.textContent = `
        .char-btn {{ padding: 6px 14px; border: 1px solid var(--border); border-radius: 999px;
          background: var(--card-bg); color: var(--text); cursor: pointer; font-size: 13px;
          transition: all .2s; }}
        .char-btn:hover {{ border-color: var(--accent); background: var(--accent-light); }}
        .char-btn.active {{ border-color: var(--accent); background: var(--accent-light);
          font-weight: 600; color: var(--accent); }}
        .char-message-avatar {{ width: 36px; height: 36px; border-radius: 50%; display: flex;
          align-items: center; justify-content: center; font-size: 18px; flex-shrink: 0;
          background: var(--bg); }}
      `;
      document.head.appendChild(style);
    }}
  }} catch (e) {{
    loading.innerHTML = '<span style="font-size:13px;color:var(--rose);">⚠️ 角色服务不可用 (端口 8003)</span>';
  }}
}}

function selectCharacter(id, chars) {{
  document.querySelectorAll('.char-btn').forEach(b => b.classList.remove('active'));
  document.querySelector(`.char-btn[data-id="${{id}}"]`)?.classList.add('active');

  // 清除自定义角色模式
  IS_CUSTOM_CHARACTER = false;
  CUSTOM_CHARACTER = null;

  const char = chars.find(c => c.id === id);
  if (!char) return;

  CURRENT_CHARACTER = char;
  document.getElementById('charAvatar').textContent = char.avatar_emoji || '🎭';
  document.getElementById('charName').textContent = char.name;
  document.getElementById('charNovel').textContent = char.novel;
  document.getElementById('charPersonality').textContent = '『' + (char.personality || []).join('、') + '』';
  document.getElementById('characterInfo').style.display = 'block';

  document.getElementById('characterChatInput').disabled = false;
  document.getElementById('charSendBtn').disabled = false;
  document.getElementById('characterChatInput').placeholder = `对 ${{char.name}} 说点什么...`;
  document.getElementById('characterChatInput').focus();

  appendCharacterMessage('assistant', `我已经准备好扮演${{char.name}}了！你可以开始和我聊天了。`);
}}

async function startCustomCharacter() {{
  const name = document.getElementById('customCharName').value.trim();
  const novel = document.getElementById('customCharNovel').value.trim();
  const errorEl = document.getElementById('customCharError');

  if (!name || !novel) {{
    errorEl.textContent = '请填写角色名和小说名';
    errorEl.style.display = 'inline';
    return;
  }}
  errorEl.style.display = 'none';

  // 取消选择预定义角色
  document.querySelectorAll('.char-btn').forEach(b => b.classList.remove('active'));

  IS_CUSTOM_CHARACTER = true;
  CUSTOM_CHARACTER = {{ name, novel }};
  CURRENT_CHARACTER = null;

  document.getElementById('charAvatar').textContent = '📖';
  document.getElementById('charName').textContent = name;
  document.getElementById('charNovel').textContent = novel;
  document.getElementById('charPersonality').textContent = '『自定义角色』';
  document.getElementById('characterInfo').style.display = 'block';

  document.getElementById('characterChatInput').disabled = false;
  document.getElementById('charSendBtn').disabled = false;
  document.getElementById('characterChatInput').placeholder = `对 ${{name}} 说点什么...`;
  document.getElementById('characterChatInput').focus();

  appendCharacterMessage('assistant',
    `好的，我来扮演《${{novel}}》中的 **${{name}}**！你可以开始和我聊天了。<br>` +
    `（如果知识库中没有收录这部小说，会返回错误信息）`);
}}

async function sendCharacterMessage() {{
  const input = document.getElementById('characterChatInput');
  const query = input.value.trim();
  if (!query || (!CURRENT_CHARACTER && !CUSTOM_CHARACTER)) return;

  const btn = document.getElementById('charSendBtn');
  input.disabled = true;
  btn.disabled = true;

  appendCharacterMessage('user', query);
  input.value = '';

  const loadingId = appendCharacterMessage('assistant', '<div class="spinner"></div> 思考中...');

  try {{
    let url, body;
    if (IS_CUSTOM_CHARACTER && CUSTOM_CHARACTER) {{
      url = `${{API.sentiment}}/api/v1/sentiment/character/chat-by-name`;
      body = JSON.stringify({{
        query,
        character_name: CUSTOM_CHARACTER.name,
        novel_name: CUSTOM_CHARACTER.novel,
        top_k: 5,
        session_id: 'dashboard-custom',
      }});
    }} else {{
      url = `${{API.sentiment}}/api/v1/sentiment/character/chat`;
      body = JSON.stringify({{
        query,
        character_id: CURRENT_CHARACTER.id,
        top_k: 5,
        session_id: 'dashboard-' + CURRENT_CHARACTER.id,
      }});
    }}
    const resp = await fetch(url, {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body
    }});
    if (!resp.ok) {{
      const errData = await resp.json().catch(() => ({{}}));
      throw new Error(errData.detail || 'API error: ' + resp.status);
    }}
    const result = await resp.json();
    updateCharacterMessage(loadingId, result.answer);
    // 检测模式并更新状态标签
    const badge = document.getElementById('charModeLabel');
    if (badge) {{
      if (result.method === 'mock' || result.method === 'mock_dynamic') {{
        badge.textContent = '⚡ Mock 模式 (固定回复，非 AI)';
        badge.style.background = '#fff3cd';
        badge.style.color = '#856404';
      }} else if (result.method && result.method.includes('rag')) {{
        badge.textContent = '🤖 LLM 模式 (DeepSeek AI 生成)';
        badge.style.background = '#d4edda';
        badge.style.color = '#155724';
      }} else if (result.method && result.method.includes('heuristic')) {{
        badge.textContent = '⚠️ 降级模式 (LLM 不可用，模板回复)';
        badge.style.background = '#f8d7da';
        badge.style.color = '#721c24';
      }}
    }}
  }} catch (e) {{
    if (IS_CUSTOM_CHARACTER) {{
      updateCharacterMessage(loadingId,
        '<p>⚠️ ' + e.message + '</p>' +
        '<p style="font-size:12px;color:var(--text2)">该小说可能未被知识库收录，请检查小说名是否正确。<br>' +
        '试试已有的小说：诡秘之主、凡人修仙传、我有一座恐怖屋、修罗武神、仙王的日常生活、斗破苍穹、剑来</p>');
    }} else {{
      updateCharacterMessage(loadingId,
        '<p>⚠️ 角色对话服务暂不可用 (端口 8003)</p>' +
        '<p style="font-size:12px;color:var(--text2)">请先启动 Sentiment Critic 服务：<br>' +
        '<code>cd "Sentiment Critic" && uvicorn sentiment_critic.sentiment_api:app --port 8003</code><br>' +
        '或使用 Mock 模式：<br>' +
        '<code>uvicorn sentiment_critic.mock_server:app --port 8003</code></p>');
    }}
  }}

  input.disabled = false;
  btn.disabled = false;
  setTimeout(() => input.focus(), 100);
}}

function appendCharacterMessage(role, html) {{
  const container = document.getElementById('characterChatMessages');
  const div = document.createElement('div');
  div.className = 'chat-msg ' + role;
  const avatar = role === 'user' ? '👤' : (IS_CUSTOM_CHARACTER ? '📖' : (CURRENT_CHARACTER?.avatar_emoji || '🎭'));
  div.innerHTML = '<div class=\"char-message-avatar\">' + avatar + '</div><div class=\"bubble\">' + html + '</div>';
  div.id = 'char-msg-' + (++_msgSeq);
  container.appendChild(div);
  scrollCharacterChatBottom();
  return div.id;
}}

function updateCharacterMessage(id, html) {{
  const div = document.getElementById(id);
  if (div) {{
    div.querySelector('.bubble').innerHTML = html;
    scrollCharacterChatBottom();
  }}
}}

// ============================================================
// 初始化
// ============================================================
renderTrendDashboard();
initAvoidTags();

window.addEventListener('resize', resizeAllCharts);
console.log('统一大屏已就绪 — 趋势大屏 · 小说评论 · AI 推荐');
</script>
</body>
</html>"""


# ============================================================
# 生成入口
# ============================================================

def render_dashboard(output_path: str | None = None, api_base: str | None = None) -> str:
    data = MOCK_DASHBOARD
    if api_base:
        fetched = fetch_dashboard(api_base)
        if fetched:
            data = fetched

    data["generatedAt"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    html = build_unified_html(data)

    save_path = Path(output_path) if output_path else Path("unified_dashboard.html")
    save_path.write_text(html, encoding="utf-8")
    print(f"统一大屏已保存: {save_path.resolve()}")
    print(f"  文件大小: {len(html):,} 字节")
    print(f"  浏览器打开: file:///{save_path.resolve().as_posix()}")
    print(f"  包含三个 Tab: 趋势大屏 / 小说评论 / AI 推荐")
    return str(save_path.resolve())


if __name__ == "__main__":
    api = None
    if len(sys.argv) > 2 and sys.argv[1] == "--api":
        api = sys.argv[2]
    output = sys.argv[-1] if sys.argv[-1].endswith(".html") else None
    render_dashboard(output_path=output, api_base=api)
