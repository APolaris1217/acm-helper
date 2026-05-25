#!/usr/bin/env python3
"""Local server for problem-tracker — proxies platform APIs and serves the frontend.

Requires: curl_cffi (pip install curl_cffi) for AtCoder and Luogu (bypasses Cloudflare).
Codeforces works with the standard library alone.
"""
import http.server
import urllib.request
import urllib.parse
import urllib.error
import json
import os
import time
import ssl
import sys
import io
from datetime import datetime, timezone

# Analysis engine (legacy)
from analyzer import analyze as analyze_submissions

# New engine: strategy-based weakness detection + behavior metrics + structured report
from engine.report_builder import ReportBuilder
from engine.config import AnalysisConfig

# --- New: crawler & db modules ---
import threading
from crawler.base_crawler import BaseCrawler, Submission
from crawler.codeforces_crawler import CodeforcesCrawler
from crawler.nowcoder_crawler import NowCoderCrawler
from crawler.task_manager import TaskManager
from db.database import init_db, get_db
from scheduler import get_scheduler
from email_sender import load_config as load_email_config, save_config as save_email_config
from report_generator import generate_report

_task_mgr = TaskManager()
_CRAWLERS = {
    "codeforces": CodeforcesCrawler(),
}
# AtCoder/Luogu added below after their wrapper classes

BOUND_ACCOUNTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bound_accounts.json")

# --- Crawler wrappers for AtCoder / Luogu ---

class _AtCoderCrawler:
    """Adapter: wraps fetch_atcoder() to match BaseCrawler interface."""
    def fetch_submissions(self, username: str) -> list:
        return [Submission(
            platform=s["platform"], problem_id=s["problemId"], name=s["name"],
            difficulty=s["difficulty"], tags=s["tags"], result=s["result"],
            submit_time=s["date"], language=s["language"],
        ) for s in fetch_atcoder(username)]


class _LuoguCrawler:
    """Adapter: wraps fetch_luogu() to match BaseCrawler interface."""
    def __init__(self, cookie: str = ""):
        self.cookie = cookie

    def fetch_submissions(self, uid_or_username: str) -> list:
        return [Submission(
            platform=s["platform"], problem_id=s["problemId"], title=s["name"],
            difficulty=s["difficulty"], tags=s["tags"], result=s["result"],
            submit_time=s["date"], language=s["language"],
        ) for s in fetch_luogu(uid_or_username, self.cookie)]


class _NowCoderCrawler:
    """Adapter: wraps NowCoderCrawler to match BaseCrawler interface."""
    def __init__(self, cookie: str = ""):
        self.cookie = cookie

    def fetch_submissions(self, username: str) -> list:
        nc = NowCoderCrawler(cookie=self.cookie)
        return nc.fetch_submissions(username)


_CRAWLERS["atcoder"] = _AtCoderCrawler()
_CRAWLERS["luogu"] = _LuoguCrawler()
_CRAWLERS["nowcoder"] = _NowCoderCrawler()

# --- Tag name mapping ---
from tag_map import TAG_CN, cn_tag as _cn_tag

def _auto_tag_untagged():
    """Auto-tag all untagged problems using DeepSeek AI."""
    import json as _j
    try:
        from ai.deepseek_tagger import auto_tag_batch
        db2 = get_db()
        # Find all unique untagged problems
        rows = db2.execute(
            "SELECT DISTINCT problem_id, title, platform FROM submissions "
            "WHERE tags='[]' OR tags=''"
        ).fetchall()
        if not rows:
            print("  [TAGGER] No untagged problems")
            return
        # Deduplicate by problem_id
        seen = set()
        problems = []
        for r in rows:
            key = f"{r['platform']}:{r['problem_id']}"
            if key not in seen:
                seen.add(key)
                problems.append({"problem_id": r["problem_id"], "title": r["title"], "platform": r["platform"]})
        print(f"  [TAGGER] Auto-tagging {len(problems)} unique untagged problems...")
        tag_map = auto_tag_batch(problems)
        updated = 0
        for p in problems:
            pid = p["problem_id"]
            plat = p["platform"]
            tags = tag_map.get(pid, [])
            if tags:
                tags_json = _j.dumps(tags, ensure_ascii=False)
                db2.execute(
                    "UPDATE submissions SET tags=? WHERE platform=? AND problem_id=? AND (tags='[]' OR tags='')",
                    (tags_json, plat, pid)
                )
                updated += db2.total_changes
        db2.commit()
        print(f"  [TAGGER] Updated {updated} rows with AI tags")
    except Exception as e:
        import traceback
        print(f"  [TAGGER] Auto-tag failed: {e}")
        traceback.print_exc()


