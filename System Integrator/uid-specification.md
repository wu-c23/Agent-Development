# UID 生成与使用规范 v1.0

## 概述

全系统统一使用 `Platform_ID + Novel_Title` 的 Hash 值作为 **Unique Identifier (UID)**，确保跨模块数据一致性。

## 生成算法

### 输入

| 字段 | 说明 | 示例 |
|------|------|------|
| `platform_id` | 小说在源平台的唯一 ID | `qidian:12345678` |
| `novel_title` | 小说原始标题（去除首尾空白，保留中间空格） | `诡秘之主` |

### 算法

```
UID = SHA256( platform_id + "|" + novel_title )
```

- 拼接符: `|` (管道符)
- Hash 算法: SHA-256
- 输出格式: 64 位十六进制小写字符串

### Python 实现参考

```python
import hashlib

def generate_uid(platform_id: str, novel_title: str) -> str:
    raw = f"{platform_id}|{novel_title.strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
```

## 使用规范

### 各模块职责

| 模块 | 生成 UID | 消费 UID |
|------|----------|----------|
| Trend Explorer (吴隐) | 采集时生成 | 输出到趋势 API |
| Safe-Search Architect (吴宸) | 索引时生成 | 搜索接口输入/输出 |
| Sentiment Critic (武文杰) | 采集时生成 | 舆情 API 输入/输出 |
| System Integrator (苗文昊) | — | 全局数据关联枢纽 |

### 数据流转规则

1. 各模块采集数据时，**自行生成 UID** 并随数据一并存储
2. 接口交互时，**UID 为必传字段**，用于跨模块数据关联
3. System Integrator 以 UID 为主键关联各模块数据
4. 同一小说在不同平台的记录视为**不同实体**（不同 UID）

## 约束

- UID 一经生成不可变更
- 禁止使用自增 ID 或平台原始 ID 替代 UID 进行跨模块通信
- 所有 Data Contract 的根节点必须包含 `uid` 字段
