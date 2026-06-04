-- =============================================================================
-- 网络小说智能推荐系统 — 统一数据库模型 v1.0
-- 目标数据库: PostgreSQL 15+
-- 设计原则: 以 UID 为核心关联所有模块数据
-- =============================================================================

-- =============================================================================
-- 1. 核心主表: 小说基础信息
-- =============================================================================
CREATE TABLE IF NOT EXISTS novels (
    uid             VARCHAR(64) PRIMARY KEY,                -- SHA256 hash
    title           VARCHAR(255) NOT NULL,                   -- 小说标题
    platform        VARCHAR(50)  NOT NULL,                   -- 来源平台
    author          VARCHAR(100),                            -- 作者
    description     TEXT,                                    -- 简介/摘要
    category        VARCHAR(100),                            -- 原始分类
    cover_url       VARCHAR(512),                            -- 封面图 URL
    source_url      VARCHAR(512),                            -- 源平台链接
    first_seen_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),    -- 首次收录时间
    last_updated_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),    -- 最后更新时间

    CONSTRAINT uq_novels_title_platform UNIQUE (title, platform)
);

CREATE INDEX idx_novels_platform ON novels (platform);
CREATE INDEX idx_novels_category ON novels (category);
CREATE INDEX idx_novels_last_updated ON novels (last_updated_at DESC);


-- =============================================================================
-- 2. Trend Explorer 域: 趋势数据
-- =============================================================================

-- 2.1 标签表
CREATE TABLE IF NOT EXISTS trend_tags (
    id          BIGSERIAL PRIMARY KEY,
    uid         VARCHAR(64) NOT NULL REFERENCES novels(uid) ON DELETE CASCADE,
    tag         VARCHAR(100) NOT NULL,
    source      VARCHAR(50)  NOT NULL DEFAULT 'auto',       -- auto / manual / user_feedback
    confidence  REAL         NOT NULL DEFAULT 1.0,           -- 标签置信度 [0, 1]
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_trend_tags UNIQUE (uid, tag)
);

CREATE INDEX idx_trend_tags_tag ON trend_tags (tag);
CREATE INDEX idx_trend_tags_uid ON trend_tags (uid);

-- 2.2 热度快照表 (每日)
CREATE TABLE IF NOT EXISTS trend_heat_snapshots (
    id            BIGSERIAL PRIMARY KEY,
    uid           VARCHAR(64) NOT NULL REFERENCES novels(uid) ON DELETE CASCADE,
    heat_score    REAL        NOT NULL DEFAULT 0.0,          -- 综合热度分 [0, 1]
    rank          INTEGER,                                   -- 当前排名
    rank_change   INTEGER     NOT NULL DEFAULT 0,            -- 排名变化
    trend_direction VARCHAR(20),                             -- rising / stable / declining
    snapshot_date DATE        NOT NULL DEFAULT CURRENT_DATE,
    captured_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_heat_snapshot UNIQUE (uid, snapshot_date)
);

CREATE INDEX idx_heat_snapshots_date ON trend_heat_snapshots (snapshot_date DESC);
CREATE INDEX idx_heat_snapshots_score ON trend_heat_snapshots (heat_score DESC);
CREATE INDEX idx_heat_snapshots_uid_date ON trend_heat_snapshots (uid, snapshot_date DESC);