def _load_bound_accounts() -> dict:
    if os.path.exists(BOUND_ACCOUNTS_FILE):
        import json as _j
        with open(BOUND_ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            try:
                return _j.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
    return {}

def _run_crawl_task(platform: str, username: str, task_id: str, cookie: str = ""):
    """在后台线程中执行爬取任务"""
    tm = _task_mgr
    crawler = _CRAWLERS.get(platform)
    if not crawler:
        tm.update(task_id, status="failed", error=f"不支持的平台: {platform}")
        return

    # 如果是 Luogu / NowCoder crawler，设置 cookie（解决 cookie 丢失导致只有 AC/unsolved 的问题）
    if platform in ("luogu", "nowcoder") and cookie:
        crawler.cookie = cookie

    try:
        tm.update(task_id, status="running", message="开始爬取...", progress=0.1)
        all_subs = crawler.fetch_submissions(username)
        tm.update(task_id, total_fetched=len(all_subs),
                  message=f"已获取 {len(all_subs)} 条提交", progress=0.7)

        ac_subs = [s for s in all_subs if s.result == "AC"]
        tm.update(task_id, ac_count=len(ac_subs),
                  message=f"爬取完成: {len(all_subs)} 条提交，{len(ac_subs)} 道 AC 题目",
                  progress=1.0, status="done")

        # 写入数据库
        db = get_db()
        db.execute(
            "INSERT OR IGNORE INTO users (platform, username, last_crawl_at, crawl_count) "
            "VALUES (?, ?, datetime('now'), 1)",
            (platform, username)
        )
        db.execute(
            "UPDATE users SET last_crawl_at=datetime('now'), crawl_count=crawl_count+1 "
            "WHERE platform=? AND username=?",
            (platform, username)
        )

        user_row = db.execute(
            "SELECT id FROM users WHERE platform=? AND username=?", (platform, username)
        ).fetchone()
        user_id = user_row["id"]

        import json
        # Disable FK checks during bulk insert (cross-thread connection issue in SQLite)
        db.execute("PRAGMA foreign_keys=OFF")
        count = 0
        for s in all_subs:
            tags_json = json.dumps(s.tags, ensure_ascii=False)
            diff = s.difficulty or 0
            db.execute(
                "INSERT OR IGNORE INTO submissions "
                "(user_id, platform, problem_id, title, difficulty, tags, result, submit_time, language, url) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (user_id, s.platform, s.problem_id, s.title, diff,
                 tags_json, s.result, s.submit_time,
                 s.language, s.url)
            )
            # Update tags/difficulty if server has new data
            if (diff and diff > 0) or (tags_json and tags_json != '[]'):
                db.execute(
                    "UPDATE submissions SET difficulty=CASE WHEN difficulty=0 AND ? > 0 THEN ? ELSE difficulty END, "
                    "tags=CASE WHEN (tags='[]' OR tags='') AND ? != '[]' THEN ? ELSE tags END "
                    "WHERE user_id=? AND platform=? AND problem_id=? AND submit_time=? AND result=?",
                    (diff, diff, tags_json, tags_json, user_id, s.platform, s.problem_id, s.submit_time, s.result)
                )
            count += 1
        db.commit()
        db.execute("PRAGMA foreign_keys=ON")
        print(f"  [TASK {task_id}] 已写入 {count} 条记录 (user_id={user_id})")

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"  [TASK {task_id}] 爬取失败: {e}")
        print(f"  [TASK {task_id}] {tb}")
        tm.update(task_id, status="failed", error=f"{e}\n{tb[-500:]}")

# ---------------------------------------------------------------------------
# TLS / HTTP client setup
# ---------------------------------------------------------------------------
_SSL_CONTEXT = ssl.create_default_context()
_SSL_CONTEXT.check_hostname = False
_SSL_CONTEXT.verify_mode = ssl.CERT_NONE

# Try to load curl_cffi for Cloudflare-protected sites (AtCoder / Luogu)
try:
    from curl_cffi import requests as cf_requests
    _HAS_CURL_CFFI = True
except ImportError:
    cf_requests = None
    _HAS_CURL_CFFI = False

def _cf_get(url, headers=None, timeout=30, cookies=None):
    """GET request with Chrome TLS fingerprint impersonation."""
    h = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    if headers:
        h.update(headers)
    kw = {"impersonate": "chrome131", "timeout": timeout}
    if cookies:
        kw["cookies"] = cookies
    return cf_requests.get(url, headers=h, **kw)

PORT = 8765
CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache.json")
HTML_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tracker.html")

# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------
def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}

def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def cache_get(key, ttl=3600):
    cache = load_cache()
    entry = cache.get(key)
    if entry and (time.time() - entry["ts"]) < ttl:
        return entry["data"]
    return None

def cache_set(key, data):
    cache = load_cache()
    cache[key] = {"ts": time.time(), "data": data}
    save_cache(cache)

# ---------------------------------------------------------------------------
# Data transformation
# ---------------------------------------------------------------------------
LUOGU_DIFF_MAP = {0: 0, 1: 800, 2: 1200, 3: 1600, 4: 2000, 5: 2400, 6: 2800, 7: 3200}

CF_VERDICT_MAP = {
    "OK": "AC", "WRONG_ANSWER": "WA", "TIME_LIMIT_EXCEEDED": "TLE",
    "RUNTIME_ERROR": "RE", "COMPILATION_ERROR": "CE", "MEMORY_LIMIT_EXCEEDED": "MLE",
    "PRESENTATION_ERROR": "WA", "IDLENESS_LIMIT_EXCEEDED": "TLE",
    "SKIPPED": "unsolved", "PARTIAL": "partial", "CHALLENGED": "unsolved",
}

AC_VERDICT_MAP = {
    "AC": "AC", "WA": "WA", "TLE": "TLE", "RE": "RE", "CE": "CE",
    "MLE": "MLE", "OLE": "RE", "IE": "RE",
}

LUOGU_STATUS_MAP = {
    0: "unsolved", 1: "unsolved", 2: "CE", 3: "RE", 4: "MLE",
    5: "TLE", 6: "WA", 7: "RE", 11: "RE", 12: "AC",
    14: "unknown",  # "Unaccepted" — need record detail to get specific status
}
LUOGU_STRING_STATUS_MAP = {
    "accepted": "AC", "wrong answer": "WA", "time limit exceeded": "TLE",
    "time exceeded": "TLE", "memory limit exceeded": "MLE",
    "runtime error": "RE", "compile error": "CE",
    "output limit exceeded": "RE", "waiting": "unsolved",
    "judging": "unsolved", "running": "unsolved", "pending": "unsolved",
    "system error": "unsolved", "unknown error": "unsolved",
    "ac": "AC", "wa": "WA", "tle": "TLE", "mle": "MLE", "re": "RE", "ce": "CE",
    "ole": "RE", "uke": "RE", "pa": "partial",
}


def transform_cf(sub):
    verdict = sub.get("verdict") or "unsolved"
    result = CF_VERDICT_MAP.get(verdict, verdict)
    prob = sub.get("problem", {})
    ts = sub.get("creationTimeSeconds", 0)
    date = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d") if ts else ""
    return {
        "platform": "codeforces",
        "problemId": f"{prob.get('contestId','')}{prob.get('index','')}",
        "name": prob.get("name", ""),
        "difficulty": prob.get("rating", 0) or 0,
        "tags": [t.lower() for t in prob.get("tags", []) if t.lower() != "*special"],
        "result": result,
        "date": date,
        "language": sub.get("programmingLanguage", ""),
    }


