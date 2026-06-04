# crawler-engine-v1.0

`crawler-engine-v1.0` 是“全网风向标”的公开数据采集层，用于从网络小说平台公开榜单中采集趋势信号，并输出统一 JSONL 数据。当前阶段实现起点中文网、纵横中文网两个 Spider；本次不采集番茄小说、七猫小说和晋江文学城。

## 已包含内容

```text
crawler-engine-v1.0/
├── scrapy.cfg
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── README.md
└── novel_crawler/
    ├── __init__.py
    ├── items.py
    ├── pipelines.py
    ├── settings.py
    ├── middlewares.py
    ├── playwright_middleware.py
    ├── selectors.py
    └── spiders/
        ├── __init__.py
        ├── base_platform_spider.py
        ├── qidian_spider.py
        └── zongheng_spider.py
```

## 统一输出结构

每条采集结果会被 Pipeline 标准化为以下字段：

```json
{
  "uid": "sha256-generated-uid",
  "id": "sha1-generated-id",
  "title": "作品标题",
  "author": "作者",
  "platform": "起点中文网",
  "rank": 1,
  "rankChange": 0,
  "category": "玄幻",
  "tags": ["系统流", "升级"],
  "heatScore": 998.0,
  "listType": "月票榜",
  "summary": "作品简介",
  "capturedAt": "2026-05-27T12:00:00Z",
  "sourceUrl": "https://www.qidian.com/rank/yuepiao/",
  "detailUrl": "https://www.zongheng.com/detail/1435440"
}
```

`uid` 为跨模块统一标识符 (SHA256)，`id`、`capturedAt`、`rankChange`、`tags`、`heatScore` 会在 Pipeline 中补齐或归一化，便于后续 API 和趋势大屏复用。

## 本地运行

建议使用 Python 3.11。

```bash
cd novel-trend-windvane/crawler-engine-v1.0
python -m venv .venv
. .venv/Scripts/activate
pip install -r requirements.txt
playwright install chromium

scrapy list
scrapy crawl qidian_trends
scrapy crawl zongheng_trends
```

Windows PowerShell 可使用：

```powershell
$env:PLAYWRIGHT_ENABLED = "true"
scrapy crawl qidian_trends
```

采集结果默认写入带 UTC 时间戳的新 JSONL 文件，避免同一天多次采集互相污染。

当前默认会按 Spider 拆分输出文件，避免旧数据混在一起：

```text
data/trend_items_qidian_trends_YYYYMMDDTHHMMSSZ.jsonl
data/trend_items_zongheng_trends_YYYYMMDDTHHMMSSZ.jsonl
```

如果某次运行没有抓到作品卡片，爬虫会自动把实际拿到的 HTML 保存到 `data/debug_html/`，用于判断是页面结构变了、动态渲染失败，还是目标站点返回了提示页。

## 分页采集

爬虫会在每个榜单页解析完成后，自动寻找公开页面中的“下一页”链接并继续抓取后续页面。分页逻辑在 `BasePlatformSpider` 中统一实现，起点和纵横都会复用。

为避免页面结构异常导致无限翻页，默认最多采集每个榜单 `50` 页：

```env
MAX_PAGES_PER_LIST=10
DEFAULT_PAGE_SIZE=20
```

- `MAX_PAGES_PER_LIST`：每个榜单最多跟进多少页。纵横榜单当前按 10 页采集，目标是每个榜单 10 页 * 20 本 = 200 本。
- `DEFAULT_PAGE_SIZE`：当页面没有提供明确排名时，用于估算跨页排名的默认页大小。

纵横 API 分页默认固定请求 10 页；详情页只用于补充细标签，排名和月票、点击量等热度值均来自榜单接口，避免不同月份榜单数据被详情页覆盖。

Docker 临时覆盖示例：

```bash
docker compose run --rm -e MAX_PAGES_PER_LIST=100 crawler
```

## 当前真实榜单 URL

默认配置采集以下公开榜单：

