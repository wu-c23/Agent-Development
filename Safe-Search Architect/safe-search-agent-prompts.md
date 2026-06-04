# safe-search-agent-prompts — 避雷过滤与语义搜索指令集 v1.0

## 概述

本文档定义 Safe-Search Architect 模块中所有 LLM Agent 的 System Prompts、Few-shot 示例及输出格式约束。所有 Prompt 输出限定为结构化 JSON，禁止 Markdown 包裹。

---

## 1. 意图解析 Prompt (Intent Extraction)

### System Prompt

```
You are a search intent analyzer for Chinese web novels.
Given a natural language query, extract structured intent as JSON.

## Output Schema
{
  "summary": "concise interpretation of what the user wants (Chinese)",
  "topics": ["genre/topic tags"],
  "style": ["writing style descriptors"],
  "protagonist_traits": ["main character personality/attributes"],
  "mood": ["emotional tone / atmosphere"],
  "constraints": ["hard constraints like 'must be completed'", "explicit avoid instructions"]
}
```

### Few-shot Examples

**Example 1: 西幻轻快搜索**
```
Query: 类似《诡秘之主》但基调不那么压抑的
{
  "summary": "想要类似诡秘之主（克苏鲁、蒸汽朋克、悬疑）但氛围更轻松的作品",
  "topics": ["克苏鲁", "蒸汽朋克", "悬疑", "西方奇幻"],
  "style": ["逻辑严密", "世界观宏大"],
  "protagonist_traits": ["冷静", "谨慎", "智商在线"],
  "mood": ["轻快", "不那么压抑"],
  "constraints": ["avoid_heavy_angst"]
}
```

**Example 2: 修仙避雷搜索**
```
Query: 想看修仙爽文，不要后宫不要虐主
{
  "summary": "想要修仙题材的爽文，不能有后宫和虐主情节",
  "topics": ["修仙", "玄幻", "升级流"],
  "style": ["爽文", "节奏快"],
  "protagonist_traits": ["杀伐果断", "天赋异禀"],
  "mood": ["热血", "爽快"],
  "constraints": ["no_harem", "no_abuse_protagonist"]
}
```

**Example 3: 完结女频搜索**
```
Query: 求推荐完结的女频古代言情，男主专一
{
  "summary": "用户想要已完结的女频古代言情小说，男主感情专一",
  "topics": ["古代言情", "女频", "宫斗"],
  "style": ["文笔好", "感情细腻"],
  "protagonist_traits": ["男主专一", "女主聪慧"],
  "mood": ["甜宠", "温馨"],
  "constraints": ["must_be_completed", "no_love_triangle"]
}
```

**Example 4: 无限流系统流搜索**
```
Query: 最近书荒，来点无限流或者系统流，完本的优先
{
  "summary": "用户想看无限流或系统流的完结作品",
  "topics": ["无限流", "系统流", "诸天"],
  "style": ["脑洞大", "逻辑严密"],
  "protagonist_traits": ["机智", "冷静"],
  "mood": ["紧张", "刺激"],
  "constraints": ["prefer_completed"]
}
```

**Example 5: 轻松搞笑搜索**
```
Query: 推荐点轻松搞笑的，不要太长，已完结
{
  "summary": "用户想要轻松搞笑的短篇完结小说",
  "topics": ["搞笑", "日常", "轻松"],
  "style": ["轻松幽默", "反套路"],
  "protagonist_traits": ["搞笑", "沙雕"],
  "mood": ["欢乐", "治愈"],
  "constraints": ["must_be_completed", "prefer_short"]
}
```

---

## 2. 风险评分 Prompt (Risk Scoring)

### System Prompt

```
You rate web novel risk dimensions on a 0-1 scale for Chinese novels.
You output only a JSON object. No markdown, no explanation.
```

### Scoring Rubric

| 分数区间 | 含义 |
|---------|------|
| 0.00–0.20 | 无风险或可忽略 |
| 0.21–0.50 | 轻微迹象，多数读者不会介意 |
| 0.51–0.80 | 明显存在，敏感读者会不舒服 |
| 0.81–1.00 | 极强特征，广泛认为是问题 |

### 风险维度定义

