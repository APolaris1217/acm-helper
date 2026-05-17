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

# Analysis engine
from analyzer import analyze as analyze_submissions

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
        "tags": [t.lower() for t in prob.get("tags", [])],
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
        lang = str(lang)
    return {
        "platform": "luogu",
        "problemId": prob.get("pid", rec.get("pid", "")),
        "name": prob.get("title", ""),
        "difficulty": LUOGU_DIFF_MAP.get(lg_diff, lg_diff * 400),
        "tags": tags,
        "result": result,
        "date": date,
        "language": lang,
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

    # Step 1: get difficulty map
    print(f"  [AT] Fetching problem difficulty map...")
    r = _cf_get("https://kenkoooo.com/atcoder/resources/merged-problems.json")
    r.raise_for_status()
    raw = r.json()
    diff_map = {p["id"]: p for p in raw}
    print(f"  [AT] Got {len(diff_map)} problems")

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
        if len(records) < 20:
            break
        page += 1
        time.sleep(0.5)
    print(f"  [LG] Got {len(submissions)} records total")
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

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Cache-Control", "no-cache")

    def do_POST(self):
        """Handle POST requests — Python http.server auto-routes here."""
        self._handle_request()

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

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
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length).decode("utf-8") if length > 0 else "[]"
                try:
                    submissions = json.loads(body)
                except json.JSONDecodeError:
                    self._send_error("Invalid JSON body", 400)
                    return
                print(f"  [ANALYZE] Analyzing {len(submissions)} submissions...")
                try:
                    report = analyze_submissions(submissions)
                    self._send_json(report)
                except Exception as e:
                    print(f"  [ANALYZE ERR] {e}")
                    self._send_error(str(e), 500)

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
