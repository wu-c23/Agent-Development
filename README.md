# Agent-Development
大作业“网络小说智能推荐与舆情分析系统”

## Safe-Search Architect 模块

### 目录结构
- src/safe_search: 语义检索 + 避雷过滤
- src/sentiment_critic: 舆情风险评分与证据摘要
- src/main.py: 最小可运行示例

### 依赖安装
```bash
pip install -r requirements.txt
```

### 环境变量
- DEEPSEEK_API_KEY: DeepSeek API key
- DEEPSEEK_BASE_URL: https://api.deepseek.com
- DEEPSEEK_CHAT_MODEL: deepseek-v4-pro

### 快速运行
```bash
python src/main.py
```

### 数据字段约定
Book 最小字段:
- id
- title
- intro
- tags
- status (可选)
- sentiment_summary (可选)

## Review Critic 模块（豆瓣书评采集与舆情看板）

### 依赖安装
```powershell
pip install -r requirements.txt
```

### 只抓豆瓣书评
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

### 分析与看板
先用本地规则跑通：

```powershell
python scripts/analyze_reviews.py --input data/raw_reviews.jsonl --output outputs/analysis_report.json --no-agent
python scripts/build_dashboard.py --report outputs/analysis_report.json --output outputs/sentiment_dashboard.html
```

使用 DeepSeek Agent 时，把 `.env.example` 复制为 `.env`，然后在 `.env` 中填写配置：

```ini
DEEPSEEK_API_KEY=你的 key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_CHAT_MODEL=deepseek-v4-pro
EASYCOMPUTE_BATCH_DELAY=8
```

脚本会自动读取仓库根目录的 `.env`，不需要每次手动执行 `$env:...`。`.env` 已加入 `.gitignore`，避免误提交 key。

配置完成后运行：

```powershell
python scripts/analyze_reviews.py --input data/raw_reviews.jsonl --output outputs/analysis_report.json
```

如果你想确认一定调用了模型，而不是回退本地启发式规则，加 `--require-agent`：

```powershell
python scripts/run_sentiment_pipeline.py --book "诡秘之主" --platform douban --max-pages 2 --require-agent
```

如果遇到 HTTP 429，表示模型服务端限流。可以降低并发压力：

```powershell
python scripts/run_sentiment_pipeline.py --book "诡秘之主" --platform douban --max-pages 2 --batch-size 3 --batch-delay 15 --require-agent
```

一键流程：

```powershell
python scripts/run_sentiment_pipeline.py --book "诡秘之主" --platform douban --subject-id "豆瓣subject数字ID" --max-pages 2 --no-agent
```

### 输出
- `data/raw_reviews.jsonl`：豆瓣书评原始数据。
- `outputs/analysis_report.json`：结构化舆情分析结果。
- `outputs/sentiment_dashboard.html`：小说详情页舆情看板。

JSONL 字段示例：

```json
{"book":"小说名","platform":"douban","title":"书评标题","author":"作者","created_at":"2026-05-22","content":"书评正文","source_url":"https://book.douban.com/review/xxxx/"}
```
