# Sentiment Critic

小说书评舆情采集与分析工具。给定一个书名，可以自动采集豆瓣读书、百度贴吧、小红书书评，分析口碑，
生成 HTML 舆情看板，并通过 REST API 输出符合 Data Contract 的舆情数据。

## REST API 服务 (联调)

启动 API 服务 (端口 8003，符合 Data Contract v1.0):

```powershell
uvicorn sentiment_critic.sentiment_api:app --host 0.0.0.0 --port 8003
```

**Mock 模式** (无需真实数据采集):

```powershell
uvicorn sentiment_critic.mock_server:app --host 0.0.0.0 --port 8003
```

### API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/sentiment/detail/{uid}` | 单书舆情详情 |
| GET | `/api/v1/sentiment/compare?uids=uid1,uid2` | 多书舆情对比 |
| GET | `/api/v1/sentiment/health` | 健康检查 |

### 评分维度

| 维度 | 范围 | 说明 |
|------|------|------|
| overall | [0, 10] | 综合加权评分 |
| style | [0, 10] | 文笔评分 |
| logic | [0, 10] | 逻辑评分 |
| character | [0, 10] | 人物塑造评分 |
| update_stability | [0, 10] | 更新稳定性评分 |
| toxicity_index | [0, 1] | 社区毒性指数 (越低越好) |

## 安装依赖

```powershell
pip install -r requirements.txt
```

## 一键生成 HTML

只给书名即可。默认会抓取 `douban + tieba`，生成原始评论、分析报告和 HTML 看板：

```powershell
python scripts/run_sentiment_pipeline.py --book "诡秘之主" --max-pages 2 --thread-pages 1 --no-agent
```

输出文件默认会进入带书名和时间戳的独立运行目录，避免覆盖旧结果：

- `outputs/runs/诡秘之主_douban_tieba_YYYYMMDD_HHMMSS/raw_reviews.jsonl`
- `outputs/runs/诡秘之主_douban_tieba_YYYYMMDD_HHMMSS/analysis_report.json`
- `outputs/runs/诡秘之主_douban_tieba_YYYYMMDD_HHMMSS/sentiment_dashboard.html`

HTML 看板是 React 交互式单文件，支持关键词搜索、平台/情绪筛选、排序、明暗主题切换、复制总结和导出筛选后的 JSON。默认从 CDN 加载 React，离线环境打开时需要联网，或把 React UMD 文件改成本地路径。

如果你想写到固定路径，可以显式传输出参数；默认不会覆盖已存在文件，会自动追加 `_2`、`_3`。只有加 `--overwrite` 才会覆盖：

```powershell
python scripts/run_sentiment_pipeline.py --book "诡秘之主" --raw-output data/raw_reviews.jsonl --report-output outputs/analysis_report.json --dashboard-output outputs/sentiment_dashboard.html --overwrite --no-agent
```

如果配置了 EasyCompute/OpenAI-compatible 模型，可以去掉 `--no-agent`：

```powershell
python scripts/run_sentiment_pipeline.py --book "诡秘之主" --max-pages 2 --thread-pages 1
```

默认平台就是豆瓣和贴吧；如果只想抓某个平台，可显式指定：

```powershell
python scripts/run_sentiment_pipeline.py --book "诡秘之主" --platform douban --max-pages 2 --no-agent
python scripts/run_sentiment_pipeline.py --book "诡秘之主" --platform tieba --max-pages 2 --thread-pages 1 --no-agent
```

## 豆瓣采集

豆瓣爬虫会自动搜索图书条目，并把书名和 subject id 缓存在 `data/douban_subject_cache.json`。更稳的方式是直接提供豆瓣图书页面的 subject id 或 URL：

豆瓣现在没有面向普通开发者、可稳定抓取图书书评的公开官方 API。当前实现采用公开网页 + 少量豆瓣站内 JSON 搜索端点做条目定位；如果页面触发安全验证，脚本会跳过豆瓣并继续其它平台，除非你加了 `--strict`。

