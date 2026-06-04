"""UID 生成工具 — 遵循 System Integrator uid-specification v1.0。

UID = SHA256(platform_id + "|" + novel_title)
"""

import hashlib


def generate_uid(platform_id: str, novel_title: str) -> str:
    """生成全系统统一的唯一标识符。

    Args:
        platform_id: 小说在源平台的唯一 ID，如 "qidian:12345678"
        novel_title: 小说原始标题

    Returns:
        64 位十六进制小写 SHA256 字符串
    """
    raw = f"{platform_id}|{novel_title.strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def validate_uid(uid: str) -> bool:
    """校验 UID 格式是否合法 (64 位小写 hex)。"""
    if len(uid) != 64:
        return False
    try:
        int(uid, 16)
        return True
    except ValueError:
        return False
