import { trendMock } from "../mock/trendMock";

export type TrendMetric = {
  id: string;
  label: string;
  value: string;
  delta?: number;
  deltaLabel?: string;
  tone: "green" | "amber" | "blue" | "rose";
};

export type HeatCurveSeries = {
  name: string;
  data: number[];
  description?: string;
};

export type HeatCurveData = {
  dates: string[];
  series: HeatCurveSeries[];
  unit?: string;
  source?: string;
  valueLabel?: string;
};

export type HotTag = {
  tag: string;
  heat: number;
  change: number;
  group?: string;
  stage?: "rising" | "stable" | "cooling" | "pending";
  relatedWorks?: string[];
};

export type PlatformCompareItem = {
  platform: string;
  heat: number;
  works: number;
  topTags: string[];
  status: "active" | "pending";
};

export type WordCloudItem = {
  name: string;
  value: number;
};

export type MigrationNode = {
  name: string;
};

export type MigrationLink = {
  source: string;
  target: string;
  value: number;
  change?: number;
  reason?: string;
};

export type GenreMigrationData = {
  nodes: MigrationNode[];
  links: MigrationLink[];
};

export type MigrationTimelineFlow = {
  id: string;
  source: string;
  target: string;
  values: number[];
  reason?: string;
};

export type GenreMigrationTimelineData = {
  periods: string[];
  flows: MigrationTimelineFlow[];
};

export type GenreCloudPeriod = {
  period: string;
  genres: WordCloudItem[];
};

export type GenreCloudTimelineData = {
  periods: string[];
  unit?: string;
  summary?: string;
  clouds: GenreCloudPeriod[];
};

export type MonthlyCoverageMonth = {
  month: string;
  label: string;
  records: number;
  uniqueWorks: number;
  tagCount: number;
  heatTotal: number;
  heatTotalK: number;
  expectedRecords: number;
  complete: boolean;
};

export type MonthlyCoverageData = {
  requiredMonths: string[];
  months: MonthlyCoverageMonth[];
  missingMonths: string[];
  incompleteMonths: string[];
  isComplete: boolean;
  note?: string;
};

export type RisingWork = {
  id: string;
  title: string;
  author?: string;
  platform: string;
  category?: string;
  tags: string[];
  detailUrl?: string;
  rank: number;
  rankChange: number;
  heatScore: number;
  listType: string;
  summary?: string;
  capturedAt?: string;
};

export type TrendDashboardData = {
  generatedAt: string;
  summary: string;
  metrics: TrendMetric[];
  heatCurve: HeatCurveData;
  hotTags: HotTag[];
  platformCompare: PlatformCompareItem[];
  wordCloud: WordCloudItem[];
  migration: GenreMigrationData;
  migrationTimeline?: GenreMigrationTimelineData;
  genreCloudTimeline?: GenreCloudTimelineData;
  dataQuality?: MonthlyCoverageData;
  risingWorks: RisingWork[];
};

export type CrawlerJobStatus = {
  id: string;
  target: "zongheng" | "all";
  mode: "docker" | "local";
  status: "queued" | "running" | "succeeded" | "failed";
  startedAt?: string;
  finishedAt?: string;
  exitCode?: number;
  message?: string;
  stdoutTail?: string;
  stderrTail?: string;
};

type ApiEnvelope<T> = {
  code: number;
  message: string;
  data: T;
  timestamp: string;
};

const API_BASE_URL = import.meta.env.VITE_TREND_API_BASE_URL ?? "";
const USE_MOCK = import.meta.env.VITE_USE_MOCK !== "false";

export function isTrendApiEnabled(): boolean {
  return !USE_MOCK && Boolean(API_BASE_URL);
}