| 平台 | 榜单 | URL |
| --- | --- | --- |
| 起点中文网 | 月票榜 | `https://www.qidian.com/rank/yuepiao/` |
| 起点中文网 | 畅销榜 | `https://www.qidian.com/rank/hotsales/` |
| 起点中文网 | 推荐榜 | `https://www.qidian.com/rank/recom/` |
| 起点中文网 | 阅读指数榜 | `https://www.qidian.com/rank/readindex/` |
| 纵横中文网 | 2026年1月月票榜 | `https://www.zongheng.com/rank?nav=monthly-ticket&rankType=1&month=20261` |
| 纵横中文网 | 2026年2月月票榜 | `https://www.zongheng.com/rank?nav=monthly-ticket&rankType=1&month=20262` |
| 纵横中文网 | 2026年3月月票榜 | `https://www.zongheng.com/rank?nav=monthly-ticket&rankType=1&month=20263` |
| 纵横中文网 | 2026年4月月票榜 | `https://www.zongheng.com/rank?nav=monthly-ticket&rankType=1&month=20264` |
| 纵横中文网 | 2026年5月月票榜 | `https://www.zongheng.com/rank?nav=monthly-ticket&rankType=1&month=20265` |
| 纵横中文网 | 畅销榜 | `https://www.zongheng.com/rank?nav=one-day&rankType=3` |
| 纵横中文网 | 推荐榜 | `https://www.zongheng.com/rank?nav=recommend&rankType=6` |
| 纵横中文网 | 点击榜 | `https://www.zongheng.com/rank?nav=click&rankType=5` |

起点默认建议启用 Playwright。若公开页面变更结构，只需要调整 `novel_crawler/selectors.py`。

## Docker Compose

默认只启动起点示例爬虫，不启动 Redis：

```bash
cd novel-trend-windvane/crawler-engine-v1.0
docker compose up --build
```

运行所有平台一次：

```bash
docker compose --profile manual run --rm crawler-all-once
```

运行纵横单个平台：

```bash
docker compose --profile manual run --rm crawler-zongheng
```

按 72 小时间隔长期运行：

```bash
docker compose --profile schedule up --build crawler-scheduled
```

`redis` 仅用于后续 Scrapy Cluster 或 `scrapy-redis` 调度扩展。默认不启动 Redis，也不启用 Redis Scheduler，避免在校园网或公网环境中暴露不必要服务。

### Redis 安全配置

Redis 只用于容器内部调度预留，不需要暴露到宿主机或校园网。当前 Compose 已做以下加固：

- Redis 服务放入 `queue` profile，默认 `docker compose up` 不会启动 Redis。
- 不再配置 `ports: "6379:6379"`，外部主机不能直接访问 Redis。
- 仅通过 Docker 内部网络让 crawler 使用 `redis:6379`。
- 使用 `requirepass` 设置 Redis 密码。
- Redis 配置文件位于 `redis/redis.conf`，启用 `protected-mode yes`。
- Redis 服务以 `redis` 用户运行，并启用 `no-new-privileges`。

建议创建本地 `.env` 文件并设置强密码，不要提交 `.env`：

```env
REDIS_PASSWORD=replace-with-a-strong-local-password
```

整改后重启：

```bash
docker compose down
docker compose up --build
```

仅当确实需要队列调度时，才启动 Redis：

```bash
docker compose --profile queue up -d redis
```

验证宿主机不再监听 `6379`：

```bash
docker ps --format "table {{.Names}}\t{{.Ports}}"
```

正常情况下，`novel-trend-redis` 不应显示 `0.0.0.0:6379->6379/tcp` 或 `:::6379->6379/tcp`。

### Docker 构建网络问题

如果构建时卡在 `apt-get install`、`pip install` 或 `playwright install`，通常是 Docker Desktop 代理或外部源访问不稳定。Dockerfile 已提供默认国内镜像源：

- `PYTHON_BASE_IMAGE=python:3.11-slim-bookworm`
- `APT_MIRROR=http://mirrors.aliyun.com/debian`
- `PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple`
- `PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright`

这里显式使用 `bookworm`，避免浮动的 `python:3.11-slim` 解析到 Debian `trixie` 后触发 Playwright 依赖包不兼容问题。

重新构建可使用：

```bash
docker compose build --no-cache --pull crawler
docker compose up
```

如需切回官方源，可手动构建：

```bash
docker build \
  --build-arg PYTHON_BASE_IMAGE=python:3.11-slim-bookworm \
  --build-arg APT_MIRROR=http://deb.debian.org/debian \
  --build-arg PIP_INDEX_URL=https://pypi.org/simple \
  --build-arg PLAYWRIGHT_DOWNLOAD_HOST=https://playwright.azureedge.net \
  -t novel-trend-crawler .
```

