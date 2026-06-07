# 交付运行指南 (Windows)

本文档面向拿到项目压缩包后在 Windows 环境下的执行者。

## 1. 前置环境

需要准备：

- Windows 10/11
- Docker Desktop (可选，用于容器化采集)
- Python 3.10+ (含 pip)
- PowerShell 5.1+

建议只在本机访问服务，FastAPI 使用 `127.0.0.1:8001`。

## 2. 解压或复制项目

将项目目录放到工作路径下，例如：

```powershell
cd D:\projects\novel-trend-windvane
```

## 3. 采集纵横榜单数据

### Docker 方式 (推荐)

确保 Docker Desktop 已启动：

```powershell
cd crawler-engine-v1.0
docker compose --profile manual run --build --rm crawler-zongheng
```

### 本地 Python 方式

```powershell
cd crawler-engine-v1.0
pip install -r requirements.txt
```

安装 Playwright 浏览器 (如需动态渲染)：

```powershell
playwright install chromium
```

运行采集：

```powershell
# 仅纵横
scrapy crawl zongheng_trends

# 全平台 (起点默认关闭)
powershell -ExecutionPolicy Bypass -File scripts\run_all_once.ps1

# 启用起点采集
$env:ENABLE_QIDIAN = "true"
powershell -ExecutionPolicy Bypass -File scripts\run_all_once.ps1
```

采集结果写入：

```text
crawler-engine-v1.0\data\trend_items_zongheng_trends_YYYYMMDDTHHMMSSZ.jsonl
```

当前自动采集范围：

- 纵横 2026 年 1-5 月月票榜，每月 10 页共 200 条
- 纵横畅销榜
- 纵横推荐榜
- 纵横点击榜
- 详情页细标签补全

起点暂不自动采集，也不会在前端平台对比中展示。

## 4. 启动 FastAPI

新 PowerShell 终端中执行：

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

## 5. Mock 模式 (无需采集数据)

```powershell
cd trend-api-spec
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

uvicorn mock_server:app --host 127.0.0.1 --port 8001
```

Mock API 提供 5 本预置小说的趋势数据，响应头含 `X-Mock: true`。

### Mock API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/trend/hot?limit=20` | 热门趋势榜单 |
| GET | `/api/v1/trend/detail/{uid}` | 单书趋势详情 |
| GET | `/api/v1/trend/tags/evolution?tag=克苏鲁&period=30d` | 标签演变数据 |
| GET | `/api/v1/trend/health` | 健康检查 |

检查数据：

```powershell
curl http://127.0.0.1:8001/api/v1/trend/hot?limit=5
curl http://127.0.0.1:8001/api/v1/trend/detail/987a2b45c6bd2baa73d750f13daf15b63c20145de2e85fff22ada96ad3d8b27b
curl "http://127.0.0.1:8001/api/v1/trend/tags/evolution?tag=克苏鲁&period=30d"
```

检查月票榜覆盖情况 (仅真实 API)：

```powershell
curl http://127.0.0.1:8001/api/debug/monthly-coverage
```

理想状态：

- `20261` 到 `20265` 都存在
- 每个月 `records` 为 `200`
- `isComplete` 为 `true`

## 6. 生成统一大屏

统一大屏使用纯 Python 生成自包含 HTML 文件 (CDN 加载 ECharts，无需 Node.js)，集成三个模块功能:

```powershell
cd trend-api-spec

# 使用 Mock 数据生成 (默认)
python unified_dashboard.py

# 或连接真实 API 生成
python unified_dashboard.py --api http://127.0.0.1:8001
```

浏览器打开生成的 HTML 文件：

```text
trend-api-spec\unified_dashboard.html
```

统一大屏包含三个 Tab：
- **📊 趋势大屏**: KPI 指标卡、热度曲线、热词柱状图、词云、平台对比、流派迁移桑基图、迁移时间线、上升作品排行表（小说名可点击跳转评论）
- **📝 小说评论**: 综合评分、优缺点、评论统计（调用 Sentiment Critic 端口 8003，无数据时显示"暂无评论数据"）
- **🤖 AI 推荐**: 自然语言输入阅读偏好，AI 推荐小说（调用 Safe-Search 端口 8002，支持 DeepSeek API 和 Mock 两种模式）

支持明暗主题切换，跨 Tab 联动（排行榜/推荐结果点击小说名 → 自动切换评论 Tab）。

> 如需使用原独立版本的 dashboard，请参考 `dashboard.py`（仅趋势大屏）或 `visual-dashboard-component/` 目录（旧 React 版本）。

## 7. Data Contract 端点 (跨模块通信)

符合苗文昊 (System Integrator) Data Contract v1.0 规范的端点，用于与 Router Agent 对接：

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/trend/hot?limit=20` | 热门趋势榜单 (TrendData[]) |
| GET | `/api/v1/trend/detail/{uid}` | 单书趋势详情 (TrendData) |
| GET | `/api/v1/trend/tags/evolution?tag={tag}&period=30d` | 标签演变数据 |

所有 Data Contract 响应使用 64 位 SHA256 UID (格式: `SHA256(platform_id|novel_title)`)，无效 UID 返回 404。

## 8. 打包转交项目

如果需要把项目交给其他执行者，可在项目上级目录执行 PowerShell：

```powershell
Compress-Archive -Path novel-trend-windvane\* -DestinationPath novel-trend-windvane.zip -Force
```

注意排除以下目录以减小体积：
- `trend-api-spec\.venv`
- `crawler-engine-v1.0\.venv`
- `crawler-engine-v1.0\.scrapy`

如果希望对方打开后直接看到当前采集结果，保留 `crawler-engine-v1.0\data\*.jsonl`。

如果希望对方重新采集，删除 `crawler-engine-v1.0\data\*.jsonl` 后再打包。

## 9. 常见问题

**Q: Docker 命令不可用**
确保 Docker Desktop 已安装并启动。也可使用本地 Python 方式运行采集。

**Q: 前端能打开但没有真实数据**
先检查 API 是否正常：

```powershell
curl http://127.0.0.1:8001/api/health
curl http://127.0.0.1:8001/api/debug/monthly-coverage
```

**Q: 月票趋势没有变化**
优先确认最新 JSONL 是否来自修正后的爬虫。新版爬虫会把历史月份传为纵横接口的 `rankNo=20261..20265`，月票数只来自对应月份榜单接口。

**Q: Playwright 报错**
确保已安装 Playwright 浏览器：

```powershell
playwright install chromium
```
