"""
Trend Explorer 趋势大屏生成器 (纯 Python, 无需 Node.js).

生成自包含的 HTML 文件，通过 CDN 加载 ECharts 实现交互式可视化。
用法:
    python dashboard.py                     # 使用内置 Mock 数据生成 trend_dashboard.html
    python dashboard.py --api http://127.0.0.1:8001  # 从 API 获取数据 (需先启动 API)
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ============================================================
# 内置 Mock 数据 (无需 API 即可生成完整大屏)
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
            {"name": "热血", "data": [68, 71, 77, 84, 92], "description": "常与传统玄幻、剑道、少年成长并存，是详情页高频细标签。"},
            {"name": "剑道", "data": [54, 62, 70, 82, 90], "description": "兼具成长线、战斗爽点和辨识度，适合做细分推荐入口。"},
            {"name": "群像", "data": [42, 49, 58, 74, 88], "description": "读者对多角色并肩、家族团队和势力成长的接受度提升。"},
            {"name": "轻量金手指", "data": [30, 35, 44, 56, 72], "description": "相比传统系统流，限制型金手指更受现阶段读者青睐。"},
            {"name": "规则怪谈", "data": [12, 18, 29, 45, 68], "description": "从废土生存向规则怪谈的迁移趋势明显，是增速最快的题材之一。"},
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
        {"name": "传统玄幻", "value": 96},
        {"name": "热血", "value": 92},
        {"name": "家族崛起", "value": 92},
        {"name": "剑道", "value": 90},
        {"name": "群像", "value": 88},
        {"name": "轻量金手指", "value": 72},
        {"name": "升级流", "value": 70},
        {"name": "规则怪谈", "value": 68},
        {"name": "少年成长", "value": 55},
        {"name": "废土生存", "value": 42},
        {"name": "凡人流", "value": 38},
        {"name": "金手指", "value": 35},
    ],
    "migration": {
        "nodes": [
            {"name": "传统升级流"},
            {"name": "反套路群像流"},
            {"name": "系统流"},
            {"name": "轻量金手指"},
            {"name": "废土生存"},
            {"name": "规则怪谈"},
            {"name": "单主角爽文"},
            {"name": "家族崛起群像"},
            {"name": "门派经营"},
            {"name": "宗族势力经营"},
            {"name": "单线复仇"},
            {"name": "权谋博弈"},
        ],
        "links": [
            {"source": "传统升级流", "target": "反套路群像流", "value": 28, "change": 35.2, "reason": "读者兴趣从单人成长转向多线叙事和群像共振。"},
            {"source": "系统流", "target": "轻量金手指", "value": 22, "change": 78.6, "reason": "系统流整体降温，限制型金手指更符合当下读者审美。"},
            {"source": "废土生存", "target": "规则怪谈", "value": 18, "change": 466.7, "reason": "规则怪谈是2026年增速最快的题材，正在大量吸收废土和悬疑读者。"},
            {"source": "单主角爽文", "target": "家族崛起群像", "value": 15, "change": 112.3, "reason": "宗族血脉线为爽文提供了更自然的成长阶梯和社交货币。"},
            {"source": "门派经营", "target": "宗族势力经营", "value": 10, "change": 45.6, "reason": "门派框架正在向更强调血缘和势力对抗的宗族方向演进。"},
            {"source": "单线复仇", "target": "权谋博弈", "value": 8, "change": 22.1, "reason": "单纯复仇线难以支撑长篇，正在融入权谋博弈的多线叙事。"},
        ],
    },
    "migrationTimeline": {
        "periods": ["01月", "02月", "03月", "04月", "05月"],
        "flows": [
            {"id": "传统升级流-反套路群像流", "source": "传统升级流", "target": "反套路群像流", "values": [12, 15, 18, 24, 28], "reason": "读者兴趣从单人成长转向多线叙事和群像共振。"},
            {"id": "系统流-轻量金手指", "source": "系统流", "target": "轻量金手指", "values": [8, 10, 12, 17, 22], "reason": "系统流整体降温，限制型金手指更符合当下读者审美。"},
            {"id": "废土生存-规则怪谈", "source": "废土生存", "target": "规则怪谈", "values": [2, 4, 7, 12, 18], "reason": "规则怪谈是2026年增速最快的题材。"},
            {"id": "单主角爽文-家族崛起群像", "source": "单主角爽文", "target": "家族崛起群像", "values": [5, 7, 9, 12, 15], "reason": "宗族血脉线为爽文提供了更自然的成长阶梯。"},
        ],
    },
    "genreCloudTimeline": {
        "periods": ["01月", "02月", "03月", "04月", "05月"],
        "unit": "k",
        "summary": "月票榜流派热度从传统玄幻、系统流、热血逐步变化到家族崛起、规则怪谈、群像，可通过逐月词云观察题材重心迁移。",
        "clouds": [
            {"period": "01月", "genres": [{"name": "传统玄幻", "value": 72}, {"name": "热血", "value": 68}, {"name": "剑道", "value": 54}, {"name": "系统流", "value": 52}, {"name": "群像", "value": 42}, {"name": "家族崛起", "value": 38}]},
            {"period": "02月", "genres": [{"name": "传统玄幻", "value": 78}, {"name": "热血", "value": 71}, {"name": "剑道", "value": 62}, {"name": "系统流", "value": 49}, {"name": "家族崛起", "value": 46}, {"name": "群像", "value": 49}]},
            {"period": "03月", "genres": [{"name": "传统玄幻", "value": 84}, {"name": "热血", "value": 77}, {"name": "剑道", "value": 70}, {"name": "家族崛起", "value": 59}, {"name": "群像", "value": 58}, {"name": "轻量金手指", "value": 44}]},
            {"period": "04月", "genres": [{"name": "传统玄幻", "value": 91}, {"name": "热血", "value": 84}, {"name": "剑道", "value": 82}, {"name": "家族崛起", "value": 77}, {"name": "群像", "value": 74}, {"name": "轻量金手指", "value": 56}]},
            {"period": "05月", "genres": [{"name": "传统玄幻", "value": 96}, {"name": "热血", "value": 92}, {"name": "家族崛起", "value": 92}, {"name": "剑道", "value": 90}, {"name": "群像", "value": 88}, {"name": "轻量金手指", "value": 72}]},
        ],
    },
    "risingWorks": [
        {"id": "r1", "title": "剑来", "author": "烽火戏诸侯", "platform": "纵横中文网", "rank": 12, "rankChange": 28, "heatScore": 28500, "listType": "月票榜-2026年05月", "tags": ["剑道", "群像", "文青", "权谋"], "summary": "大千世界，无奇不有。陈平安本只想在东宝瓶洲做个普通人..."},
        {"id": "r2", "title": "家族修仙：从种植开始", "author": "青云子", "platform": "纵横中文网", "rank": 35, "rankChange": 52, "heatScore": 18200, "listType": "月票榜-2026年05月", "tags": ["家族崛起", "修仙", "种田流"], "summary": "穿越修仙界，从一块灵田开始经营家族..."},
        {"id": "r3", "title": "规则怪谈：我能完美利用规则", "author": "夜不语", "platform": "纵横中文网", "rank": 8, "rankChange": 64, "heatScore": 45200, "listType": "月票榜-2026年05月", "tags": ["规则怪谈", "无限流", "悬疑"], "summary": "当世界被规则覆盖，只有找到规则的漏洞才能活下去..."},
        {"id": "r4", "title": "我的模拟长生路", "author": "愤怒的香蕉", "platform": "纵横中文网", "rank": 22, "rankChange": 41, "heatScore": 24500, "listType": "月票榜-2026年05月", "tags": ["轻量金手指", "修仙", "模拟器"], "summary": "修仙世界太危险？我有长生模拟器..."},
        {"id": "r5", "title": "苟在妖武乱世修仙", "author": "文抄公", "platform": "纵横中文网", "rank": 18, "rankChange": 33, "heatScore": 27600, "listType": "月票榜-2026年05月", "tags": ["轻量金手指", "妖武", "苟道"], "summary": "穿越妖武世界，方行决定做一个低调的修仙者..."},
        {"id": "r6", "title": "斗破苍穹", "author": "天蚕土豆", "platform": "纵横中文网", "rank": 5, "rankChange": 3, "heatScore": 58000, "listType": "月票榜-2026年05月", "tags": ["传统玄幻", "爽文", "热血"], "summary": "三十年河东三十年河西，莫欺少年穷..."},
        {"id": "r7", "title": "修仙家族不能飘", "author": "青衫仗剑", "platform": "纵横中文网", "rank": 40, "rankChange": 48, "heatScore": 16200, "listType": "月票榜-2026年05月", "tags": ["家族崛起", "修仙", "经营"], "summary": "一人得道鸡犬升天？不，我要整个家族一起飞升..."},
        {"id": "r8", "title": "全球规则化", "author": "黑山老鬼", "platform": "纵横中文网", "rank": 15, "rankChange": 57, "heatScore": 31500, "listType": "月票榜-2026年05月", "tags": ["规则怪谈", "末世", "进化"], "summary": "一夜之间，地球被未知规则覆盖..."},
    ],
}


def fetch_dashboard(api_base: str) -> dict[str, Any] | None:
    """Try to fetch dashboard data from a running Trend API."""
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
            return MOCK_DASHBOARD
    except Exception as exc:
        print(f"Warning: Could not fetch from API ({exc}), using mock data.")
        return None


def build_dashboard_html(data: dict[str, Any]) -> str:
    """Generate a self-contained HTML dashboard string."""
    json_data = json.dumps(data, ensure_ascii=False, default=str)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>全网风向标 — 趋势大屏</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.1/dist/echarts.min.js">
</script>
<style>
:root {{ --bg: #f5f6fa; --card-bg: #fff; --text: #1a1a2e; --text2: #6b7280;
  --border: #e5e7eb; --green: #10b981; --amber: #f59e0b; --blue: #3b82f6;
  --rose: #f43f5e; --shadow: 0 1px 3px rgba(0,0,0,.08); }}
[data-theme="dark"] {{ --bg: #0f172a; --card-bg: #1e293b; --text: #f1f5f9;
  --text2: #94a3b8; --border: #334155; --shadow: 0 1px 3px rgba(0,0,0,.3); }}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: var(--bg); color: var(--text); min-height: 100vh; }}
.header {{ background: var(--card-bg); border-bottom: 1px solid var(--border);
  padding: 14px 24px; display: flex; align-items: center; justify-content: space-between;
  position: sticky; top: 0; z-index: 100; box-shadow: var(--shadow); }}
.header h1 {{ font-size: 20px; font-weight: 700; }}
.header .subtitle {{ font-size: 13px; color: var(--text2); }}
.header .toolbar {{ display: flex; gap: 10px; align-items: center; }}
.header .toolbar button {{ padding: 6px 14px; border: 1px solid var(--border);
  border-radius: 6px; background: var(--card-bg); color: var(--text); cursor: pointer;
  font-size: 13px; }}
.header .toolbar button:hover {{ background: var(--border); }}
.container {{ max-width: 1440px; margin: 0 auto; padding: 20px 24px; }}
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
.footer {{ text-align: center; padding: 20px; font-size: 12px; color: var(--text2); }}
@media (max-width: 960px) {{
  .metrics {{ grid-template-columns: repeat(2, 1fr); }}
  .grid2, .grid3 {{ grid-template-columns: 1fr; }}
}}
@media (max-width: 640px) {{
  .metrics {{ grid-template-columns: 1fr; }}
  .header h1 {{ font-size: 16px; }}
}}
</style>
</head>
<body data-theme="light">
<div class="header">
  <div>
    <h1>📊 全网风向标 — 网络小说趋势大屏</h1>
    <div class="subtitle">数据来源: 纵横中文网月票榜 · 生成时间: <span id="genTime"></span></div>
  </div>
  <div class="toolbar">
    <button onclick="refreshData()" title="重新加载数据">🔄 刷新</button>
    <button onclick="toggleTheme()" title="切换明暗主题">🌓 主题</button>
  </div>
</div>
<div class="container">

  <!-- 数据概览 -->
  <div class="summary" id="summary"></div>

  <!-- KPI 指标卡片 -->
  <div class="metrics" id="metrics"></div>

  <!-- 月票覆盖 -->
  <div class="panel full-width" style="margin-bottom:16px">
    <h2>📅 历史月票榜覆盖</h2>
    <div class="coverage" id="coverage"></div>
  </div>

  <!-- 热度曲线 + 标签排行 -->
  <div class="grid3">
    <div class="panel"><h2>🔥 标签热度趋势曲线</h2><div class="chart" id="heatCurve"></div></div>
    <div class="panel"><h2>🏷️ 热门标签 Top 12</h2><div class="chart-sm" id="hotTagsBar"></div></div>
  </div>

  <!-- 词云 + 平台对比 -->
  <div class="grid2">
    <div class="panel"><h2>☁️ 标签词云</h2><div class="chart" id="wordCloud"></div></div>
    <div class="panel"><h2>📱 平台热度对比</h2><div class="chart-sm" id="platformCompare"></div></div>
  </div>

  <!-- 流派迁移桑基图 -->
  <div class="panel full-width" style="margin-bottom:16px">
    <h2>🔀 流派迁移关系</h2>
    <div class="chart-lg" id="migrationSankey"></div>
  </div>

  <!-- 迁移时间线 -->
  <div class="panel full-width" style="margin-bottom:16px">
    <h2>📈 流派迁移时间线</h2>
    <div class="chart-lg" id="migrationTimeline"></div>
  </div>

  <!-- 上升作品表 -->
  <div class="panel full-width" style="margin-bottom:16px">
    <h2>🚀 上升作品</h2>
    <div style="overflow-x:auto" id="risingWorksTable"></div>
  </div>

</div>
<div class="footer">
  网络小说智能推荐与舆情分析系统 — Trend Explorer 模块 · 纯 Python 生成，无需 Node.js
</div>

<script>
const DATA = {json_data};

// ---- 主题 ----
function toggleTheme() {{
  const el = document.documentElement;
  const next = el.dataset.theme === 'dark' ? 'light' : 'dark';
  el.dataset.theme = next;
  localStorage.setItem('trend-theme', next);
  Object.values(CHARTS).forEach(c => c?.resize());
}}
(function() {{
  const saved = localStorage.getItem('trend-theme');
  if (saved) document.documentElement.dataset.theme = saved;
}})();

// ---- 图表实例管理 ----
const CHARTS = {{}};
function initChart(id) {{
  const dom = document.getElementById(id);
  if (!dom) return null;
  if (CHARTS[id]) CHARTS[id].dispose();
  const inst = echarts.init(dom, document.documentElement.dataset.theme === 'dark' ? 'dark' : null);
  CHARTS[id] = inst;
  return inst;
}}

// ---- 初始化 ----
document.getElementById('genTime').textContent = DATA.generatedAt || '-';
document.getElementById('summary').textContent = DATA.summary || '';

// KPI 指标
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
    series: [{{
      type: 'bar', data: tags.map(t => t.heat).reverse(),
      itemStyle: {{ color: e => ['#10b981','#f59e0b','#3b82f6','#8b5cf6','#f43f5e','#06b6d4'][e.dataIndex % 6] }},
      label: {{ show: true, position: 'right', fontSize: 11 }}
    }}]
  }});
}})();

// 词云 (用 ECharts 散点图模拟)
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
    series: [{{
      type: 'scatter',
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
    series: [{{
      type: 'bar', data: pc.map(p => p.heat),
      itemStyle: {{ color: p => p.data.status === 'active' ? '#10b981' : '#9ca3af' }},
      label: {{ show: true, position: 'right', fontSize: 11,
        formatter: p => p.data.status === 'active' ? p.value + ' (活跃)' : p.value + ' (待接入)' }}
    }}]
  }});
}})();

// 桑基图
(function() {{
  const chart = initChart('migrationSankey');
  if (!chart) return;
  const mig = DATA.migration || {{}};
  chart.setOption({{
    tooltip: {{ trigger: 'item', triggerOn: 'mousemove' }},
    series: [{{
      type: 'sankey', layout: 'none', emphasis: {{ focus: 'adjacency' }},
      data: (mig.nodes || []).map(n => ({{ name: n.name }})),
      links: (mig.links || []).map(l => ({{ source: l.source, target: l.target, value: l.value }})),
      label: {{ fontSize: 12 }},
      lineStyle: {{ color: 'gradient', curveness: 0.5 }}
    }}]
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
    tooltip: {{ trigger: 'item', formatter: p => p.seriesName + '<br/>' + p.name + ': ' + (p.value||'') }},
    legend: {{ type: 'scroll', bottom: 0, textStyle: {{ fontSize: 11 }} }},
    grid: {{ left: 50, right: 20, top: 20, bottom: 50 }},
    xAxis: {{ type: 'category', data: periods, axisLabel: {{ fontSize: 11 }} }},
    yAxis: {{ type: 'value', axisLabel: {{ fontSize: 11 }} }},
    series: flows.map(f => ({{ name: f.id, type: 'line', data: f.values || [], smooth: true, symbol: 'circle', symbolSize: 8 }}))
  }});
}})();

// 上升作品表
(function() {{
  const works = DATA.risingWorks || [];
  const stages = {{ rising: '↑上升', stable: '→平稳', cooling: '↓降温' }};
  document.getElementById('risingWorksTable').innerHTML =
    '<table><thead><tr><th>#</th><th>作品</th><th>作者</th><th>平台</th><th>榜单</th><th>排名变化</th><th>热度</th><th>标签</th></tr></thead><tbody>' +
    works.map((w, i) =>
      `<tr>
        <td>${{i + 1}}</td>
        <td><strong>${{w.title || '-'}}</strong></td>
        <td>${{w.author || '-'}}</td>
        <td>${{w.platform || '-'}}</td>
        <td>${{w.listType || '-'}}</td>
        <td>${{w.rankChange > 0 ? '🔺 +'+w.rankChange : w.rankChange < 0 ? '🔻 '+w.rankChange : '➖ 0'}}</td>
        <td>${{(w.heatScore || 0).toLocaleString()}}</td>
        <td>${{(w.tags || []).slice(0,4).map(t => '<span class="tag-chip">'+t+'</span>').join('')}}</td>
      </tr>`
    ).join('') + '</tbody></table>';
}})();

// 响应式
window.addEventListener('resize', () => Object.values(CHARTS).forEach(c => c?.resize()));

function refreshData() {{ location.reload(); }}
console.log('Trend Explorer 趋势大屏已就绪 — 纯 Python + CDN ECharts，无需 Node.js');
</script>
</body>
</html>"""


def render_dashboard(output_path: str | None = None, api_base: str | None = None) -> str:
    """Generate the trend dashboard HTML file.

    Args:
        output_path: Where to save the HTML (default: trend_dashboard.html in current dir).
        api_base: If set, try fetching data from this API URL first.

    Returns:
        The path to the generated HTML file.
    """
    data = MOCK_DASHBOARD
    if api_base:
        fetched = fetch_dashboard(api_base)
        if fetched:
            data = fetched

    data["generatedAt"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    html = build_dashboard_html(data)

    save_path = Path(output_path) if output_path else Path("trend_dashboard.html")
    save_path.write_text(html, encoding="utf-8")
    print(f"Trend dashboard saved to: {save_path.resolve()}")
    print(f"  Size: {len(html):,} bytes")
    print(f"  Open in browser: file:///{save_path.resolve().as_posix()}")
    return str(save_path.resolve())


if __name__ == "__main__":
    api = None
    if len(sys.argv) > 2 and sys.argv[1] == "--api":
        api = sys.argv[2]
    output = sys.argv[-1] if sys.argv[-1].endswith(".html") else None
    render_dashboard(output_path=output, api_base=api)