如果使用 Shadowrocket、Clash 或 v2rayN：

- 只开虚拟网卡时，Docker Desktop 可能可以直接走系统网络，但不一定拥有 HTTP/HTTPS 代理。
- 如果 Docker Desktop 的 `Settings > Resources > Proxies` 配了 `127.0.0.1:xxxx`，必须确认该端口确实是代理软件正在监听的 HTTP/Mixed 代理端口。
- 如果没有显式 HTTP 代理端口，建议先关闭 Docker Desktop 里的手动代理，再用上面的国内镜像源构建。

如果运行时出现 `cannot import name '_setAcceptableProtocols'`，说明环境安装了过新的 Twisted。当前 `requirements.txt` 已固定 `Twisted==23.10.0`，请使用 `--no-cache` 重新构建镜像，避免复用旧依赖层。

## 反爬与限速策略

当前实现只处理公开页面，并保持保守访问策略：

- `ROBOTSTXT_OBEY=true` 默认遵守 robots.txt。
- `DOWNLOAD_DELAY`、`RANDOMIZE_DOWNLOAD_DELAY`、`AUTOTHROTTLE_ENABLED` 控制请求频率。
- `USER_AGENT_POOL` 支持 User-Agent 轮换。
- `PROXY_LIST` 支持静态代理列表，`PROXY_POOL_URL` 仅预留，不自动调用未知代理池。
- `QIDIAN_COOKIE`、`ZONGHENG_COOKIE` 仅在人工显式配置时注入。
- `RETRY_TIMES` 与 `RETRY_HTTP_CODES` 控制失败重试。
- 不绕过登录、验证码、付费墙或平台访问限制。

## Playwright 说明

Scrapy 默认使用普通 HTTP 下载器。Spider 可通过 `request.meta["use_playwright"] = True` 请求动态渲染。起点示例默认设置了 `use_playwright = True`，但只有在 `PLAYWRIGHT_ENABLED=true` 时才会真正启用 Playwright；否则会退回 Scrapy 下载器。

相关配置：

```env
PLAYWRIGHT_ENABLED=false
PLAYWRIGHT_HEADLESS=true
PLAYWRIGHT_TIMEOUT_MS=15000
PLAYWRIGHT_WAIT_UNTIL=domcontentloaded
PLAYWRIGHT_POST_LOAD_WAIT_MS=1500
PLAYWRIGHT_BLOCK_RESOURCE_TYPES=image,media,font
```

默认会屏蔽图片、媒体和字体资源请求，减少不必要的外部访问。爬虫只导航到各 Spider 的 `allowed_domains`，并会拒绝配置错误导致的站外起始 URL 或翻页 URL。

## 选择器维护

所有平台选择器集中在 `novel_crawler/selectors.py`。若平台页面结构变化，优先调整该文件，而不是修改 Spider 业务逻辑。

### 保存页面 HTML 辅助调试

如果某个平台日志出现 `No trend cards matched`，可以保存 Scrapy 或 Playwright 实际拿到的 HTML：

```bash
SAVE_RESPONSE_HTML=true PLAYWRIGHT_ENABLED=true scrapy crawl qidian_trends
```

Docker 中可临时覆盖环境变量：

```bash
docker compose run --rm -e SAVE_RESPONSE_HTML=true -e PLAYWRIGHT_ENABLED=true crawler
```

HTML 会保存到 `data/debug_html/`。这个文件只用于维护公开页面选择器，不要上传 Cookie、Authorization 等敏感请求头。

建议排错命令：

```bash
docker compose build --no-cache
docker compose run --rm \
  -e LOG_LEVEL=INFO \
  -e SAVE_RESPONSE_HTML=true \
  -e OUTPUT_FILE_PREFIX=debug_run \
  crawler-zongheng
```

完成后查看：

```bash
ls -lh data
ls -lh data/debug_html
```

### 如何复制作品列表 HTML

你不需要从整页“查看网页源代码”里手动猜。推荐用浏览器开发者工具：

1. 打开目标榜单页面，例如起点月票榜。
2. 按 `F12` 打开开发者工具。
3. 点击左上角的元素选择按钮，或按 `Ctrl+Shift+C`。
4. 在页面上点击某一本小说的标题或作品卡片。
5. 开发者工具的 `Elements` 面板会定位到对应节点。
6. 向上找最近的包含标题、作者、分类、简介、排名的父节点，通常是一个 `li` 或 `div`。
7. 右键该节点，选择 `Copy > Copy outerHTML`。
8. 粘贴给我时只贴 1-2 个作品卡片片段即可，不要复制 Cookie、请求头、账号信息或任何凭据。

