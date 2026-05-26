# unified-data-model-sql · 统一数据模型设计文档

> 模块：系统集成与交互体验  
> 负责人：苗文昊（System Integrator & UI/UX）  
> 版本：v1.0  
> 适用范围：AI Fiction Navigator 网络小说智能推荐系统全模块

---

## 一、设计思路说明

### 1.1 为什么需要统一数据模型

本系统由四个高度自治的业务模块构成（趋势采集、语义搜索、舆情分析、系统集成），各模块在物理存储上分别使用 **关系型库（PostgreSQL）**、**向量库（Milvus/Pinecone）** 与 **文档型数据**。若不建立统一关系骨架，将出现以下问题：

- 同一本小说在三个模块中被识别为三条不同记录，无法聚合展示
- Router Agent 在结果聚合阶段无法 JOIN 多模块数据
- 增量更新时缺乏全局一致性校验入口
- 舆情模块的原始评论数据若散落各处，将无法支撑后续可追溯审计

因此，集成端必须提供一份 **"主数据骨架（Master Schema）"**，作为各模块数据落库与对外输出的共同参照系。

### 1.2 核心设计原则

- **UID 单一事实源（Single Source of Truth）**  
  全系统统一以 `SHA256(platform_id + novel_title)` 的十六进制字符串作为 Novel 主键，所有模块外键引用此 UID。
- **宽表 + 子表混合**  
  小说主信息使用宽表（`novels`），各模块业务数据使用子表（一对一或一对多），保证模块解耦同时支持联合查询。
- **原始数据与衍生数据分离**  
  舆情模块的"原始评论"与"聚合评分"分两张表，原始评论用于审计与追溯，聚合评分用于前端高速展示。
- **JSONB 字段兜底**  
  对于结构尚未稳定的字段（如趋势标签、舆情维度分数），使用 PostgreSQL 的 `JSONB` 类型，既允许各模块自由演进，又能利用 GIN 索引加速查询。
- **软删除 + 时间戳全覆盖**  
  所有表强制包含 `created_at` / `updated_at` / `is_deleted`，便于增量同步与审计。
- **与 JSON Schema 数据契约对齐**  
  表结构字段命名与文档第 3.1 节《数据契约示例》严格一一对应，确保契约即模型。

### 1.3 表结构总览

- `novels`：小说主表（UID 锚点）
- `trend_metrics`：趋势指标表（吴隐模块产出落库）
- `sentiment_scores`：舆情聚合评分表（武文杰模块产出落库，前端展示用）
- `raw_reviews`：原始评论表（武文杰模块采集端落库，审计与追溯用）
- `vector_refs`：向量索引引用表（吴宸模块产出落库，仅存元数据，向量本体在 Milvus）
- `user_profiles`：用户画像表（集成端，用于 Router Agent 个性化分发与避雷过滤）
- `agent_session_logs`：Agent 会话日志表（集成端，用于运维监控）
- `token_usage_logs`：Token 消耗审计表（集成端，对接月报模板）

### 1.4 表间关系总览（无插件，纯列表表达）

- `novels` (uid)
  - 一对多 → `trend_metrics` (uid, snapshot_at)
  - 一对一 → `sentiment_scores` (uid)
  - 一对多 → `raw_reviews` (uid, review_id)
  - 一对一 → `vector_refs` (uid)
- `user_profiles` (user_id)
  - 一对多 → `agent_session_logs` (user_id)
- `agent_session_logs` (session_id)
  - 一对多 → `token_usage_logs` (session_id)

---

## 二、PostgreSQL 建表 SQL

### 2.1 小说主表 `novels`

```sql
CREATE TABLE novels (
    uid                VARCHAR(64) PRIMARY KEY,
    title              VARCHAR(255) NOT NULL,
    platform           VARCHAR(32)  NOT NULL,
    platform_novel_id  VARCHAR(64)  NOT NULL,
    author             VARCHAR(128),
    category           VARCHAR(64),
    cover_url          TEXT,
    description        TEXT,
    last_update        TIMESTAMP    NOT NULL DEFAULT NOW(),
    created_at         TIMESTAMP    NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMP    NOT NULL DEFAULT NOW(),
    is_deleted         BOOLEAN      NOT NULL DEFAULT FALSE,
    CONSTRAINT uq_platform_novel UNIQUE (platform, platform_novel_id)
);

CREATE INDEX idx_novels_platform   ON novels(platform);
CREATE INDEX idx_novels_category   ON novels(category);
CREATE INDEX idx_novels_updated_at ON novels(updated_at);
```

**字段说明：**

- `uid`：全系统主键，由 `SHA256(platform + '::' + platform_novel_id)` 生成
- `platform`：起点 / 纵横 / 番茄 等，枚举值由集成端维护
- `platform_novel_id`：原平台书号，便于反查
- `is_deleted`：软删除标识，保留历史数据供运维审计

