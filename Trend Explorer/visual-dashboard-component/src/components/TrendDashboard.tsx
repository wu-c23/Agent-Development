import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";
import { Activity, BarChart3, Clock3, Maximize2, RefreshCw } from "lucide-react";
import type { HotTag, TrendDashboardData } from "../api/trendApi";
import { fetchTrendDashboard } from "../api/trendApi";
import { CrawlerControl } from "./CrawlerControl";
import {
  DetailShell,
  HeatDetailView,
  MigrationDetailView,
  TagInventoryView,
  WordCloudDetailView,
  WorksDetailView,
  type DashboardDetailView
} from "./DetailViews";
import { DynamicWordCloud } from "./DynamicWordCloud";
import { GenreCloudTimeline } from "./GenreCloudTimeline";
import { GenreMigrationGraph } from "./GenreMigrationGraph";
import { HeatCurveChart } from "./HeatCurveChart";
import { MigrationTimelineChart } from "./MigrationTimelineChart";
import { RisingWorksTable } from "./RisingWorksTable";

const metricIcons = [Activity, BarChart3, Clock3, RefreshCw];

export function TrendDashboard() {
  const [data, setData] = useState<TrendDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeView, setActiveView] = useState<DashboardDetailView | null>(null);

  const loadDashboard = useCallback(async () => {
    try {
      const payload = await fetchTrendDashboard();
      setData(payload);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "趋势数据加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  const tagRankOption = useMemo(() => (data ? buildTagRankOption(data.hotTags.slice(0, 10)) : null), [data]);

  if (loading) {
    return <div className="dashboard-state">趋势数据加载中...</div>;
  }

  if (error || !data) {
    return <div className="dashboard-state">{error || "暂无趋势数据"}</div>;
  }

  if (activeView) {
    return renderDetailView(activeView, data, () => setActiveView(null));
  }

  return (
    <main className="trend-dashboard">
      <header className="dashboard-header">
        <div>
          <p className="eyebrow">Novel Trend Windvane</p>
          <h1>全网风向标</h1>
        </div>
        <div className="header-actions">
          <CrawlerControl onRefresh={loadDashboard} />
          <div className="time-chip">
            <Clock3 size={16} aria-hidden />
            <span>{formatGeneratedAt(data.generatedAt)}</span>
          </div>
        </div>
      </header>

      <section className="metric-grid" aria-label="核心指标">
        {data.metrics.map((metric, index) => {
          const Icon = metricIcons[index % metricIcons.length];
          return (
            <article className={`metric-card tone-${metric.tone}`} key={metric.id}>
              <div className="metric-icon">
                <Icon size={19} aria-hidden />
              </div>
              <span>{metric.label}</span>
              <strong>{metric.value}</strong>
              <small>
                {typeof metric.delta === "number"
                  ? `${metric.delta >= 0 ? "+" : ""}${metric.delta}%`
                  : metric.deltaLabel || "平稳"}
              </small>
            </article>
          );
        })}
      </section>

      <section className="summary-band">
        <span>趋势摘要</span>
        <p>{data.summary}</p>
      </section>

      {data.dataQuality && <MonthlyCoverageStrip data={data.dataQuality} />}

      <section className="dashboard-grid">
        <Panel title="全标签月票趋势" className="panel-wide" actionLabel="展开曲线" onAction={() => setActiveView("heat")}>
          <HeatCurveChart data={data.heatCurve} />
        </Panel>

        <Panel title="热门标签排行" actionLabel="标签盘点" onAction={() => setActiveView("tags")}>
          {tagRankOption && <ReactECharts option={tagRankOption} className="chart-fill" notMerge lazyUpdate />}
        </Panel>

        <Panel title="动态词云" actionLabel="词云清单" onAction={() => setActiveView("wordCloud")}>
          <DynamicWordCloud words={data.wordCloud} />
        </Panel>

        <Panel title="流派迁移词云" className="panel-wide" actionLabel="展开流派" onAction={() => setActiveView("migration")}>
          {data.genreCloudTimeline ? (
            <GenreCloudTimeline data={data.genreCloudTimeline} />
          ) : data.migrationTimeline ? (
            <MigrationTimelineChart data={data.migrationTimeline} />
          ) : (
            <GenreMigrationGraph data={data.migration} />
          )}
        </Panel>

        <Panel title="作品上升榜" className="panel-tall" actionLabel="完整榜单" onAction={() => setActiveView("works")}>
          <RisingWorksTable works={data.risingWorks.slice(0, 6)} />
        </Panel>
      </section>
    </main>
  );
}

function MonthlyCoverageStrip({ data }: { data: NonNullable<TrendDashboardData["dataQuality"]> }) {
  return (
    <section className="coverage-strip" aria-label="历史月票榜覆盖情况">
      {data.months.map((month) => (
        <article className={`coverage-pill ${month.complete ? "complete" : "incomplete"}`} key={month.month}>
          <span>{month.label}</span>
          <strong>
            {month.records}/{month.expectedRecords}
          </strong>
          <small>{month.tagCount} 个细标签 · {month.heatTotalK}k 月票</small>
        </article>
      ))}
    </section>
  );
}

function renderDetailView(view: DashboardDetailView, data: TrendDashboardData, onBack: () => void) {
  const detailMeta = {
    heat: {
      title: "全标签月票趋势",
      subtitle: "只使用历史月票榜，按作品月票数累加到该作品的所有标签。"
    },
    tags: {
      title: "全标签盘点",
      subtitle: "汇总榜单粗分类与详情页细标签，识别上升、稳定和回落元素。"
    },
    wordCloud: {
      title: "词云元素清单",
      subtitle: "将大屏词云拆解为可排序的元素清单，方便后续接入推荐召回。"
    },
    migration: {
      title: "流派迁移词云",
      subtitle: "只使用历史月票榜数据，按月份对比各流派月票热度词云。"
    },
    works: {
      title: "上升作品明细",
      subtitle: "展示作品排名、热度、详情页细标签和公开详情链接。"
    }
  }[view];

  return (
    <DetailShell title={detailMeta.title} subtitle={detailMeta.subtitle} onBack={onBack}>
      {view === "heat" && <HeatDetailView data={data.heatCurve} />}
      {view === "tags" && <TagInventoryView data={data} />}
      {view === "wordCloud" && <WordCloudDetailView words={data.wordCloud} />}
      {view === "migration" && (
        <MigrationDetailView
          data={data.migration}
          timeline={data.migrationTimeline}
          genreCloudTimeline={data.genreCloudTimeline}
        />
      )}
      {view === "works" && <WorksDetailView works={data.risingWorks} />}
    </DetailShell>
  );
}

function Panel({
  title,
  className = "",
  actionLabel,
  onAction,
  children
}: {
  title: string;
  className?: string;
  actionLabel?: string;
  onAction?: () => void;
  children: ReactNode;
}) {
  return (
    <section className={`dashboard-panel ${className}`}>
      <div className="panel-title">
        <h2>{title}</h2>
        {actionLabel && onAction && (
          <button className="panel-action" type="button" onClick={onAction}>
            <Maximize2 size={14} aria-hidden />
            {actionLabel}
          </button>
        )}
      </div>
      <div className="panel-body">{children}</div>
    </section>
  );
}

function buildTagRankOption(tags: HotTag[]): EChartsOption {
  return {
    color: ["#f2b84b"],
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      backgroundColor: "#ffffff",
      borderColor: "#d8e0ea",
      textStyle: { color: "#111827" }
    },
    grid: {
      top: 12,
      left: 20,
      right: 36,
      bottom: 12,
      containLabel: true
    },
    xAxis: {
      type: "value",
      max: 100,
      splitLine: { lineStyle: { color: "rgba(100, 116, 139, 0.14)" } },
      axisLabel: { color: "#64748b" }
    },
    yAxis: {
      type: "category",
      inverse: true,
      data: tags.map((item) => item.tag),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: "#334155" }
    },
    series: [
      {
        type: "bar",
        data: tags.map((item) => item.heat),
        barMaxWidth: 16,
        itemStyle: {
          borderRadius: [0, 4, 4, 0],
          color: (params) => {
            const item = tags[params.dataIndex];
            if (item.change > 15) return "#24c08b";
            if (item.change < 0) return "#ff6b86";
            return "#f2b84b";
          }
        },
        label: {
          show: true,
          position: "right",
          color: "#334155",
          formatter: (params) => String(params.value)
        }
      }
    ]
  };
}

function formatGeneratedAt(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  }).format(date);
}