```powershell
python scripts/collect_douban_reviews.py --book "诡秘之主" --subject-id "豆瓣subject数字ID" --pages 2
python scripts/collect_douban_reviews.py --book "诡秘之主" --subject-url "https://book.douban.com/subject/xxxx/" --pages 2
```

只检查自动搜索能找到哪些豆瓣条目：

```powershell
python scripts/collect_douban_reviews.py --book "诡秘之主" --search-only
```

豆瓣如果遇到安全验证、403 或搜不到条目，可以在 `.env` 中设置合法 Cookie：

```env
DOUBAN_COOKIE=你的豆瓣 Cookie
```

## 贴吧采集

贴吧默认使用 `aiotieba` 后端采集同名贴吧帖子，再进入帖子楼层抽取长评；失败时回退到网页解析。

```powershell
python scripts/collect_tieba_reviews.py --book "诡秘之主" --pages 2 --thread-pages 1
```

可选择后端：

```powershell
python scripts/collect_tieba_reviews.py --book "诡秘之主" --backend aiotieba
python scripts/collect_tieba_reviews.py --book "诡秘之主" --backend web
```

如果贴吧接口或页面被 403，可以设置 Cookie，或导入浏览器保存的 HTML：

```env
TIEBA_COOKIE=你的贴吧 Cookie
```

```powershell
python scripts/collect_tieba_reviews.py --book "诡秘之主" --input-html data/tieba_thread.html
```

## 统一采集入口

只采集、不生成 HTML：

```powershell
python scripts/collect_reviews.py --book "诡秘之主" --max-pages 2 --thread-pages 1
```

不填 `--output` 时会写到 `data/runs/书名_平台_时间戳.jsonl`。不填 `--platform` 时默认抓 `douban + tieba`。也可以扩展到小红书：

```powershell
python scripts/collect_reviews.py --book "诡秘之主" --platform douban --platform tieba --platform xiaohongshu --max-pages 1
```

## 小红书采集

小红书没有面向普通开发者的公开“按关键词搜索笔记/抓评论”官方 API。当前实现优先解析公开 HTML、分享页和你合法登录态下能访问的页面。

```powershell
python scripts/collect_xiaohongshu_reviews.py --book "诡秘之主" --url "https://www.xiaohongshu.com/explore/真实笔记ID"
python scripts/collect_xiaohongshu_reviews.py --book "诡秘之主" --url "https://xhslink.com/真实分享码"
```

`.env` 中可设置：

```env
XHS_COOKIE=你的小红书 Cookie
```

## Agent 配置

把 `.env.example` 复制为 `.env`，然后填写：

```env
EASYCOMPUTE_API_KEY=你的 key
EASYCOMPUTE_BASE_URL=https://llmapi.paratera.com/v1
EASYCOMPUTE_MODEL=DeepSeek-V4-Pro
EASYCOMPUTE_TIMEOUT=180
EASYCOMPUTE_RETRIES=2
EASYCOMPUTE_BATCH_DELAY=8

TIEBA_COOKIE=
DOUBAN_COOKIE=
XHS_COOKIE=
```

脚本会自动读取仓库根目录的 `.env`。`.env` 已加入 `.gitignore`，避免误提交 key。

成功的 Agent batch 之间不会固定等待；只有遇到 429、超时、503/504 这类可重试错误时，才按 `EASYCOMPUTE_BATCH_DELAY` 或 `--batch-delay` 退避后重试。
如果遇到模型 HTTP 429，可以降低 batch 压力：

```powershell
python scripts/run_sentiment_pipeline.py --book "诡秘之主" --batch-size 3 --batch-delay 15
```

## JSONL 字段示例

```json
{"book":"小说名","platform":"tieba","title":"书评标题","author":"作者","created_at":"2026-05-22","content":"书评正文","source_url":"https://tieba.baidu.com/p/xxxx","extra":{"tieba_thread_id":"xxxx","tieba_floor":1}}
```