---

### 2.2 趋势指标表 `trend_metrics`

```sql
CREATE TABLE trend_metrics (
    uid           VARCHAR(64)  NOT NULL,
    snapshot_at   TIMESTAMP    NOT NULL DEFAULT NOW(),
    heat_score    NUMERIC(5,4) NOT NULL,
    rank_overall  INTEGER,
    rank_category INTEGER,
    tags          JSONB        NOT NULL DEFAULT '[]'::JSONB,
    extra         JSONB,
    PRIMARY KEY (uid, snapshot_at),
    CONSTRAINT fk_trend_uid FOREIGN KEY (uid) REFERENCES novels(uid) ON DELETE CASCADE
);

CREATE INDEX idx_trend_heat_score ON trend_metrics(heat_score DESC);
CREATE INDEX idx_trend_tags_gin   ON trend_metrics USING GIN (tags);
```

**设计要点：**

- 采用 `(uid, snapshot_at)` 联合主键，支持热度时间序列存储，便于绘制趋势曲线
- `tags` 字段使用 `JSONB` 并建立 GIN 索引，支持"包含某标签"的高速过滤
- `extra` 预留给吴隐后续扩展（如"流派迁移向量"等）

---

### 2.3 舆情聚合评分表 `sentiment_scores`

```sql
CREATE TABLE sentiment_scores (
    uid               VARCHAR(64)  PRIMARY KEY,
    logic_score       NUMERIC(3,1),
    style_score       NUMERIC(3,1),
    update_score      NUMERIC(3,1),
    character_score   NUMERIC(3,1),
    toxicity_index    NUMERIC(4,3),
    positive_ratio    NUMERIC(4,3),
    review_count      INTEGER      NOT NULL DEFAULT 0,
    critic_summary    TEXT,
    dimension_extra   JSONB,
    analyzed_at       TIMESTAMP    NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_sent_uid FOREIGN KEY (uid) REFERENCES novels(uid) ON DELETE CASCADE
);

CREATE INDEX idx_sent_logic    ON sentiment_scores(logic_score DESC);
CREATE INDEX idx_sent_toxicity ON sentiment_scores(toxicity_index ASC);
```

**设计要点：**

- 主维度（文笔、逻辑、更新、人设）使用强类型 `NUMERIC(3,1)`，确保前端展示稳定
- `dimension_extra` 用 `JSONB` 兜底武文杰的新增评分维度
- `critic_summary` 存储"一句话毒舌点评"，由 `critic-summary-generator` 写入
- 该表为**聚合结果**，原始评论存储于 `raw_reviews` 表

---

### 2.4 原始评论表 `raw_reviews`

```sql
CREATE TABLE raw_reviews (
    review_id        VARCHAR(64)  PRIMARY KEY,
    uid              VARCHAR(64)  NOT NULL,
    source_platform  VARCHAR(32)  NOT NULL,
    source_url       TEXT,
    author_name      VARCHAR(128),
    author_id_hash   VARCHAR(64),
    content          TEXT         NOT NULL,
    raw_rating       NUMERIC(3,1),
    sentiment_label  VARCHAR(16),
    classified_tags  JSONB        NOT NULL DEFAULT '[]'::JSONB,
    like_count       INTEGER      NOT NULL DEFAULT 0,
    posted_at        TIMESTAMP,
    crawled_at       TIMESTAMP    NOT NULL DEFAULT NOW(),
    is_processed     BOOLEAN      NOT NULL DEFAULT FALSE,
    is_deleted       BOOLEAN      NOT NULL DEFAULT FALSE,
    CONSTRAINT fk_review_uid FOREIGN KEY (uid) REFERENCES novels(uid) ON DELETE CASCADE
);

CREATE INDEX idx_review_uid          ON raw_reviews(uid);
CREATE INDEX idx_review_platform     ON raw_reviews(source_platform);
CREATE INDEX idx_review_sentiment    ON raw_reviews(sentiment_label);
CREATE INDEX idx_review_posted_at    ON raw_reviews(posted_at DESC);
CREATE INDEX idx_review_processed    ON raw_reviews(is_processed);
CREATE INDEX idx_review_tags_gin     ON raw_reviews USING GIN (classified_tags);
```

**字段说明：**

