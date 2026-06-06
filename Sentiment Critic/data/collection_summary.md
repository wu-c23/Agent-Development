# Data Collection Summary

Generated at: 2026-06-06T16:16:56+08:00

Scope: main coverage statistics use formal collection outputs under `Sentiment Critic/data/runs/*.jsonl`. Root-level JSONL files under `Sentiment Critic/data/*.jsonl` are listed separately as seed/sample/test data.

## Overall Coverage
| Metric | Value |
| --- | --- |
| Indexed books in `data/novels.json` | 1631 |
| Collected books in `data/runs` | 311 |
| Collected indexed books | 310 |
| Collected extra books not in `novels.json` | 1 |
| Uncovered indexed books | 1321 |
| Indexed-book coverage rate | 19.01% |
| Run JSONL files | 334 |
| Run JSONL files with records | 333 |
| Run raw review records | 1343 |
| Run de-duplicated review records | 1306 |
| Invalid JSONL lines in runs | 0 |

## Platform Summary (`data/runs`)
| Platform | Covered books | Raw records | Dedup records |
| --- | --- | --- | --- |
| douban | 19 | 190 | 153 |
| tieba | 309 | 1153 | 1153 |

## Full Batch Manifests
| Batch | Candidates | Collected books | Skipped existing | Empty | No subject | Errors | New raw reviews | Finished at |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| tieba aiotieba full run | 1631 | 307 | 3 | 1321 | 0 | 0 | 1147 | 2026-06-06T13:13:39+08:00 |
| douban subject_suggest full run | 1631 | 14 | 4 | 18 | 1595 | 0 | 97 | 2026-06-06T16:08:44+08:00 |

## Root-Level JSONL Files (`data/*.jsonl`)
| Metric | Value |
| --- | --- |
| Root JSONL files | 3 |
| Root raw review records | 61 |
| Root de-duplicated review records | 61 |
| Root covered books | 2 |
| File | Records | Platforms | Top books |
| --- | --- | --- | --- |
| raw_reviews.jsonl | 51 | douban:25, tieba:26 | 斗罗大陆 |
| sample_reviews.jsonl | 5 | douban:2, tieba:2, xiaohongshu:1 | 诡秘之主 |
| tieba_aiotieba_test.jsonl | 5 | tieba:5 | 诡秘之主 |

