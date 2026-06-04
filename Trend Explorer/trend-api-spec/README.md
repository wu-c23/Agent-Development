# trend-api-spec

本目录提供"全网风向标"的 FastAPI 服务，连接爬虫 JSONL 数据和 React 趋势大屏，同时提供符合 Data Contract v1.0 的跨模块通信端点。

## 能力

- 读取 `crawler-engine-v1.0/data/*.jsonl`，聚合为前端大屏数据。
- 提供 `/api/trends/dashboard` 和拆分趋势接口。
- `heatCurve` 只统计历史月票榜，并按作品月票数累加到每个细标签，单位为 `k`。
- `genreCloudTimeline` 按月份生成流派词云，用于观察流派热度重心迁移。
- `/api/debug/monthly-coverage` 可检查 `20261` 到 `20265` 是否都采集到，以及每个月是否达到 200 条。
- 提供 `/api/crawler/run`，允许前端按钮触发预定义爬虫任务。
- 只执行固定目标：`zongheng` 或 `all`，不会接收任意 shell 命令。
- 默认只读取最新 JSONL 文件，避免早期试采或旧的不完整文件污染展示；如果确认历史文件都干净，可设置 `TREND_READ_MODE=all`。
- **Data Contract v1.0 端点**: `GET /api/v1/trend/hot`, `GET /api/v1/trend/detail/{uid}`, `GET /api/v1/trend/tags/evolution` 用于与 Router Agent 对接。

## Windows 启动 (真实 API)

```powershell
cd trend-api-spec
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

$env:TREND_DATA_DIR = "..\crawler-engine-v1.0\data"
$env:CRAWLER_DIR = "..\crawler-engine-v1.0"
$env:ALLOW_CRAWLER_RUN = "true"

uvicorn fastapi_demo:app --host 127.0.0.1 --port 8001 --reload
```

## Mock 模式

```powershell
uvicorn mock_server:app --host 127.0.0.1 --port 8001
```

Mock API 提供 5 本预置小说，响应头含 `X-Mock: true`。

## Data Contract 端点 (跨模块通信)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/trend/hot?limit=20` | 热门趋势榜单 |
| GET | `/api/v1/trend/detail/{uid}` | 单书趋势详情 |
| GET | `/api/v1/trend/tags/evolution?tag={tag}&period=30d` | 标签演变数据 |
| GET | `/api/v1/trend/health` | 健康检查 |

所有 Data Contract 响应符合 TrendData JSON Schema，使用 64 位 SHA256 UID。

## 前端配置

前端 `.env.local`：

```env
VITE_USE_MOCK=false
VITE_TREND_API_BASE_URL=http://127.0.0.1:8001
```

然后在前端页面点击"采集更新"即可触发纵横榜单采集，采集完成后会自动刷新大屏。

检查月票榜覆盖情况：

```powershell
curl http://127.0.0.1:8001/api/debug/monthly-coverage
```

## 安全边界

- API 建议只绑定 `127.0.0.1`，不要暴露到校园网或公网。
- 采集任务只访问公开榜单页面/API，不绕过登录、验证码或付费墙。
- 起点目前仍暂缓自动采集，默认 `ENABLE_QIDIAN=false`。