- `review_id`：评论唯一标识，建议格式 `SHA256(source_platform + '::' + 原平台评论ID)`
- `source_platform`：取值 `tieba` / `xiaohongshu` / `douban` / `zhihu` 等
- `source_url`：原始链接，用于事实核查与可追溯
- `author_id_hash`：评论作者 ID 的哈希值，**满足隐私合规**，不存储明文用户标识
- `content`：评论原文，供 LLM 进行 Zero-shot 分类时读取
- `raw_rating`：若原平台有打分，存储原始值（如豆瓣 8.5 分）
- `sentiment_label`：LLM 给出的粗粒度标签 `positive` / `negative` / `neutral` / `controversial`
- `classified_tags`：LLM 抽取的细粒度标签（如 `["烂尾警告", "文笔流畅", "人设崩塌"]`）
- `is_processed`：标记该评论是否已被纳入 `sentiment_scores` 聚合，便于增量计算

**设计要点：**

- **冷热分离**：原始评论数据量大但访问频率低，前端展示直接读 `sentiment_scores`，仅在"查看完整评论"等深度交互时才查 `raw_reviews`
- **审计可追溯**：当用户质疑某本书的评分时，可通过 `raw_reviews` 反查所有源评论与原始链接
- **增量重算友好**：`is_processed` 字段使武文杰的聚合脚本可只处理新增评论
- **隐私安全**：评论作者标识强制哈希化，符合数据合规要求

---

### 2.5 向量索引引用表 `vector_refs`

```sql
CREATE TABLE vector_refs (
    uid             VARCHAR(64) PRIMARY KEY,
    vector_id       VARCHAR(64) NOT NULL,
    collection      VARCHAR(64) NOT NULL DEFAULT 'novels_v1',
    embedding_model VARCHAR(64) NOT NULL DEFAULT 'text-embedding-3-small',
    dim             INTEGER     NOT NULL DEFAULT 1536,
    indexed_at      TIMESTAMP   NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_vec_uid FOREIGN KEY (uid) REFERENCES novels(uid) ON DELETE CASCADE,
    CONSTRAINT uq_vector_id UNIQUE (vector_id)
);
```

**设计要点：**

- 关系库只存"指针"（`vector_id`），向量本体仍在 Milvus/Pinecone，避免数据冗余
- `embedding_model` + `dim` 字段支持未来吴宸升级到更高维模型时的平滑过渡

---

### 2.6 用户画像表 `user_profiles`

```sql
CREATE TABLE user_profiles (
    user_id          VARCHAR(64)  PRIMARY KEY,
    nickname         VARCHAR(64),
    preferred_tags   JSONB        NOT NULL DEFAULT '[]'::JSONB,
    avoid_tags       JSONB        NOT NULL DEFAULT '[]'::JSONB,
    preferred_styles JSONB        NOT NULL DEFAULT '[]'::JSONB,
    reading_history  JSONB        NOT NULL DEFAULT '[]'::JSONB,
    interaction_stats JSONB       NOT NULL DEFAULT '{}'::JSONB,
    created_at       TIMESTAMP    NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMP    NOT NULL DEFAULT NOW(),
    last_active_at   TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_user_pref_gin   ON user_profiles USING GIN (preferred_tags);
CREATE INDEX idx_user_avoid_gin  ON user_profiles USING GIN (avoid_tags);
CREATE INDEX idx_user_active     ON user_profiles(last_active_at DESC);
```

**字段说明：**

- `preferred_tags`：用户主动收藏或频繁点击的正向标签（如 `["修仙", "无敌流"]`）
- `avoid_tags`：用户的避雷标签，**直接对接吴宸的避雷 Agent 作为默认过滤条件**
- `preferred_styles`：用户偏好的文风（如 `["轻快", "硬核", "治愈"]`），用于语义搜索的隐式 query 增强
- `reading_history`：JSONB 结构 `[{uid, read_at, progress, rating}]`，避免单独建表
- `interaction_stats`：JSONB 结构 `{query_count, click_count, favorite_count, last_query_intent}`，供 Router Agent 做个性化决策

**设计要点：**

- 用户画像是 **Router Agent 实现"千人千面"分发的关键依据**，例如同一个 query "推荐玄幻"，老用户与新用户的 Agent 链路应有差异
- `avoid_tags` 与吴宸模块**双向同步**：用户在前端添加避雷词时同时更新此表，吴宸的搜索接口在执行时读取此字段做隐式过滤
- 即使当前 MVP 未实现登录系统，也可使用"游客 UUID"作为 `user_id` 落库，便于后续平滑升级到真实账号体系

---

### 2.7 Agent 会话日志表 `agent_session_logs`

```sql
CREATE TABLE agent_session_logs (
    session_id     VARCHAR(64)  PRIMARY KEY,
    user_id        VARCHAR(64),
    intent         VARCHAR(32)  NOT NULL,
    route_modules  JSONB        NOT NULL,
    user_query     TEXT         NOT NULL,
    final_response TEXT,
    latency_ms     INTEGER,
    status         VARCHAR(16)  NOT NULL DEFAULT 'success',
    error_message  TEXT,
    created_at     TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_session_user    ON agent_session_logs(user_id);
CREATE INDEX idx_session_intent  ON agent_session_logs(intent);
CREATE INDEX idx_session_status  ON agent_session_logs(status);
CREATE INDEX idx_session_created ON agent_session_logs(created_at DESC);
```