-- 2.3 标签演变记录
CREATE TABLE IF NOT EXISTS trend_tag_evolution (
    id          BIGSERIAL PRIMARY KEY,
    tag         VARCHAR(100) NOT NULL,
    period_start DATE        NOT NULL,
    period_end  DATE         NOT NULL,
    frequency   INTEGER      NOT NULL DEFAULT 0,             -- 该周期内出现次数
    growth_rate REAL,                                       -- 环比增长率
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_tag_evolution_tag ON trend_tag_evolution (tag);
CREATE INDEX idx_tag_evolution_period ON trend_tag_evolution (period_start, period_end);


-- =============================================================================
-- 3. Safe-Search Architect 域: 向量索引与搜索
-- =============================================================================

-- 3.1 向量索引映射表 (向量数据存储在 Milvus/Pinecone 中，此表做关系映射)
CREATE TABLE IF NOT EXISTS search_vector_index (
    id              BIGSERIAL PRIMARY KEY,
    uid             VARCHAR(64) NOT NULL REFERENCES novels(uid) ON DELETE CASCADE,
    vector_id       VARCHAR(255) NOT NULL UNIQUE,            -- 外部向量库 ID
    embedding_model VARCHAR(100) NOT NULL,                   -- 如 text-embedding-3-small
    embedding_dim   INTEGER     NOT NULL,                    -- 向量维度
    text_chunk      TEXT        NOT NULL,                    -- 被向量化的原始文本
    chunk_type      VARCHAR(50) NOT NULL DEFAULT 'description', -- description / review / full_text
    indexed_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_search_vector_uid ON search_vector_index (uid);

-- 3.2 避雷标签定义表
CREATE TABLE IF NOT EXISTS search_safe_tags (
    id          BIGSERIAL PRIMARY KEY,
    uid         VARCHAR(64) NOT NULL REFERENCES novels(uid) ON DELETE CASCADE,
    tag         VARCHAR(100) NOT NULL,                       -- 避雷标签
    severity    VARCHAR(20)  NOT NULL DEFAULT 'warning',     -- warning / critical
    description TEXT,                                        -- 具体原因说明
    source      VARCHAR(50)  NOT NULL DEFAULT 'system',      -- system / user_report / agent
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_safe_tags UNIQUE (uid, tag)
);

CREATE INDEX idx_safe_tags_tag ON search_safe_tags (tag);

-- 3.3 搜索日志 (用于评估召回率)
CREATE TABLE IF NOT EXISTS search_logs (
    id              BIGSERIAL PRIMARY KEY,
    session_id      VARCHAR(64) NOT NULL,
    query_raw       TEXT        NOT NULL,
    query_rewritten TEXT,
    filters_json    JSONB,
    safe_tags_json  JSONB,
    results_uids    TEXT[],
    user_feedback   SMALLINT,                                -- -1=不满意, 0=无反馈, 1=满意
    latency_ms      INTEGER,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_search_logs_session ON search_logs (session_id);
CREATE INDEX idx_search_logs_created ON search_logs (created_at DESC);


-- =============================================================================
-- 4. Sentiment Critic 域: 舆情与评分
-- =============================================================================

-- 4.1 多维度评分表
CREATE TABLE IF NOT EXISTS sentiment_scores (
    id                  BIGSERIAL PRIMARY KEY,
    uid                 VARCHAR(64) NOT NULL REFERENCES novels(uid) ON DELETE CASCADE,
    overall             REAL        NOT NULL DEFAULT 0.0,     -- 综合分 [0, 10]
    style               REAL,                                 -- 文笔
    logic               REAL,                                 -- 逻辑
    character_building  REAL,                                 -- 人物塑造
    update_stability    REAL,                                 -- 更新稳定性
    toxicity_index      REAL        NOT NULL DEFAULT 0.0,     -- 毒性指数 [0, 1]
    score_version       VARCHAR(20) NOT NULL DEFAULT 'v1.0',
    scored_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_sentiment_score UNIQUE (uid, score_version)
);

CREATE INDEX idx_sentiment_scores_uid ON sentiment_scores (uid);
CREATE INDEX idx_sentiment_scores_overall ON sentiment_scores (overall DESC);

-- 4.2 点评摘要表
CREATE TABLE IF NOT EXISTS sentiment_summaries (
    id          BIGSERIAL PRIMARY KEY,
    uid         VARCHAR(64) NOT NULL REFERENCES novels(uid) ON DELETE CASCADE,
    one_liner   TEXT        NOT NULL,                         -- 一句话毒舌点评
    pros        TEXT[]      NOT NULL DEFAULT '{}',            -- 入坑理由 (最多 3 条)
    cons        TEXT[]      NOT NULL DEFAULT '{}',            -- 避雷点 (最多 3 条)
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_sentiment_summary UNIQUE (uid)
);

-- 4.3 原始评论数据
CREATE TABLE IF NOT EXISTS sentiment_raw_reviews (
    id              BIGSERIAL PRIMARY KEY,
    uid             VARCHAR(64) NOT NULL REFERENCES novels(uid) ON DELETE CASCADE,
    source_platform VARCHAR(50)  NOT NULL,                    -- douban / tieba / xiaohongshu
    source_url      VARCHAR(512),
    author_nickname VARCHAR(100),
    content         TEXT        NOT NULL,
    rating          SMALLINT,                                 -- 原始评分 (如有)
    sentiment_label VARCHAR(20),                              -- positive / negative / neutral
    crawled_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_raw_reviews_uid ON sentiment_raw_reviews (uid);
CREATE INDEX idx_raw_reviews_source ON sentiment_raw_reviews (source_platform);

-- 4.4 评论统计快照
CREATE TABLE IF NOT EXISTS sentiment_review_stats (
    id              BIGSERIAL PRIMARY KEY,
    uid             VARCHAR(64) NOT NULL REFERENCES novels(uid) ON DELETE CASCADE,
    total_count     INTEGER     NOT NULL DEFAULT 0,
    positive_ratio  REAL        NOT NULL DEFAULT 0.0,
    negative_ratio  REAL        NOT NULL DEFAULT 0.0,
    neutral_ratio   REAL        NOT NULL DEFAULT 0.0,
    source_breakdown JSONB,                                   -- {"tieba": N, "douban": N, ...}
    calculated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_review_stats UNIQUE (uid)
);


-- =============================================================================
-- 5. System Integrator 域: 系统运维
-- =============================================================================

-- 5.1 用户会话表
CREATE TABLE IF NOT EXISTS system_sessions (
    id              BIGSERIAL PRIMARY KEY,
    session_id      VARCHAR(64) NOT NULL UNIQUE,
    user_ip_hash    VARCHAR(64),
    intent          VARCHAR(50),                               -- search / sentiment / trend / mixed
    status          VARCHAR(20) NOT NULL DEFAULT 'active',     -- active / completed / expired
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ
);

CREATE INDEX idx_sessions_created ON system_sessions (created_at DESC);

-- 5.2 Token 消耗日志
CREATE TABLE IF NOT EXISTS system_token_logs (
    id              BIGSERIAL PRIMARY KEY,
    module          VARCHAR(50)  NOT NULL,                     -- trend / search / sentiment / router
    operation       VARCHAR(100) NOT NULL,                     -- embedding / completion / classification
    model_name      VARCHAR(100) NOT NULL,                     -- GPT-4 / Claude 3.5 / text-embedding-3-small
    tokens_input    INTEGER      NOT NULL DEFAULT 0,
    tokens_output   INTEGER      NOT NULL DEFAULT 0,
    cost_estimate   REAL,                                      -- 预估费用 (USD)
    latency_ms      INTEGER,
    success         BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_token_logs_module ON system_token_logs (module);
CREATE INDEX idx_token_logs_created ON system_token_logs (created_at DESC);

-- 5.3 API 调用审计日志
CREATE TABLE IF NOT EXISTS system_api_audit (
    id              BIGSERIAL PRIMARY KEY,
    endpoint        VARCHAR(255) NOT NULL,
    method          VARCHAR(10)  NOT NULL,
    caller_module   VARCHAR(50),
    status_code     SMALLINT,
    latency_ms      INTEGER,
    error_message   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_api_audit_created ON system_api_audit (created_at DESC);
CREATE INDEX idx_api_audit_endpoint ON system_api_audit (endpoint, created_at DESC);


-- =============================================================================
-- 6. 视图: 全局聚合数据 (供 Router Agent 快速查询)
-- =============================================================================
CREATE OR REPLACE VIEW v_novel_aggregated AS
SELECT
    n.uid,
    n.title,
    n.platform,
    n.author,
    n.category,
    n.last_updated_at,
    -- 趋势
    ths.heat_score,
    ths.rank,
    ths.trend_direction,
    -- 标签
    (SELECT array_agg(DISTINCT tt.tag) FROM trend_tags tt WHERE tt.uid = n.uid) AS tags,
    -- 评分
    ss.overall       AS sentiment_overall,
    ss.style         AS sentiment_style,
    ss.logic         AS sentiment_logic,
    ss.toxicity_index,
    -- 点评
    ssum.one_liner   AS critic_one_liner,
    -- 统计
    srs.total_count  AS review_count,
    srs.positive_ratio
FROM novels n
LEFT JOIN LATERAL (
    SELECT heat_score, rank, trend_direction
    FROM trend_heat_snapshots
    WHERE uid = n.uid
    ORDER BY snapshot_date DESC
    LIMIT 1
) ths ON TRUE
LEFT JOIN sentiment_scores ss ON n.uid = ss.uid AND ss.score_version = 'v1.0'
LEFT JOIN sentiment_summaries ssum ON n.uid = ssum.uid
LEFT JOIN sentiment_review_stats srs ON n.uid = srs.uid;
