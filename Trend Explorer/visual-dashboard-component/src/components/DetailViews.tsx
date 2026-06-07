import { ArrowLeft, ArrowUpRight, BarChart3, GitBranch, Layers3, ListFilter } from "lucide-react";
import type { ReactNode } from "react";
import type {
  GenreMigrationData,
  GenreMigrationTimelineData,
  GenreCloudTimelineData,
  HeatCurveData,
  HeatCurveSeries,
  HotTag,
  RisingWork,
  TrendDashboardData,
  WordCloudItem
} from "../api/trendApi";
import { GenreMigrationGraph } from "./GenreMigrationGraph";
import { GenreCloudTimeline } from "./GenreCloudTimeline";
import { HeatCurveChart } from "./HeatCurveChart";
import { MigrationTimelineChart } from "./MigrationTimelineChart";
import { RisingWorksTable } from "./RisingWorksTable";

export type DashboardDetailView = "heat" | "tags" | "wordCloud" | "migration" | "works";

type DetailShellProps = {
  title: string;
  subtitle: string;
  onBack: () => void;
  children: ReactNode;
};

export function DetailShell({ title, subtitle, onBack, children }: DetailShellProps) {
  return (
    <main className="trend-dashboard detail-dashboard">
      <header className="dashboard-header detail-header">
        <button className="ghost-button" type="button" onClick={onBack}>
          <ArrowLeft size={17} aria-hidden />
          返回总览
        </button>
        <div>
          <p className="eyebrow">Windvane Drilldown</p>
          <h1>{title}</h1>
          <p className="detail-subtitle">{subtitle}</p>
        </div>
      </header>
      {children}
    </main>
  );
}

