"""SQLite database connection management and schema.

Tables (7):
  app_users          — application users (multi-user support)
  platform_accounts  — OJ platform account bindings (replaces old 'users' table)
  problems           — problem library (normalized from submissions)
  tags               — tag dictionary (canonical Chinese name is key)
  problem_tags       — many-to-many junction: problems <-> tags
  submissions        — submission records (references problems + platform_accounts)
  weekly_reports     — persisted generated weekly reports

Views (3):
  v_user_submission_stats   — per-user aggregate statistics
  v_tag_weakness_ranking    — tag-level weakness analysis
  v_daily_activity          — daily submission trends

Triggers (2):
  trg_app_users_updated_at          — auto-set updated_at on app_users modification
  trg_platform_accounts_updated_at  — auto-set updated_at on platform_accounts
"""
import sqlite3
import json
import os
import threading

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "acm_helper.db")

_local = threading.local()


def get_db() -> sqlite3.Connection:
    """Get the current thread's database connection."""
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(DB_PATH)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA foreign_keys=ON")
    return _local.conn


def _create_new_schema(db: sqlite3.Connection):
    """Create the new 7-table schema with views, triggers, and indexes."""
    db.executescript("""
        -- ============================================================
        -- TABLE 1: app_users — application users (multi-user support)
        -- ============================================================
        CREATE TABLE IF NOT EXISTS app_users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT NOT NULL UNIQUE,
            email         TEXT DEFAULT '',
            password_hash TEXT DEFAULT '',
            created_at    TEXT DEFAULT (datetime('now')),
            updated_at    TEXT DEFAULT (datetime('now'))
        );

        -- ============================================================
        -- TABLE 2: platform_accounts — OJ account bindings
        -- ============================================================
        CREATE TABLE IF NOT EXISTS platform_accounts (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            app_user_id   INTEGER NOT NULL REFERENCES app_users(id),
            platform      TEXT NOT NULL,
            username      TEXT NOT NULL,
            cookie        TEXT DEFAULT '',
            last_crawl_at TEXT,
            crawl_count   INTEGER DEFAULT 0,
            created_at    TEXT DEFAULT (datetime('now')),
            updated_at    TEXT DEFAULT (datetime('now')),
            UNIQUE(app_user_id, platform),
            UNIQUE(platform, username)
        );

        -- ============================================================
        -- TABLE 3: problems — problem library
        -- ============================================================
        CREATE TABLE IF NOT EXISTS problems (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            platform        TEXT NOT NULL,
            problem_id      TEXT NOT NULL,
            title           TEXT DEFAULT '',
            difficulty      INTEGER DEFAULT 0,
            url             TEXT DEFAULT '',
            content_snippet TEXT DEFAULT '',
            created_at      TEXT DEFAULT (datetime('now')),
            UNIQUE(platform, problem_id)
        );

        -- ============================================================
        -- TABLE 4: tags — tag dictionary
        -- ============================================================
        CREATE TABLE IF NOT EXISTS tags (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name_en     TEXT DEFAULT '',
            name_cn     TEXT NOT NULL UNIQUE,
            category    TEXT DEFAULT '',
            created_at  TEXT DEFAULT (datetime('now'))
        );

        -- ============================================================
        -- TABLE 5: problem_tags — N:M junction
        -- ============================================================
        CREATE TABLE IF NOT EXISTS problem_tags (
            problem_id  INTEGER NOT NULL REFERENCES problems(id) ON DELETE CASCADE,
            tag_id      INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
            PRIMARY KEY (problem_id, tag_id)
        );

        -- ============================================================
        -- TABLE 6: submissions — submission records (new structure)
        -- ============================================================
        CREATE TABLE IF NOT EXISTS submissions (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            platform_account_id INTEGER NOT NULL REFERENCES platform_accounts(id),
            problem_id          INTEGER NOT NULL REFERENCES problems(id),
            result              TEXT DEFAULT '',
            submit_time         TEXT DEFAULT '',
            language            TEXT DEFAULT '',
            code                TEXT DEFAULT '',
            record_id           TEXT DEFAULT '',
            created_at          TEXT DEFAULT (datetime('now')),
            UNIQUE(platform_account_id, problem_id, submit_time, result, language, record_id)
        );

        -- Indexes for submissions
        CREATE INDEX IF NOT EXISTS idx_submissions_pa_id
            ON submissions(platform_account_id);
        CREATE INDEX IF NOT EXISTS idx_submissions_pa_result
            ON submissions(platform_account_id, result);
        CREATE INDEX IF NOT EXISTS idx_submissions_pa_time
            ON submissions(platform_account_id, submit_time);

        -- ============================================================
        -- TABLE 7: weekly_reports — persisted reports
        -- ============================================================
        CREATE TABLE IF NOT EXISTS weekly_reports (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            app_user_id      INTEGER NOT NULL REFERENCES app_users(id),
            report_content   TEXT NOT NULL,
            period_start     TEXT NOT NULL,
            period_end       TEXT NOT NULL,
            platforms_covered TEXT DEFAULT '',
            generated_at     TEXT DEFAULT (datetime('now')),
            created_at       TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_weekly_reports_user
            ON weekly_reports(app_user_id, period_end);

        -- ============================================================
        -- Keep: deepseek_config (singleton)
        -- ============================================================
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
        INSERT OR IGNORE INTO deepseek_config (id) VALUES (1);

        -- ============================================================
        -- Keep: analysis_snapshots
        -- ============================================================
        CREATE TABLE IF NOT EXISTS analysis_snapshots (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER NOT NULL REFERENCES app_users(id),
            snapshot_data TEXT NOT NULL,
            generated_at  TEXT DEFAULT (datetime('now')),
            UNIQUE(user_id)
        );
    """)

    # Additional indexes
    db.executescript("""
        CREATE INDEX IF NOT EXISTS idx_problems_diff
            ON problems(platform, difficulty);
        CREATE INDEX IF NOT EXISTS idx_problem_tags_tag
            ON problem_tags(tag_id);
    """)

    # ---- VIEWS ----
    db.executescript("""
        -- View 1: Per-user submission statistics
        CREATE VIEW IF NOT EXISTS v_user_submission_stats AS
        SELECT
            pa.app_user_id,
            pa.platform,
            pa.username AS oj_username,
            COUNT(DISTINCT s.id) AS total_submissions,
            COUNT(DISTINCT CASE WHEN s.result = 'AC' THEN s.problem_id END) AS ac_problems,
            ROUND(
                CAST(COUNT(DISTINCT CASE WHEN s.result = 'AC' THEN s.problem_id END) AS REAL)
                / NULLIF(COUNT(DISTINCT s.problem_id), 0) * 100, 1
            ) AS ac_rate_pct,
            COUNT(DISTINCT CASE WHEN s.submit_time != ''
                THEN SUBSTR(s.submit_time, 1, 10) END) AS active_days,
            MAX(s.submit_time) AS last_submit,
            MIN(s.submit_time) AS first_submit
        FROM platform_accounts pa
        LEFT JOIN submissions s ON s.platform_account_id = pa.id
        GROUP BY pa.app_user_id, pa.platform, pa.username;

        -- View 2: Tag-level weakness analysis across all users
        CREATE VIEW IF NOT EXISTS v_tag_weakness_ranking AS
        SELECT
            pa.app_user_id,
            pa.platform,
            t.name_cn AS tag_name,
            t.name_en AS tag_en,
            COUNT(DISTINCT s.problem_id) AS problems_attempted,
            COUNT(DISTINCT CASE WHEN s.result = 'AC' THEN s.problem_id END) AS problems_ac,
            ROUND(
                CAST(COUNT(DISTINCT CASE WHEN s.result = 'AC' THEN s.problem_id END) AS REAL)
                / NULLIF(COUNT(DISTINCT s.problem_id), 0), 4
            ) AS ac_rate,
            ROUND(AVG(p.difficulty), 0) AS avg_difficulty,
            COUNT(DISTINCT CASE WHEN s.result = 'WA' THEN s.id END) AS wa_count,
            COUNT(DISTINCT CASE WHEN s.result = 'TLE' THEN s.id END) AS tle_count,
            COUNT(DISTINCT CASE WHEN s.result = 'RE' THEN s.id END) AS re_count
        FROM tags t
        JOIN problem_tags pt ON pt.tag_id = t.id
        JOIN problems p ON p.id = pt.problem_id
        JOIN submissions s ON s.problem_id = p.id
        JOIN platform_accounts pa ON pa.id = s.platform_account_id
        GROUP BY pa.app_user_id, pa.platform, t.id
        HAVING COUNT(DISTINCT s.problem_id) >= 3;

        -- View 3: Daily activity trends
        CREATE VIEW IF NOT EXISTS v_daily_activity AS
        SELECT
            pa.app_user_id,
            pa.platform,
            SUBSTR(s.submit_time, 1, 10) AS submit_date,
            COUNT(*) AS total_subs,
            SUM(CASE WHEN s.result = 'AC' THEN 1 ELSE 0 END) AS ac_subs
        FROM submissions s
        JOIN platform_accounts pa ON pa.id = s.platform_account_id
        WHERE s.submit_time != ''
        GROUP BY pa.app_user_id, pa.platform, SUBSTR(s.submit_time, 1, 10);
    """)

    # ---- TRIGGERS ----
    db.executescript("""
        -- Trigger 1: auto-set updated_at on app_users modification
        CREATE TRIGGER IF NOT EXISTS trg_app_users_updated_at
        AFTER UPDATE ON app_users
        FOR EACH ROW
        BEGIN
            UPDATE app_users SET updated_at = datetime('now') WHERE id = NEW.id;
        END;

        -- Trigger 2: auto-set updated_at on platform_accounts modification
        CREATE TRIGGER IF NOT EXISTS trg_platform_accounts_updated_at
        AFTER UPDATE ON platform_accounts
        FOR EACH ROW
        BEGIN
            UPDATE platform_accounts SET updated_at = datetime('now') WHERE id = NEW.id;
        END;
    """)