def transform_ac(sub, diff_map):
    result = AC_VERDICT_MAP.get(sub.get("result", ""), sub.get("result", "unsolved"))
    ts = sub.get("epoch_second", 0)
    date = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d") if ts else ""
    pid = sub.get("problem_id", "")
    info = diff_map.get(pid, {})
    return {
        "platform": "atcoder",
        "problemId": pid,
        "name": info.get("title", pid),
        "difficulty": info.get("difficulty", 0) or 0,
        "tags": [],
        "result": result,
        "date": date,
        "language": sub.get("language", ""),
    }


def transform_lg(rec):
    status = rec.get("status", 0)
    if isinstance(status, str):
        result = LUOGU_STRING_STATUS_MAP.get(status.strip().lower(), "unsolved")
    else:
        result = LUOGU_STATUS_MAP.get(status, "unsolved")
    prob = rec.get("problem", {}) or {}
    ts = rec.get("submitTime", 0) or rec.get("time", 0)
    date = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d") if ts else ""
    lg_diff = prob.get("difficulty", 0)
    tags = prob.get("tags", []) or []
    if isinstance(tags, list) and tags and isinstance(tags[0], dict):
        tags = [t.get("name", str(t)) for t in tags]
    else:
        tags = [str(t) for t in tags]
    lang = rec.get("language", "")
    if isinstance(lang, int):
        LG_LANG = {
            0:"?",1:"C",2:"C++98",3:"C++11",4:"C++14",5:"C++17",
            6:"C++20",7:"C++23",8:"C#",9:"Python 3",10:"Java 8",
            11:"Java 11",12:"C++14",14:"Ruby",15:"Rust",16:"Go",
            17:"Kotlin",18:"Haskell",19:"JavaScript",20:"TypeScript",
            21:"Scala",22:"C++17",23:"C++20",24:"C++23",
            25:"Python 3",27:"Python 3",28:"C++17",
        }
        lang = LG_LANG.get(lang, f"ID:{lang}")
    rid = rec.get("id", 0)
    return {
        "platform": "luogu",
        "problemId": prob.get("pid", rec.get("pid", "")),
        "name": prob.get("title", ""),
        "difficulty": LUOGU_DIFF_MAP.get(lg_diff, lg_diff * 400),
        "tags": tags,
        "result": result,
        "date": date,
        "language": lang,
        "recordId": rid,
        "url": f"https://www.luogu.com.cn/record/{rid}" if rid else "",
    }

# ---------------------------------------------------------------------------
# Platform fetchers
# ---------------------------------------------------------------------------

def fetch_codeforces(handle):
    """CF has a public API — no Cloudflare, standard urllib works fine."""
    url = f"https://codeforces.com/api/user.status?handle={urllib.parse.quote(handle)}&from=1&count=100000"
    print(f"  [CF] Fetching...")
    req = urllib.request.Request(url, headers={"User-Agent": "problem-tracker/1.0"})
    with urllib.request.urlopen(req, timeout=30, context=_SSL_CONTEXT) as resp:
        data = json.loads(resp.read().decode())
    if data.get("status") != "OK":
        raise Exception(f"CF API error: {data.get('comment', 'unknown')}")
    submissions = data.get("result", [])
    print(f"  [CF] Got {len(submissions)} submissions")
    return [transform_cf(s) for s in submissions]


def fetch_atcoder(username):
    """Fetch from kenkoooo API — needs curl_cffi to bypass Cloudflare."""
    if not _HAS_CURL_CFFI:
        raise ClientError(
            "AtCoder 同步需要 curl_cffi 库来绕过 Cloudflare 保护。\n"
            "请运行: pip install curl_cffi"
        )

    # Step 1: get problem info + difficulty models
    print(f"  [AT] Fetching problem info...")
    r1 = _cf_get("https://kenkoooo.com/atcoder/resources/merged-problems.json", timeout=120)
    r1.raise_for_status()
    info_map = {p["id"]: p for p in r1.json()}
    print(f"  [AT] Got {len(info_map)} problems")

    print(f"  [AT] Fetching difficulty models...")
    r2 = _cf_get("https://kenkoooo.com/atcoder/resources/problem-models.json", timeout=120)
    r2.raise_for_status()
    models = r2.json()
    # Build combined map: title from info, difficulty from models (normalized +1000)
    diff_map = {}
    for pid, info in info_map.items():
        diff = models.get(pid, {}).get("difficulty")
        diff_map[pid] = {
            "title": info.get("title", pid),
            "difficulty": round(diff + 1000) if diff is not None else 0,
        }
    print(f"  [AT] Built diff_map with {len(diff_map)} entries")

    # Step 2: paginate submissions
    submissions = []
    from_second = 0
    page = 0
    while True:
        page += 1
        url = f"https://kenkoooo.com/atcoder/atcoder-api/v3/user/submissions?user={urllib.parse.quote(username)}&from_second={from_second}"
        if page > 1:
            time.sleep(0.3)
        r = _cf_get(url)
        if r.status_code == 404:
            break
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        submissions.extend(batch)
        from_second = batch[-1]["epoch_second"]
        print(f"  [AT] Page {page}: {len(batch)} subs (total {len(submissions)})")
        if len(batch) < 500:
            break
    print(f"  [AT] Got {len(submissions)} submissions total")
    return [transform_ac(s, diff_map) for s in submissions]