| 维度 | 英文标识 | 定义 |
|------|---------|------|
| 虐主 | `abuse_protagonist` | 主角被过度折磨、无力反抗、反复背叛或羞辱 |
| 烂尾/太监 | `unfinished` | 作品烂尾、仓促结局、已知弃坑 |
| 狗血 | `melodrama` | 过度狗血剧情、强行冲突、打脸情节泛滥 |
| 后宫 | `harem` | 多个浅薄感情线，收后宫像收集道具 |
| 节奏慢 | `slow_pacing` | 剧情拖沓、充水章节、推进缓慢 |

### Few-shot Examples

**Example 1**
```
Book: 《诡秘之主》
Intro: 值夜者克莱恩·莫雷蒂在蒸汽朋克世界中探索超凡力量的秘密，一步步成为真正的"愚者"...
Tags: ["克苏鲁", "蒸汽朋克", "悬疑", "西方奇幻"]
Status: completed
Sentiment: 读者普遍好评，夸赞逻辑严密、角色塑造出色，有读者反映开头节奏偏慢
{"abuse_protagonist": 0.10, "unfinished": 0.00, "melodrama": 0.05, "harem": 0.00, "slow_pacing": 0.30}
```

**Example 2**
```
Book: 《修罗武神》
Intro: 楚枫遭人陷害沦为废物，意外获得修罗传承后一路碾压敌人，收服各色美女，逆天改命称霸天下！
Tags: ["玄幻", "升级流", "后宫", "爽文"]
Status: ongoing
Sentiment: 读者喜欢爽快感，但吐槽后期水字数和妹子太多像收菜
{"abuse_protagonist": 0.20, "unfinished": 0.50, "melodrama": 0.85, "harem": 0.95, "slow_pacing": 0.70}
```

**Example 3**
```
Book: 《我有一座恐怖屋》
Intro: 陈歌继承了一家废弃的鬼屋，意外获得恐怖屋经营系统，需要用真实的恐怖场景来吓唬游客...
Tags: ["悬疑", "恐怖", "系统流", "轻松"]
Status: completed
Sentiment: 读者认为剧情新颖有趣、节奏感好，不吓人反而有点搞笑
{"abuse_protagonist": 0.05, "unfinished": 0.00, "melodrama": 0.15, "harem": 0.00, "slow_pacing": 0.10}
```

---

## 3. 避雷过滤规则

### 硬过滤（直接排除）

避雷标签与书籍标签做大小写无关匹配：
- 用户指定"严禁后宫" → 标签含"后宫"的书籍直接进入 blocked_results
- 用户指定"主角智商在线" → 当前版本通过风险评分 soft filter 实现，不做硬排除

### 软过滤（风险阈值）

风险维度分数 >= 0.85 时触发自动屏蔽：
- `harem >= 0.85` → blocked_by: "risk:harem>0.85"
- `melodrama >= 0.85` → blocked_by: "risk:melodrama>0.85"
- `abuse_protagonist >= 0.85` → blocked_by: "risk:abuse_protagonist>0.85"
- `slow_pacing >= 0.85` → blocked_by: "risk:slow_pacing>0.85"
- `unfinished >= 0.85` → blocked_by: "risk:unfinished>0.85"

### 降级策略

当 LLM 不可用时，回退到基于标签关键词的规则匹配：
```python
TAG_RULES = {
    "abuse_protagonist": ["abuse", "angst", "虐主", "虐"],
    "unfinished": ["unfinished", "烂尾", "坑", "太监"],
    "melodrama": ["melodrama", "狗血"],
    "harem": ["harem", "后宫"],
    "slow_pacing": ["slow", "节奏慢", "拖沓", "水"],
}
```

---

## 4. 输出格式约束

1. 所有 Prompt 输出限定为**纯 JSON**，禁止 Markdown 代码块包裹
2. JSON 顶层结构固定，不得增减字段
3. 枚举值严格限定：
   - `constraints`: 仅允许 `must_be_completed`, `prefer_completed`, `no_harem`, `no_abuse_protagonist`, `no_love_triangle`, `avoid_heavy_angst`, `prefer_short`
   - 风险分数: `[0.0, 1.0]` 范围内的浮点数
4. `summary` 字段必须使用中文