export async function fetchTrendDashboard(): Promise<TrendDashboardData> {
  if (USE_MOCK || !API_BASE_URL) {
    return Promise.resolve(trendMock);
  }

  try {
    return await request<TrendDashboardData>("/api/trends/dashboard");
  } catch (err) {
    console.warn("Dashboard aggregate endpoint unavailable, fallback to split endpoints.", err);
  }

  const [hotTags, heatCurve, platformCompare, genreMigration, risingWorks, summary] = await Promise.all([
    request<HotTag[]>("/api/trends/hot-tags"),
    request<HeatCurveData>("/api/trends/heat-curve"),
    request<PlatformCompareItem[]>("/api/trends/platform-compare"),
    request<GenreMigrationData>("/api/trends/genre-migration"),
    request<RisingWork[]>("/api/trends/rising-works"),
    request<{ summary: string }>("/api/trends/summary")
  ]);

  return {
    generatedAt: new Date().toISOString(),
    summary: summary.summary,
    metrics: buildMetrics(hotTags, platformCompare, risingWorks, genreMigration),
    heatCurve,
    hotTags,
    platformCompare,
    wordCloud: hotTags.map((item) => ({ name: item.tag, value: item.heat })),
    migration: genreMigration,
    migrationTimeline: buildFallbackMigrationTimeline(genreMigration, heatCurve.dates),
    genreCloudTimeline: buildFallbackGenreCloudTimeline(hotTags, heatCurve.dates),
    risingWorks
  };
}

export async function startCrawlerRefresh(target: "zongheng" | "all" = "zongheng"): Promise<CrawlerJobStatus> {
  return request<CrawlerJobStatus>("/api/crawler/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ target })
  });
}

export async function fetchCrawlerJob(jobId: string): Promise<CrawlerJobStatus> {
  return request<CrawlerJobStatus>(`/api/crawler/jobs/${jobId}`);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status} ${path}`);
  }
  const payload = (await response.json()) as ApiEnvelope<T>;
  if (payload.code !== 0) {
    throw new Error(payload.message || `API error: ${path}`);
  }
  return payload.data;
}

function buildMetrics(
  hotTags: HotTag[],
  platformCompare: PlatformCompareItem[],
  risingWorks: RisingWork[],
  genreMigration: GenreMigrationData
): TrendMetric[] {
  const activePlatforms = platformCompare.filter((item) => item.status === "active").length;
  return [
    { id: "hot-tags", label: "细标签数", value: String(hotTags.length), delta: 0, tone: "green" },
    { id: "rising-works", label: "上升作品", value: String(risingWorks.length), delta: 0, tone: "amber" },
    {
      id: "platforms",
      label: "监测平台",
      value: String(activePlatforms),
      deltaLabel: `${activePlatforms} 个可用`,
      tone: "blue"
    },
    { id: "migration", label: "流派月份", value: String(genreMigration.links.length), delta: 0, tone: "rose" }
  ];
}

function buildFallbackMigrationTimeline(
  genreMigration: GenreMigrationData,
  dates: string[]
): GenreMigrationTimelineData {
  const periods = dates.length > 0 ? dates : ["当前"];
  const lastIndex = Math.max(periods.length - 1, 1);

  return {
    periods,
    flows: genreMigration.links.map((link) => {
      const changeFactor = (link.change ?? 0) / 100;
      return {
        id: `${link.source}-${link.target}`,
        source: link.source,
        target: link.target,
        reason: link.reason,
        values: periods.map((_, index) => {
          const progress = index / lastIndex;
          const base = 0.62 + progress * 0.38;
          const change = 1 + changeFactor * progress;
          return Math.max(1, Math.round(link.value * base * change));
        })
      };
    })
  };
}

function buildFallbackGenreCloudTimeline(hotTags: HotTag[], dates: string[]): GenreCloudTimelineData {
  return {
    periods: dates,
    unit: "k",
    summary: "后端暂未返回流派词云时间线，当前以前排标签生成占位视图。",
    clouds: dates.map((period, index) => ({
      period,
      genres: hotTags.slice(0, 12).map((tag) => ({
        name: tag.group && tag.group !== "细标签" ? `${tag.group}-${tag.tag}` : tag.tag,
        value: Math.max(1, Math.round(tag.heat * (0.72 + index * 0.06)))
      }))
    }))
  };
}
