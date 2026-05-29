# Agent-Development

小说书评舆情采集与分析工具。当前支持豆瓣读书、百度贴吧、小红书三类来源，采集结果统一写入 JSONL，后续继续复用 Agent 分析和舆情看板生成流程。

## 安装依赖

```powershell
pip install -r requirements.txt
```

## 采集豆瓣书评

最稳的方式是直接提供豆瓣图书页面的 subject id 或 URL：

```powershell
python scripts/collect_douban_reviews.py --book "诡秘之主" --subject-id "豆瓣subject数字ID" --pages 2 --output data/raw_reviews.jsonl
python scripts/collect_douban_reviews.py --book "诡秘之主" --subject-url "https://book.douban.com/subject/xxxx/" --pages 2
```

如果不提供 subject，脚本会尝试自动搜索：

```powershell
python scripts/collect_douban_reviews.py --book "诡秘之主" --search-only
python scripts/collect_douban_reviews.py --book "诡秘之主" --pages 1
```

豆瓣有反爬和登录态限制。如果遇到安全验证、403 或搜不到条目，可以设置自己的合法 Cookie：

```powershell
$env:DOUBAN_COOKIE="你的豆瓣 Cookie"
python scripts/collect_douban_reviews.py --book "诡秘之主" --subject-id "豆瓣subject数字ID" --pages 2
```

## 采集贴吧书评

贴吧爬虫会先搜索帖子，再进入 `/p/{thread_id}` 抽取楼层正文，并保留楼层、帖子 id 等信息到 `extra`。
默认会优先尝试 `aiotieba` 后端；它参考贴吧移动端核心接口，通常比 PC 网页 HTML 更不容易被 403。失败时会回退到网页解析。

```powershell
python scripts/collect_tieba_reviews.py --book "诡秘之主" --pages 2 --thread-pages 1 --output data/raw_reviews.jsonl
```

只使用网页解析或强制使用 `aiotieba`：

```powershell
python scripts/collect_tieba_reviews.py --book "诡秘之主" --backend web
python scripts/collect_tieba_reviews.py --book "诡秘之主" --backend aiotieba
```

也可以直接给指定帖子或搜索页 URL：

```powershell
python scripts/collect_tieba_reviews.py --book "诡秘之主" --url "https://tieba.baidu.com/p/xxxx"
```

如果想只解析搜索页摘要，不进入帖子详情：

```powershell
python scripts/collect_tieba_reviews.py --book "诡秘之主" --pages 1 --no-fetch-detail
```

## 采集小红书书评

小红书爬虫会从搜索页发现笔记链接，再解析笔记页的 meta 信息和页面内 SSR 状态。小红书页面经常需要登录态，实际使用时推荐优先提供具体笔记 URL 或设置 `XHS_COOKIE`。

```powershell
python scripts/collect_xiaohongshu_reviews.py --book "诡秘之主" --pages 1 --output data/raw_reviews.jsonl
python scripts/collect_xiaohongshu_reviews.py --book "诡秘之主" --url "https://www.xiaohongshu.com/explore/xxxx"
python scripts/collect_xiaohongshu_reviews.py --book "诡秘之主" --url "https://xhslink.com/xxxx"
```

设置 Cookie：

```powershell
$env:XHS_COOKIE="你的小红书 Cookie"
python scripts/collect_xiaohongshu_reviews.py --book "诡秘之主" --pages 1
```

## 统一入口

`collect_reviews.py` 会自动把 `tieba`、`xiaohongshu` 分发到专用爬虫；只抓豆瓣且没有指定 URL 时，仍会走豆瓣专用爬虫。

```powershell
python scripts/collect_reviews.py --book "诡秘之主" --platform douban --subject-id "豆瓣subject数字ID" --max-pages 2
python scripts/collect_reviews.py --book "诡秘之主" --platform tieba --platform xiaohongshu --max-pages 1
python scripts/collect_reviews.py --book "诡秘之主" --platform douban --platform tieba --platform xiaohongshu --subject-id "豆瓣subject数字ID" --max-pages 1
python scripts/collect_reviews.py --book "诡秘之主" --platform tieba --keyword "诡秘之主 长评" --thread-pages 2
```

本地保存的 HTML 也可以导入：

```powershell
python scripts/collect_reviews.py --book "诡秘之主" --platform tieba --input-html saved_tieba_thread.html
python scripts/collect_reviews.py --book "诡秘之主" --platform xiaohongshu --input-html saved_xhs_note.html
```

## 分析与看板

先用本地规则跑通：

```powershell
python scripts/analyze_reviews.py --input data/raw_reviews.jsonl --output outputs/analysis_report.json --no-agent
python scripts/build_dashboard.py --report outputs/analysis_report.json --output outputs/sentiment_dashboard.html
```

使用 EasyCompute Agent 时，把 `.env.example` 复制为 `.env`，然后填写配置：

```powershell
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

脚本会自动读取仓库根目录的 `.env`，不需要每次手动执行 `$env:...`。`.env` 已加入 `.gitignore`，避免误提交 key。

一键流程：

```powershell
python scripts/run_sentiment_pipeline.py --book "诡秘之主" --platform tieba --platform xiaohongshu --max-pages 1 --no-agent
python scripts/run_sentiment_pipeline.py --book "诡秘之主" --platform douban --subject-id "豆瓣subject数字ID" --max-pages 2 --require-agent
```

如果遇到模型 HTTP 429，可以降低 batch 压力：

```powershell
python scripts/run_sentiment_pipeline.py --book "诡秘之主" --platform douban --max-pages 2 --batch-size 3 --batch-delay 15 --require-agent
```

## 输出

- `data/raw_reviews.jsonl`：原始书评数据。
- `outputs/analysis_report.json`：结构化舆情分析结果。
- `outputs/sentiment_dashboard.html`：小说详情页舆情看板。

JSONL 字段示例：

```json
{"book":"小说名","platform":"tieba","title":"书评标题","author":"作者","created_at":"2026-05-22","content":"书评正文","source_url":"https://tieba.baidu.com/p/xxxx","extra":{"tieba_thread_id":"xxxx","tieba_floor":1}}
```

## 说明

脚本采用 `requests.Session` 维持请求头和 Cookie，`BeautifulSoup` 按平台页面结构解析，并加入延时、重试、反爬页面检测。小红书没有在这里实现绕签名接口，优先解析公开 HTML、分享页和你合法登录态下能访问的页面。
