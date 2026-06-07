"""搜索缺失 book_id 的3本书"""
import sys, warnings
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
warnings.filterwarnings("ignore", category=ResourceWarning)

from review_critic.zongheng import ZonghengReviewCrawler

BOOKS = ["帝族长歌", "一剑镇山河", "夜行规则"]

crawler = ZonghengReviewCrawler(delay=2.0, timeout=30, retries=2, headless=True)

for title in BOOKS:
    print(f"\nSearching: {title}")
    result = crawler.search_book(title)
    if result:
        print(f"  Found: {result['title']}")
        print(f"  book_id: {result['book_id']}")
        print(f"  url: {result.get('url', '')}")
    else:
        print(f"  NOT FOUND")

import asyncio
asyncio.run(crawler._close_browser())
