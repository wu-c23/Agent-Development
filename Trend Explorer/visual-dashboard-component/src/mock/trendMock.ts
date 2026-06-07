import type { TrendDashboardData } from "../api/trendApi";

export const trendMock: TrendDashboardData = {
  generatedAt: "2026-05-29T09:30:00+08:00",
  summary:
    "全标签热度趋势仅统计历史月票榜，并按作品月票总数贡献到该作品的所有标签；当前榜单只用于作品榜和平台概览。流派趋势改为逐月词云，对比玄幻、系统流、家族群像等流派在月票榜中的重心变化。",
  metrics: [
    {
      id: "hot-tags",
      label: "细标签数",
      value: "52",
      delta: 18.4,
      tone: "green"
    },
    {
      id: "rising-works",
      label: "上升作品",
      value: "168",
      delta: 21.7,
      tone: "amber"
    },
    {
      id: "platforms",
      label: "监测平台",
      value: "1",
      deltaLabel: "纵横中文网",
      tone: "blue"
    },
    {
      id: "migration",
      label: "流派月份",
      value: "5",
      delta: 9.1,
      tone: "rose"
    }
  ],
  dataQuality: {
    requiredMonths: ["20261", "20262", "20263", "20264", "20265"],
    missingMonths: [],
    incompleteMonths: [],
    isComplete: true,
    note: "月票趋势仅使用带 month 参数的历史月票榜记录，详情页只补充细标签。",
    months: [
      { month: "20261", label: "2026年01月", records: 200, uniqueWorks: 200, tagCount: 160, heatTotal: 980000, heatTotalK: 980, expectedRecords: 200, complete: true },
      { month: "20262", label: "2026年02月", records: 200, uniqueWorks: 200, tagCount: 160, heatTotal: 1025000, heatTotalK: 1025, expectedRecords: 200, complete: true },
      { month: "20263", label: "2026年03月", records: 200, uniqueWorks: 200, tagCount: 160, heatTotal: 1102000, heatTotalK: 1102, expectedRecords: 200, complete: true },
      { month: "20264", label: "2026年04月", records: 200, uniqueWorks: 200, tagCount: 160, heatTotal: 1188000, heatTotalK: 1188, expectedRecords: 200, complete: true },
      { month: "20265", label: "2026年05月", records: 200, uniqueWorks: 200, tagCount: 160, heatTotal: 1240000, heatTotalK: 1240, expectedRecords: 200, complete: true }
    ]
  },
  heatCurve: {
    dates: ["01月", "02月", "03月", "04月", "05月"],
    series: [
      {
        name: "传统玄幻",
        data: [72, 78, 84, 91, 96],
        description: "纵横月票榜中长期基本盘，强设定、升级体系和高燃战斗仍是主轴。"
      },
      {
        name: "家族崛起",
        data: [38, 46, 59, 77, 92],
        description: "从单主角爽点转向宗族、血脉、群像共振，近期上升速度最快。"
      },
      {
        name: "热血",
        data: [68, 71, 77, 84, 92],
        description: "常与传统玄幻、剑道、少年成长并存，是详情页高频细标签。"
      },
      {
        name: "剑道",
        data: [54, 62, 70, 82, 90],
        description: "兼具成长线、战斗爽点和辨识度，适合做细分推荐入口。"
      },
      {
        name: "群像",
        data: [42, 49, 58, 74, 88],
        description: "读者对多角色并肩、家族团队和势力成长的接受度提升。"
      },
      {
        name: "轻量金手指",
        data: [36, 45, 63, 79, 84],
        description: "系统流的显性机制变轻，转向低解释成本的能力或物件设定。"
      },
      {
        name: "规则怪谈",
        data: [51, 55, 68, 73, 70],
        description: "仍有讨论度，但在本轮纵横榜单中不是最强增长项。"
      },
      {
        name: "废土生存",
        data: [57, 55, 52, 50, 47],
        description: "热度有回落迹象，部分悬疑压力感被规则怪谈和副本结构吸收。"
      }
    ],
    unit: "k",
    source: "monthly-ticket",
    valueLabel: "月票"
  },
  hotTags: [
    {
      tag: "传统玄幻",
      heat: 96,
      change: 14.2,
      group: "题材",
      stage: "stable",
      relatedWorks: ["齐天", "无敌天命", "星辰大道"]
    },
    {
      tag: "家族崛起",
      heat: 92,
      change: 28.4,
      group: "作品元素",
      stage: "rising",
      relatedWorks: ["齐天", "帝族长歌"]
    },
    {
      tag: "热血",
      heat: 92,
      change: 16.8,
      group: "情绪价值",
      stage: "rising",
      relatedWorks: ["齐天", "无敌天命"]
    },
    {
      tag: "剑道",
      heat: 90,
      change: 15.1,
      group: "战斗元素",
      stage: "rising",
      relatedWorks: ["齐天", "一剑镇山河"]
    },
    {
      tag: "少年",
      heat: 89,
      change: 13.7,
      group: "人设",
      stage: "rising",
      relatedWorks: ["齐天", "万古少年游"]
    },
    {
      tag: "群像",
      heat: 88,
      change: 22.5,
      group: "叙事结构",
      stage: "rising",
      relatedWorks: ["星辰大道", "众仙俯首"]
    },
    {
      tag: "轻量金手指",
      heat: 84,
      change: 24.6,
      group: "能力机制",
      stage: "rising",
      relatedWorks: ["无敌天命", "天命图录"]
    },
    {
      tag: "高燃",
      heat: 82,
      change: 18.9,
      group: "情绪价值",
      stage: "rising",
      relatedWorks: ["无敌天命", "齐天"]
    },
    {
      tag: "世界观",
      heat: 78,
      change: 9.3,
      group: "设定",
      stage: "stable",
      relatedWorks: ["星辰大道", "万界归墟"]
    },
    {
      tag: "成长",
      heat: 76,
      change: 7.8,
      group: "主角线",
      stage: "stable",
      relatedWorks: ["众仙俯首", "万古少年游"]
    },
    {
      tag: "反套路",
      heat: 73,
      change: 11.4,
      group: "叙事策略",
      stage: "stable",
      relatedWorks: ["众仙俯首", "我在宗门当咸鱼"]
    },
    {
      tag: "规则怪谈",
      heat: 70,
      change: -3.8,
      group: "题材",
      stage: "cooling",
      relatedWorks: ["夜行规则"]
    },
    {
      tag: "副本",
      heat: 67,
      change: 5.5,
      group: "结构",
      stage: "stable",
      relatedWorks: ["夜行规则", "诡门十日"]
    },
    {
      tag: "废土生存",
      heat: 47,
      change: -8.2,
      group: "题材",
      stage: "cooling",
      relatedWorks: ["荒原纪元"]
    },
    {
      tag: "女强逆袭",
      heat: 58,
      change: 6.8,
      group: "人设",
      stage: "stable",
      relatedWorks: ["凤临九天"]
    },
    {
      tag: "都市异能",
      heat: 49,
      change: 2.4,
      group: "题材",
      stage: "stable",
      relatedWorks: ["都市灵能局"]
    }
  ],
  platformCompare: [
    {
      platform: "纵横中文网",
      heat: 92,
      works: 820,
      topTags: ["传统玄幻", "热血", "家族崛起", "剑道", "群像"],
      status: "active"
    }
  ],
  wordCloud: [
    { name: "传统玄幻", value: 96 },
    { name: "家族崛起", value: 92 },
    { name: "热血", value: 92 },
    { name: "剑道", value: 90 },
    { name: "少年", value: 89 },
    { name: "群像并肩", value: 88 },
    { name: "轻量金手指", value: 84 },
    { name: "高燃", value: 82 },
    { name: "世界观", value: 78 },
    { name: "成长", value: 76 },
    { name: "反套路", value: 73 },
    { name: "规则限制", value: 70 },
    { name: "副本", value: 67 },
    { name: "权谋博弈", value: 61 },
    { name: "女强逆袭", value: 58 },
    { name: "废土生存", value: 47 },
    { name: "都市异能", value: 49 },
    { name: "无限流", value: 43 },
    { name: "情绪治愈", value: 39 },
    { name: "宗门经营", value: 37 },
    { name: "凡人流", value: 46 },
    { name: "诡异复苏", value: 50 }
  ],
  migration: {
    nodes: [
      { name: "传统升级流" },
      { name: "反套路群像流" },
      { name: "系统流" },
      { name: "轻量金手指" },
      { name: "废土生存" },
      { name: "规则怪谈" },
      { name: "单主角爽文" },
      { name: "家族崛起群像" },
      { name: "门派经营" },
      { name: "宗族势力经营" },
      { name: "单线复仇" },
      { name: "权谋博弈" }
    ],
    links: [
      {
        source: "传统升级流",
        target: "反套路群像流",
        value: 18,
        change: 9.4,
        reason: "传统修炼阶梯仍有效，但读者更希望看到多角色并肩和反预期推进。"
      },
      {
        source: "系统流",
        target: "轻量金手指",
        value: 24,
        change: 14.8,
        reason: "显性任务面板减少，能力来源更轻，减少解释成本并提高进入速度。"
      },
      {
        source: "废土生存",
        target: "规则怪谈",
        value: 13,
        change: -2.1,
        reason: "高压生存感被规则限制、副本博弈和悬疑反转重新包装。"
      },
      {
        source: "单主角爽文",
        target: "家族崛起群像",
        value: 22,
        change: 19.3,
        reason: "爽点从个人压制扩展为家族、宗族和势力共同抬升。"
      },
      {
        source: "门派经营",
        target: "宗族势力经营",
        value: 15,
        change: 11.6,
        reason: "经营线与血脉、祖地、帝族背景结合，形成更强身份认同。"
      },
      {
        source: "单线复仇",
        target: "权谋博弈",
        value: 10,
        change: 4.2,
        reason: "复仇目标不再只是打脸，更多进入势力对抗和长线布局。"
      }
    ]
  },
  migrationTimeline: {
    periods: ["01月", "02月", "03月", "04月", "05月"],
    flows: [
      {
        id: "upgrade-to-ensemble",
        source: "传统升级流",
        target: "反套路群像流",
        values: [8, 10, 13, 16, 18],
        reason: "从单线升级转向多角色并肩，读者更关注团队关系和反预期推进。"
      },
      {
        id: "system-to-light-cheat",
        source: "系统流",
        target: "轻量金手指",
        values: [7, 11, 16, 21, 24],
        reason: "系统提示减少，能力设定更轻，保留爽点但降低阅读门槛。"
      },
      {
        id: "wasteland-to-rules",
        source: "废土生存",
        target: "规则怪谈",
        values: [13, 15, 16, 15, 13],
        reason: "高压生存感转向规则限制和副本博弈，但近期增速放缓。"
      },
      {
        id: "solo-to-clan",
        source: "单主角爽文",
        target: "家族崛起群像",
        values: [6, 9, 14, 19, 22],
        reason: "爽点从主角个人抬升扩展到家族、血脉和势力共同成长。"
      },
      {
        id: "sect-to-clan-operation",
        source: "门派经营",
        target: "宗族势力经营",
        values: [5, 7, 10, 13, 15],
        reason: "经营线叠加宗族身份认同，更适合长线榜单留存。"
      },
      {
        id: "revenge-to-politics",
        source: "单线复仇",
        target: "权谋博弈",
        values: [4, 5, 7, 8, 10],
        reason: "复仇目标被更长线的势力布局和权谋博弈吸收。"
      }
    ]
  },
  genreCloudTimeline: {
    periods: ["01月", "02月", "03月", "04月", "05月"],
    unit: "k",
    summary: "逐月词云显示，月票榜流派重心从传统玄幻的稳定基本盘，逐步扩展到家族群像流和轻量金手指。",
    clouds: [
      {
        period: "01月",
        genres: [
          { name: "传统玄幻", value: 128 },
          { name: "都市爽文", value: 74 },
          { name: "仙侠修真", value: 62 },
          { name: "系统流", value: 49 },
          { name: "规则怪谈", value: 42 },
          { name: "家族群像流", value: 36 }
        ]
      },
      {
        period: "02月",
        genres: [
          { name: "传统玄幻", value: 136 },
          { name: "都市爽文", value: 78 },
          { name: "系统流", value: 61 },
          { name: "仙侠修真", value: 59 },
          { name: "规则怪谈", value: 47 },
          { name: "家族群像流", value: 44 }
        ]
      },
      {
        period: "03月",
        genres: [
          { name: "传统玄幻", value: 151 },
          { name: "系统流", value: 82 },
          { name: "家族群像流", value: 72 },
          { name: "都市爽文", value: 69 },
          { name: "规则怪谈", value: 55 },
          { name: "仙侠修真", value: 54 }
        ]
      },
      {
        period: "04月",
        genres: [
          { name: "传统玄幻", value: 168 },
          { name: "家族群像流", value: 106 },
          { name: "系统流", value: 98 },
          { name: "仙侠修真", value: 63 },
          { name: "规则怪谈", value: 58 },
          { name: "都市爽文", value: 57 }
        ]
      },
      {
        period: "05月",
        genres: [
          { name: "传统玄幻", value: 181 },
          { name: "家族群像流", value: 132 },
          { name: "系统流", value: 111 },
          { name: "仙侠修真", value: 69 },
          { name: "规则怪谈", value: 53 },
          { name: "都市爽文", value: 49 }
        ]
      }
    ]
  },
  risingWorks: [
    {
      id: "zh-1435440",
      title: "齐天",
      author: "日落红尘",
      platform: "纵横中文网",
      category: "玄幻奇幻",
      tags: ["玄幻奇幻", "热血", "剑道", "少年", "传统玄幻", "家族崛起"],
      detailUrl: "https://www.zongheng.com/detail/1435440",
      rank: 1,
      rankChange: 19,
      heatScore: 96,
      listType: "月票榜-2026年05月",
      summary: "以帝族、守灵人和群像并肩为核心，强化传统玄幻的高燃战斗和家族崛起爽点。",
      capturedAt: "2026-05-29T09:10:00+08:00"
    },
    {
      id: "zh-1336976",
      title: "无敌天命",
      author: "青鸾峰上",
      platform: "纵横中文网",
      category: "玄幻奇幻",
      tags: ["玄幻奇幻", "无敌流", "热血", "强者成长", "高燃", "爽文"],
      detailUrl: "https://www.zongheng.com/detail/1336976",
      rank: 2,
      rankChange: 12,
      heatScore: 90,
      listType: "月票榜-2026年05月",
      summary: "以高燃战斗和强者成长驱动榜单热度，适合与传统玄幻、轻量金手指标签联动。",
      capturedAt: "2026-05-29T09:10:00+08:00"
    },
    {
      id: "zh-1385191",
      title: "星辰大道",
      author: "随散飘风",
      platform: "纵横中文网",
      category: "玄幻奇幻",
      tags: ["玄幻奇幻", "世界观", "群像", "长线剧情", "星空", "成长"],
      detailUrl: "https://www.zongheng.com/detail/1385191",
      rank: 4,
      rankChange: 9,
      heatScore: 84,
      listType: "点击榜",
      summary: "世界观与长线剧情驱动，适合观察群像和宏大叙事的稳定热度。",
      capturedAt: "2026-05-29T09:10:00+08:00"
    },
    {
      id: "zh-1410173",
      title: "众仙俯首",
      author: "咸鱼老白",
      platform: "纵横中文网",
      category: "武侠仙侠",
      tags: ["武侠仙侠", "仙侠", "反套路", "成长", "群像"],
      detailUrl: "https://www.zongheng.com/detail/1410173",
      rank: 7,
      rankChange: 8,
      heatScore: 78,
      listType: "推荐榜",
      summary: "以仙侠反套路和成长线切入，补足传统玄幻之外的仙侠趋势观察。",
      capturedAt: "2026-05-29T09:10:00+08:00"
    },
    {
      id: "mock-empire",
      title: "帝族长歌",
      author: "观海听雷",
      platform: "纵横中文网",
      category: "玄幻奇幻",
      tags: ["玄幻奇幻", "家族崛起", "宗族势力", "权谋博弈", "群像", "热血"],
      rank: 11,
      rankChange: 7,
      heatScore: 76,
      listType: "月票榜-2026年04月",
      summary: "家族崛起与权谋博弈结合，代表宗族势力经营的上升方向。",
      capturedAt: "2026-05-29T09:10:00+08:00"
    },
    {
      id: "mock-sword",
      title: "一剑镇山河",
      author: "长夜照雪",
      platform: "纵横中文网",
      category: "玄幻奇幻",
      tags: ["玄幻奇幻", "剑道", "少年", "热血", "成长", "高燃"],
      rank: 15,
      rankChange: 6,
      heatScore: 73,
      listType: "推荐榜",
      summary: "剑道和少年成长高度绑定，适合观察细标签如何影响推荐解释。",
      capturedAt: "2026-05-29T09:10:00+08:00"
    },
    {
      id: "mock-rule",
      title: "夜行规则",
      author: "渡鸦灯",
      platform: "纵横中文网",
      category: "悬疑灵异",
      tags: ["悬疑灵异", "规则怪谈", "副本", "生存博弈", "反转"],
      rank: 22,
      rankChange: 3,
      heatScore: 68,
      listType: "点击榜",
      summary: "规则怪谈仍有讨论度，但相对传统玄幻的增速偏弱。",
      capturedAt: "2026-05-29T09:10:00+08:00"
    }
  ]
};
