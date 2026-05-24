from __future__ import annotations

from pathlib import Path
from typing import Any
import json


def render_dashboard(report: dict[str, Any], output_path: str | Path) -> Path:
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    report_json = json.dumps(report, ensure_ascii=False).replace("</", "<\\/")
    target.write_text(TEMPLATE.replace("__REPORT_JSON__", report_json), encoding="utf-8", newline="\n")
    return target


TEMPLATE = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Sentiment Critic 舆情看板</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #17202a;
      --muted: #687385;
      --line: #d9dee8;
      --page: #f7f8fb;
      --panel: #ffffff;
      --good: #248a5c;
      --mid: #9a6b10;
      --bad: #c4433b;
      --accent: #2d5bd1;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      font-family: "Microsoft YaHei", "PingFang SC", system-ui, sans-serif;
      color: var(--ink);
      background: var(--page);
    }
    header {
      padding: 28px clamp(18px, 4vw, 48px) 20px;
      background: #ffffff;
      border-bottom: 1px solid var(--line);
    }
    header h1 {
      margin: 0;
      font-size: clamp(26px, 4vw, 42px);
      line-height: 1.15;
      letter-spacing: 0;
    }
    header p {
      margin: 10px 0 0;
      color: var(--muted);
      max-width: 760px;
      line-height: 1.65;
    }
    main {
      width: min(1180px, calc(100% - 32px));
      margin: 24px auto 48px;
      display: grid;
      gap: 18px;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(12, 1fr);
      gap: 16px;
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
    }
    .span-4 { grid-column: span 4; }
    .span-5 { grid-column: span 5; }
    .span-7 { grid-column: span 7; }
    .span-12 { grid-column: span 12; }
    .metric {
      display: grid;
      gap: 8px;
      min-height: 128px;
    }
    .metric small {
      color: var(--muted);
      font-weight: 700;
    }
    .metric strong {
      font-size: clamp(30px, 5vw, 52px);
      line-height: 1;
    }
    .positive { color: var(--good); }
    .neutral { color: var(--mid); }
    .negative { color: var(--bad); }
    .bar {
      height: 18px;
      display: flex;
      overflow: hidden;
      border-radius: 999px;
      background: #e9edf4;
      border: 1px solid var(--line);
    }
    .bar span { min-width: 2px; }
    .bar .positive { background: var(--good); }
    .bar .neutral { background: #d49b22; }
    .bar .negative { background: var(--bad); }
    h2 {
      margin: 0 0 14px;
      font-size: 18px;
      letter-spacing: 0;
    }
    .score-row, .platform-row, .tag-row {
      display: grid;
      grid-template-columns: 120px 1fr auto;
      gap: 12px;
      align-items: center;
      padding: 10px 0;
      border-top: 1px solid #edf0f5;
    }
    .score-row:first-of-type, .platform-row:first-of-type, .tag-row:first-of-type { border-top: 0; }
    .track {
      height: 10px;
      border-radius: 999px;
      background: #edf0f5;
      overflow: hidden;
    }
    .track i {
      display: block;
      height: 100%;
      width: var(--w);
      background: var(--accent);
      border-radius: inherit;
    }
    .platform-row {
      grid-template-columns: minmax(90px, 130px) 1fr minmax(70px, auto);
    }
    .platform-stack {
      display: flex;
      height: 12px;
      overflow: hidden;
      border-radius: 999px;
      background: #edf0f5;
    }
    .platform-stack span { min-width: 2px; }
    .platform-stack .p { background: var(--good); }
    .platform-stack .n { background: #d49b22; }
    .platform-stack .b { background: var(--bad); }
    .tag-cloud {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }
    .tag {
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 6px 10px;
      color: #344050;
      background: #fafbfe;
      font-size: 13px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
    }
    th, td {
      padding: 12px 10px;
      border-top: 1px solid #edf0f5;
      text-align: left;
      vertical-align: top;
      line-height: 1.55;
      word-break: break-word;
    }
    th {
      color: var(--muted);
      font-size: 13px;
      border-top: 0;
    }
    .pill {
      display: inline-flex;
      align-items: center;
      min-height: 26px;
      border-radius: 999px;
      padding: 2px 9px;
      color: #fff;
      font-size: 12px;
      font-weight: 700;
    }
    .pill.positive { background: var(--good); color: #fff; }
    .pill.neutral { background: #b17b13; color: #fff; }
    .pill.negative { background: var(--bad); color: #fff; }
    .verdict {
      font-size: 18px;
      line-height: 1.7;
      border-left: 4px solid var(--accent);
      padding-left: 14px;
      margin: 0;
    }
    @media (max-width: 860px) {
      .grid { grid-template-columns: 1fr; }
      .span-4, .span-5, .span-7, .span-12 { grid-column: 1; }
      .score-row, .platform-row, .tag-row { grid-template-columns: 1fr; gap: 8px; }
      table, thead, tbody, th, td, tr { display: block; }
      thead { display: none; }
      tr { border-top: 1px solid #edf0f5; padding: 10px 0; }
      td { border-top: 0; padding: 6px 0; }
      td::before {
        content: attr(data-label);
        display: block;
        color: var(--muted);
        font-size: 12px;
        font-weight: 700;
      }
    }
  </style>
</head>
<body>
  <header>
    <h1 id="title">Sentiment Critic</h1>
    <p id="subtitle"></p>
  </header>
  <main>
    <section class="grid">
      <div class="panel metric span-4">
        <small>正面评论</small>
        <strong class="positive" id="positive-ratio">0%</strong>
        <div class="bar" aria-label="正负评论比">
          <span class="positive" id="bar-positive"></span>
          <span class="neutral" id="bar-neutral"></span>
          <span class="negative" id="bar-negative"></span>
        </div>
      </div>
      <div class="panel metric span-4">
        <small>负面评论</small>
        <strong class="negative" id="negative-ratio">0%</strong>
        <span id="sample-size"></span>
      </div>
      <div class="panel metric span-4">
        <small>综合判断</small>
        <p class="verdict" id="verdict"></p>
      </div>
    </section>

    <section class="grid">
      <div class="panel span-5">
        <h2>多维评分</h2>
        <div id="scores"></div>
      </div>
      <div class="panel span-7">
        <h2>平台分布</h2>
        <div id="platforms"></div>
      </div>
    </section>

    <section class="panel">
      <h2>高频口碑标签</h2>
      <div class="tag-cloud" id="tags"></div>
    </section>

    <section class="panel">
      <h2>深度评论拆解</h2>
      <table>
        <thead>
          <tr>
            <th style="width: 92px;">平台</th>
            <th style="width: 92px;">倾向</th>
            <th>毒舌点评</th>
            <th>入坑理由</th>
            <th style="width: 150px;">评分</th>
          </tr>
        </thead>
        <tbody id="items"></tbody>
      </table>
    </section>
  </main>

  <script id="report-data" type="application/json">__REPORT_JSON__</script>
  <script>
    const report = JSON.parse(document.getElementById("report-data").textContent);
    const pct = value => `${Math.round((value || 0) * 100)}%`;
    const esc = value => String(value ?? "").replace(/[&<>"']/g, ch => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
    }[ch]));

    document.getElementById("title").textContent = `${report.book || "小说"} 舆情看板`;
    document.getElementById("subtitle").textContent =
      `共分析 ${report.review_count || 0} 条深度书评，模型分析：${report.agent_used ? "已启用" : "未启用，使用本地规则兜底"}`;
    document.getElementById("positive-ratio").textContent = pct(report.ratio.positive);
    document.getElementById("negative-ratio").textContent = pct(report.ratio.negative);
    document.getElementById("sample-size").textContent = `${report.review_count || 0} 条样本`;
    document.getElementById("verdict").textContent = report.verdict || "";
    document.getElementById("bar-positive").style.width = pct(report.ratio.positive);
    document.getElementById("bar-neutral").style.width = pct(report.ratio.neutral);
    document.getElementById("bar-negative").style.width = pct(report.ratio.negative);

    const scoreNames = { writing: "文笔", logic: "逻辑", update_speed: "更新速度", sentiment: "情绪均值" };
    document.getElementById("scores").innerHTML = Object.entries(scoreNames).map(([key, label]) => {
      const raw = Number(report.average_scores[key] || 0);
      const value = key === "sentiment" ? ((raw + 1) / 2 * 10) : raw;
      return `<div class="score-row">
        <span>${esc(label)}</span>
        <span class="track"><i style="--w:${Math.max(0, Math.min(100, value * 10))}%"></i></span>
        <strong>${key === "sentiment" ? raw.toFixed(2) : raw.toFixed(1)}</strong>
      </div>`;
    }).join("");

    document.getElementById("platforms").innerHTML =
      Object.entries(report.platform_breakdown || {}).map(([platform, row]) => {
        const total = Math.max(row.total || 0, 1);
        return `<div class="platform-row">
          <strong>${esc(platform)}</strong>
          <span class="platform-stack">
            <span class="p" style="width:${row.positive / total * 100}%"></span>
            <span class="n" style="width:${row.neutral / total * 100}%"></span>
            <span class="b" style="width:${row.negative / total * 100}%"></span>
          </span>
          <span>${row.total || 0} 条</span>
        </div>`;
      }).join("") || "<p>暂无平台数据</p>";

    document.getElementById("tags").innerHTML =
      (report.top_tags || []).map(row => `<span class="tag">${esc(row.tag)} ${row.count}</span>`).join("") ||
      "<span class='tag'>暂无标签</span>";

    document.getElementById("items").innerHTML = (report.items || []).map(item => {
      const score = `文 ${Number(item.writing_score || 0).toFixed(1)} / 逻 ${Number(item.logic_score || 0).toFixed(1)} / 更 ${Number(item.update_speed_score || 0).toFixed(1)}`;
      return `<tr>
        <td data-label="平台">${esc(item.platform)}</td>
        <td data-label="倾向"><span class="pill ${esc(item.sentiment)}">${esc(sentimentLabel(item.sentiment))}</span></td>
        <td data-label="毒舌点评">${esc(item.one_liner)}<br><small>${esc((item.tags || []).join("、"))}</small></td>
        <td data-label="入坑理由">${esc(item.entry_reason)}<br><small>${esc(item.evidence || "")}</small></td>
        <td data-label="评分">${esc(score)}</td>
      </tr>`;
    }).join("");

    function sentimentLabel(value) {
      return ({ positive: "正面", neutral: "中性", negative: "负面" })[value] || "中性";
    }
  </script>
</body>
</html>
"""
