# Agent-Development

本仓库当前实现了“舆情分析与深度评价专家（Sentiment Critic）”脚本模块，用来采集小说深度书评、调用 Agent 做多维口碑分析，并生成小说详情页可用的舆情看板。

## 功能

- 采集：支持贴吧、豆瓣、小红书搜索页或指定 URL，也支持导入本地 HTML / JSONL。
- 分析：按文笔、逻辑、更新速度、情绪倾向打分，输出“一句话毒舌点评”和“入坑理由”。
- 前端：生成静态 HTML 看板，展示正面/中性/负面比例、平台分布、高频标签和逐条评论拆解。
- 兜底：没有模型 key 时，可以用本地启发式规则跑通流程，便于课堂展示和前端联调。

## 快速运行

先用示例数据跑通：

```powershell
python scripts/run_sentiment_pipeline.py --book "诡秘之主" --input data/sample_reviews.jsonl --no-agent
```

输出文件：

- `data/raw_reviews.jsonl`：采集/导入后的评论。
- `outputs/analysis_report.json`：结构化舆情分析结果。
- `outputs/sentiment_dashboard.html`：小说详情页舆情看板，可直接用浏览器打开。

## 使用 EasyCompute Agent

把 `.env.example` 里的配置复制到自己的环境变量中，`base_url` 和 `model` 按 easycompute 页面给出的调用方式填写：

```powershell
$env:EASYCOMPUTE_API_KEY="你的 key"
$env:EASYCOMPUTE_BASE_URL="https://easycompute.cs.tsinghua.edu.cn/v1"
$env:EASYCOMPUTE_MODEL="页面上给出的模型名"
python scripts/run_sentiment_pipeline.py --book "诡秘之主" --input data/sample_reviews.jsonl
```

脚本使用 OpenAI-compatible `/chat/completions` 调用格式；如果 easycompute 页面给出的路径已经包含 `/chat/completions`，可以把完整路径直接填到 `EASYCOMPUTE_BASE_URL`。

## 采集真实平台评论

直接搜索平台：

```powershell
python scripts/collect_reviews.py --book "小说名" --platform tieba --platform douban --platform xiaohongshu --max-pages 1 --output data/raw_reviews.jsonl
```

指定页面 URL：

```powershell
python scripts/collect_reviews.py --book "小说名" --url "https://example.com/review-page" --output data/raw_reviews.jsonl
```

如果平台页面需要登录态，可以设置：

```powershell
$env:DOUBAN_COOKIE="你的 cookie"
$env:XHS_COOKIE="你的 cookie"
$env:TIEBA_COOKIE="你的 cookie"
```

社交平台反爬和页面结构经常变化，稳定课堂演示时推荐先保存 HTML 或整理 JSONL，再用 `--input-html` / `--input-jsonl` 导入。

默认情况下，某个平台返回 403、安全验证或网络错误时，采集脚本会打印 `[warn]` 并继续处理其他平台/输入源；如果你希望一遇到错误就退出，加 `--strict`。
如果所有在线页面都失败，脚本默认不会用空结果覆盖已有输出；确实需要空文件时加 `--allow-empty-output`。

如果误抓到了脚本、页脚、备案信息等非书评内容，可以清洗已有 JSONL：

```powershell
python scripts/clean_reviews.py --input data/raw_reviews.jsonl --output data/raw_reviews.cleaned.jsonl --book "小说名"
```

## 分步运行

```powershell
python scripts/collect_reviews.py --book "小说名" --input-jsonl data/sample_reviews.jsonl --output data/raw_reviews.jsonl
python scripts/analyze_reviews.py --input data/raw_reviews.jsonl --output outputs/analysis_report.json
python scripts/build_dashboard.py --report outputs/analysis_report.json --output outputs/sentiment_dashboard.html
```

JSONL 评论格式示例：

```json
{"book":"小说名","platform":"douban","title":"标题","content":"深度书评正文","source_url":"https://..."}
```