如果页面数据来自接口，也可以在 `Network` 面板中筛选 `Fetch/XHR`，刷新页面后查看响应的 `Preview` 或 `Response`。只复制作品 JSON 片段，不要复制请求头。

新增平台时建议：

1. 在 `selectors.py` 增加平台选择器。
2. 继承 `BasePlatformSpider` 创建新 Spider。
3. 设置 `platform_key`、`platform_name`、`list_type`、`start_urls`。
4. 如页面强依赖动态渲染，设置 `use_playwright = True` 和合适的 `wait_for_selector`。

## 分布式扩展预留

当需要 Redis 调度时，可设置：

```env
USE_REDIS_SCHEDULER=true
REDIS_PASSWORD=replace-with-a-strong-local-password
REDIS_URL=redis://:replace-with-a-strong-local-password@redis:6379/0
```

代码中已预留 `scrapy-redis` 的 Scheduler 与 DupeFilter 配置。Kafka 可在后续通过新增 Pipeline 将标准化后的 `TrendItem` 投递到主题，例如 `novel.trends.raw`。

## 合规边界

本模块仅用于课程项目与公开数据趋势分析。请在实际运行前复核目标平台规则、robots.txt、访问频率与授权范围。不要采集需要登录、验证码、人机验证或付费权限才能访问的数据。
## 真实数据排查说明

采集结果在 `data/` 下查看。开启 `OUTPUT_INCLUDE_SPIDER=true` 后，每个 Spider 会写到独立文件；文件名还会包含本次运行时间戳，避免历史数据混在一起：

```text
data/debug_run_qidian_trends_YYYYMMDDTHHMMSSZ.jsonl
data/debug_run_zongheng_trends_YYYYMMDDTHHMMSSZ.jsonl
```

如果起点返回腾讯验证码、人机验证或访问挑战页，爬虫会记录 `Access challenge detected` 并停止该响应，不会绕过验证码。此时 `data/debug_html/qidian_*.html` 只是验证页，不代表选择器失效。合规做法是降低频率、等待访问恢复、改用平台允许的公开接口或人工导出的公开数据片段。

纵横榜单默认启用公开 JSON 榜单接口分页。月票榜 URL 中的 `month=20261` 到 `month=20265` 会转换为接口的 `rankNo=20261..20265`，月票数从对应月份榜单接口返回的 `number` 字段读取，并写入 `listType`，例如 `月票榜-2026年01月`，便于后续按月比较题材热度：

```env
ZONGHENG_USE_API=true
MAX_PAGES_PER_LIST=10
DEFAULT_PAGE_SIZE=20
```

如果接口不可用，会自动退回到 Playwright 渲染 HTML 的首屏解析。需要临时关闭接口模式时，可设置 `ZONGHENG_USE_API=false`。

Docker 镜像不会自动感知本机代码改动。修改 Spider 后请先重建镜像，再运行纵横采集：

```bash
docker compose --profile manual build crawler-zongheng
docker compose --profile manual run --rm \
  -e OUTPUT_FILE_PREFIX=zongheng_api_probe \
  -e MAX_PAGES_PER_LIST=10 \
  crawler-zongheng
```

如果日志里出现 `Zongheng API pagination enabled` 和 `Request Zongheng API page 2`，说明已经进入接口分页逻辑；如果仍然只出现 `No next page link found`，说明运行的还是旧镜像或手动关闭了 `ZONGHENG_USE_API`。

纵横榜单页只提供粗分类。默认会根据 API 返回的 `bookId` 访问公开详情页，例如 `https://www.zongheng.com/detail/1435440`，从 `.book-info--tags span` 中补全细标签，并过滤 `已签约`、`连载中`、`已完结` 等状态类词。详情页标签补全可以关闭：

```env
ZONGHENG_DETAIL_ENABLED=false
```

详情页请求仍会遵守全局 `DOWNLOAD_DELAY`、`AUTOTHROTTLE_*` 和失败重试策略。若详情页失败，爬虫会保留榜单页已有分类标签，不会中断整批榜单采集。
