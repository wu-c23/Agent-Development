# 作品核心标签抽取 Prompt

请分析下面的网络小说作品数据，抽取它的核心流行标签、流派归属、热门元素、读者情绪价值和进入趋势榜的可能原因。

输入数据可能包含：

- title：作品标题
- author：作者
- platform：平台来源
- rank：当前排名
- rankChange：排名变化
- category：平台分类
- tags：已有标签
- heatScore：热度值
- listType：榜单类型
- summary：作品简介
- commentSummary：评论摘要
- capturedAt：采集时间

作品数据：

{work_payload}

判断重点：

- 从标题、简介、分类、已有标签中提取 3 到 8 个稳定标签。
- 区分平台分类和真实流行元素，例如“仙侠”是大类，“凡人流”“苟道”“家族修仙”“女强逆袭”是更有推荐价值的元素。
- reader_emotion_value 应描述读者获得的情绪体验，例如爽感、压迫感、治愈感、代入感、反转快感、成长满足、权谋博弈感。
- trend_reason 应解释它为什么可能在当前榜单上涨或保持高位。
- 如果输入缺少评论或榜单变化，不要臆测具体读者反馈，只能从文本元素和榜单位置保守推断。

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
