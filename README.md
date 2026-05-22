# Agent-Development

当前版本先把范围收窄到“豆瓣读书书评”采集：定位豆瓣图书条目，抓取 `subject/{id}/reviews` 书评列表，再进入单篇书评页抓全文，最后复用 Agent 分析和舆情看板生成流程。

## 安装依赖

```powershell
pip install -r requirements.txt
```

## 只抓豆瓣书评

最稳的方式是直接提供豆瓣图书页面的 subject id 或 URL：

```powershell
python scripts/collect_douban_reviews.py --book "诡秘之主" --subject-id "豆瓣subject数字ID" --pages 2 --output data/raw_reviews.jsonl
```

也可以给 subject URL：

```powershell
python scripts/collect_douban_reviews.py --book "诡秘之主" --subject-url "https://book.douban.com/subject/xxxx/" --pages 2
```

如果不提供 subject，脚本会尝试用豆瓣搜索找第一个匹配结果：

```powershell
python scripts/collect_douban_reviews.py --book "诡秘之主" --pages 1
```

先只检查自动搜索能找到哪些豆瓣条目：

```powershell
python scripts/collect_douban_reviews.py --book "诡秘之主" --search-only
```

成功抓取过一次后，脚本会把书名和 subject id 写入 `data/douban_subject_cache.json`；之后即使豆瓣搜索接口被 403，也可以直接按书名复用缓存。

豆瓣有反爬和登录态限制。如果遇到安全验证、403 或搜不到条目，可以设置自己的合法 Cookie：

```powershell
$env:DOUBAN_COOKIE="你的豆瓣 Cookie"
python scripts/collect_douban_reviews.py --book "诡秘之主" --subject-id "豆瓣subject数字ID" --pages 2
```

抓取本地保存的豆瓣书评 HTML：

```powershell
python scripts/collect_douban_reviews.py --book "诡秘之主" --input-html saved_review_page.html --output data/raw_reviews.jsonl
```

旧入口也接入了豆瓣专用采集逻辑，下面这条会走同一套豆瓣爬虫：

```powershell
python scripts/collect_reviews.py --book "诡秘之主" --platform douban --subject-id "豆瓣subject数字ID" --max-pages 2
```

## 分析与看板

先用本地规则跑通：

```powershell
python scripts/analyze_reviews.py --input data/raw_reviews.jsonl --output outputs/analysis_report.json --no-agent
python scripts/build_dashboard.py --report outputs/analysis_report.json --output outputs/sentiment_dashboard.html
```

使用 EasyCompute Agent 时，按课程页面给出的调用信息设置环境变量：

```powershell
$env:EASYCOMPUTE_API_KEY="你的 key"
$env:EASYCOMPUTE_BASE_URL="https://easycompute.cs.tsinghua.edu.cn/v1"
$env:EASYCOMPUTE_MODEL="页面上给出的模型名"
python scripts/analyze_reviews.py --input data/raw_reviews.jsonl --output outputs/analysis_report.json
```

一键流程：

```powershell
python scripts/run_sentiment_pipeline.py --book "诡秘之主" --platform douban --subject-id "豆瓣subject数字ID" --max-pages 2 --no-agent
```

## 输出

- `data/raw_reviews.jsonl`：豆瓣书评原始数据。
- `outputs/analysis_report.json`：结构化舆情分析结果。
- `outputs/sentiment_dashboard.html`：小说详情页舆情看板。

JSONL 字段示例：

```json
{"book":"小说名","platform":"douban","title":"书评标题","author":"作者","created_at":"2026-05-22","content":"书评正文","source_url":"https://book.douban.com/review/xxxx/"}
```

## 说明

脚本采用 GitHub 上常见豆瓣爬虫的朴素做法：`requests.Session` 维持请求头和 Cookie，`BeautifulSoup` 按豆瓣书评页 DOM 结构解析，加入延时、重试、反爬页面检测，并只抽取 `.review-item` / `.review-content`，避免把搜索页脚本和备案信息当成评论。
