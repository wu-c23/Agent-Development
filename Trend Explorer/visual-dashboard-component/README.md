# visual-dashboard-component

“全网风向标”趋势大屏前端模块，使用 React + TypeScript + Vite + ECharts 展示网络小说市场的热度曲线、热门标签、动态词云、流派迁移和上升作品。

## 当前能力

- 总览驾驶舱：核心指标、趋势摘要、月票标签趋势、热门标签、词云、流派月票词云、上升作品榜。
- 明细下钻页：每个核心面板都提供展开入口。
- 标签盘点：展示详情页补全后的细标签、分组、热度、变化、趋势状态和代表作品。
- 热度明细：只使用历史月票榜，按作品月票数统计标签趋势、走势卡片和月份矩阵。
- 流派迁移明细：舍弃迁移图，改用逐月流派词云对比，观察流派热度重心变化。
- 作品明细：展示排名、热度、细标签、简介和公开详情页链接。
- 页面采集控制：连接本地 FastAPI 后，可在大屏右上角点击“采集更新”触发纵横榜单采集。

## 文件结构

```text
visual-dashboard-component/
├── package.json
├── tsconfig.json
├── vite.config.ts
├── index.html
└── src/
    ├── App.tsx
    ├── main.tsx
    ├── styles.css
    ├── api/
    │   └── trendApi.ts
    ├── mock/
    │   └── trendMock.ts
    └── components/
        ├── TrendDashboard.tsx
        ├── DetailViews.tsx
        ├── HeatCurveChart.tsx
        ├── DynamicWordCloud.tsx
        ├── PlatformCompareChart.tsx       # 预留组件，当前大屏不展示
        ├── GenreCloudTimeline.tsx
        ├── GenreMigrationGraph.tsx
        ├── MigrationTimelineChart.tsx
        └── RisingWorksTable.tsx
```

## 启动

```bash
cd /mnt/c/Users/86136/Documents/Codex/2026-05-27/goal-ai-python-scrapy-scrapy-cluster/novel-trend-windvane/visual-dashboard-component
npm install
npm run dev
```

默认使用 Mock 数据。浏览器打开 Vite 输出的地址，一般是：

```text
http://localhost:5173
```

## 接入真实 API

后续接入 FastAPI 时设置环境变量：

```env
VITE_USE_MOCK=false
VITE_TREND_API_BASE_URL=http://localhost:8000
```

本项目已提供本地 API 示例，先启动 `trend-api-spec/fastapi_demo.py`，再启动前端。前端会优先读取 `/api/trends/dashboard` 聚合数据，并通过 `/api/crawler/run` 触发采集任务。

API 调用位于 `src/api/trendApi.ts`，已按接口文档拆分调用：

- `/api/trends/hot-tags`
- `/api/trends/heat-curve`
- `/api/trends/platform-compare`
- `/api/trends/genre-migration`
- `/api/trends/rising-works`
- `/api/trends/summary`

纵横爬虫补全详情页标签后，`risingWorks[].tags` 可以包含多枚细标签，例如 `热血`、`剑道`、`少年`、`传统玄幻`、`家族崛起`。作品上升榜会展示细标签，并通过 `detailUrl` 链接到公开详情页。

全标签热度趋势只使用历史月票榜。一本作品如果同时拥有 `玄幻奇幻` 和 `系统流` 两个标签，并在某月获得 `100000` 月票，则这两个标签在该月都贡献 `100k` 热度。

流派趋势支持字段 `genreCloudTimeline`：

```ts
{
  periods: ["01月", "02月", "03月"],
  unit: "k",
  clouds: [
    {
      period: "01月",
      genres: [
        { name: "传统玄幻", value: 128 },
        { name: "系统流", value: 49 }
      ]
    }
  ]
}
```

旧版迁移时间轴字段 `migrationTimeline` 仍可作为兼容字段：

```ts
{
  periods: ["01月", "02月", "03月", "04月", "05月"],
  flows: [
    {
      id: "solo-to-clan",
      source: "单主角爽文",
      target: "家族崛起群像",
      values: [6, 9, 14, 19, 22],
      reason: "爽点从主角个人抬升扩展到家族、血脉和势力共同成长。"
    }
  ]
}
```

如果真实 API 暂时不返回 `migrationTimeline`，前端会根据 `genreMigration` 和热度日期生成一个保守的时间轴占位。

起点数据暂缺时，当前大屏不展示平台对比板块，核心指标中的来源平台数只统计已自动采集的平台。后续如恢复起点数据，可重新接入 `PlatformCompareChart.tsx` 和 `/api/trends/platform-compare`。
