"""Sentiment Critic Mock API Server — 符合 Data Contract v1.0。

独立于数据采集 pipeline，提供联调所需的标准 Mock 响应。

启动: uvicorn sentiment_critic.mock_server:app --port 8003
"""

from __future__ import annotations

import asyncio
import random
import time

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(
    title="Sentiment Critic Mock API",
    description="网络小说舆情分析 Mock 服务 — Sentiment Critic",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MOCK_NOVELS = [
    {
        "uid": "987a2b45c6bd2baa73d750f13daf15b63c20145de2e85fff22ada96ad3d8b27b",
        "metadata": {"title": "诡秘之主", "platform": "qidian", "last_update": "2026-06-03T12:00:00Z"},
        "sentiment_scores": {
            "overall": 9.1, "style": 9.2, "logic": 9.5,
            "character": 9.0, "update_stability": 8.8, "toxicity_index": 0.08,
        },
        "critic_summary": {
            "one_liner": "逻辑严密的克苏鲁神作，但前200页像在读说明书。",
            "pros": ["世界观构建顶级", "伏笔回收大师级", "角色智商集体在线"],
            "cons": ["开头节奏偏慢", "对轻度读者门槛较高"],
        },
        "review_stats": {
            "total_count": 1250, "positive_ratio": 0.86, "negative_ratio": 0.05,
            "source_breakdown": {"douban": 620, "tieba": 430, "xiaohongshu": 200},
        },
    },
    {
        "uid": "26d4613826eb8819a9a601cfb88eb7621b0e6cc5c46ffefa96b5dea22ca938dc",
        "metadata": {"title": "我有一座恐怖屋", "platform": "qidian", "last_update": "2026-06-02T10:00:00Z"},
        "sentiment_scores": {
            "overall": 8.5, "style": 8.0, "logic": 8.2,
            "character": 8.8, "update_stability": 9.0, "toxicity_index": 0.05,
        },
        "critic_summary": {
            "one_liner": "不吓人的恐怖小说才是好喜剧，陈歌把鬼屋经营成了迪士尼。",
            "pros": ["角色塑造鲜明", "恐怖与搞笑平衡出色", "更新稳定"],
            "cons": ["后期略有套路化", "部分副本节奏不均"],
        },
        "review_stats": {
            "total_count": 890, "positive_ratio": 0.82, "negative_ratio": 0.06,
            "source_breakdown": {"douban": 420, "tieba": 350, "xiaohongshu": 120},
        },
    },
    {
        "uid": "f551b43b941bf7f47d6006792b26da44b8554945c72766133cb0c59771f48c89",
        "metadata": {"title": "修罗武神", "platform": "qidian", "last_update": "2026-06-03T08:00:00Z"},
        "sentiment_scores": {
            "overall": 5.2, "style": 5.0, "logic": 4.0,
            "character": 3.5, "update_stability": 6.0, "toxicity_index": 0.45,
        },
        "critic_summary": {
            "one_liner": "爽是真的爽，水也是真的水，后宫像Pokemon收集图鉴。",
            "pros": ["爽点密集节奏快", "适合无脑放松"],
            "cons": ["后宫角色扁平化", "后期严重注水", "逻辑经不起推敲"],
        },
        "review_stats": {
            "total_count": 2100, "positive_ratio": 0.45, "negative_ratio": 0.35,
            "source_breakdown": {"douban": 300, "tieba": 1500, "xiaohongshu": 300},
        },
    },
    {
        "uid": "22ed60b7b27cf4c8b77c1439cb7a9d82eb4667f6eafab681bcd415e18adbd0a4",
        "metadata": {"title": "凡人修仙传", "platform": "qidian", "last_update": "2026-05-28T16:00:00Z"},
        "sentiment_scores": {
            "overall": 8.3, "style": 7.5, "logic": 9.0,
            "character": 8.5, "update_stability": 9.5, "toxicity_index": 0.10,
        },
        "critic_summary": {
            "one_liner": "凡人流教科书，韩立教你什么叫真正的'凡人'——连老婆都是分身上位的。",
            "pros": ["逻辑自洽的修仙体系", "主角智商长期在线", "完结稳定不烂尾"],
            "cons": ["前期节奏偏慢", "女主存在感薄弱"],
        },
        "review_stats": {
            "total_count": 3200, "positive_ratio": 0.80, "negative_ratio": 0.08,
            "source_breakdown": {"douban": 1800, "tieba": 1100, "xiaohongshu": 300},
        },
    },
    {
        "uid": "587986904db3db77b83e2d7b49165f2f6e9ec1b6552b621e340695f21c240d8c",
        "metadata": {"title": "仙王的日常生活", "platform": "qidian", "last_update": "2026-06-01T09:00:00Z"},
        "sentiment_scores": {
            "overall": 7.8, "style": 7.2, "logic": 6.5,
            "character": 8.0, "update_stability": 8.5, "toxicity_index": 0.12,
        },
        "critic_summary": {
            "one_liner": "仙王装高中生的日常，像拿核弹打蚊子——浪费但好笑。",
            "pros": ["轻松解压", "反套路设定有趣", "角色讨喜"],
            "cons": ["深度不足", "单元剧形式缺乏主线推进"],
        },
        "review_stats": {
            "total_count": 780, "positive_ratio": 0.78, "negative_ratio": 0.09,
            "source_breakdown": {"douban": 350, "tieba": 280, "xiaohongshu": 150},
        },
    },
]

_UID_MAP = {n["uid"]: n for n in MOCK_NOVELS}
_TITLE_MAP = {n["metadata"]["title"]: n for n in MOCK_NOVELS}


@app.middleware("http")
async def add_mock_latency(request, call_next):
    delay = random.uniform(0.05, 0.15)
    time.sleep(delay)
    response = await call_next(request)
    response.headers["X-Mock"] = "true"
    response.headers["X-Mock-Latency"] = f"{delay:.3f}s"
    return response


def _fmt(novel: dict) -> dict:
    return {
        "uid": novel["uid"],
        "metadata": novel["metadata"],
        "sentiment_scores": novel["sentiment_scores"],
        "critic_summary": novel["critic_summary"],
        "review_stats": novel["review_stats"],
    }


@app.get("/api/v1/sentiment/detail/{uid}")
async def sentiment_detail(uid: str):
    novel = _UID_MAP.get(uid)
    if novel is None:
        raise HTTPException(status_code=404, detail=f"Sentiment data not found for UID: {uid}")
    return _fmt(novel)


@app.post("/api/v1/sentiment/refresh")
async def refresh_data():
    """强制重新从磁盘加载数据。Mock 模式下刷新 Mock 缓存。"""
    return {"status": "refreshed", "index_count": len(MOCK_NOVELS)}


@app.get("/api/v1/sentiment/compare")
async def sentiment_compare(uids: str = Query(..., description="逗号分隔的 UID 列表")):
    uid_list = [u.strip() for u in uids.split(",") if u.strip()]
    if not uid_list:
        raise HTTPException(status_code=400, detail="At least one UID required")
    results = []
    for uid in uid_list:
        novel = _UID_MAP.get(uid)
        if novel:
            results.append(_fmt(novel))
        else:
            results.append({"uid": uid, "error": "not_found"})
    return results


@app.get("/api/v1/sentiment/health")
async def health():
    return {"status": "healthy", "version": "1.0.0", "index_count": len(MOCK_NOVELS)}


# ---------------------------------------------------------------------------
# 角色对话端点 (Mock)
# ---------------------------------------------------------------------------

MOCK_CHARACTERS = [
    {
        "id": "klein",
        "name": "克莱恩·莫雷蒂",
        "novel": "诡秘之主",
        "personality": ["谨慎", "冷静", "富有正义感", "轻微吐槽役"],
        "avatar_emoji": "🎩",
        "catchphrases": ["主保佑你。", "我只是一个平平无奇的占卜家。"],
    },
    {
        "id": "hanli",
        "name": "韩立",
        "novel": "凡人修仙传",
        "personality": ["谨慎", "隐忍", "务实", "低调"],
        "avatar_emoji": "🏔️",
        "catchphrases": ["修仙之道，财侣法地，缺一不可。", "韩某一介散修，不敢当此大任。"],
    },
    {
        "id": "chenge",
        "name": "陈歌",
        "novel": "我有一座恐怖屋",
        "personality": ["乐观", "幽默", "胆大心细", "脑回路清奇"],
        "avatar_emoji": "👻",
        "catchphrases": ["欢迎光临恐怖屋，包您满意！", "鬼不可怕，可怕的是没钱赚。"],
    },
    {
        "id": "wangling",
        "name": "王令",
        "novel": "仙王的日常生活",
        "personality": ["低调", "懒散", "内心吐槽丰富", "吃貨"],
        "avatar_emoji": "😐",
        "catchphrases": ["……哦。", "无聊。", "今天中午吃什么。"],
    },
    {
        "id": "xiao_yan",
        "name": "萧炎",
        "novel": "斗破苍穹",
        "personality": ["坚韧不拔", "重情重义", "有仇必报", "热血"],
        "avatar_emoji": "🔥",
        "catchphrases": ["三十年河东，三十年河西，莫欺少年穷！", "老师，我需要丹药！"],
    },
]


@app.get("/api/v1/sentiment/character/list")
async def mock_character_list():
    return {
        "characters": MOCK_CHARACTERS,
        "total": len(MOCK_CHARACTERS),
    }


class MockCharacterChatRequest(BaseModel):
    query: str
    character_id: str
    top_k: int = Field(default=5, ge=1, le=10)
    session_id: str = Field(default="", max_length=128)


_MOCK_CHARACTER_RESPONSES: dict[str, list[str]] = {
    "klein": [
        "（略微沉吟）这个问题很有意思……不过作为一位占卜家，我需要先提醒你：有些事情知道得太多未必是好事。",
        "主保佑你。如果你对神秘学感兴趣，我倒是可以推荐几本入门书籍——当然，前提是你做好了面对非凡世界的准备。",
        "（压低声音）廷根市最近确实不太平，各种非凡事件频发。但具体细节……抱歉，这涉及值夜者的保密条例。",
        "唔…以一个序列9占卜家的经验来看，凡事都要留一手准备。毕竟，在这个世界上，谨慎才能活得长久。",
        "（微笑）蒸汽与机械之神在上，你今天遇到的问题，也许可以用最简单的方式解决——比如先喝杯红茶冷静一下。",
    ],
    "hanli": [
        "（面无表情）修仙之路，本就充满艰险。韩某能走到今日，靠的不是运气，而是凡事多想三步。",
        "嗯……此事倒也有趣。不过在下修为尚浅，恐怕帮不上什么忙。",
        "（略作思索）修仙界中，财侣法地，缺一不可。你若是散修，更要懂得量力而行的道理。",
        "（语气平淡）天下没有白得的机缘。看上去越美好的事物，背后的代价往往越难以承受。",
        "（微微颔首）韩某倒是听说过类似的事。不过其中牵扯甚广，不便多言。",
    ],
    "chenge": [
        "（笑容灿烂）欢迎光临恐怖屋！今天想体验什么项目？我们新出了一个'午夜凶铃'主题房，保证让你满意！",
        "（挠头）其实吧，开鬼屋这件事，最重要的不是吓人，而是让游客玩得开心。毕竟，笑点和泪点之间只差一个反转嘛。",
        "（眨眨眼）你知道吗？我们恐怖屋的员工都很有特色——比如李叔，他不用化妆就能吓哭小朋友。",
        "（一本正经）经研究表明，适度恐惧能让人分泌多巴胺。所以来我们鬼屋=快乐，这是科学。",
        "（边走边介绍）这边是新的'深井医院'主题区，灵感来自本市的一个真实案件…呃，这个还是等买了票再细说吧。",
    ],
    "wangling": [
        "（面无表情地看了你一眼）……哦。",
        "（慢吞吞地）嗯。今天食堂有红烧肉。",
        "（眼神放空）……说完了？",
        "（叹了口气）又要拯救世界了吗……能等我吃完饭再说吗？",
        "（稍微有了点兴趣）这个嘛……还行。比上次那个有意思一点。",
    ],
    "xiao_yan": [
        "（昂首挺胸）三十年河东三十年河西，莫欺少年穷！这点困难算什么，我萧炎一路走来，什么大风大浪没见过！",
        "（眼神坚定）老师说过，修炼一途，不进则退。既然选择了这条路，就要走到底。",
        "（咧嘴一笑）想要丹药？行啊，拿等价的东西来换。炼药师的时间可是很宝贵的。",
        "（语气渐冷）你最好不是在打萧家的主意。否则……我的异火可不长眼睛。",
        "（豪爽地拍拍你）放心，有我在，不会让朋友吃亏的。这是我萧炎的承诺。",
    ],
}


@app.post("/api/v1/sentiment/character/chat")
async def mock_character_chat(request: MockCharacterChatRequest):
    import random

    character_id = request.character_id
    responses = _MOCK_CHARACTER_RESPONSES.get(character_id)
    character = None
    for c in MOCK_CHARACTERS:
        if c["id"] == character_id:
            character = c
            break

    if not responses or character is None:
        raise HTTPException(status_code=404, detail=f"Character '{character_id}' not found")

    # Pick a response based on query content and randomness
    query_lower = request.query.lower()
    greetings = ["你好", "嗨", "hi", "hello", "在吗"]
    about_self = ["你是谁", "你叫什么", "介绍"]
    about_novel = ["什么小说", "哪本书", "出自"]

    if any(g in query_lower for g in greetings):
        answer = f"{character['name']}：你好。{character['catchphrases'][0] if character['catchphrases'] else ''}"
    elif any(w in query_lower for w in about_self):
        answer = f"我是{character['name']}，来自《{character['novel']}》。"
    elif any(w in query_lower for w in about_novel):
        answer = f"我出自《{character['novel']}》。"
    else:
        answer = random.choice(responses)

    return {
        "query": request.query,
        "answer": answer,
        "character": {
            "id": character["id"],
            "name": character["name"],
            "novel": character["novel"],
            "avatar_emoji": character.get("avatar_emoji", "🎭"),
        },
        "sources": [character["novel"]],
        "method": "mock",
    }


class MockCharacterChatByNameRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    character_name: str = Field(..., min_length=1, max_length=100)
    novel_name: str = Field(..., min_length=1, max_length=100)
    top_k: int = Field(default=5, ge=1, le=10)
    session_id: str = Field(default="", max_length=128)


@app.post("/api/v1/sentiment/character/chat-by-name")
async def mock_character_chat_by_name(request: MockCharacterChatByNameRequest):
    """Mock — 以任意指定的小说角色身份对话。"""
    novel_title = request.novel_name
    character_name = request.character_name

    # 检查小说是否在 mock 数据中
    novel = _TITLE_MAP.get(novel_title)
    if novel is None:
        raise HTTPException(
            status_code=404,
            detail=f"知识库中暂未收录《{novel_title}》，无法创建「{character_name}」的角色扮演。",
        )

    # 模拟思考延迟
    await asyncio.sleep(random.uniform(0.3, 0.8))

    return {
        "query": request.query,
        "answer": f"（{character_name}微微点头）你好，我是{character_name}，来自《{novel_title}》。"
                   f"\n\n{character_name}思索片刻，说道："
                   f"「{random.choice(['很高兴见到你', '有什么可以帮你的吗', '不知阁下有何见教'])}」",
        "character": {
            "name": character_name,
            "novel": novel_title,
            "avatar_emoji": "📖",
        },
        "sources": [novel_title],
        "method": "mock_dynamic",
    }

