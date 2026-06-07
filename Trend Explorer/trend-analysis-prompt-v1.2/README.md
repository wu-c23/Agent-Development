# trend-analysis-prompt-v1.2

本模块是“全网风向标”的趋势分析 Agent 层，用于把爬虫输出的榜单数据、作品标题、简介、标签、评论摘要和榜单变化，转换为推荐系统可复用的结构化趋势洞察。

## 文件说明

```text
trend-analysis-prompt-v1.2/
├── system_prompt.md
├── tag_extraction_prompt.md
├── genre_evolution_prompt.md
├── trend_summary_prompt.md
├── langchain_chains.py
└── README.md
```

- `system_prompt.md`：全局角色、合规边界、统一 JSON 输出结构。
- `tag_extraction_prompt.md`：作品核心标签、流派、热门元素和情绪价值抽取。
- `genre_evolution_prompt.md`：跨时间窗口的流派迁移和元素演变分析。
- `trend_summary_prompt.md`：生成可用于趋势大屏和 API 的摘要。
- `langchain_chains.py`：提供 `extract_tags_chain`、`analyze_genre_evolution_chain`、`generate_trend_summary_chain`。

## 安装依赖

```bash
pip install langchain-core langchain-openai
```

使用统一的 DeepSeek API Key（从 Safe-Search Architect/.env 读取）：

```bash
# 配置位置: Safe-Search Architect/.env
# DEEPSEEK_API_KEY=你的key
# DEEPSEEK_BASE_URL=https://api.deepseek.com
# DEEPSEEK_CHAT_MODEL=deepseek-v4-pro
# NOVEL_TREND_LLM_TEMPERATURE=0.2
```

## 使用示例

```python
from langchain_chains import extract_tags_chain

chain = extract_tags_chain()
result = chain.invoke({
    "work_payload": {
        "title": "雾都规则档案",
        "platform": "示例平台",
        "rank": 3,
        "category": "悬疑",
        "tags": ["规则怪谈", "无限流"],
        "summary": "主角进入被规则支配的城市副本，在限制条件中寻找生路。"
    }
})

print(result)
```

所有 Chain 都返回 JSON dict，字段统一为：

```json
{
  "core_tags": [],
  "genre": "",
  "hot_elements": [],
  "reader_emotion_value": [],
  "trend_reason": "",
  "evolution_relation": {
    "from": null,
    "to": null,
    "logic": ""
  },
  "confidence": 0.0
}
```

## 扩展方式

后续可以把爬虫输出的 `TrendItem` JSONL 汇总为时间窗口数据，传入 `generate_trend_summary_chain` 生成 `/api/trends/summary` 的数据源；也可以把作品级输出写入标签库，支持推荐系统做题材召回、相似作品聚类和趋势加权排序。

纵横历史月票榜会以 `listType` 区分月份，例如 `月票榜-2026年01月`、`月票榜-2026年02月`。构造 `trend_window` 或 `trend_items` 时可以直接保留这些字段，分析链会把它们作为跨月趋势窗口，用于判断题材连续升温、短期爆发和回落。
