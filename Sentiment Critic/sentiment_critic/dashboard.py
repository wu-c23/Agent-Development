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
  <title>Sentiment Critic React Dashboard</title>
  <style>
    :root {
      color-scheme: light;
      --page: #f4f6f6;
      --ink: #18211f;
      --muted: #65736f;
      --soft: #8a9692;
      --line: #dce5e1;
      --panel: #ffffff;
      --panel-soft: #f8faf9;
      --accent: #2f6f73;
      --accent-2: #685bc7;
      --good: #14845f;
      --mid: #a96b13;
      --bad: #bd3f49;
      --info: #2b6cb0;
      --shadow: 0 12px 28px rgba(24, 33, 31, 0.08);
    }
    [data-theme="dark"] {
      color-scheme: dark;
      --page: #111716;
      --ink: #edf4f2;
      --muted: #a8b5b1;
      --soft: #83928d;
      --line: #293633;
      --panel: #18211f;
      --panel-soft: #1e2926;
      --accent: #58b7ae;
      --accent-2: #a99cff;
      --good: #55c896;
      --mid: #e3a943;
      --bad: #ff727e;
      --info: #74a7e8;
      --shadow: 0 16px 34px rgba(0, 0, 0, 0.22);
    }
    * { box-sizing: border-box; }
    html { background: var(--page); }
    body {
      margin: 0;
      min-height: 100vh;
      font-family: "Microsoft YaHei", "PingFang SC", system-ui, sans-serif;
      color: var(--ink);
      background:
        linear-gradient(180deg, rgba(47, 111, 115, 0.11), transparent 320px),
        radial-gradient(circle at 85% 4%, rgba(104, 91, 199, 0.12), transparent 260px),
        var(--page);
    }
    button, input, select {
      font: inherit;
    }
    button {
      border: 0;
      cursor: pointer;
    }
    a { color: inherit; }
    .app-shell {
      min-height: 100vh;
    }
    .topbar {
      border-bottom: 1px solid var(--line);
      background: color-mix(in srgb, var(--panel) 88%, transparent);
      backdrop-filter: blur(14px);
      position: sticky;
      top: 0;
      z-index: 20;
    }
    .topbar-inner {
      width: min(1240px, calc(100% - 32px));
      margin: 0 auto;
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 20px;
      align-items: center;
      padding: 18px 0;
    }
    .brand {
      display: grid;
      gap: 5px;
      min-width: 0;
    }
    .eyebrow {
      margin: 0;
      color: var(--accent);
      font-size: 12px;
      font-weight: 800;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    h1 {
      margin: 0;
      font-size: clamp(25px, 4vw, 42px);
      line-height: 1.12;
      letter-spacing: 0;
    }
    .subtitle {
      margin: 0;
      color: var(--muted);
      line-height: 1.55;
    }
    .toolbar {
      display: flex;
      gap: 8px;
      justify-content: flex-end;
      flex-wrap: wrap;
    }
    .icon-button, .text-button {
      min-height: 36px;
      border-radius: 8px;
      border: 1px solid var(--line);
      background: var(--panel);
      color: var(--ink);
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 7px;
      padding: 7px 10px;
      box-shadow: 0 6px 14px rgba(24, 33, 31, 0.05);
    }
    .icon-button {
      width: 38px;
      padding: 0;
    }
    .icon {
      width: 17px;
      height: 17px;
      display: inline-block;
    }
    main {
      width: min(1240px, calc(100% - 32px));
      margin: 22px auto 52px;
      display: grid;
      gap: 18px;
    }
    .summary-grid {
      display: grid;
      grid-template-columns: 1.2fr repeat(3, minmax(160px, 0.7fr));
      gap: 14px;
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
    }
    .hero-panel {
      min-height: 174px;
      padding: 20px;
      display: grid;
      gap: 16px;
      align-content: space-between;
      overflow: hidden;
      position: relative;
    }
    .hero-panel::before {
      content: "";
      position: absolute;
      inset: 0 0 auto;
      height: 4px;
      background: linear-gradient(90deg, var(--accent), var(--accent-2));
    }
    .verdict {
      margin: 0;
      font-size: 18px;
      line-height: 1.7;
      color: var(--ink);
    }
    .chip-row {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }
    .chip {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      min-height: 30px;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 5px 9px;
      background: var(--panel-soft);
      color: var(--muted);
      font-size: 13px;
      white-space: nowrap;
    }
    .chip strong { color: var(--ink); }
    .metric {
      min-height: 174px;
      padding: 18px;
      display: grid;
      align-content: space-between;
      gap: 12px;
      position: relative;
      overflow: hidden;
    }
    .metric::before {
      content: "";
      position: absolute;
      inset: 0 0 auto;
      height: 4px;
      background: var(--accent);
    }
    .metric.good::before { background: var(--good); }
    .metric.mid::before { background: var(--mid); }
    .metric.bad::before { background: var(--bad); }
    .metric-label {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      color: var(--muted);
      font-size: 13px;
      font-weight: 800;
    }
    .metric-value {
      font-size: clamp(33px, 5vw, 54px);
      line-height: 1;
      font-weight: 850;
      letter-spacing: 0;
    }
    .metric-note {
      color: var(--soft);
      font-size: 13px;
    }
    .positive { color: var(--good); }
    .neutral { color: var(--mid); }
    .negative { color: var(--bad); }
    .ratio-bar {
      height: 15px;
      display: flex;
      border-radius: 999px;
      overflow: hidden;
      border: 1px solid var(--line);
      background: color-mix(in srgb, var(--line) 52%, transparent);
    }
    .ratio-bar span { min-width: 2px; }
    .ratio-bar .positive { background: var(--good); }
    .ratio-bar .neutral { background: var(--mid); }
    .ratio-bar .negative { background: var(--bad); }
    .content-grid {
      display: grid;
      grid-template-columns: minmax(280px, 0.85fr) minmax(0, 1.25fr);
      gap: 16px;
      align-items: start;
    }
    .stack {
      display: grid;
      gap: 16px;
    }
    .section {
      padding: 18px;
    }
    .section-title {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 14px;
    }
    .section-title h2 {
      margin: 0;
      font-size: 18px;
      letter-spacing: 0;
    }
    .section-title span {
      color: var(--soft);
      font-size: 13px;
    }
    .score-row, .platform-row {
      display: grid;
      grid-template-columns: 104px 1fr auto;
      align-items: center;
      gap: 12px;
      padding: 11px 0;
      border-top: 1px solid color-mix(in srgb, var(--line) 74%, transparent);
    }
    .score-row:first-of-type, .platform-row:first-of-type { border-top: 0; }
    .track {
      height: 10px;
      border-radius: 999px;
      background: color-mix(in srgb, var(--line) 64%, transparent);
      overflow: hidden;
    }
    .track i {
      height: 100%;
      display: block;
      width: var(--w);
      border-radius: inherit;
      background: linear-gradient(90deg, var(--accent), var(--accent-2));
    }
    .platform-row {
      grid-template-columns: 92px 1fr 58px;
    }
    .platform-stack {
      display: flex;
      height: 13px;
      overflow: hidden;
      border-radius: 999px;
      background: color-mix(in srgb, var(--line) 64%, transparent);
    }
    .platform-stack span { min-width: 2px; }
    .platform-stack .p { background: var(--good); }
    .platform-stack .n { background: var(--mid); }
    .platform-stack .b { background: var(--bad); }
    .tag-cloud {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .tag {
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 7px 10px;
      background: var(--panel-soft);
      color: var(--ink);
      font-size: 13px;
      font-weight: 700;
    }
    .control-panel {
      padding: 14px;
      display: grid;
      gap: 12px;
    }
    .control-row {
      display: grid;
      grid-template-columns: 1fr minmax(120px, auto);
      gap: 10px;
    }
    .search-input, .select-input {
      width: 100%;
      min-height: 38px;
      border-radius: 8px;
      border: 1px solid var(--line);
      background: var(--panel);
      color: var(--ink);
      padding: 8px 10px;
      outline: none;
    }
    .search-input:focus, .select-input:focus {
      border-color: var(--accent);
      box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 18%, transparent);
    }
    .segmented {
      display: flex;
      flex-wrap: wrap;
      gap: 7px;
    }
    .segment {
      min-height: 32px;
      border-radius: 8px;
      border: 1px solid var(--line);
      background: var(--panel-soft);
      color: var(--muted);
      padding: 6px 9px;
      font-size: 13px;
      font-weight: 750;
    }
    .segment.active {
      border-color: color-mix(in srgb, var(--accent) 62%, var(--line));
      background: color-mix(in srgb, var(--accent) 13%, var(--panel));
      color: var(--ink);
    }
    .review-list {
      display: grid;
      gap: 10px;
    }
    .review-card {
      width: 100%;
      text-align: left;
      display: grid;
      gap: 9px;
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      color: var(--ink);
      box-shadow: 0 6px 14px rgba(24, 33, 31, 0.04);
    }
    .review-card:hover, .review-card.active {
      border-color: color-mix(in srgb, var(--accent) 55%, var(--line));
      background: color-mix(in srgb, var(--accent) 6%, var(--panel));
    }
    .review-head {
      display: flex;
      gap: 8px;
      align-items: center;
      justify-content: space-between;
    }
    .review-title {
      margin: 0;
      font-size: 15px;
      font-weight: 800;
      line-height: 1.45;
    }
    .review-meta {
      display: flex;
      gap: 7px;
      flex-wrap: wrap;
      color: var(--soft);
      font-size: 12px;
    }
    .pill {
      display: inline-flex;
      align-items: center;
      min-height: 24px;
      border-radius: 999px;
      padding: 2px 8px;
      color: #fff;
      font-size: 12px;
      font-weight: 800;
      white-space: nowrap;
    }
    .pill.positive { background: var(--good); }
    .pill.neutral { background: var(--mid); }
    .pill.negative { background: var(--bad); }
    .one-liner {
      margin: 0;
      color: var(--ink);
      line-height: 1.6;
    }
    .detail-panel {
      padding: 18px;
      position: sticky;
      top: 92px;
      display: grid;
      gap: 14px;
    }
    .detail-title {
      margin: 0;
      font-size: 20px;
      line-height: 1.45;
    }
    .score-grid {
      display: grid;
      grid-template-columns: repeat(5, 1fr);
      gap: 9px;
    }
    .mini-score {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
      background: var(--panel-soft);
    }
    .mini-score span {
      display: block;
      color: var(--soft);
      font-size: 12px;
      margin-bottom: 5px;
    }
    .mini-score strong {
      font-size: 22px;
    }
    .detail-copy {
      margin: 0;
      color: var(--muted);
      line-height: 1.75;
    }
    .empty-state {
      border: 1px dashed var(--line);
      border-radius: 8px;
      padding: 18px;
      color: var(--muted);
      text-align: center;
      background: var(--panel-soft);
    }
    .runtime-warning {
      width: min(760px, calc(100% - 32px));
      margin: 28px auto;
      padding: 16px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      color: var(--muted);
    }
    @media (max-width: 960px) {
      .topbar-inner, .summary-grid, .content-grid, .control-row {
        grid-template-columns: 1fr;
      }
      .toolbar {
        justify-content: flex-start;
      }
      .detail-panel {
        position: static;
      }
    }
    @media (max-width: 640px) {
      main, .topbar-inner {
        width: min(100% - 22px, 1240px);
      }
      .score-grid {
        grid-template-columns: repeat(3, 1fr);
      }
      .metric, .hero-panel {
        min-height: auto;
      }
    }
  </style>
</head>
<body>
  <div id="root">
    <div class="runtime-warning">正在加载 React 交互看板。如果长时间没有显示，请确认浏览器可以访问 React CDN，或使用网络正常的环境打开。</div>
  </div>
  <script id="report-data" type="application/json">__REPORT_JSON__</script>
  <script crossorigin src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
  <script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
  <script>
    let h;
    const report = JSON.parse(document.getElementById("report-data").textContent);
    const pct = value => `${Math.round((Number(value) || 0) * 100)}%`;
    const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
    const sentimentLabel = value => ({ positive: "正面", neutral: "中性", negative: "负面" })[value] || "中性";
    const platformLabel = value => ({ douban: "豆瓣", tieba: "贴吧", xiaohongshu: "小红书", manual: "手动" })[value] || value || "未知";
    const scoreText = value => Number(value || 0).toFixed(1);

    function App() {
      const items = report.items || [];
      const platforms = Object.keys(report.platform_breakdown || {});
      const [theme, setTheme] = React.useState(localStorage.getItem("sentiment-theme") || "light");
      const [query, setQuery] = React.useState("");
      const [platform, setPlatform] = React.useState("all");
      const [sentiment, setSentiment] = React.useState("all");
      const [sort, setSort] = React.useState("sentiment_abs");
      const [selectedId, setSelectedId] = React.useState(items[0]?.review_id || "");

      React.useEffect(() => {
        document.documentElement.dataset.theme = theme;
        localStorage.setItem("sentiment-theme", theme);
      }, [theme]);

      const filtered = React.useMemo(() => {
        const needle = query.trim().toLowerCase();
        const rows = items.filter(item => {
          if (platform !== "all" && item.platform !== platform) return false;
          if (sentiment !== "all" && item.sentiment !== sentiment) return false;
          if (!needle) return true;
          const haystack = [
            item.platform,
            item.title,
            item.one_liner,
            item.entry_reason,
            item.evidence,
            ...(item.tags || [])
          ].join(" ").toLowerCase();
          return haystack.includes(needle);
        });
        return rows.sort(sorters[sort] || sorters.sentiment_abs);
      }, [items, query, platform, sentiment, sort]);

      const selected = filtered.find(item => item.review_id === selectedId) || filtered[0] || items[0] || null;

      React.useEffect(() => {
        if (selected && selected.review_id !== selectedId) {
          setSelectedId(selected.review_id);
        }
      }, [filtered.length, selectedId]);

      function exportFiltered() {
        const payload = JSON.stringify({ ...report, items: filtered, filtered_count: filtered.length }, null, 2);
        const blob = new Blob([payload], { type: "application/json;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = `${report.book || "sentiment"}_filtered_reviews.json`;
        link.click();
        URL.revokeObjectURL(url);
      }

      function copySummary() {
        const text = `${report.book || "小说"}：${report.verdict || ""} 正面 ${pct(report.ratio?.positive)}，负面 ${pct(report.ratio?.negative)}，样本 ${report.review_count || 0} 条。`;
        navigator.clipboard?.writeText(text);
      }

      return h("div", { className: "app-shell" },
        h(Header, { theme, setTheme, exportFiltered, copySummary }),
        h("main", null,
          h(SummaryGrid, null),
          h("section", { className: "content-grid" },
            h("div", { className: "stack" },
              h(ScoresPanel, null),
              h(PlatformPanel, { platforms }),
              h(TagsPanel, null),
              h(FilterPanel, { query, setQuery, platform, setPlatform, sentiment, setSentiment, sort, setSort, platforms, filteredCount: filtered.length, total: items.length }),
              h(ReviewList, { rows: filtered, selectedId, setSelectedId })
            ),
            h(DetailPanel, { item: selected })
          )
        )
      );
    }

    const sorters = {
      sentiment_abs: (a, b) => Math.abs(Number(b.sentiment_score || 0)) - Math.abs(Number(a.sentiment_score || 0)),
      newest_platform: (a, b) => String(a.platform || "").localeCompare(String(b.platform || "")),
      writing: (a, b) => Number(b.writing_score || 0) - Number(a.writing_score || 0),
      logic: (a, b) => Number(b.logic_score || 0) - Number(a.logic_score || 0),
      update: (a, b) => Number(b.update_speed_score || 0) - Number(a.update_speed_score || 0)
    };

    function Header({ theme, setTheme, exportFiltered, copySummary }) {
      return h("header", { className: "topbar" },
        h("div", { className: "topbar-inner" },
          h("div", { className: "brand" },
            h("p", { className: "eyebrow" }, "Sentiment Critic · React"),
            h("h1", null, `${report.book || "小说"} 舆情看板`),
            h("p", { className: "subtitle" }, `已分析 ${report.review_count || 0} 条深度书评，当前方法：${report.agent_used ? "Agent" : "本地规则"}。`)
          ),
          h("div", { className: "toolbar" },
            h("button", { className: "text-button", onClick: copySummary, title: "复制摘要" }, h(Icon, { name: "copy" }), "复制摘要"),
            h("button", { className: "text-button", onClick: exportFiltered, title: "导出当前筛选结果" }, h(Icon, { name: "download" }), "导出筛选"),
            h("button", { className: "icon-button", onClick: () => setTheme(theme === "dark" ? "light" : "dark"), title: "切换主题" }, h(Icon, { name: theme === "dark" ? "sun" : "moon" }))
          )
        )
      );
    }

    function SummaryGrid() {
      const ratio = report.ratio || {};
      const counts = report.counts || {};
      return h("section", { className: "summary-grid" },
        h("div", { className: "panel hero-panel" },
          h("p", { className: "verdict" }, report.verdict || "暂无综合判断。"),
          h("div", { className: "chip-row" },
            h("span", { className: "chip" }, "样本 ", h("strong", null, `${report.review_count || 0} 条`)),
            h("span", { className: "chip" }, "平台 ", h("strong", null, Object.keys(report.platform_breakdown || {}).map(platformLabel).join(" / ") || "暂无")),
            h("span", { className: "chip" }, "模型 ", h("strong", null, report.agent_used ? "Agent" : "本地规则"))
          )
        ),
        h(Metric, { label: "正面评论", value: pct(ratio.positive), note: `${counts.positive || 0} 条`, tone: "good", className: "positive" }),
        h(Metric, { label: "中性评论", value: pct(ratio.neutral), note: `${counts.neutral || 0} 条`, tone: "mid", className: "neutral" }),
        h(Metric, { label: "负面评论", value: pct(ratio.negative), note: `${counts.negative || 0} 条`, tone: "bad", className: "negative",
          footer: h(RatioBar, { ratio })
        })
      );
    }

    function Metric({ label, value, note, tone, className, footer }) {
      return h("div", { className: `panel metric ${tone || ""}` },
        h("div", { className: "metric-label" }, h("span", null, label), h("span", null, note)),
        h("div", { className: `metric-value ${className || ""}` }, value),
        footer || h("span", { className: "metric-note" }, "按当前样本计算")
      );
    }

    function RatioBar({ ratio }) {
      return h("div", { className: "ratio-bar", title: "正面 / 中性 / 负面" },
        h("span", { className: "positive", style: { width: pct(ratio.positive) } }),
        h("span", { className: "neutral", style: { width: pct(ratio.neutral) } }),
        h("span", { className: "negative", style: { width: pct(ratio.negative) } })
      );
    }

    function ScoresPanel() {
      const scores = report.average_scores || {};
      const rows = [
        ["文笔", scores.writing, 10],
        ["逻辑", scores.logic, 10],
        ["人物", scores.character, 10],
        ["更新", scores.update_speed, 10],
        ["情绪", scores.sentiment, 1]
      ];
      return h("section", { className: "panel section" },
        h("div", { className: "section-title" }, h("h2", null, "多维评分"), h("span", null, "量化概览")),
        rows.map(([label, raw, max]) => {
          const value = Number(raw || 0);
          const normalized = label === "情绪" ? (value + 1) / 2 * 100 : value / max * 100;
          return h("div", { className: "score-row", key: label },
            h("strong", null, label),
            h("span", { className: "track" }, h("i", { style: { "--w": `${clamp(normalized, 0, 100)}%` } })),
            h("span", null, label === "情绪" ? value.toFixed(2) : scoreText(value))
          );
        })
      );
    }

    function PlatformPanel({ platforms }) {
      const breakdown = report.platform_breakdown || {};
      return h("section", { className: "panel section" },
        h("div", { className: "section-title" }, h("h2", null, "平台声量"), h("span", null, "正 / 中 / 负")),
        platforms.length ? platforms.map(platform => {
          const row = breakdown[platform] || {};
          const total = Math.max(row.total || 0, 1);
          return h("div", { className: "platform-row", key: platform },
            h("strong", null, platformLabel(platform)),
            h("span", { className: "platform-stack" },
              h("span", { className: "p", style: { width: `${(row.positive || 0) / total * 100}%` } }),
              h("span", { className: "n", style: { width: `${(row.neutral || 0) / total * 100}%` } }),
              h("span", { className: "b", style: { width: `${(row.negative || 0) / total * 100}%` } })
            ),
            h("span", null, `${row.total || 0} 条`)
          );
        }) : h("div", { className: "empty-state" }, "暂无平台数据")
      );
    }

    function TagsPanel() {
      const tags = report.top_tags || [];
      return h("section", { className: "panel section" },
        h("div", { className: "section-title" }, h("h2", null, "高频口碑标签"), h("span", null, `${tags.length} 个`)),
        h("div", { className: "tag-cloud" }, tags.length ? tags.map(row => h("span", { className: "tag", key: row.tag }, `${row.tag} ${row.count}`)) : h("span", { className: "tag" }, "暂无标签"))
      );
    }

    function FilterPanel(props) {
      const sentiments = ["all", "positive", "neutral", "negative"];
      return h("section", { className: "panel control-panel" },
        h("div", { className: "section-title" }, h("h2", null, "筛选评论"), h("span", null, `${props.filteredCount} / ${props.total}`)),
        h("div", { className: "control-row" },
          h("input", {
            className: "search-input",
            value: props.query,
            placeholder: "搜索标题、标签、点评、证据",
            onChange: event => props.setQuery(event.target.value)
          }),
          h("select", { className: "select-input", value: props.sort, onChange: event => props.setSort(event.target.value) },
            h("option", { value: "sentiment_abs" }, "按情绪强度"),
            h("option", { value: "writing" }, "按文笔评分"),
            h("option", { value: "logic" }, "按逻辑评分"),
            h("option", { value: "update" }, "按更新评分"),
            h("option", { value: "newest_platform" }, "按平台")
          )
        ),
        h("div", { className: "segmented" },
          h("button", { className: `segment ${props.platform === "all" ? "active" : ""}`, onClick: () => props.setPlatform("all") }, "全部平台"),
          props.platforms.map(name => h("button", { key: name, className: `segment ${props.platform === name ? "active" : ""}`, onClick: () => props.setPlatform(name) }, platformLabel(name)))
        ),
        h("div", { className: "segmented" },
          sentiments.map(name => h("button", { key: name, className: `segment ${props.sentiment === name ? "active" : ""}`, onClick: () => props.setSentiment(name) }, name === "all" ? "全部倾向" : sentimentLabel(name)))
        )
      );
    }

    function ReviewList({ rows, selectedId, setSelectedId }) {
      return h("section", { className: "review-list" },
        rows.length ? rows.map(item => h(ReviewCard, { key: item.review_id, item, active: item.review_id === selectedId, onClick: () => setSelectedId(item.review_id) })) :
        h("div", { className: "empty-state" }, "没有符合条件的评论。")
      );
    }

    function ReviewCard({ item, active, onClick }) {
      return h("button", { className: `review-card ${active ? "active" : ""}`, onClick },
        h("div", { className: "review-head" },
          h("p", { className: "review-title" }, item.title || item.one_liner || "未命名评论"),
          h("span", { className: `pill ${item.sentiment}` }, sentimentLabel(item.sentiment))
        ),
        h("p", { className: "one-liner" }, item.one_liner || item.evidence || "暂无摘要"),
        h("div", { className: "review-meta" },
          h("span", null, platformLabel(item.platform)),
          h("span", null, `文 ${scoreText(item.writing_score)}`),
          h("span", null, `逻 ${scoreText(item.logic_score)}`),
          h("span", null, `人 ${scoreText(item.character_score)}`),
          h("span", null, `更 ${scoreText(item.update_speed_score)}`)
        )
      );
    }

    function DetailPanel({ item }) {
      if (!item) return h("aside", { className: "panel detail-panel" }, h("div", { className: "empty-state" }, "请选择一条评论。"));
      return h("aside", { className: "panel detail-panel" },
        h("div", { className: "review-meta" },
          h("span", { className: `pill ${item.sentiment}` }, sentimentLabel(item.sentiment)),
          h("span", null, platformLabel(item.platform)),
          item.source_url ? h("a", { href: item.source_url, target: "_blank", rel: "noreferrer" }, "来源链接") : null
        ),
        h("h2", { className: "detail-title" }, item.title || "评论详情"),
        h("div", { className: "score-grid" },
          h(MiniScore, { label: "文笔", value: item.writing_score }),
          h(MiniScore, { label: "逻辑", value: item.logic_score }),
          h(MiniScore, { label: "人物", value: item.character_score }),
          h(MiniScore, { label: "更新", value: item.update_speed_score }),
          h(MiniScore, { label: "毒性", value: item.toxicity_index })
        ),
        h("p", { className: "detail-copy" }, item.one_liner || ""),
        h("p", { className: "detail-copy" }, item.entry_reason || ""),
        h("div", { className: "tag-cloud" }, (item.tags || []).map(tag => h("span", { className: "tag", key: tag }, tag))),
        item.evidence ? h("p", { className: "detail-copy" }, `证据：${item.evidence}`) : null
      );
    }

    function MiniScore({ label, value }) {
      return h("div", { className: "mini-score" }, h("span", null, label), h("strong", null, scoreText(value)));
    }

    function Icon({ name }) {
      const paths = {
        copy: "M8 8h8v10H8z M5 5h8v3H8v7H5z",
        download: "M12 3v10 M8 9l4 4 4-4 M5 18h14",
        moon: "M18 14.5A7 7 0 0 1 9.5 6a7 7 0 1 0 8.5 8.5z",
        sun: "M12 6v-3 M12 21v-3 M4.6 4.6l2.1 2.1 M17.3 17.3l2.1 2.1 M3 12h3 M18 12h3 M4.6 19.4l2.1-2.1 M17.3 6.7l2.1-2.1 M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z"
      };
      return h("svg", { className: "icon", viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round", strokeLinejoin: "round", "aria-hidden": true },
        h("path", { d: paths[name] || paths.copy })
      );
    }

    if (!window.React || !window.ReactDOM) {
      document.getElementById("root").innerHTML = '<div class="runtime-warning">React 运行时没有加载成功。请联网后重新打开，或把 React UMD 文件改成本地路径。</div>';
    } else {
      h = window.React.createElement;
      ReactDOM.createRoot(document.getElementById("root")).render(h(App));
    }
  </script>
</body>
</html>
"""
