"""SQLite 数据库连接管理"""
import sqlite3
import os
import threading

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "acm_helper.db")

_local = threading.local()


def get_db() -> sqlite3.Connection:
    """获取当前线程的数据库连接"""
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(DB_PATH)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA foreign_keys=ON")
    return _local.conn


def init_db():
    """初始化数据库表"""
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            platform      TEXT NOT NULL,
            username      TEXT NOT NULL,
            last_crawl_at TEXT,
            crawl_count   INTEGER DEFAULT 0,
            created_at    TEXT DEFAULT (datetime('now')),
            UNIQUE(platform, username)
        );

        CREATE TABLE IF NOT EXISTS submissions (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER NOT NULL REFERENCES users(id),
            platform      TEXT NOT NULL,
            problem_id    TEXT NOT NULL,
            title         TEXT DEFAULT '',
            difficulty    INTEGER DEFAULT 0,
            tags          TEXT DEFAULT '[]',
            result        TEXT DEFAULT '',
            submit_time   TEXT DEFAULT '',
            language      TEXT DEFAULT '',
            code          TEXT DEFAULT '',
            url           TEXT DEFAULT '',
            created_at    TEXT DEFAULT (datetime('now')),
            UNIQUE(user_id, platform, problem_id, submit_time, result)
        );

        CREATE INDEX IF NOT EXISTS idx_submissions_user
            ON submissions(user_id);
        CREATE INDEX IF NOT EXISTS idx_submissions_result
            ON submissions(user_id, result);
        CREATE INDEX IF NOT EXISTS idx_submissions_time
            ON submissions(user_id, submit_time);

        CREATE TABLE IF NOT EXISTS analysis_snapshots (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER NOT NULL REFERENCES users(id),
            snapshot_data TEXT NOT NULL,
            generated_at  TEXT DEFAULT (datetime('now')),
            UNIQUE(user_id)
        );

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
    """)

    # Migration: add 'result' to UNIQUE constraint (fixes same-day multi-submission dedup bug)
    cur = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='submissions'")
    row = cur.fetchone()
    old_sql = row['sql'] if row else ''
    if 'record_id' not in old_sql:
        print("  [DB] 迁移 submissions 表：添加 record_id 列 + 修正 UNIQUE 约束...")
        db.executescript("""
            CREATE TABLE IF NOT EXISTS submissions_new (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id       INTEGER NOT NULL REFERENCES users(id),
                platform      TEXT NOT NULL,
                problem_id    TEXT NOT NULL,
                title         TEXT DEFAULT '',
                difficulty    INTEGER DEFAULT 0,
                tags          TEXT DEFAULT '[]',
                result        TEXT DEFAULT '',
                submit_time   TEXT DEFAULT '',
                language      TEXT DEFAULT '',
                code          TEXT DEFAULT '',
                url           TEXT DEFAULT '',
                record_id     TEXT DEFAULT '',
                created_at    TEXT DEFAULT (datetime('now')),
                UNIQUE(user_id, platform, problem_id, submit_time, result, language)
            );
            INSERT OR IGNORE INTO submissions_new (id, user_id, platform, problem_id, title, difficulty, tags, result, submit_time, language, code, url, record_id, created_at)
                SELECT id, user_id, platform, problem_id, title, difficulty, tags, result, submit_time, language, code, url, '', created_at FROM submissions;
            DROP TABLE submissions;
            ALTER TABLE submissions_new RENAME TO submissions;
            CREATE INDEX IF NOT EXISTS idx_submissions_user ON submissions(user_id);
            CREATE INDEX IF NOT EXISTS idx_submissions_result ON submissions(user_id, result);
            CREATE INDEX IF NOT EXISTS idx_submissions_time ON submissions(user_id, submit_time);
        """)
        db.commit()
        print("  [DB] 迁移完成")
    db.commit()
    print(f"  [DB] 数据库已初始化: {DB_PATH}")
