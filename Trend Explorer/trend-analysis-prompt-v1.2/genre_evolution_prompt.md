# 流派与元素演变分析 Prompt

请比较两个时间窗口或两组榜单数据，分析网络小说流行元素是否发生迁移、扩散、融合或衰退。

当前窗口数据：

{trend_window}

上一窗口或对照数据：

{previous_window}

重点观察元素：

{target_elements}

分析任务：

- 找出当前窗口中更突出的题材、标签、作品元素和读者情绪价值。
- 如果输入来自历史月票榜，请优先按 `listType` 中的月份标识比较，例如 `月票榜-2026年01月` 到 `月票榜-2026年04月`，识别连续上升、短期爆发和回落元素。
- 判断是否存在流派迁移，例如“废土生存”向“规则怪谈”，“系统流”向“轻量金手指”，“传统玄幻升级流”向“反套路群像流”。
- 解释迁移逻辑：题材压力、爽点结构、篇幅节奏、人设变化、平台榜单机制、读者情绪需求变化等。
- 如果没有足够证据证明迁移，请保持 evolution_relation.from/to 为 null，并在 logic 中说明证据不足。
- confidence 必须体现证据强弱：多平台、多榜单、多作品共同出现时更高，单一作品或样本稀疏时更低。

只输出合法 JSON，不要输出 Markdown 或解释文字。字段必须完全使用以下结构：

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
