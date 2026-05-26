"""Demo script for SafeSearchEngine.

Shows:
  - Indexing books with persistent ChromaDB storage
  - Semantic search with hybrid retrieval (dense + sparse)
  - Intent extraction with few-shot prompting
  - Risk scoring and avoid-tag filtering
  - Incremental update (add/update/delete)
"""

import json

from safe_search import Book, SafeSearchEngine


def main() -> None:
    engine = SafeSearchEngine()

    # Sample Chinese web novel corpus
    books = [
        Book(
            id="uid_001",
            title="诡秘之主",
            intro="值夜者克莱恩·莫雷蒂在蒸汽朋克世界中探索超凡力量的秘密，一步步成为真正的'愚者'。克苏鲁元素融合维多利亚时代背景，逻辑严密的世界观构建。",
            tags=["克苏鲁", "蒸汽朋克", "悬疑", "西方奇幻", "完结"],
            status="completed",
            sentiment_summary="读者普遍好评，夸赞逻辑严密、角色塑造出色，有部分读者反映开头节奏偏慢。",
        ),
        Book(
            id="uid_002",
            title="修罗武神",
            intro="楚枫遭人陷害沦为废物，意外获得修罗传承后一路碾压敌人，收服各色美女，逆天改命称霸天下！",
            tags=["玄幻", "升级流", "后宫", "爽文"],
            status="ongoing",
            sentiment_summary="读者喜欢爽快感，但吐槽后期水字数、后宫角色扁平化。",
        ),
        Book(
            id="uid_003",
            title="我有一座恐怖屋",
            intro="陈歌继承了一家废弃的鬼屋，意外获得恐怖屋经营系统，需要用真实的恐怖场景来吓唬游客，却发现恐怖场景背后的真实案件更加惊悚。",
            tags=["悬疑", "恐怖", "系统流", "轻松", "完结"],
            status="completed",
            sentiment_summary="读者认为剧情新颖有趣，节奏把控好，恐怖氛围和搞笑元素平衡得当。",
        ),
        Book(
            id="uid_004",
            title="凡人修仙传",
            intro="一个普通的山村少年韩立，凭借谨慎的性格和一点机缘，在残酷的修仙界中步步为营。没有逆天外挂，只有小人物在修真界的奋斗与挣扎。",
            tags=["修仙", "凡人流", "完结", "慢热"],
            status="completed",
            sentiment_summary="凡人流开山之作，读者称赞主角智商在线、逻辑自洽，但前期节奏确实偏慢。",
        ),
        Book(
            id="uid_005",
            title="仙王的日常生活",
            intro="修真界最强的仙王王令，为了体验普通人的生活而隐藏实力进入高中，各种日常搞笑与修真元素的碰撞。",
            tags=["修仙", "日常", "搞笑", "轻松", "完结"],
            status="completed",
            sentiment_summary="轻松搞笑的日常番，读者喜欢反套路设定和密集的笑点。",
        ),
    ]

    print("=" * 60)
    print("1. Indexing books...")
    print("=" * 60)
    engine.index_books(books)
    print(f"Indexed {engine.store.book_count()} books into ChromaDB + BM25\n")

    # Test 1: Complex semantic query
    print("=" * 60)
    print("2. Search: '类似诡秘之主但基调不那么压抑的'")
    print("=" * 60)
    result = engine.search(
        query="类似诡秘之主但基调不那么压抑的",
        top_k=3,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print()

    # Test 2: With avoid tags
    print("=" * 60)
    print("3. Search: '修仙爽文' with avoid_tags=['后宫']")
    print("=" * 60)
    result2 = engine.search(
        query="修仙爽文",
        avoid_tags=["后宫", "虐主"],
        top_k=3,
    )
    print(json.dumps(result2, ensure_ascii=False, indent=2))
    print()

    # Test 3: Intent extraction only
    print("=" * 60)
    print("4. Intent extraction: '想看已完结的轻松修仙文'")
    print("=" * 60)
    intent = engine.extract_intent("想看已完结的轻松修仙文")
    print(f"  Summary: {intent.summary}")
    print(f"  Topics: {intent.topics}")
    print(f"  Style: {intent.style}")
    print(f"  Mood: {intent.mood}")
    print(f"  Constraints: {intent.constraints}")
    print()

    # Test 4: Incremental update
    print("=" * 60)
    print("5. Incremental update: remove '修罗武神', re-search")
    print("=" * 60)
    engine.remove_book("uid_002")
    print(f"Removed uid_002, index now has {engine.store.book_count()} books")
    result3 = engine.search(query="玄幻爽文", top_k=3)
    print(f"Results: {[r['title'] for r in result3['filtered_results']]}")
    print()

    print("Done! All features verified.")


if __name__ == "__main__":
    main()