export function HeatDetailView({ data }: { data: HeatCurveData }) {
  const stats = data.series.map((series) => buildSeriesStats(series));

  return (
    <div className="detail-stack">
      <section className="detail-panel detail-chart-panel">
        <div className="detail-section-title">
          <BarChart3 size={18} aria-hidden />
          <h2>全标签月票趋势</h2>
        </div>
        <HeatCurveChart data={data} className="detail-chart" />
      </section>

      <section className="detail-panel">
        <div className="detail-section-title">
          <ListFilter size={18} aria-hidden />
          <h2>标签月票盘点</h2>
        </div>
        <div className="insight-grid">
          {stats.map((item) => (
            <article className="insight-card" key={item.name}>
              <span>{item.name}</span>
              <strong>{item.latest}</strong>
              <small className={item.delta >= 0 ? "rank-rise" : "rank-fall"}>
                {formatSigned(item.delta)} · 峰值 {item.peak} · 均值 {item.average}
              </small>
              {item.description && <p>{item.description}</p>}
            </article>
          ))}
        </div>
      </section>

      <section className="detail-panel">
        <div className="detail-section-title">
          <Layers3 size={18} aria-hidden />
          <h2>月份矩阵</h2>
        </div>
        <div className="detail-table-wrap">
          <table className="detail-table">
            <thead>
              <tr>
                <th>标签</th>
                {data.dates.map((date) => (
                  <th key={date}>{date}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.series.map((series) => (
                <tr key={series.name}>
                  <td>{series.name}</td>
                  {series.data.map((value, index) => (
                    <td key={`${series.name}-${data.dates[index]}`}>{value}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

export function TagInventoryView({ data }: { data: TrendDashboardData }) {
  const rows = [...data.hotTags].sort((a, b) => b.heat - a.heat);

  return (
    <div className="detail-stack">
      <section className="detail-panel">
        <div className="detail-section-title">
          <ListFilter size={18} aria-hidden />
          <h2>全标签盘点</h2>
        </div>
        <div className="tag-inventory">
          {rows.map((tag) => {
            const relatedWorks = findRelatedWorks(tag, data.risingWorks);
            return (
              <article className="tag-inventory-card" key={tag.tag}>
                <div>
                  <strong>{tag.tag}</strong>
                  <span>{tag.group || "未分组"}</span>
                </div>
                <div className="tag-score">
                  <b>{tag.heat}</b>
                  <small className={tag.change >= 0 ? "rank-rise" : "rank-fall"}>{formatSigned(tag.change)}%</small>
                </div>
                <p>{stageLabels[tag.stage || inferStage(tag.change)]}</p>
                <div className="tag-line">
                  {relatedWorks.slice(0, 4).map((work) => (
                    <span key={work}>{work}</span>
                  ))}
                  {relatedWorks.length === 0 && <span>等待作品样本</span>}
                </div>
              </article>
            );
          })}
        </div>
      </section>
    </div>
  );
}

export function WordCloudDetailView({ words }: { words: WordCloudItem[] }) {
  const sorted = [...words].sort((a, b) => b.value - a.value);

  return (
    <div className="detail-stack">
      <section className="detail-panel">
        <div className="detail-section-title">
          <Layers3 size={18} aria-hidden />
          <h2>词云元素清单</h2>
        </div>
        <div className="word-list-grid">
          {sorted.map((word, index) => (
            <article className="word-list-item" key={word.name}>
              <span>{String(index + 1).padStart(2, "0")}</span>
              <strong>{word.name}</strong>
              <b>{word.value}</b>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}

export function MigrationDetailView({
  data,
  timeline,
  genreCloudTimeline
}: {
  data: GenreMigrationData;
  timeline?: GenreMigrationTimelineData;
  genreCloudTimeline?: GenreCloudTimelineData;
}) {
  return (
    <div className="detail-stack">
      {genreCloudTimeline && (
        <section className="detail-panel detail-chart-panel">
          <div className="detail-section-title">
            <GitBranch size={18} aria-hidden />
            <h2>流派月票词云</h2>
          </div>
          <GenreCloudTimeline data={genreCloudTimeline} detail />
        </section>
      )}

      {!genreCloudTimeline && timeline && (
        <section className="detail-panel detail-chart-panel">
          <div className="detail-section-title">
            <GitBranch size={18} aria-hidden />
            <h2>迁移时间轴</h2>
          </div>
          <MigrationTimelineChart data={timeline} className="detail-chart migration-timeline-detail" />
        </section>
      )}

      {!genreCloudTimeline && (
      <section className="detail-panel detail-chart-panel">
        <div className="detail-section-title">
          <GitBranch size={18} aria-hidden />
          <h2>流派迁移全图</h2>
        </div>
        <GenreMigrationGraph data={data} className="detail-chart detail-sankey" />
      </section>
      )}

      {!genreCloudTimeline && (
      <section className="detail-panel">
        <div className="detail-section-title">
          <ListFilter size={18} aria-hidden />
          <h2>迁移链路解释</h2>
        </div>
        <div className="migration-link-list">
          {data.links.map((link) => (
            <article className="migration-link-card" key={`${link.source}-${link.target}`}>
              <div>
                <strong>{link.source}</strong>
                <ArrowUpRight size={16} aria-hidden />
                <strong>{link.target}</strong>
              </div>
              <span>
                强度 {link.value}
                {typeof link.change === "number" ? ` · 变化 ${formatSigned(link.change)}%` : ""}
              </span>
              <p>{link.reason || "该链路表示读者兴趣、爽点结构或题材包装方式正在发生转移。"}</p>
            </article>
          ))}
        </div>
      </section>
      )}
    </div>
  );
}

export function WorksDetailView({ works }: { works: RisingWork[] }) {
  return (
    <div className="detail-stack">
      <section className="detail-panel">
        <div className="detail-section-title">
          <ListFilter size={18} aria-hidden />
          <h2>上升作品完整榜</h2>
        </div>
        <RisingWorksTable works={works} mode="detail" />
      </section>
    </div>
  );
}

function buildSeriesStats(series: HeatCurveSeries) {
  const latest = series.data[series.data.length - 1] ?? 0;
  const previous = series.data[series.data.length - 2] ?? latest;
  const peak = Math.max(...series.data);
  const average = Math.round(series.data.reduce((sum, value) => sum + value, 0) / Math.max(series.data.length, 1));
  return {
    name: series.name,
    latest,
    delta: latest - previous,
    peak,
    average,
    description: series.description
  };
}

function findRelatedWorks(tag: HotTag, works: RisingWork[]) {
  const fromWorks = works.filter((work) => work.tags.includes(tag.tag)).map((work) => work.title);
  return fromWorks.length > 0 ? fromWorks : tag.relatedWorks || [];
}

function inferStage(change: number): "rising" | "stable" | "cooling" {
  if (change >= 12) return "rising";
  if (change < 0) return "cooling";
  return "stable";
}

function formatSigned(value: number) {
  return `${value >= 0 ? "+" : ""}${Number.isInteger(value) ? value : value.toFixed(1)}`;
}

const stageLabels = {
  rising: "上升：近期热度增幅明显，适合进入推荐系统的趋势候选池。",
  stable: "稳定：已形成基本盘，可作为同类作品召回和榜单解释的参考。",
  cooling: "回落：讨论度下降，需要结合平台推荐位和样本量谨慎判断。",
  pending: "待补：等待人工导入或后续爬虫补齐样本。"
};