**设计要点：**

- `intent` 取值：`find_book` / `review` / `trend` / `chat`，由 Router Agent 写入
- `route_modules` 存储本次会话实际调用了哪些下游模块，作为运维分析依据
- `error_message` 用于记录降级或失败的具体原因，对接"架构解耦"约束的可观测性需求

---

### 2.8 Token 消耗审计表 `token_usage_logs`

```sql
CREATE TABLE token_usage_logs (
    log_id            BIGSERIAL    PRIMARY KEY,
    session_id        VARCHAR(64),
    module_owner      VARCHAR(32)  NOT NULL,
    model_name        VARCHAR(64)  NOT NULL,
    prompt_tokens     INTEGER      NOT NULL,
    completion_tokens INTEGER      NOT NULL,
    total_tokens      INTEGER      NOT NULL,
    cost_usd          NUMERIC(10,6) NOT NULL,
    occurred_at       TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_token_module ON token_usage_logs(module_owner);
CREATE INDEX idx_token_time   ON token_usage_logs(occurred_at DESC);
CREATE INDEX idx_token_session ON token_usage_logs(session_id);
```

**设计要点：**

- `module_owner` 取值：`trend` / `search` / `sentiment` / `integration`，与团队成员一一对应
- 该表直接对接交付物 4《运维月报模板》，无需额外 ETL

---

## 三、与数据契约（Data Contract）的字段对照

| 契约字段                          | 落库位置                          |
| --------------------------------- | --------------------------------- |
| `uid`                             | `novels.uid`                      |
| `metadata.title`                  | `novels.title`                    |
| `metadata.platform`               | `novels.platform`                 |
| `metadata.last_update`            | `novels.last_update`              |
| `trend_metrics.heat_score`        | `trend_metrics.heat_score`        |
| `trend_metrics.tags`              | `trend_metrics.tags`              |
| `sentiment_scores.logic`          | `sentiment_scores.logic_score`    |
| `sentiment_scores.style`          | `sentiment_scores.style_score`    |
| `sentiment_scores.toxicity_index` | `sentiment_scores.toxicity_index` |
| `vector_id`                       | `vector_refs.vector_id`           |

任何模块在输出 JSON 时必须满足以上映射，集成端将通过 JSON Schema 强校验拒绝非法数据。

---

## 四、UID 生成规范（强制）

- 算法：`uid = sha256(platform + '::' + platform_novel_id).hexdigest()`
- 字符集：小写十六进制，固定 64 字符长度
- 各模块必须使用集成端提供的 `utils/uid.py::generate_uid()` 工具函数，禁止自行实现
- 同一本小说在不同平台视为不同 UID（如起点版《诡秘之主》与番茄版《诡秘之主》UID 不同）

### 4.1 评论 ID 生成规范

- 算法：`review_id = sha256(source_platform + '::' + 原平台评论ID).hexdigest()`
- 若原平台无评论 ID，则使用 `sha256(source_url + '::' + content[:50])` 兜底

---

## 五、增量更新与一致性策略

- **写入主表优先**：任何模块新增小说时，必须先 `INSERT INTO novels` 再写入子表
- **子表 UPSERT**：使用 `ON CONFLICT (uid) DO UPDATE` 保证幂等
- **删除采用软删**：`is_deleted = TRUE`，由集成端每周扫描清理 30 天前的逻辑删除数据
- **跨模块校验**：集成端每 24 小时执行一致性脚本，检测孤儿子表记录（无对应 `novels.uid`）并告警
- **评论增量聚合**：武文杰模块每 6 小时扫描 `raw_reviews.is_processed = FALSE` 的记录，重算 `sentiment_scores` 并标记已处理

---

## 六、数据流转示意（无插件，纯列表）

- 采集阶段
  - 吴隐爬虫 → 写入 `novels` + `trend_metrics`
  - 武文杰爬虫 → 写入 `novels`（若新书）+ `raw_reviews`
- 处理阶段
  - 吴宸索引脚本 → 读取 `novels.description` → 写入 Milvus → 回填 `vector_refs`
  - 武文杰聚合脚本 → 读取 `raw_reviews` → 聚合写入 `sentiment_scores`
- 服务阶段
  - 用户请求 → Router Agent 写入 `agent_session_logs`
  - 各模块 LLM 调用 → 写入 `token_usage_logs`
  - Agent 读取 `user_profiles` 实现个性化响应
- 监控阶段
  - 集成端定时任务 → 聚合 `token_usage_logs` + `agent_session_logs` → 生成月报
