# Agent-Development

小说书评舆情采集与分析工具。给定一个书名，可以自动采集豆瓣读书与百度贴吧书评，分析口碑，并生成 HTML 舆情看板。

## 安装依赖

```powershell
pip install -r requirements.txt
```

## 一键生成 HTML

只给书名即可。默认会抓取 `douban + tieba`，生成原始评论、分析报告和 HTML 看板：

```powershell
python scripts/run_sentiment_pipeline.py --book "诡秘之主" --max-pages 2 --thread-pages 1 --no-agent
```

输出文件：

- `data/raw_reviews.jsonl`：豆瓣 + 贴吧原始书评。
- `outputs/analysis_report.json`：结构化舆情分析结果。
- `outputs/sentiment_dashboard.html`：HTML 舆情看板。

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

不填 `--platform` 时默认抓 `douban + tieba`。也可以扩展到小红书：

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

如果遇到模型 HTTP 429，可以降低 batch 压力：

```powershell
python scripts/run_sentiment_pipeline.py --book "诡秘之主" --batch-size 3 --batch-delay 15
```

## JSONL 字段示例

```json
{"book":"小说名","platform":"tieba","title":"书评标题","author":"作者","created_at":"2026-05-22","content":"书评正文","source_url":"https://tieba.baidu.com/p/xxxx","extra":{"tieba_thread_id":"xxxx","tieba_floor":1}}
```