def fetch_luogu(uid, cookie_str=""):
    """Fetch from Luogu internal API.

    Luogu /record/list REQUIRES authentication.  The user must provide
    login cookies (__client_id + _uid) extracted from their browser.
    """
    if not _HAS_CURL_CFFI:
        raise ClientError(
            "洛谷同步需要 curl_cffi 库来绕过 Cloudflare 保护。\n"
            "请运行: pip install curl_cffi"
        )

    headers = {
        "x-lentille-request": "content-only",
        "x-luogu-type": "content-only",
        "Accept": "application/json",
        "Referer": "https://www.luogu.com.cn/",
    }

    # Parse cookie string into dict (supports key=value; key=value format)
    cookies = {}
    if cookie_str:
        for part in cookie_str.split(";"):
            part = part.strip()
            if "=" in part:
                k, v = part.split("=", 1)
                cookies[k.strip()] = v.strip()
        print(f"  [LG] Parsed {len(cookies)} cookies: {list(cookies.keys())}")

    submissions = []
    page = 1
    while True:
        url = f"https://www.luogu.com.cn/record/list?user={uid}&page={page}&_contentOnly=1"
        print(f"  [LG] Fetching page {page}...")
        r = _cf_get(url, headers=headers, cookies=cookies if cookies else None)
        print(f"  [LG] Page {page}: status={r.status_code}, content-type={r.headers.get('Content-Type','')[:60]}, len={len(r.text)}")

        if r.status_code != 200:
            print(f"  [LG] Non-200 status, stopping. Body[:300]: {r.text[:300]}")
            break

        # Try to parse JSON, provide details on failure
        try:
            data = r.json()
        except Exception as je:
            print(f"  [LG] JSON parse error: {je}")
            print(f"  [LG] Raw response[:500]: {r.text[:500]}")
            raise ClientError(
                f"洛谷返回了非 JSON 数据（可能是 Cookie 无效或已过期）。\n"
                f"请重新从浏览器复制 Cookie。\n"
                f"响应内容: {r.text[:300]}"
            )

        # Check for auth wall
        if data.get("instance") == "auth" or data.get("template") == "login":
            raise ClientError(
                "洛谷 /record/list 需要登录认证。Cookie 无效或已过期。\n"
                "请在浏览器中重新登录洛谷后，F12 → Application → Cookies → luogu.com.cn\n"
                "复制所有 Cookie 的 name=value，以分号分隔粘贴到输入框。\n"
                "示例: __client_id=xxx; _uid=yyy; C3VK=zzz"
            )

        # Try multiple response paths for records
        records = []
        for path in [
            ["currentData", "records", "result"],
            ["currentData", "result"],
            ["data", "records", "result"],
            ["data", "result"],
            ["result"],
        ]:
            d = data
            for key in path:
                d = d.get(key, {}) if isinstance(d, dict) else {}
            if isinstance(d, list) and len(d) > 0:
                records = d
                break

        if not records:
            # Print available keys to help debug
            cd = data.get("currentData", {})
            print(f"  [LG] No records found. currentData keys: {list(cd.keys()) if isinstance(cd, dict) else 'not dict'}")
            if isinstance(cd, dict) and "records" in cd:
                rd = cd["records"]
                print(f"  [LG] records keys: {list(rd.keys()) if isinstance(rd, dict) else type(rd).__name__}")
            break
        submissions.extend(records)
        print(f"  [LG] Page {page}: {len(records)} records (total {len(submissions)})")
        if records and page == 1:
            r0 = records[0]
            print(f"  [LG] DEBUG record keys: {list(r0.keys())}")
            print(f"  [LG] DEBUG record status: {r0.get('status')!r} (type={type(r0.get('status')).__name__})")
        if len(records) < 20:
            break
        page += 1
        time.sleep(0.5)
    print(f"  [LG] Got {len(submissions)} records total")

    # Enrich status=14 (Unaccepted) records by fetching individual detail
    unknown = [r for r in submissions if r.get("status") == 14]
    if unknown:
        print(f"  [LG] Enriching {len(unknown)} status=14 records...")
        enriched = 0
        for i, r in enumerate(unknown):
            rid = r.get("id", 0)
            if not rid:
                continue
            try:
                detail_url = f"https://www.luogu.com.cn/record/{rid}?_contentOnly=1"
                dr = _cf_get(detail_url, headers=headers, cookies=cookies if cookies else None, timeout=15)
                dd = dr.json()
                cd = dd.get("currentData", {})
                rec = cd.get("record", cd)
                if isinstance(rec, dict):
                    # Priority 1: direct status from record detail page
                    direct_status = rec.get("status")
                    if isinstance(direct_status, int) and direct_status not in (0, 1, 12, 14):
                        r["status"] = direct_status
                        enriched += 1
                        continue

                    # Priority 2: test case statuses from detail.judgeResult.subtasks
                    judge = rec.get("detail", {}).get("judgeResult", {})
                    subtasks = judge.get("subtasks", [])
                    tc_statuses = set()
                    for sub in subtasks:
                        tcs = sub.get("testCases") or []
                        if isinstance(tcs, dict):
                            for tc in tcs.values():
                                tc_statuses.add(tc.get("status"))
                        elif isinstance(tcs, list):
                            for tc in tcs:
                                tc_statuses.add(tc.get("status"))
                    # Find the most specific error (exclude 12=AC and 14=Unknown)
                    specific = tc_statuses - {12, 14}
                    if specific:
                        for priority in [6, 5, 7, 4, 2, 3]:
                            if priority in specific:
                                r["status"] = priority
                                enriched += 1
                                if enriched <= 3:
                                    print(f"    [LG]   {rid}: 14→{priority} ({LUOGU_STATUS_MAP.get(priority, '?')}) [testCases: {sorted(specific)}]")
                                break
                        else:
                            r["status"] = sorted(specific)[0]
                            enriched += 1
                    elif not tc_statuses:
                        # No test cases at all — use score to guess: 0=CE, >0=WA
                        score = rec.get("score", 0)
                        if score == 0:
                            r["status"] = 2  # CE
                        else:
                            r["status"] = 6  # WA
                        enriched += 1
                    else:
                        # tc_statuses only contains {12, 14} — all passed or unknown
                        # Use score to determine: 0 → likely CE, otherwise WA
                        score = rec.get("score", 0)
                        if score == 0:
                            r["status"] = 2  # CE
                        elif score >= 100:
                            r["status"] = 12  # full AC
                        else:
                            r["status"] = 6  # WA (partial)
                        enriched += 1
            except Exception:
                pass
            if i % 10 == 0 and i > 0:
                print(f"    [LG]   progress {i}/{len(unknown)}")
            time.sleep(0.15)  # rate limit
        print(f"  [LG] Enriched {enriched}/{len(unknown)} records")

    return [transform_lg(r) for r in submissions]