## Book Coverage (`data/runs`)
| Book | Raw records | Dedup records | Raw by platform | Dedup by platform |
| --- | --- | --- | --- | --- |
| 剑来 | 39 | 22 | douban:34, tieba:5 | douban:17, tieba:5 |
| 诡秘之主 | 35 | 25 | douban:34, tieba:1 | douban:24, tieba:1 |
| 逆天邪神 | 19 | 9 | douban:15, tieba:4 | douban:5, tieba:4 |
| 宰执天下 | 15 | 15 | douban:10, tieba:5 | douban:10, tieba:5 |
| 武夫 | 15 | 15 | douban:10, tieba:5 | douban:10, tieba:5 |
| 玲珑塔 | 15 | 15 | douban:10, tieba:5 | douban:10, tieba:5 |
| 罗浮 | 15 | 15 | douban:10, tieba:5 | douban:10, tieba:5 |
| 登天 | 14 | 14 | douban:10, tieba:4 | douban:10, tieba:4 |
| 永夜君王 | 13 | 13 | douban:8, tieba:5 | douban:8, tieba:5 |
| 雪中悍刀行 | 13 | 13 | douban:10, tieba:3 | douban:10, tieba:3 |
| 摘星 | 11 | 11 | douban:10, tieba:1 | douban:10, tieba:1 |
| 天神下凡 | 8 | 8 | douban:3, tieba:5 | douban:3, tieba:5 |
| 最高权力 | 8 | 8 | douban:7, tieba:1 | douban:7, tieba:1 |
| 匠心 | 7 | 7 | douban:2, tieba:5 | douban:2, tieba:5 |
| 西望 | 7 | 7 | douban:5, tieba:2 | douban:5, tieba:2 |
| 过河卒 | 6 | 6 | douban:1, tieba:5 | douban:1, tieba:5 |
| 万域之王 | 5 | 5 | tieba:5 | tieba:5 |
| 三国之争霸天下 | 5 | 5 | tieba:5 | tieba:5 |
| 上门龙婿 | 5 | 5 | tieba:5 | tieba:5 |
| 不死帝尊 | 5 | 5 | tieba:5 | tieba:5 |
| 不让江山 | 5 | 5 | tieba:5 | tieba:5 |
| 九天剑主 | 5 | 5 | tieba:5 | tieba:5 |
| 九阴九阳 | 5 | 5 | tieba:5 | tieba:5 |
| 书剑长安 | 5 | 5 | tieba:5 | tieba:5 |
| 争霸天下 | 5 | 5 | tieba:5 | tieba:5 |
| 五仙门 | 5 | 5 | tieba:5 | tieba:5 |
| 人间最得意 | 5 | 5 | tieba:5 | tieba:5 |
| 仙侣 | 5 | 5 | tieba:5 | tieba:5 |
| 仙帝归来 | 5 | 5 | tieba:5 | tieba:5 |
| 仙都 | 5 | 5 | tieba:5 | tieba:5 |
| 仙魔变 | 5 | 5 | tieba:5 | tieba:5 |
| 众仙俯首 | 5 | 5 | tieba:5 | tieba:5 |
| 修真狂少 | 5 | 5 | tieba:5 | tieba:5 |
| 元尊 | 5 | 5 | tieba:5 | tieba:5 |
| 全球灾变之末日游戏 | 5 | 5 | tieba:5 | tieba:5 |
| 凡尘飞仙 | 5 | 5 | tieba:5 | tieba:5 |
| 剑帝 | 5 | 5 | tieba:5 | tieba:5 |
| 剑王朝 | 5 | 5 | tieba:5 | tieba:5 |
| 剑道第一仙 | 5 | 5 | tieba:5 | tieba:5 |
| 剑骨 | 5 | 5 | tieba:5 | tieba:5 |
| 医品宗师 | 5 | 5 | tieba:5 | tieba:5 |
| 十代掌门 | 5 | 5 | tieba:5 | tieba:5 |
| 十国千娇 | 5 | 5 | tieba:5 | tieba:5 |
| 十方乾坤 | 5 | 5 | tieba:5 | tieba:5 |
| 却道寻常 | 5 | 5 | tieba:5 | tieba:5 |
| 吞天决 | 5 | 5 | tieba:5 | tieba:5 |
| 吞天圣帝 | 5 | 5 | tieba:5 | tieba:5 |
| 吞海 | 5 | 5 | tieba:5 | tieba:5 |
| 四界之歌 | 5 | 5 | tieba:5 | tieba:5 |
| 国王万岁 | 5 | 5 | tieba:5 | tieba:5 |
| 圣王 | 5 | 5 | tieba:5 | tieba:5 |
| 大周王侯 | 5 | 5 | tieba:5 | tieba:5 |
| 大明1617 | 5 | 5 | tieba:5 | tieba:5 |
| 大明春色 | 5 | 5 | douban:1, tieba:4 | douban:1, tieba:4 |
| 大魔仙 | 5 | 5 | tieba:5 | tieba:5 |
| 天上白玉京 | 5 | 5 | tieba:5 | tieba:5 |
| 天刑纪 | 5 | 5 | tieba:5 | tieba:5 |
| 天工 | 5 | 5 | tieba:5 | tieba:5 |
| 天灾 | 5 | 5 | tieba:5 | tieba:5 |
| 天骄战纪 | 5 | 5 | tieba:5 | tieba:5 |
| 太平客栈 | 5 | 5 | tieba:5 | tieba:5 |
| 寒门仕子 | 5 | 5 | tieba:5 | tieba:5 |
| 寒门枭士 | 5 | 5 | tieba:5 | tieba:5 |
| 寻宝全世界 | 5 | 5 | tieba:5 | tieba:5 |
| 帝世无双 | 5 | 5 | tieba:5 | tieba:5 |
| 开个诊所来修仙 | 5 | 5 | tieba:5 | tieba:5 |
| 开局养成圣女，我靠多子多福争霸天下 | 5 | 5 | tieba:5 | tieba:5 |
| 异界之公主鉴赏专家 | 5 | 5 | tieba:5 | tieba:5 |
| 憋宝人 | 5 | 5 | tieba:5 | tieba:5 |
| 我有一剑 | 5 | 5 | tieba:5 | tieba:5 |
| 斗罗大陆 | 5 | 5 | douban:5 | douban:5 |
| 斩妖 | 5 | 5 | tieba:5 | tieba:5 |
| 新宋 | 5 | 5 | tieba:5 | tieba:5 |
| 无仙 | 5 | 5 | tieba:5 | tieba:5 |
| 无尽海图 | 5 | 5 | tieba:5 | tieba:5 |
| 无敌剑域 | 5 | 5 | tieba:5 | tieba:5 |
| 无敌剑魂 | 5 | 5 | tieba:5 | tieba:5 |
| 无敌天命 | 5 | 5 | tieba:5 | tieba:5 |
| 明末求生记 | 5 | 5 | tieba:5 | tieba:5 |
| 星河大帝 | 5 | 5 | tieba:5 | tieba:5 |
| 星辰大道 | 5 | 5 | tieba:5 | tieba:5 |
| 春梦无痕 | 5 | 5 | tieba:5 | tieba:5 |
| 最强战神 | 5 | 5 | tieba:5 | tieba:5 |
| 最强武神 | 5 | 5 | tieba:5 | tieba:5 |
| 末日之无上王座 | 5 | 5 | tieba:5 | tieba:5 |
| 末日崛起 | 5 | 5 | tieba:5 | tieba:5 |
| 末日边缘 | 5 | 5 | tieba:5 | tieba:5 |
| 权力巅峰 | 5 | 5 | tieba:5 | tieba:5 |
| 权臣 | 5 | 5 | tieba:5 | tieba:5 |
| 极品神眼 | 5 | 5 | tieba:5 | tieba:5 |
| 极道剑尊 | 5 | 5 | tieba:5 | tieba:5 |
| 桃花劫 | 5 | 5 | tieba:5 | tieba:5 |
| 楚臣 | 5 | 5 | tieba:5 | tieba:5 |
| 武神 | 5 | 5 | tieba:5 | tieba:5 |
| 民间诡闻实录 | 5 | 5 | tieba:5 | tieba:5 |
| 灭神 | 5 | 5 | tieba:5 | tieba:5 |
| 灰烬领主 | 5 | 5 | tieba:5 | tieba:5 |
| 特种兵王 | 5 | 5 | tieba:5 | tieba:5 |
| 狂傲为仙 | 5 | 5 | tieba:5 | tieba:5 |
| 玄龙战神 | 5 | 5 | tieba:5 | tieba:5 |
| 盖世 | 5 | 5 | tieba:5 | tieba:5 |
| 盖世帝尊 | 5 | 5 | tieba:5 | tieba:5 |
| 真灵九变 | 5 | 5 | tieba:5 | tieba:5 |
| 神国之上 | 5 | 5 | tieba:5 | tieba:5 |
| 符篆苍穹 | 5 | 5 | tieba:5 | tieba:5 |
| 第一氏族 | 5 | 5 | tieba:5 | tieba:5 |
| 繁星书士 | 5 | 5 | tieba:5 | tieba:5 |
| 绝世小仙医 | 5 | 5 | tieba:5 | tieba:5 |
| 绝世邪神 | 5 | 5 | tieba:5 | tieba:5 |
| 网游之剑刃舞者 | 5 | 5 | tieba:5 | tieba:5 |
| 老实人逆袭2003 | 5 | 5 | tieba:5 | tieba:5 |
| 至尊剑帝 | 5 | 5 | tieba:5 | tieba:5 |
| 诡秘之上 | 5 | 5 | tieba:5 | tieba:5 |
| 赘婿出山 | 5 | 5 | tieba:5 | tieba:5 |
| 超奥特传记 | 5 | 5 | tieba:5 | tieba:5 |
| 超神玩家 | 5 | 5 | tieba:5 | tieba:5 |
| 跃马大唐 | 5 | 5 | tieba:5 | tieba:5 |
| 跃马大明 | 5 | 5 | tieba:5 | tieba:5 |
| 踏天争仙 | 5 | 5 | tieba:5 | tieba:5 |
| 踏星 | 5 | 5 | tieba:5 | tieba:5 |
| 逆鳞 | 5 | 5 | tieba:5 | tieba:5 |
| 道诡异仙 | 5 | 5 | douban:5 | douban:5 |
| 都市极品仙帝 | 5 | 5 | tieba:5 | tieba:5 |
| 都市潜龙 | 5 | 5 | tieba:5 | tieba:5 |
| 都市超级高手 | 5 | 5 | tieba:5 | tieba:5 |
| 重生之老婆爱上我 | 5 | 5 | tieba:5 | tieba:5 |
| 重生贾环 | 5 | 5 | tieba:5 | tieba:5 |
| 长宁帝军 | 5 | 5 | tieba:5 | tieba:5 |
| 问镜 | 5 | 5 | tieba:5 | tieba:5 |
| 阴神 | 5 | 5 | tieba:5 | tieba:5 |
| 阴阳石 | 5 | 5 | tieba:5 | tieba:5 |
| 阴阳鼎 | 5 | 5 | tieba:5 | tieba:5 |
| 陆地键仙 | 5 | 5 | tieba:5 | tieba:5 |
| 陌上行 | 5 | 5 | tieba:5 | tieba:5 |
| 骑士征程 | 5 | 5 | tieba:5 | tieba:5 |
| 魔法学院的闪现天才 | 5 | 5 | tieba:5 | tieba:5 |
| 齐天 | 5 | 5 | tieba:5 | tieba:5 |
| 龙符 | 5 | 5 | tieba:5 | tieba:5 |
| 一世独尊 | 4 | 4 | tieba:4 | tieba:4 |
| 一剑独尊 | 4 | 4 | tieba:4 | tieba:4 |
| 万古剑尊 | 4 | 4 | tieba:4 | tieba:4 |
| 万古龙帝 | 4 | 4 | tieba:4 | tieba:4 |
| 万界仙王 | 4 | 4 | tieba:4 | tieba:4 |
| 不负韶华 | 4 | 4 | tieba:4 | tieba:4 |
| 世界又又又毁灭了 | 4 | 4 | tieba:4 | tieba:4 |
| 九星杀神 | 4 | 4 | tieba:4 | tieba:4 |
| 九阳武神 | 4 | 4 | tieba:4 | tieba:4 |
| 仙朝 | 4 | 4 | tieba:4 | tieba:4 |
| 全军列阵 | 4 | 4 | tieba:4 | tieba:4 |
| 农女医妃别太甜 | 4 | 4 | tieba:4 | tieba:4 |
| 凡徒 | 4 | 4 | tieba:4 | tieba:4 |
| 凶灵秘闻录 | 4 | 4 | tieba:4 | tieba:4 |
| 剑仙在此 | 4 | 4 | tieba:4 | tieba:4 |
| 剑道通神 | 4 | 4 | tieba:4 | tieba:4 |
| 十方神王 | 4 | 4 | tieba:4 | tieba:4 |
| 双衍纪 | 4 | 4 | tieba:4 | tieba:4 |
| 大明烟火 | 4 | 4 | tieba:4 | tieba:4 |
| 大逆之门 | 4 | 4 | tieba:4 | tieba:4 |
| 大道问鼎 | 4 | 4 | tieba:4 | tieba:4 |
| 大魏芳华 | 4 | 4 | tieba:4 | tieba:4 |
| 天道天骄 | 4 | 4 | tieba:4 | tieba:4 |
| 妙医鸿途 | 4 | 4 | tieba:4 | tieba:4 |
| 将军好凶猛 | 4 | 4 | tieba:4 | tieba:4 |
| 小爷江湖走一遭 | 4 | 4 | tieba:4 | tieba:4 |
| 巴山剑场 | 4 | 4 | tieba:4 | tieba:4 |
| 平天策 | 4 | 4 | tieba:4 | tieba:4 |
| 我不会武功 | 4 | 4 | tieba:4 | tieba:4 |
| 我体内有个修仙界 | 4 | 4 | tieba:4 | tieba:4 |
| 我只有两千五百岁 | 4 | 4 | tieba:4 | tieba:4 |
| 我捡到仙瓶以后 | 4 | 4 | tieba:4 | tieba:4 |
| 我有一座随身农场 | 4 | 4 | tieba:4 | tieba:4 |
| 探宝修真在都市 | 4 | 4 | tieba:4 | tieba:4 |
| 时空法则 | 4 | 4 | tieba:4 | tieba:4 |
| 星海王座 | 4 | 4 | tieba:4 | tieba:4 |
| 星辰之主 | 4 | 4 | tieba:4 | tieba:4 |
| 暗体 | 4 | 4 | tieba:4 | tieba:4 |
| 最强狂兵 | 4 | 4 | tieba:4 | tieba:4 |
| 望仙门 | 4 | 4 | tieba:4 | tieba:4 |
| 末日城邦 | 4 | 4 | tieba:4 | tieba:4 |
| 极品太子爷 | 4 | 4 | tieba:4 | tieba:4 |
| 枭臣 | 4 | 4 | tieba:4 | tieba:4 |
| 毁灭游戏 | 4 | 4 | tieba:4 | tieba:4 |
| 混沌天尊 | 4 | 4 | tieba:4 | tieba:4 |
| 特战之王 | 4 | 4 | tieba:4 | tieba:4 |
| 白夜浮生录 | 4 | 4 | tieba:4 | tieba:4 |
| 盖世人王 | 4 | 4 | tieba:4 | tieba:4 |
| 绝世强龙 | 4 | 4 | tieba:4 | tieba:4 |
| 绝世神医 | 4 | 4 | tieba:4 | tieba:4 |
| 缥缈寻仙传 | 4 | 4 | tieba:4 | tieba:4 |
| 网游之剑逝 | 4 | 4 | tieba:4 | tieba:4 |
| 诸仙 | 4 | 4 | tieba:4 | tieba:4 |
| 负鼎 | 4 | 4 | tieba:4 | tieba:4 |
| 超能星武 | 4 | 4 | tieba:4 | tieba:4 |
| 踏路追仙传 | 4 | 4 | tieba:4 | tieba:4 |
| 这个世界很危险 | 4 | 4 | tieba:4 | tieba:4 |
| 逆命相师 | 4 | 4 | tieba:4 | tieba:4 |
| 通天剑帝 | 4 | 4 | tieba:4 | tieba:4 |
| 道印 | 4 | 4 | tieba:4 | tieba:4 |
| 道断修罗 | 4 | 4 | tieba:4 | tieba:4 |
| 道爷不好惹 | 4 | 4 | tieba:4 | tieba:4 |
| 都市最强仙医 | 4 | 4 | tieba:4 | tieba:4 |
| 都市绝品仙医 | 4 | 4 | tieba:4 | tieba:4 |
| 都市隐龙 | 4 | 4 | tieba:4 | tieba:4 |
| 金币即是正义 | 4 | 4 | tieba:4 | tieba:4 |
| 钧天图 | 4 | 4 | tieba:4 | tieba:4 |
| 问道红尘 | 4 | 4 | tieba:4 | tieba:4 |
| 阴阳同修 | 4 | 4 | tieba:4 | tieba:4 |
| 雄宋 | 4 | 4 | tieba:4 | tieba:4 |
| 风云龙婿 | 4 | 4 | tieba:4 | tieba:4 |
| 黑雾之下 | 4 | 4 | tieba:4 | tieba:4 |
| 不死邪神 | 3 | 3 | tieba:3 | tieba:3 |
| 不败战神 | 3 | 3 | tieba:3 | tieba:3 |
| 仙侠世界 | 3 | 3 | tieba:3 | tieba:3 |
| 仙武同修 | 3 | 3 | tieba:3 | tieba:3 |
| 仙路至尊 | 3 | 3 | tieba:3 | tieba:3 |
| 原血神座 | 3 | 3 | tieba:3 | tieba:3 |
| 大荒蛮神 | 3 | 3 | tieba:3 | tieba:3 |
| 大道青帝 | 3 | 3 | tieba:3 | tieba:3 |
| 天黑请点灯 | 3 | 3 | tieba:3 | tieba:3 |
| 崩仙逆道 | 3 | 3 | tieba:3 | tieba:3 |
| 帝道独尊 | 3 | 3 | tieba:3 | tieba:3 |
| 战神殿 | 3 | 3 | tieba:3 | tieba:3 |
| 撼天 | 3 | 3 | tieba:3 | tieba:3 |
| 斗罗大陆V重生唐三 | 3 | 3 | tieba:3 | tieba:3 |
| 星河长明 | 3 | 3 | tieba:3 | tieba:3 |
| 星空纪元 | 3 | 3 | tieba:3 | tieba:3 |
| 星际猎人 | 3 | 3 | tieba:3 | tieba:3 |
| 暗涌 | 3 | 3 | tieba:3 | tieba:3 |
| 最强末世进化 | 3 | 3 | tieba:3 | tieba:3 |
| 末日岩帝 | 3 | 3 | tieba:3 | tieba:3 |
| 此地有妖气 | 3 | 3 | tieba:3 | tieba:3 |
| 武逆九千界 | 3 | 3 | tieba:3 | tieba:3 |
| 混沌剑帝 | 3 | 3 | tieba:3 | tieba:3 |
| 王牌保镖 | 3 | 3 | tieba:3 | tieba:3 |
| 界起通天 | 3 | 3 | tieba:3 | tieba:3 |
| 神奇道具师 | 3 | 3 | tieba:3 | tieba:3 |
| 神级奶爸 | 3 | 3 | tieba:3 | tieba:3 |
| 祭炼山河 | 3 | 3 | tieba:3 | tieba:3 |
| 符皇 | 3 | 3 | tieba:3 | tieba:3 |
| 绝世神皇 | 3 | 3 | tieba:3 | tieba:3 |
| 藏剑江南 | 3 | 3 | tieba:3 | tieba:3 |
| 都市古仙医 | 3 | 3 | tieba:3 | tieba:3 |
| 问天星途 | 3 | 3 | tieba:3 | tieba:3 |
| 隐动仙魔 | 3 | 3 | tieba:3 | tieba:3 |
| 青山下 | 3 | 3 | tieba:3 | tieba:3 |
| 非洲酋长 | 3 | 3 | tieba:3 | tieba:3 |
| 龙象 | 3 | 3 | tieba:3 | tieba:3 |
| 万相之王 | 2 | 2 | tieba:2 | tieba:2 |
| 世子无双 | 2 | 2 | tieba:2 | tieba:2 |
| 主宰星河 | 2 | 2 | tieba:2 | tieba:2 |
| 仙魔春秋 | 2 | 2 | tieba:2 | tieba:2 |
| 伐天记 | 2 | 2 | tieba:2 | tieba:2 |
| 出阳神 | 2 | 2 | tieba:2 | tieba:2 |
| 剑开天门 | 2 | 2 | tieba:2 | tieba:2 |
| 剑道狂仙 | 2 | 2 | tieba:2 | tieba:2 |
| 吞明 | 2 | 2 | tieba:2 | tieba:2 |
| 大至尊 | 2 | 2 | tieba:2 | tieba:2 |
| 天问九歌 | 2 | 2 | tieba:2 | tieba:2 |
| 太古神族 | 2 | 2 | tieba:2 | tieba:2 |
| 太荒吞天诀 | 2 | 2 | tieba:2 | tieba:2 |
| 好戏登场 | 2 | 2 | tieba:2 | tieba:2 |
| 御天神帝 | 2 | 2 | tieba:2 | tieba:2 |
| 我契约了我自己 | 2 | 2 | tieba:2 | tieba:2 |
| 无敌剑道 | 2 | 2 | tieba:2 | tieba:2 |
| 最狂战神 | 2 | 2 | tieba:2 | tieba:2 |
| 朝天子 | 2 | 2 | tieba:2 | tieba:2 |
| 灵域战仙 | 2 | 2 | tieba:2 | tieba:2 |
| 点道为止 | 2 | 2 | tieba:2 | tieba:2 |
| 猎天争锋 | 2 | 2 | tieba:2 | tieba:2 |
| 相逢少年时 | 2 | 2 | tieba:2 | tieba:2 |
| 神帝归来 | 2 | 2 | tieba:2 | tieba:2 |
| 第一剑仙 | 2 | 2 | tieba:2 | tieba:2 |
| 绝世强者 | 2 | 2 | tieba:2 | tieba:2 |
| 绝色生骄 | 2 | 2 | tieba:2 | tieba:2 |
| 踏天无痕 | 2 | 2 | tieba:2 | tieba:2 |
| 锦医成凰 | 2 | 2 | tieba:2 | tieba:2 |
| 龙神决 | 2 | 2 | tieba:2 | tieba:2 |
| 一语破天机 | 1 | 1 | tieba:1 | tieba:1 |
| 万仙来朝 | 1 | 1 | tieba:1 | tieba:1 |
| 万物为契 | 1 | 1 | tieba:1 | tieba:1 |
| 万道武尊 | 1 | 1 | tieba:1 | tieba:1 |
| 九天斩神诀 | 1 | 1 | tieba:1 | tieba:1 |
| 九龙吞天诀 | 1 | 1 | tieba:1 | tieba:1 |
| 其实你有一点甜 | 1 | 1 | tieba:1 | tieba:1 |
| 北冥之主 | 1 | 1 | tieba:1 | tieba:1 |
| 十国帝王 | 1 | 1 | tieba:1 | tieba:1 |
| 双生战记 | 1 | 1 | tieba:1 | tieba:1 |
| 嚣张傻婿 | 1 | 1 | tieba:1 | tieba:1 |
| 大厨小婿 | 1 | 1 | tieba:1 | tieba:1 |
| 大明1368 | 1 | 1 | tieba:1 | tieba:1 |
| 太初灵境 | 1 | 1 | tieba:1 | tieba:1 |
| 如果如果书店 | 1 | 1 | tieba:1 | tieba:1 |
| 如果时光倒流 | 1 | 1 | tieba:1 | tieba:1 |
| 帝道无疆 | 1 | 1 | tieba:1 | tieba:1 |
| 怀璧 | 1 | 1 | tieba:1 | tieba:1 |
| 悍卒斩天 | 1 | 1 | tieba:1 | tieba:1 |
| 我在大宋当提刑 | 1 | 1 | tieba:1 | tieba:1 |
| 末日孢子2 | 1 | 1 | tieba:1 | tieba:1 |
| 杨氏崛起之啃孙成仙 | 1 | 1 | tieba:1 | tieba:1 |
| 极品少帅 | 1 | 1 | tieba:1 | tieba:1 |
| 江湖枭雄 | 1 | 1 | tieba:1 | tieba:1 |
| 炮灰修仙 | 1 | 1 | tieba:1 | tieba:1 |
| 猎户出山 | 1 | 1 | tieba:1 | tieba:1 |
| 皑如山上雪 | 1 | 1 | tieba:1 | tieba:1 |
| 第一瞳术师 | 1 | 1 | tieba:1 | tieba:1 |
| 红颜劫 | 1 | 1 | tieba:1 | tieba:1 |
| 绝代玄尊 | 1 | 1 | tieba:1 | tieba:1 |
| 网游之全服公敌 | 1 | 1 | tieba:1 | tieba:1 |
| 逍遥四公子 | 1 | 1 | tieba:1 | tieba:1 |
| 逐星 | 1 | 1 | tieba:1 | tieba:1 |
| 镇山河 | 1 | 1 | tieba:1 | tieba:1 |

## Notes

- `Raw records` counts every JSONL row with non-empty content. Re-running a crawler for the same book can increase this number.
- `Dedup records` removes duplicates using book, platform, content prefix, and source URL.
- `No subject` in the Douban batch means `book.douban.com/j/subject_suggest` did not return a usable book entry for that novel title.
- `Empty` means a source entry was found or attempted, but no review passed the current content-length / review-likeness filters.
