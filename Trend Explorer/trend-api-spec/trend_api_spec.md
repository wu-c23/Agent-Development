# 全网风向标趋势 API 文档

本文档定义“全网风向标”模块对外输出的趋势数据接口，用于连接：

- `crawler-engine-v1.0`：采集公开榜单和作品详情细标签。
- `trend-analysis-prompt-v1.2`：生成趋势摘要、标签归因和流派演变分析。
- `visual-dashboard-component`：展示趋势大屏。
- 推荐系统后续链路：将热门标签、上升作品、来源平台和流派变化作为召回与排序特征。

## 统一响应结构

所有接口都返回统一 envelope：

```json
{
  "code": 0,
  "message": "success",
  "data": {},
  "timestamp": "2026-05-30T12:00:00Z"
}
```

字段说明：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `code` | number | `0` 表示成功，非 `0` 预留给业务错误。 |
| `message` | string | 人类可读消息，成功时为 `success`。 |
| `data` | object/array | 接口业务数据。 |
| `timestamp` | string | API 返回时间，ISO 8601 格式。 |

## 统一趋势数据结构

爬虫和 API 内部统一使用 `TrendItem`：

```ts
type TrendItem = {
  id: string;
  title: string;
  author?: string;
  platform: string;
  rank: number;
  rankChange?: number;
  category?: string;
  tags: string[];
  heatScore: number;
  listType: string;
  summary?: string;
  capturedAt: string;
  sourceUrl?: string;
  detailUrl?: string;
};
```

重要约定：

- `heatScore` 对月票榜表示对应月份榜单返回的月票数。
- 月票趋势只使用 `listType/sourceUrl` 中包含月份的历史月票榜记录。
- 作品详情页只用于补充细标签，不用于获取月票数、点击数等榜单热度。
- 一本作品如果有多个标签，该作品在某月的月票数会完整贡献给每一个标签。
- 前端展示热度曲线时使用 `k` 作为单位，例如 `100000` 月票显示为 `100k`。

## 接口列表

### GET `/api/trends/hot-tags`

返回热门标签排行。

用途：

- 发现热门题材和作品元素。
- 给推荐系统提供标签热度特征。
- 支持前端“热门标签排行”和“动态词云”。

响应 `data`：

```json
[
  {
    "tag": "热血",
    "heat": 96,
    "change": 18.6,
    "group": "情绪价值",
    "stage": "rising",
    "relatedWorks": ["齐天", "无敌天命"]
  }
]
```

### GET `/api/trends/heat-curve`

返回全标签月票热度趋势。

计算规则：

- 只统计历史月票榜：`20261`、`20262`、`20263`、`20264`、`20265`。
- 月票数从对应月份榜单接口读取。
- 详情页只补标签。
- 一个作品有多个标签时，对每个标签都贡献完整月票值。

响应 `data`：

```json
{
  "dates": ["01月", "02月", "03月", "04月", "05月"],
  "unit": "k",
  "source": "monthly-ticket",
  "valueLabel": "月票",
  "series": [
    {
      "name": "热血",
      "data": [124.3, 118.6, 132.1, 146.8, 153.2],
      "description": "热血 仅按历史月票榜统计，作品月票会同时贡献给该作品的所有细标签。"
    }
  ]
}
```

### GET `/api/trends/platform-compare`

返回已接入来源平台的数据概览。

当前阶段：

- 纵横中文网为自动采集。
- 起点中文网暂缓自动采集，当前不在前端大屏展示，也不注入 pending 数据。

响应 `data`：

```json
[
  {
    "platform": "纵横中文网",
    "heat": 100,
    "works": 576,
    "topTags": ["玄幻奇幻", "热血", "剑道"],
    "status": "active"
  }
]
```

### GET `/api/trends/genre-migration`

返回兼容旧版大屏的流派迁移关系图。

说明：

- 该接口保留为关系图兼容接口。
- 新版趋势大屏优先使用 `/api/trends/genre-cloud-timeline` 绘制逐月流派词云。

响应 `data`：

```json
{
  "nodes": [{ "name": "传统升级流" }, { "name": "家族群像流" }],
  "links": [
    {
      "source": "传统升级流",
      "target": "家族群像流",
      "value": 18,
      "change": 26.4,
      "reason": "同样强调成长路径，但近期更偏向家族势力、群像并肩和背景压迫感。"
    }
  ]
}
```

### GET `/api/trends/rising-works`

返回上升作品榜。

用途：

- 识别上升最快作品。
- 给推荐系统提供候选作品池。
- 展示作品标签、榜单、热度和详情页链接。

响应 `data`：

```json
[
  {
    "id": "work-1435440",
    "title": "齐天",
    "author": "日落红尘",
    "platform": "纵横中文网",
    "category": "玄幻奇幻",
    "tags": ["玄幻奇幻", "热血", "剑道", "少年", "传统玄幻", "家族崛起"],
    "detailUrl": "https://www.zongheng.com/detail/1435440",
    "rank": 2,
    "rankChange": 8,
    "heatScore": 16458,
    "listType": "月票榜-2026年04月",
    "summary": "传统玄幻、家族崛起和群像爽点明显。",
    "capturedAt": "2026-05-30T12:00:00Z"
  }
]
```

### GET `/api/trends/summary`

返回趋势摘要。

响应 `data`：

```json
{
  "summary": "本次共聚合公开榜单记录，其中历史月票榜记录完整覆盖 1-5 月。高热标签集中在热血、玄幻奇幻、剑道、家族崛起。"
}
```

## 扩展接口

### GET `/api/trends/dashboard`

返回前端大屏一次渲染所需的聚合数据，包括：

- `metrics`
- `summary`
- `heatCurve`
- `hotTags`
- `platformCompare`
- `wordCloud`
- `genreCloudTimeline`
- `risingWorks`
- `dataQuality`

### GET `/api/trends/genre-cloud-timeline`

返回逐月流派词云。

该接口用于替代传统静态流派迁移图，更适合展示“1 月到 5 月哪些流派升温、哪些流派降温”。

### GET `/api/debug/monthly-coverage`

检查历史月票榜覆盖情况。

建议每次采集后执行：

```bash
curl http://127.0.0.1:8000/api/debug/monthly-coverage
```

理想结果：

- `20261` 到 `20265` 都存在。
- 每个月 `records` 都为 `200`。
- `isComplete` 为 `true`。

## FastAPI Demo 启动

WSL 中启动：

```bash
cd /mnt/c/Users/86136/Documents/Codex/2026-05-27/goal-ai-python-scrapy-scrapy-cluster/novel-trend-windvane/trend-api-spec
source .venv/bin/activate

export TREND_DATA_DIR=../crawler-engine-v1.0/data
export CRAWLER_DIR=../crawler-engine-v1.0
export ALLOW_CRAWLER_RUN=true

uvicorn fastapi_demo:app --host 127.0.0.1 --port 8000 --reload
```

## 合规与安全

- API 默认建议只绑定 `127.0.0.1`。
- 不暴露 Redis、FastAPI 或前端开发服务器到公网或校园网。
- 爬虫只读取公开榜单和公开详情页标签。
- 不绕过登录、验证码、付费墙或访问限制。
- 所有 LLM、数据库、消息队列接入均使用环境变量配置。