# ---------------------------------------------------------------------------
# HTTP Handler
# ---------------------------------------------------------------------------
class ClientError(Exception):
    """User-correctable error (bad input, missing auth, etc.)."""
    pass


class Handler(http.server.BaseHTTPRequestHandler):
    def _send_json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, content, code=200):
        body = content.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, msg, code=400):
        self._send_json({"error": True, "message": msg}, code)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        body = self.rfile.read(length).decode("utf-8")
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {}

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Cache-Control", "no-cache")

    def do_POST(self):
        """Handle POST requests — Python http.server auto-routes here."""
        self._handle_request()

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_DELETE(self):
        self._handle_request()

    def do_GET(self):
        self._handle_request()

    def _handle_request(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")
        params = dict(urllib.parse.parse_qsl(parsed.query))

        try:
            if path == "" or path == "/":
                if not os.path.exists(HTML_FILE):
                    self._send_error("tracker.html not found", 500)
                    return
                with open(HTML_FILE, "r", encoding="utf-8") as f:
                    self._send_html(f.read())

            elif path == "/api/fetch/codeforces":
                handle = params.get("handle", "").strip()
                if not handle:
                    self._send_error("Missing parameter: handle")
                    return
                cache_key = f"cf_{handle}"
                cached = cache_get(cache_key, ttl=1800)
                if cached is not None:
                    print(f"  [CF] Returning cached data for {handle}")
                    self._send_json(cached)
                    return
                data = fetch_codeforces(handle)
                cache_set(cache_key, data)
                self._send_json(data)

            elif path == "/api/fetch/atcoder":
                username = params.get("username", "").strip()
                if not username:
                    self._send_error("Missing parameter: username")
                    return
                cache_key = f"at_{username}"
                cached = cache_get(cache_key, ttl=3600)
                if cached is not None:
                    print(f"  [AT] Returning cached data for {username}")
                    self._send_json(cached)
                    return
                data = fetch_atcoder(username)
                cache_set(cache_key, data)
                self._send_json(data)

            elif path == "/api/fetch/luogu":
                uid = params.get("uid", "").strip()
                if not uid:
                    self._send_error("Missing parameter: uid")
                    return
                cookie = params.get("cookie", "")
                cache_key = f"lg_{uid}"
                cached = cache_get(cache_key, ttl=3600)
                if cached is not None:
                    print(f"  [LG] Returning cached data for {uid}")
                    self._send_json(cached)
                    return
                data = fetch_luogu(uid, cookie)
                cache_set(cache_key, data)
                self._send_json(data)

            elif path == "/api/analyze" and self.command == "POST":
                body = self._read_body()
                submissions = body if isinstance(body, list) else body.get("submissions", [])
                if not submissions:
                    self._send_error("Missing submissions", 400)
                    return
                print(f"  [ANALYZE] Analyzing {len(submissions)} submissions...")
                try:
                    report = analyze_submissions(submissions)
                    self._send_json(report)
                except Exception as e:
                    print(f"  [ANALYZE ERR] {e}")
                    self._send_error(str(e), 500)

            # ---- V2 API: 用户名分析流程 ----

            elif path == "/api/v2/crawl/start" and self.command == "POST":
                body = self._read_body()
                platform = body.get("platform", "").strip()
                username = body.get("username", "").strip()
                cookie = body.get("cookie", "")
                if not platform or not username:
                    self._send_error("Missing platform or username", 400)
                    return
                task = _task_mgr.create(platform, username)
                print(f"  [TASK {task.task_id}] 创建爬取任务: {platform}/{username}")
                # 启动后台线程执行爬取
                t = threading.Thread(
                    target=_run_crawl_task,
                    args=(platform, username, task.task_id, cookie),
                    daemon=True
                )
                t.start()
                self._send_json({
                    "task_id": task.task_id,
                    "status": "running",
                    "message": "任务已创建，开始爬取...",
                })

            elif path.startswith("/api/v2/crawl/progress/"):
                task_id = path.split("/")[-1]
                task = _task_mgr.get(task_id)
                if not task:
                    self._send_error("Task not found", 404)
                    return
                self._send_json({
                    "task_id": task.task_id,
                    "platform": task.platform,
                    "username": task.username,
                    "status": task.status,
                    "progress": task.progress,
                    "total_fetched": task.total_fetched,
                    "ac_count": task.ac_count,
                    "message": task.message,
                    "error": task.error,
                })

            # ---- V2.1 API: 新策略引擎分析 (strategy-based, must be before /api/v2/analysis/) ----

            elif path.startswith("/api/v2/analysis-v2/") and self.command == "GET":
                parts = path.split("/")
                if len(parts) < 6:
                    self._send_error("Invalid path, use /api/v2/analysis-v2/{platform}/{username}", 400)
                    return
                platform = parts[4]
                username = parts[5]

                db = get_db()
                user_row = db.execute(
                    "SELECT id FROM users WHERE platform=? AND username=?",
                    (platform, username)
                ).fetchone()

                if not user_row:
                    self._send_error(f"未找到用户: {platform}/{username}，请先爬取数据", 404)
                    return

                user_id = user_row["id"]
                rows = db.execute(
                    "SELECT * FROM submissions WHERE user_id=? AND platform=?",
                    (user_id, platform)
                ).fetchall()

                import json as _json
                subs = []
                for r in rows:
                    subs.append({
                        "platform": r["platform"],
                        "problemId": r["problem_id"],
                        "name": r["title"],
                        "difficulty": r["difficulty"],
                        "tags": _json.loads(r["tags"]) if r["tags"] else [],
                        "result": r["result"],
                        "date": (r["submit_time"] or "")[:10],
                        "language": r["language"],
                    })

                if not subs:
                    self._send_json({
                        "platform": platform,
                        "username": username,
                        "error": "无提交数据",
                        "summary": {},
                        "metrics": {},
                        "weaknesses": [],
                        "recommendations": [],
                    })
                    return

                try:
                    config = AnalysisConfig()
                    builder = ReportBuilder()
                    report = builder.build(subs, config)
                    report["platform"] = platform
                    report["username"] = username
                    self._send_json(report)
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    self._send_error(str(e), 500)

            elif path.startswith("/api/v2/analysis/") and self.command == "GET":
                # path: /api/v2/analysis/{platform}/{username}
                parts = path.split("/")
                if len(parts) < 6:
                    self._send_error("Invalid path, use /api/v2/analysis/{platform}/{username}", 400)
                    return
                platform = parts[4]
                username = parts[5]
                refresh = params.get("refresh", "false") == "true"

                # 从数据库加载用户提交
                db = get_db()
                user_row = db.execute(
                    "SELECT id FROM users WHERE platform=? AND username=?",
                    (platform, username)
                ).fetchone()

                if not user_row:
                    self._send_error(f"未找到用户: {platform}/{username}，请先爬取数据", 404)
                    return

                user_id = user_row["id"]
                rows = db.execute(
                    "SELECT * FROM submissions WHERE user_id=? AND platform=?",
                    (user_id, platform)
                ).fetchall()

                import json as _json
                subs = []
                for r in rows:
                    subs.append({
                        "platform": r["platform"],
                        "problemId": r["problem_id"],
                        "name": r["title"],
                        "difficulty": r["difficulty"],
                        "tags": _json.loads(r["tags"]) if r["tags"] else [],
                        "result": r["result"],
                        "date": (r["submit_time"] or "")[:10],
                        "language": r["language"],
                    })

                # 运行分析
                if subs:
                    raw_report = analyze_submissions(subs)
                    # Map analyzer output to v2 API format
                    weakness_ranking = raw_report.get("weakness_ranking", [])
                    suggestions_raw = raw_report.get("suggestions", [])
                    behavior = raw_report.get("behavior", {})

                    # Convert weakness_ranking to tag_weakness with frontend fields
                    tag_weakness = []
                    for item in weakness_ranking:
                        raw_tag = item.get("tag", "")
                        tag_weakness.append({
                            "tag": raw_tag,
                            "tag_cn": _cn_tag(raw_tag),
                            "ac_rate": round(item.get("ac_rate", 0) * 100, 1) if isinstance(item.get("ac_rate"), float) and item.get("ac_rate", 1) < 1 else item.get("ac_rate", 0),
                            "total": item.get("problem_count", len(item.get("problems", []))),
                            "weakness_score": item.get("score", 0),
                            "avg_difficulty": 0,
                            "error_breakdown": item.get("error_detail", {}),
                            "problem_list": [f"{platform}:{p}" for p in item.get("problems", [])[:10]],
                        })

                    # Convert suggestions to have level and single advice string
                    suggestions = []
                    for s in suggestions_raw:
                        raw_tag = s.get("tag", "")
                        score = s.get("score", 0)
                        advices = s.get("advice", [])
                        if isinstance(advices, str):
                            advices = [advices]
                        level = "critical" if score > 100 else "warning" if score > 50 else "info"
                        suggestions.append({
                            "level": level,
                            "tag": raw_tag,
                            "tag_cn": _cn_tag(raw_tag),
                            "advice": "；".join(advices),
                            "recommended_count": max(5, s.get("problem_count", 0) // 3),
                        })
                    print(f"  [V2-ANALYZE] Post-processed {len(suggestions_raw)} raw suggestions -> {len(suggestions)} formatted", flush=True)

                    report = {
                        "tag_weakness": tag_weakness,
                        "behavior_profile": behavior,
                        "suggestions": suggestions,
                        "_handler": "v2_analysis",  # marker to verify handler
                    }
                else:
                    report = {"tag_weakness": [], "behavior_profile": {}, "suggestions": []}

                # 基础统计
                ac_subs = [s for s in subs if s["result"] == "AC"]
                unique_ac = {}
                for s in ac_subs:
                    pid = s["problemId"]
                    if pid not in unique_ac:
                        unique_ac[pid] = s

                active_days = len(set(s["date"] for s in subs if s["date"]))
                total = len(subs)
                ac_cnt = len(ac_subs)

                from collections import Counter
                diff_counter = Counter(s["difficulty"] for s in unique_ac.values() if s["difficulty"])

                difficulty_distribution = {
                    "入门 (0-800)": sum(c for d, c in diff_counter.items() if d < 800),
                    "普及 (800-1200)": sum(c for d, c in diff_counter.items() if 800 <= d < 1200),
                    "提高 (1200-1600)": sum(c for d, c in diff_counter.items() if 1200 <= d < 1600),
                    "省选 (1600-2000)": sum(c for d, c in diff_counter.items() if 1600 <= d < 2000),
                    "NOI (2000-2400)": sum(c for d, c in diff_counter.items() if 2000 <= d < 2400),
                    "3000+": sum(c for d, c in diff_counter.items() if d >= 3000),
                }

                self._send_json({
                    "platform": platform,
                    "username": username,
                    "basic_stats": {
                        "total_ac_problems": len(unique_ac),
                        "total_submissions": total,
                        "ac_count": ac_cnt,
                        "ac_rate": round(ac_cnt / total * 100, 1) if total > 0 else 0,
                        "active_days": active_days,
                    },
                    "difficulty_distribution": difficulty_distribution,
                    "weakness": report,
                })

            # ---- Account binding ----

            elif path == "/api/accounts/bind" and self.command == "GET":
                accounts = {}
                if os.path.exists(BOUND_ACCOUNTS_FILE):
                    import json as _j
                    with open(BOUND_ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                        accounts = _j.load(f)
                safe = {}
                for plat, acc in accounts.items():
                    safe[plat] = {"username": acc.get("username", ""), "cookie": "***" if acc.get("cookie") else ""}
                self._send_json({"accounts": safe, "count": len(accounts)})

            elif path == "/api/accounts/bind" and self.command == "POST":
                body = self._read_body()
                platform = body.get("platform", "").strip()
                username = body.get("username", "").strip()
                cookie = body.get("cookie", "")
                if not platform or not username:
                    self._send_error("Missing platform or username", 400)
                    return
                accounts = {}
                if os.path.exists(BOUND_ACCOUNTS_FILE):
                    import json as _j
                    with open(BOUND_ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                        accounts = _j.load(f)
                accounts[platform] = {"username": username, "cookie": cookie}
                import json as _j
                with open(BOUND_ACCOUNTS_FILE, "w", encoding="utf-8") as f:
                    _j.dump(accounts, f, ensure_ascii=False, indent=2)
                get_scheduler().reload_accounts()
                print(f"  [ACCOUNTS] 绑定 {platform}: {username}")
                self._send_json({"ok": True, "platform": platform, "username": username})

            elif path.startswith("/api/accounts/bind/") and self.command == "DELETE":
                platform = path.split("/")[-1]
                accounts = {}
                if os.path.exists(BOUND_ACCOUNTS_FILE):
                    import json as _j
                    with open(BOUND_ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                        accounts = _j.load(f)
                if platform in accounts:
                    del accounts[platform]
                    import json as _j
                    with open(BOUND_ACCOUNTS_FILE, "w", encoding="utf-8") as f:
                        _j.dump(accounts, f, ensure_ascii=False, indent=2)
                    get_scheduler().reload_accounts()
                    self._send_json({"ok": True, "message": f"已解绑 {platform}"})
                else:
                    self._send_error(f"未找到 {platform} 绑定", 404)

            # ---- Email config ----

            elif path == "/api/email-config" and self.command == "GET":
                cfg = load_email_config()
                safe = dict(cfg)
                safe["sender_password"] = "***" if cfg.get("sender_password") else ""
                self._send_json(safe)

            elif path == "/api/email-config" and self.command == "POST":
                body = self._read_body()
                cfg = load_email_config()
                for key in ("smtp_host", "smtp_port", "sender_email", "sender_password",
                           "receiver_email", "schedule_day", "schedule_hour", "enabled"):
                    if key in body:
                        cfg[key] = body[key]
                save_email_config(cfg)
                if cfg.get("enabled"):
                    get_scheduler().reload_accounts()
                    get_scheduler().start()
                self._send_json({"ok": True, "message": "邮件配置已保存"})

            elif path == "/api/email-config/test" and self.command == "POST":
                body = self._read_body()
                cfg = load_email_config()
                try:
                    from email_sender import send_report
                    send_report(
                        "# ACM Helper 测试邮件\n\n这是一封测试邮件。\n\n> ACM Helper 自动发送",
                        f"[测试] ACM Helper 邮件配置验证 - {datetime.now().strftime('%H:%M:%S')}"
                    )
                    self._send_json({"ok": True, "message": "测试邮件已发送"})
                except Exception as e:
                    self._send_error(str(e), 500)

            # ---- Scheduler ----

            elif path == "/api/scheduler/status" and self.command == "GET":
                cfg = load_email_config()
                self._send_json({
                    "enabled": cfg.get("enabled", False),
                    "schedule_day": cfg.get("schedule_day", 1),
                    "schedule_hour": cfg.get("schedule_hour", 9),
                    "bound_accounts": len(get_scheduler()._bound_accounts),
                })

            elif path == "/api/scheduler/trigger" and self.command == "POST":
                body = self._read_body()
                platform = body.get("platform", "").strip()
                username = body.get("username", "").strip()
                if not platform or not username:
                    self._send_error("Missing platform or username", 400)
                    return

                def _manual_report():
                    sched = get_scheduler()
                    try:
                        sched._refresh_data(platform, username)
                        subs = sched._load_submissions(platform, username)
                        from datetime import timedelta
                        now = datetime.now()
                        report = generate_report(
                            target=f"{platform}: {username}",
                            from_date=(now - timedelta(days=7)).strftime("%Y-%m-%d"),
                            to_date=now.strftime("%Y-%m-%d"),
                            submissions=subs,
                        )
                        cfg = load_email_config()
                        if cfg.get("enabled") and cfg.get("receiver_email"):
                            send_report(report, f"ACM 训练周报 - {username}({platform}) - {now.strftime('%Y-%m-%d')}")
                        print(f"  [SCHEDULER] 手动周报已生成: {platform}/{username}")
                    except Exception as e:
                        print(f"  [SCHEDULER] 手动周报失败: {e}")

                threading.Thread(target=_manual_report, daemon=True).start()
                self._send_json({"ok": True, "message": f"周报生成已触发: {platform}/{username}"})

            # ---- Get submissions for bound accounts ----
            elif path == "/api/v2/submissions" and self.command == "GET":
                platform = params.get("platform", "").strip()
                username = params.get("username", "").strip()
                db = get_db()
                if platform and username:
                    user_row = db.execute("SELECT id FROM users WHERE platform=? AND username=?", (platform, username)).fetchone()
                    if not user_row:
                        self._send_json([])
                        return
                    rows = db.execute("SELECT * FROM submissions WHERE user_id=?", (user_row["id"],)).fetchall()
                else:
                    # Return all bound accounts' submissions
                    accounts = _load_bound_accounts()
                    rows = []
                    for plat, acc in accounts.items():
                        uname = acc.get("username", "")
                        if not uname:
                            continue
                        ur = db.execute("SELECT id FROM users WHERE platform=? AND username=?", (plat, uname)).fetchone()
                        if ur:
                            batch = db.execute("SELECT * FROM submissions WHERE user_id=?", (ur["id"],)).fetchall()
                            rows.extend(batch)
                import json as _j
                result = []
                for r in rows:
                    result.append({
                        "platform": r["platform"],
                        "problemId": r["problem_id"],
                        "name": r["title"],
                        "difficulty": r["difficulty"],
                        "tags": _j.loads(r["tags"]) if r["tags"] else [],
                        "result": r["result"],
                        "date": (r["submit_time"] or "")[:10],
                        "language": r["language"],
                    })
                self._send_json(result)

            # ---- Sync all bound accounts ----
            elif path == "/api/v2/sync-all" and self.command == "POST":
                accounts = _load_bound_accounts()
                if not accounts:
                    self._send_error("没有绑定的账户，请先在「账户绑定」页面添加", 400)
                    return

                task = _task_mgr.create("all", ", ".join(f"{p}:{a.get('username','')}" for p, a in accounts.items()))
                task_id = task.task_id

                def _sync_all():
                    tm = _task_mgr
                    sched = get_scheduler()
                    plats = list(accounts.keys())
                    total = len(plats)
                    for i, plat in enumerate(plats):
                        acc = accounts[plat]
                        uname = acc.get("username", "")
                        if not uname:
                            continue
                        tm.update(task_id, status="running", progress=round(i/total, 2),
                                  message=f"正在同步 {plat}/{uname} ({i+1}/{total})...")
                        try:
                            sched._refresh_data(plat, uname, acc.get("cookie", ""))
                            tm.update(task_id, total_fetched=(i+1), ac_count=0,
                                      message=f"{plat}/{uname} 完成 ({i+1}/{total})",
                                      progress=round((i+1)/total, 2))
                            print(f"  [SYNC-ALL] {plat}/{uname} OK")
                        except Exception as e:
                            print(f"  [SYNC-ALL] {plat}/{uname} 失败: {e}")
                            tm.update(task_id, error=f"{plat}/{uname}: {e}")
                    # Auto-tag untagged problems
                    tm.update(task_id, status="running", progress=0.95,
                              message="AI 自动识别题目标签...")
                    _auto_tag_untagged()
                    tm.update(task_id, status="done", progress=1.0,
                              message=f"全部 {total} 个账户同步完成")

                threading.Thread(target=_sync_all, daemon=True).start()
                self._send_json({"ok": True, "task_id": task_id, "accounts": list(accounts.keys())})

            # ---- AI Auto-tag ----
            elif path == "/api/auto-tag" and self.command == "POST":
                body = self._read_body()
                platform = body.get("platform", "").strip()
                if not platform:
                    self._send_error("Missing platform", 400)
                    return
                from ai.deepseek_tagger import auto_tag_batch
                db = get_db()
                # Find untagged problems
                rows = db.execute(
                    "SELECT DISTINCT problem_id, title FROM submissions "
                    "WHERE platform=? AND (tags='[]' OR tags='')",
                    (platform,)
                ).fetchall()
                problems = [{"problem_id": r["problem_id"], "title": r["title"]} for r in rows]
                # Deduplicate by problem_id
                seen = {}
                unique = []
                for p in problems:
                    if p["problem_id"] not in seen:
                        seen[p["problem_id"]] = True
                        unique.append(p)
                if not unique:
                    self._send_json({"ok": True, "message": "没有需要打标签的题目", "count": 0})
                    return

                print(f"  [TAGGER] Auto-tagging {len(unique)} problems for {platform}...")
                def _do_tag():
                    import json as _j
                    try:
                        tag_map = auto_tag_batch(unique)
                        db2 = get_db()
                        updated = 0
                        for pid, tags in tag_map.items():
                            if tags:
                                tags_json = _j.dumps(tags, ensure_ascii=False)
                                db2.execute(
                                    "UPDATE submissions SET tags=? WHERE platform=? AND problem_id=? AND (tags='[]' OR tags='')",
                                    (tags_json, platform, pid)
                                )
                                updated += db2.total_changes
                        db2.commit()
                        print(f"  [TAGGER] Updated {updated} rows for {platform}")
                    except Exception as e:
                        import traceback
                        print(f"  [TAGGER] Failed: {e}")
                        traceback.print_exc()

                threading.Thread(target=_do_tag, daemon=True).start()
                self._send_json({"ok": True, "message": f"开始为 {len(unique)} 道{platform}题目打标签...", "count": len(unique)})

            # ---- Clear data ----
            elif path == "/api/clear-data" and self.command == "POST":
                body = self._read_body()
                tgt_plat = body.get("platform", "").strip()
                tgt_user = body.get("username", "").strip()
                db = get_db()
                if tgt_plat and tgt_user:
                    ur = db.execute("SELECT id FROM users WHERE platform=? AND username=?", (tgt_plat, tgt_user)).fetchone()
                    if ur:
                        db.execute("DELETE FROM submissions WHERE user_id=?", (ur["id"],))
                        db.execute("DELETE FROM users WHERE id=?", (ur["id"],))
                        db.commit()
                        self._send_json({"ok": True, "message": f"已清除 {tgt_plat}/{tgt_user}"})
                    else:
                        self._send_error("未找到", 404)
                else:
                    db.execute("DELETE FROM submissions")
                    db.execute("DELETE FROM users")
                    db.execute("DELETE FROM analysis_snapshots")
                    db.commit()
                    self._send_json({"ok": True, "message": "已清除全部数据"})

            else:
                self._send_error("Not found", 404)

        except urllib.error.URLError as e:
            print(f"  [ERR] Network: {e}")
            self._send_error(f"Network error: {e.reason}", 502)
        except urllib.error.HTTPError as e:
            print(f"  [ERR] HTTP: {e.code} {e.reason}")
            self._send_error(f"Upstream API returned {e.code}", 502)
        except json.JSONDecodeError as e:
            print(f"  [ERR] JSON: {e}")
            self._send_error("Failed to parse upstream API response", 502)
        except ClientError as e:
            print(f"  [CLIENT_ERR] {e}")
            self._send_error(str(e), 400)
        except Exception as e:
            print(f"  [ERR] {e}")
            self._send_error(str(e), 500)

    def log_message(self, format, *args):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]}")


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    init_db()

    # 启动周报调度器
    email_cfg = load_email_config()
    if email_cfg.get("enabled"):
        sched = get_scheduler()
        sched.start()

    if not _HAS_CURL_CFFI:
        print("=" * 60)
        print("  注意: 未安装 curl_cffi，洛谷和 AtCoder 同步将不可用。")
        print("  请运行: pip install curl_cffi")
        print("  Codeforces 同步不受影响。")
        print("=" * 60)
    else:
        print(f"=" * 60)
        print(f"  做题记录平台服务已启动")
        print(f"  打开浏览器访问: http://localhost:{PORT}")
        print(f"  按 Ctrl+C 停止")
        print(f"=" * 60)

    addr = ("0.0.0.0", PORT)
    server = http.server.HTTPServer(addr, Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止")
        server.server_close()


if __name__ == "__main__":
    main()