def _migrate_old_data(db: sqlite3.Connection):
    """Migrate data from old _migrate_* tables to new 7-table schema."""
    import sys
    print("  [DB] 检测到旧数据库格式，开始迁移...")

    # Check what old tables exist (renamed in init_db)
    has_old_users = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='_migrate_users'"
    ).fetchone() is not None
    has_old_submissions = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='_migrate_submissions'"
    ).fetchone() is not None

    if not has_old_users and not has_old_submissions:
        print("  [DB] 已是新格式，跳过迁移")
        return

    db.execute("PRAGMA foreign_keys=OFF")

    # ---- Step 1: Seed app_users ----
    db.execute("INSERT OR IGNORE INTO app_users (id, username, email) VALUES (1, '默认用户', '')")
    print("  [DB]   创建默认用户 (id=1)")

    # ---- Step 2: Migrate _migrate_users -> platform_accounts ----
    if has_old_users:
        old_users = db.execute(
            "SELECT id, platform, username, last_crawl_at, crawl_count, created_at FROM _migrate_users"
        ).fetchall()
        for u in old_users:
            db.execute(
                """INSERT OR IGNORE INTO platform_accounts
                   (id, app_user_id, platform, username, last_crawl_at, crawl_count, created_at)
                   VALUES (?, 1, ?, ?, ?, ?, ?)""",
                (u["id"], u["platform"], u["username"],
                 u["last_crawl_at"], u["crawl_count"], u["created_at"])
            )
        print(f"  [DB]   迁移 {len(old_users)} 条 users -> platform_accounts")

    # ---- Step 3: Seed tags from TAG_CN mapping ----
    from tag_map import TAG_CN, normalize_tags as _norm
    unique_cn_tags = set()
    for en_key, cn_name in TAG_CN.items():
        if cn_name and cn_name.strip():
            unique_cn_tags.add(cn_name.strip())
    for cn_name in sorted(unique_cn_tags):
        db.execute(
            "INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES (?, ?)",
            ("", cn_name)
        )
    print(f"  [DB]   种子 {len(unique_cn_tags)} 个标签")

    # ---- Step 4: Extract problems from _migrate_submissions ----
    if has_old_submissions:
        db.executescript("""
            INSERT OR IGNORE INTO problems (platform, problem_id, title, difficulty, url)
            SELECT
                platform,
                problem_id,
                MAX(COALESCE(title, '')),
                MAX(COALESCE(difficulty, 0)),
                MAX(COALESCE(url, ''))
            FROM _migrate_submissions
            WHERE platform IS NOT NULL AND problem_id IS NOT NULL
            GROUP BY platform, problem_id;
        """)
        problem_count = db.execute("SELECT COUNT(*) as c FROM problems").fetchone()["c"]
        print(f"  [DB]   提取 {problem_count} 个题目 -> problems")

        # ---- Step 5: Populate problem_tags from old JSON tags ----
        old_subs_with_tags = db.execute(
            "SELECT DISTINCT platform, problem_id, tags FROM _migrate_submissions WHERE tags != '[]' AND tags != ''"
        ).fetchall()
        tag_map = {}
        inserted_pairs = set()
        for row in old_subs_with_tags:
            try:
                raw_tags = json.loads(row["tags"])
            except (json.JSONDecodeError, TypeError):
                raw_tags = []
            normalized = _norm(raw_tags)
            for cn_tag in normalized:
                if cn_tag not in tag_map:
                    tr = db.execute(
                        "SELECT id FROM tags WHERE name_cn=?", (cn_tag,)
                    ).fetchone()
                    if tr:
                        tag_map[cn_tag] = tr["id"]
                    else:
                        cur = db.execute(
                            "INSERT OR IGNORE INTO tags (name_cn) VALUES (?)", (cn_tag,)
                        )
                        tag_map[cn_tag] = cur.lastrowid if cur.lastrowid else db.execute(
                            "SELECT id FROM tags WHERE name_cn=?", (cn_tag,)
                        ).fetchone()["id"]
                tag_id = tag_map[cn_tag]
                prob_row = db.execute(
                    "SELECT id FROM problems WHERE platform=? AND problem_id=?",
                    (row["platform"], row["problem_id"])
                ).fetchone()
                if prob_row:
                    pair = (prob_row["id"], tag_id)
                    if pair not in inserted_pairs:
                        db.execute(
                            "INSERT OR IGNORE INTO problem_tags (problem_id, tag_id) VALUES (?,?)",
                            pair
                        )
                        inserted_pairs.add(pair)
        print(f"  [DB]   创建 {len(inserted_pairs)} 条 problem_tags 关联")

        # ---- Step 6: Migrate _migrate_submissions to new submissions table ----
        migrated = 0
        failed = 0
        batch = []
        old_rows = db.execute(
            "SELECT id, user_id, platform, problem_id, result, submit_time, language, code, record_id, created_at FROM _migrate_submissions"
        ).fetchall()
        for row in old_rows:
            # Map old user_id -> new platform_accounts.id (same id preserved)
            pa_id = row["user_id"]
            # Map old (platform, problem_id) -> new problems.id
            prob_row = db.execute(
                "SELECT id FROM problems WHERE platform=? AND problem_id=?",
                (row["platform"], row["problem_id"])
            ).fetchone()
            if prob_row is None:
                failed += 1
                continue
            prob_id = prob_row["id"]
            batch.append((
                row["id"], pa_id, prob_id,
                row["result"] or "",
                row["submit_time"] or "",
                row["language"] or "",
                row["code"] or "",
                row["record_id"] or "",
                row["created_at"] or "",
            ))
            if len(batch) >= 500:
                db.executemany(
                    """INSERT OR IGNORE INTO submissions
                       (id, platform_account_id, problem_id, result, submit_time, language, code, record_id, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    batch
                )
                migrated += len(batch)
                batch = []
        if batch:
            db.executemany(
                """INSERT OR IGNORE INTO submissions
                   (id, platform_account_id, problem_id, result, submit_time, language, code, record_id, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                batch
            )
            migrated += len(batch)

        print(f"  [DB]   迁移 {migrated} 条提交记录 (跳过 {failed} 条无题目映射)")

    # ---- Step 7: Cleanup old tables ----
    if has_old_users:
        db.execute("DROP TABLE IF EXISTS _migrate_users")
        print("  [DB]   清理旧表 _migrate_users")
    if has_old_submissions:
        db.execute("DROP TABLE IF EXISTS _migrate_submissions")
        print("  [DB]   清理旧表 _migrate_submissions")

    db.execute("PRAGMA foreign_keys=ON")
    db.commit()
    print("  [DB] 迁移完成!")


def init_db():
    """Initialize database tables, views, triggers, and run migration if needed."""
    db = get_db()

    # Check what exists
    has_new = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='app_users'"
    ).fetchone() is not None
    has_old_users = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
    ).fetchone() is not None
    has_old_subs = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='submissions'"
    ).fetchone() is not None

    if not has_new:
        # Migration needed: rename old tables to avoid name conflicts
        if has_old_users:
            db.execute("ALTER TABLE users RENAME TO _migrate_users")
            print("  [DB] 重命名旧表 users -> _migrate_users")
        if has_old_subs:
            db.execute("ALTER TABLE submissions RENAME TO _migrate_submissions")
            print("  [DB] 重命名旧表 submissions -> _migrate_submissions")

        # Also handle deepseek_config and analysis_snapshots if they exist
        # (they are compatible, just preserve them via IF NOT EXISTS in _create_new_schema)
        has_old_snapshots = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='analysis_snapshots'"
        ).fetchone() is not None

        # Create new schema (now no conflicts)
        _create_new_schema(db)

        if has_old_users or has_old_subs:
            _migrate_old_data(db)
        else:
            # Fresh install: seed default user and tags
            db.execute("INSERT OR IGNORE INTO app_users (id, username, email) VALUES (1, '默认用户', '')")
            from tag_map import TAG_CN
            unique_cn_tags = set()
            for en_key, cn_name in TAG_CN.items():
                if cn_name and cn_name.strip():
                    unique_cn_tags.add(cn_name.strip())
            for cn_name in sorted(unique_cn_tags):
                db.execute("INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES (?, ?)", ("", cn_name))
            print(f"  [DB] 全新安装: 创建默认用户 + {len(unique_cn_tags)} 个种子标签")

    db.commit()
    print(f"  [DB] 数据库已就绪: {DB_PATH}")

    # Print schema summary
    tables = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    views = db.execute(
        "SELECT name FROM sqlite_master WHERE type='view' ORDER BY name"
    ).fetchall()
    triggers = db.execute(
        "SELECT name FROM sqlite_master WHERE type='trigger' ORDER BY name"
    ).fetchall()
    print(f"  [DB] 表: {', '.join(r['name'] for r in tables)}")
    print(f"  [DB] 视图: {', '.join(r['name'] for r in views)}")
    print(f"  [DB] 触发器: {', '.join(r['name'] for r in triggers)}")
