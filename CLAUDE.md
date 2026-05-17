# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

A local competitive programming (OJ) problem tracker with multi-platform sync, weakness analysis, and weekly AI-powered reports. Single-user, browser-based, Python backend + vanilla JS frontend.

## Commands

```bash
# Install deps (only curl_cffi is optional, for AtCoder/Luogu Cloudflare bypass)
pip install requests beautifulsoup4 curl_cffi

# Start server
NO_PROXY=* python server.py
# Opens at http://localhost:8765

# Delete all data and start fresh
rm -f acm_helper.db* cache.json bound_accounts.json email_config.json
```

No tests, no linter, no build step. The "backend" and "frontend" are in the same directory.

## Architecture

```
browser (tracker.html)
  │ localStorage: problem_tracker_data (JSON array)
  │ fetch() → localhost:8765
  ▼
server.py (http.server, port 8765)
  ├── /api/fetch/{codeforces,atcoder,luogu}     # old sync endpoints
  ├── /api/v2/crawl/start, /api/v2/crawl/progress/{id}  # task-based crawl
  ├── /api/v2/sync-all                          # sync all bound accounts
  ├── /api/v2/analysis/{platform}/{username}    # weakness analysis
  ├── /api/v2/submissions                       # get stored submissions
  ├── /api/accounts/bind                        # bind/unbind platform accounts
  ├── /api/email-config                         # SMTP + DeepSeek key config
  ├── /api/scheduler/trigger, /api/scheduler/status
  ├── /api/auto-tag                             # AI tag inference
  ├── /api/clear-data                           # wipe DB
  └── /api/analyze                              # old analysis endpoint
  │
  ├── crawler/          # CF crawler + task manager (in-memory)
  ├── db/               # SQLite via threading.local() connections
  ├── scheduler.py      # WeeklyReportScheduler: background thread, checks every 60s
  ├── report_generator.py  # Fills requirement.rm template → Markdown report
  ├── email_sender.py   # SMTP via smtplib
  ├── analyzer.py       # Weakness scoring engine (behavior-based, not tag-based)
  └── ai/deepseek_tagger.py  # DeepSeek API auto-tagging for untagged problems
```

## Key data flow

1. **Account binding**: POST `/api/accounts/bind` → writes `bound_accounts.json`
2. **Sync**: POST `/api/v2/sync-all` → background thread calls platform fetchers → writes SQLite → task progress tracked in `_task_mgr` (in-memory TaskManager singleton)
3. **Frontend load**: After sync, `loadFromServer()` calls GET `/api/v2/submissions` → merges into `localStorage.problem_tracker_data`
4. **Analysis**: Frontend sends all `problems` to POST `/api/analyze` (old) or GET `/api/v2/analysis/{p}/{u}` (new, queries DB)

## Important gotchas

- **Proxy**: The host has `HTTP_PROXY=127.0.0.1:7897`. ALL server requests must set `NO_PROXY=*` or `os.environ['NO_PROXY'] = '*'` before network calls. This has caused many hard-to-debug timeout issues.
- **curl_cffi threading**: `curl_cffi` can hang in background threads. The scheduler uses `server.fetch_luogu()` / `server.fetch_atcoder()` directly (lazy import) rather than duplicating the fetch logic, to avoid thread issues.
- **Submission dataclass**: `Submission.title` not `Submission.name`. Creating Submissions with `name=` kwarg causes silent failures. Both `_fetch_atcoder_subs` and `_fetch_luogu_subs` had this bug.
- **Luogu tags**: The `/record/list` API does NOT return tags — only `pid, title, difficulty, fullScore, type`. Tags require scraping problem detail pages (tag IDs like `[60,516]`) or using AI auto-tagging.
- **SQLite FK**: Foreign key checks fail in cross-thread connections despite `PRAGMA foreign_keys=ON`. Workaround: `PRAGMA foreign_keys=OFF` before bulk inserts, re-enable after.
- **User data**: The app was designed around `localStorage` but now syncs to SQLite. The bridge is `loadFromServer()` → merges into `problems[]` → `save()` → `localStorage`.
- **Port conflicts**: Old Python processes often linger on port 8765. Use `taskkill //F //IM python.exe` before restarting.
- **Encoding**: Terminal output is often garbled (GBK vs UTF-8 mismatch), but file I/O uses UTF-8 correctly.

## Chinese tag mapping

`TAG_CN` dict in `server.py` maps English algorithm tags to Chinese. `cnTag()` in `tracker.html` does the same for the frontend. Both must be kept in sync when adding new tags.
