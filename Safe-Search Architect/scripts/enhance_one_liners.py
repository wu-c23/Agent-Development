"""用 DeepSeek 为每本书生成真实的毒舌点评，替换千篇一律的模板 one_liner。

用法:
  python scripts/enhance_one_liners.py [--limit N] [--delay 2]

每本书收集评论样本发给 DeepSeek，生成有网感的犀利点评。
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC = _PROJECT_ROOT / "Safe-Search Architect" / "src"
sys.path.insert(0, str(SRC))

from review_critic.models import normalize_space, read_json, read_jsonl, write_json

RUNS_DIR = _PROJECT_ROOT / "Sentiment Critic" / "data" / "runs"
INDEX_PATH = _PROJECT_ROOT / "Sentiment Critic" / "data" / "sentiment_index.json"
NOVELS_PATH = _PROJECT_ROOT / "Sentiment Critic" / "data" / "novels.json"

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_KEY = "sk-14ff889c5e8940e682c1824adf40effd"
DEEPSEEK_MODEL = "deepseek-v4-pro"

# 需要替换的模板 one_liner 前缀
BORING_PREFIXES = (
    "优缺点都很明显",
    "不是无脑吹",
    "雷点不藏着掖着",
)

def load_review_samples(book_title: str, max_samples: int = 20, max_chars: int = 300) -> list[str]:
    """为一本书收集评论样本（截取前 max_chars 字符）。"""
    samples: list[str] = []
    key = normalize_space(book_title).lower()

    for f in sorted(RUNS_DIR.glob("*.jsonl")):
        fname_lower = normalize_space(f.stem).lower()
        if key not in fname_lower:
            continue
        try:
            reviews = read_jsonl(str(f))
        except Exception:
            continue
        for r in reviews:
            text = (r.content or "").strip()
            if len(text) >= 30:
                samples.append(text[:max_chars])
                if len(samples) >= max_samples:
                    return samples
    return samples


def call_deepseek(prompt: str) -> str | None:
    """调用 DeepSeek，返回文本结果。"""
    import urllib.request
    try:
        body = json.dumps({
            "model": DEEPSEEK_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.9,
            "max_tokens": 150,
        }, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(DEEPSEEK_URL, data=body, headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_KEY}",
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"    DeepSeek error: {e}")
        return None


def generate_one_liner(book: str, samples: list[str], review_count: int,
                       pos_ratio: float, neg_ratio: float) -> str | None:
    """用 DeepSeek 为单本书生成毒舌点评。"""
    sample_text = "\n---\n".join(
        f"评论{i+1}: {s}" for i, s in enumerate(samples[:15])
    )

    prompt = f"""你是网络小说评论区的毒舌点评员。请根据以下读者评论，为小说《{book}》写一句毒舌点评（20-60字）。

要求：
- 网感强，像豆瓣短评或知乎高赞
- 既戳中优点也点出槽点
- 有记忆点，不是模板套话
- 只输出一句点评，不要引号、不要前缀

统计：{review_count}条评论，好评率{pos_ratio:.0%}，差评率{neg_ratio:.0%}

读者评论摘录：
{sample_text}

毒舌点评："""

    return call_deepseek(prompt)


def clean_text(text: str) -> str:
    """去掉 HTML 标签、emoji 标签、零宽字符等脏数据。"""
    import re as _re
    text = _re.sub(r"<[^>]*>", "", text)           # HTML 标签
    text = text.replace("​", "")               # 零宽空格
    text = text.replace("‎", "")               # 零宽不连字
    text = _re.sub(r"&[a-z]+;", "", text)           # HTML 实体
    return normalize_space(text)


def fallback_one_liner(samples: list[str]) -> str:
    """没有足够评论时，直接从真实评论里取一条截断作为 one_liner。"""
    import random
    text = random.choice(samples).strip()
    # 截断到 60 字，尽量在句号/逗号处断开
    if len(text) <= 60:
        return text
    cut = text[:60]
    for sep in ("。", "，", "！", "？", "…", "~", "～", ",", ".", "!"):
        idx = cut.rfind(sep)
        if idx >= 20:
            return cut[:idx + 1]
    return cut + "…"


def needs_enhance(one_liner: str) -> bool:
    """判断 one_liner 是否需要增强（是模板生成的）。"""
    if not one_liner:
        return True
    return one_liner.startswith(BORING_PREFIXES)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="最多处理 N 本")
    parser.add_argument("--delay", type=float, default=2.0, help="请求间隔秒数")
    parser.add_argument("--force", action="store_true", help="覆盖所有 one_liner（含非模板）")
    args = parser.parse_args()

    # 加载
    index = read_json(str(INDEX_PATH))
    novels_data = []
    if NOVELS_PATH.exists():
        novels_data = read_json(str(NOVELS_PATH))

    # 建立 uid -> book_title 映射
    uid_to_title: dict[str, str] = {}
    for n in novels_data:
        uid = n.get("uid", "")
        title = n.get("title", "")
        if uid and title:
            uid_to_title[uid] = title

    # 收集需要增强的条目
    to_enhance: list[tuple[str, str]] = []  # (uid, book_title)
    for uid, entry in index.items():
        one_liner = entry.get("one_liner", "")
        if args.force or needs_enhance(one_liner):
            title = entry.get("metadata", {}).get("title", "") if isinstance(entry.get("metadata"), dict) else ""
            if not title:
                title = uid_to_title.get(uid, "")
            if title:
                to_enhance.append((uid, title))

    print(f"共 {len(index)} 本书，{len(to_enhance)} 本需要增强 one_liner")

    if args.limit:
        to_enhance = to_enhance[:args.limit]

    enhanced = 0
    fallback = 0
    skipped = 0

    for i, (uid, title) in enumerate(to_enhance):
        print(f"[{i+1}/{len(to_enhance)}] {title} ...", end=" ", flush=True)

        entry = index[uid]
        review_count = entry.get("review_count", 0)
        pos_ratio = entry.get("positive_ratio", 0)
        neg_ratio = entry.get("negative_ratio", 0)

        samples = load_review_samples(title, max_samples=20)

        if review_count >= 3 and len(samples) >= 3:
            # 评论够 → 优先用 DeepSeek 生成
            new_one = generate_one_liner(title, samples, review_count, pos_ratio, neg_ratio)
            if new_one:
                entry["one_liner"] = clean_text(new_one.strip().strip('"').strip("'").strip("「」"))
                print(f"[AI] {entry['one_liner'][:60]}".encode("gbk", errors="replace").decode("gbk"))
                enhanced += 1
            elif samples:
                entry["one_liner"] = fallback_one_liner(samples)
                print(f"[FB] {entry['one_liner'][:60]}".encode("gbk", errors="replace").decode("gbk"))
                fallback += 1
            else:
                print("skip (API failed, no samples)")
                skipped += 1
        elif samples:
            entry["one_liner"] = fallback_one_liner(samples)
            print(f"[FB] {entry['one_liner'][:60]}".encode("gbk", errors="replace").decode("gbk"))
            fallback += 1
        else:
            print("skip (无评论样本)")
            skipped += 1

        # 每 10 本保存一次
        if (enhanced + fallback) % 10 == 0:
            write_json(str(INDEX_PATH), index)

        if i < len(to_enhance) - 1:
            time.sleep(args.delay)

    # 最终保存
    write_json(str(INDEX_PATH), index)
    print(f"\n完成！AI 增强 {enhanced} 本，评论摘录 {fallback} 本，跳过 {skipped} 本")
    print(f"文件: {INDEX_PATH}")


if __name__ == "__main__":
    main()
