-- =============================================================================
-- ACM-Helper Database Schema
-- 7 tables + 8 indexes
-- Usage: sqlite3 acm_helper.db < schema.sql
-- =============================================================================

PRAGMA foreign_keys = ON;

-- =============================================================================
-- TABLE 1: app_users — application users (multi-user support)
-- =============================================================================
CREATE TABLE IF NOT EXISTS app_users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    email         TEXT DEFAULT '',
    password_hash TEXT DEFAULT '',
    created_at    TEXT DEFAULT (datetime('now')),
    updated_at    TEXT DEFAULT (datetime('now'))
);

-- =============================================================================
-- TABLE 2: platform_accounts — OJ platform account bindings
--           1 app_user : N platform_accounts
-- =============================================================================
CREATE TABLE IF NOT EXISTS platform_accounts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    app_user_id   INTEGER NOT NULL REFERENCES app_users(id),
    platform      TEXT NOT NULL,          -- 'codeforces' | 'atcoder' | 'luogu' | 'nowcoder'
    username      TEXT NOT NULL,          -- OJ username
    cookie        TEXT DEFAULT '',
    last_crawl_at TEXT,
    crawl_count   INTEGER DEFAULT 0,
    created_at    TEXT DEFAULT (datetime('now')),
    updated_at    TEXT DEFAULT (datetime('now')),
    UNIQUE(app_user_id, platform),
    UNIQUE(platform, username)
);

-- =============================================================================
-- TABLE 3: problems — problem library (normalized from submissions)
-- =============================================================================
CREATE TABLE IF NOT EXISTS problems (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    platform        TEXT NOT NULL,
    problem_id      TEXT NOT NULL,        -- platform-specific ID (e.g., "4A" for CF)
    title           TEXT DEFAULT '',
    difficulty      INTEGER DEFAULT 0,
    url             TEXT DEFAULT '',
    content_snippet TEXT DEFAULT '',
    created_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(platform, problem_id)
);

-- =============================================================================
-- TABLE 4: tags — algorithm tag dictionary
-- =============================================================================
CREATE TABLE IF NOT EXISTS tags (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name_en     TEXT DEFAULT '',
    name_cn     TEXT NOT NULL UNIQUE,      -- canonical Chinese name (e.g., "动态规划")
    category    TEXT DEFAULT '',           -- 'algorithm' | 'data-structure' | 'math' | ...
    created_at  TEXT DEFAULT (datetime('now'))
);

-- =============================================================================
-- TABLE 5: problem_tags — N:M junction: problems <-> tags
--           Replaces old JSON tags column, satisfies 1NF
-- =============================================================================
CREATE TABLE IF NOT EXISTS problem_tags (
    problem_id  INTEGER NOT NULL REFERENCES problems(id) ON DELETE CASCADE,
    tag_id      INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (problem_id, tag_id)
);

-- =============================================================================
-- TABLE 6: submissions — submission records
--           1 platform_account : N submissions
--           1 problem : N submissions
-- =============================================================================
CREATE TABLE IF NOT EXISTS submissions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    platform_account_id INTEGER NOT NULL REFERENCES platform_accounts(id),
    problem_id          INTEGER NOT NULL REFERENCES problems(id),
    result              TEXT DEFAULT '',    -- 'AC' | 'WA' | 'TLE' | 'RE' | 'CE' | ...
    submit_time         TEXT DEFAULT '',    -- ISO 8601 format
    language            TEXT DEFAULT '',
    code                TEXT DEFAULT '',
    record_id           TEXT DEFAULT '',    -- platform-specific submission ID
    created_at          TEXT DEFAULT (datetime('now')),
    UNIQUE(platform_account_id, problem_id, submit_time, result, language, record_id)
);

-- =============================================================================
-- TABLE 7: weekly_reports — persisted AI-generated weekly reports
-- =============================================================================
CREATE TABLE IF NOT EXISTS weekly_reports (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    app_user_id       INTEGER NOT NULL REFERENCES app_users(id),
    report_content    TEXT NOT NULL,         -- Markdown content
    period_start      TEXT NOT NULL,
    period_end        TEXT NOT NULL,
    platforms_covered TEXT DEFAULT '',       -- comma-separated platform names
    generated_at      TEXT DEFAULT (datetime('now')),
    created_at        TEXT DEFAULT (datetime('now'))
);

-- =============================================================================
-- TABLE 8: deepseek_config — AI configuration singleton (id always = 1)
-- =============================================================================
CREATE TABLE IF NOT EXISTS deepseek_config (
    id            INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    api_key       TEXT DEFAULT '',
    model         TEXT DEFAULT 'deepseek-chat',
    temperature   REAL DEFAULT 0.2,
    max_tokens    INTEGER DEFAULT 4096,
    timeout_s     INTEGER DEFAULT 600,
    base_url      TEXT DEFAULT 'https://api.deepseek.com/v1',
    updated_at    TEXT DEFAULT (datetime('now'))
);

-- =============================================================================
-- TABLE 9: analysis_snapshots — cached weakness analysis results
-- =============================================================================
CREATE TABLE IF NOT EXISTS analysis_snapshots (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL REFERENCES app_users(id),
    snapshot_data TEXT NOT NULL,             -- JSON blob
    generated_at  TEXT DEFAULT (datetime('now')),
    UNIQUE(user_id)
);

-- =============================================================================
-- INDEXES
-- =============================================================================

-- Speed up: query submissions by platform_account
CREATE INDEX IF NOT EXISTS idx_submissions_pa_id
    ON submissions(platform_account_id);

-- Speed up: filter submissions by result (e.g., AC rate calculation)
CREATE INDEX IF NOT EXISTS idx_submissions_pa_result
    ON submissions(platform_account_id, result);

-- Speed up: sort submissions by time for trend analysis
CREATE INDEX IF NOT EXISTS idx_submissions_pa_time
    ON submissions(platform_account_id, submit_time);

-- Speed up: find problems by difficulty range
CREATE INDEX IF NOT EXISTS idx_problems_diff
    ON problems(platform, difficulty);

-- Speed up: reverse lookup — which problems have a given tag
CREATE INDEX IF NOT EXISTS idx_problem_tags_tag
    ON problem_tags(tag_id);

-- Speed up: query weekly reports by user and period
CREATE INDEX IF NOT EXISTS idx_weekly_reports_user
    ON weekly_reports(app_user_id, period_end);
