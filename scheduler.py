"""定时任务调度器 — 每周自动生成并发送周报"""
import threading
import time
import json
import os
from datetime import datetime, timedelta
from db.database import get_db
from email_sender import load_config as load_email_config, send_report
from report_generator import generate_report

SCHEDULE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "email_config.json")


class WeeklyReportScheduler:
    """周报定时调度器

    用法:
        sched = WeeklyReportScheduler()
        sched.start()  # 后台运行
    """

    def __init__(self):
        self._running = False
        self._thread = None
        self._last_sent_week = None  # 防止同一周重复发送
        self._bound_accounts: dict[str, dict] = {}  # platform -> {username, cookie}
        self._last_periodic_sync = 0  # 上次定时同步的时间戳
        self._periodic_interval = 6 * 3600  # 每 6 小时同步一次

    def start(self):
        if self._running:
            return
        self._running = True
        self._load_bound_accounts()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print("  [SCHEDULER] 周报调度器已启动")

    def stop(self):
        self._running = False

    def reload_accounts(self):
        self._load_bound_accounts()

    def _load_bound_accounts(self):
        """从配置文件加载绑定的账户"""
        import json as _json
        cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bound_accounts.json")
        if os.path.exists(cfg_path):
            with open(cfg_path, "r", encoding="utf-8") as f:
                self._bound_accounts = _json.load(f)
        else:
            self._bound_accounts = {}

    def _loop(self):
        """主循环：每分钟检查一次是否到发送时间"""
        while self._running:
            try:
                self._check_and_send()
                self._check_periodic_sync()
            except Exception as e:
                print(f"  [SCHEDULER ERR] {e}")

            # 每分钟检查一次
            time.sleep(60)

    def _check_and_send(self):
        cfg = load_email_config()
        if not cfg.get("enabled"):
            return

        now = datetime.now()
        target_day = cfg.get("schedule_day", 1)  # 默认周一
        target_hour = cfg.get("schedule_hour", 9)

        # 检查是否到了发送时间（目标星期几 + 目标小时）
        if now.weekday() != target_day:
            return
        if now.hour != target_hour:
            return

        # 检查本周是否已发送
        week_key = f"{now.year}-W{now.isocalendar()[1]}"
        if self._last_sent_week == week_key:
            return

        self._last_sent_week = week_key

        print(f"  [SCHEDULER] 触发周报生成: {week_key}")

        # 收集所有平台数据
        all_subs = []
        accounts = list(self._bound_accounts.items())
        for platform, account in accounts:
            username = account.get("username", "")
            if not username:
                continue
            try:
                self._refresh_data(platform, username, account.get("cookie", ""))
            except Exception as e:
                print(f"  [SCHEDULER] 爬取失败 {platform}/{username}: {e}")
                continue
            subs = self._load_submissions(platform, username)
            for s in subs:
                s["_platform"] = platform
                s["_username"] = username
            all_subs.extend(subs)

        if not all_subs:
            print("  [SCHEDULER] 无提交数据，跳过周报")
            return

        # 生成统一综合周报
        try:
            from_date = (now - timedelta(days=7)).strftime("%Y-%m-%d")
            to_date = now.strftime("%Y-%m-%d")
            targets = [f"{p}: {a.get('username', '')}" for p, a in accounts if a.get("username", "")]
            report = generate_report(
                target=", ".join(targets),
                from_date=from_date,
                to_date=to_date,
                submissions=all_subs,
            )
            subject = f"ACM 训练周报 - {to_date}"
            send_report(report, subject)
            print(f"  [SCHEDULER] 周报已发送: {subject}")
        except Exception as e:
            print(f"  [SCHEDULER] 周报发送失败: {e}")

    def _check_periodic_sync(self):
        """每隔 N 小时自动同步所有平台数据，保持数据新鲜"""
        if not self._bound_accounts:
            return
        now = time.time()
        # 首次跳过，让启动同步先完成
        if self._last_periodic_sync == 0:
            self._last_periodic_sync = now
            return
        if now - self._last_periodic_sync < self._periodic_interval:
            return
        self._last_periodic_sync = now
        print(f"  [SCHEDULER] 定时同步触发（每 {self._periodic_interval // 3600}h）")
        for platform, account in self._bound_accounts.items():
            username = account.get("username", "")
            if not username:
                continue
            try:
                self._refresh_data(platform, username, account.get("cookie", ""))
                print(f"  [SCHEDULER] 定时同步 {platform}/{username} OK")
            except Exception as e:
                print(f"  [SCHEDULER] 定时同步 {platform}/{username} FAILED: {e}")
        try:
            import server as _sv
            _sv._auto_tag_untagged()
            print("  [SCHEDULER] 定时标签补全完成")
        except Exception as e:
            print(f"  [SCHEDULER] 定时标签补全失败: {e}")

    def _refresh_data(self, platform: str, username: str, cookie: str = "", app_user_id: int = 1):
        """Fetch latest data and write to database — new schema."""
        from db.database import get_db
        import json as _json

        # Get submissions based on platform
        if platform == "codeforces":
            from crawler.codeforces_crawler import CodeforcesCrawler
            subs = CodeforcesCrawler().fetch_submissions(username)
        elif platform == "atcoder":
            import server as _sv
            from crawler.base_crawler import Submission
            raw = _sv.fetch_atcoder(username)
            subs = [Submission(
                platform=r["platform"], problem_id=r["problemId"], title=r["name"],
                difficulty=r["difficulty"], tags=r["tags"], result=r["result"],
                submit_time=r["date"], language=r["language"],
            ) for r in raw]
        elif platform == "luogu":
            import server as _sv
            from crawler.base_crawler import Submission
            raw = _sv.fetch_luogu(username, cookie)
            subs = [Submission(
                platform=r["platform"], problem_id=r["problemId"], title=r["name"],
                difficulty=r["difficulty"], tags=r["tags"], result=r["result"],
                submit_time=r["date"], language=r["language"],
                url=r.get("url", ""), record_id=str(r.get("recordId", "")),
            ) for r in raw]
        elif platform == "nowcoder":
            from crawler.nowcoder_crawler import NowCoderCrawler
            subs = NowCoderCrawler(cookie=cookie).fetch_submissions(username)
        else:
            print(f"  [SCHEDULER] 不支持的平台: {platform}")
            return

        if not subs:
            print(f"  [SCHEDULER] {platform}/{username}: 无数据")
            return

        db = get_db()

        # Upsert platform_accounts (new schema)
        db.execute(
            "INSERT OR IGNORE INTO platform_accounts (app_user_id, platform, username, last_crawl_at, crawl_count) "
            "VALUES (?, ?, ?, datetime('now'), 1)",
            (app_user_id, platform, username)
        )
        db.execute(
            "UPDATE platform_accounts SET last_crawl_at=datetime('now'), crawl_count=crawl_count+1 "
            "WHERE platform=? AND username=?",
            (platform, username)
        )
        pa_row = db.execute(
            "SELECT id FROM platform_accounts WHERE platform=? AND username=?", (platform, username)
        ).fetchone()
        pa_id = pa_row["id"]

        # Pre-build caches
        prob_cache = {}
        for row in db.execute("SELECT id, platform, problem_id FROM problems").fetchall():
            prob_cache[(row["platform"], row["problem_id"])] = row["id"]
        tag_cache = {}
        for row in db.execute("SELECT id, name_cn FROM tags").fetchall():
            tag_cache[row["name_cn"]] = row["id"]

        db.execute("PRAGMA foreign_keys=OFF")
        for s in subs:
            # Extract attrs
            plat = s.platform if not isinstance(s, dict) else s.get('platform','')
            pid = s.problem_id if not isinstance(s, dict) else s.get('problemId','')
            title = s.title if not isinstance(s, dict) else s.get('name','')
            diff = s.difficulty if not isinstance(s, dict) else s.get('difficulty',0)
            result = s.result if not isinstance(s, dict) else s.get('result','')
            stime = s.submit_time if not isinstance(s, dict) else (s.get('submit_time') or s.get('date',''))
            lang = s.language if not isinstance(s, dict) else s.get('language','')
            s_url = s.url if not isinstance(s, dict) else s.get('url','')
            s_tags = s.tags if not isinstance(s, dict) else s.get('tags',[])
            record_id = str(getattr(s, 'record_id', s.get('recordId', '')) if isinstance(s, dict) else getattr(s, 'record_id', '') or '')

            # 1. Upsert problem
            prob_key = (plat, pid)
            if prob_key not in prob_cache:
                db.execute(
                    "INSERT OR IGNORE INTO problems (platform, problem_id, title, difficulty, url) VALUES (?,?,?,?,?)",
                    (plat, pid, title, diff or 0, s_url or "")
                )
                pr = db.execute("SELECT id FROM problems WHERE platform=? AND problem_id=?", (plat, pid)).fetchone()
                prob_cache[prob_key] = pr["id"]
            prob_id = prob_cache[prob_key]

            # 2. Upsert tags + problem_tags
            for tag_cn in (s_tags or []):
                if tag_cn not in tag_cache:
                    db.execute("INSERT OR IGNORE INTO tags (name_cn) VALUES (?)", (tag_cn,))
                    tr = db.execute("SELECT id FROM tags WHERE name_cn=?", (tag_cn,)).fetchone()
                    if tr:
                        tag_cache[tag_cn] = tr["id"]
                tid = tag_cache.get(tag_cn)
                if tid:
                    db.execute("INSERT OR IGNORE INTO problem_tags (problem_id, tag_id) VALUES (?,?)", (prob_id, tid))

            # 3. Update problem metadata
            if diff > 0:
                db.execute(
                    "UPDATE problems SET difficulty=CASE WHEN difficulty=0 THEN ? ELSE difficulty END, "
                    "title=CASE WHEN title='' THEN ? ELSE title END, url=CASE WHEN url='' THEN ? ELSE url END WHERE id=?",
                    (diff, title, s_url or "", prob_id)
                )

            # 4. Handle record_id linking
            if record_id:
                db.execute(
                    "UPDATE OR IGNORE submissions SET record_id=? "
                    "WHERE platform_account_id=? AND problem_id=? AND submit_time=? AND result=? AND language=? "
                    "AND (record_id='' OR record_id IS NULL)",
                    (record_id, pa_id, prob_id, stime, result, lang)
                )

            # 5. Insert submission
            db.execute(
                "INSERT OR IGNORE INTO submissions "
                "(platform_account_id, problem_id, result, submit_time, language, code, record_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (pa_id, prob_id, result, stime, lang, "", record_id)
            )
        db.commit()
        db.execute("PRAGMA foreign_keys=ON")

        print(f"  [SCHEDULER] 已刷新 {platform}/{username}: {len(subs)} 条")

    def _fetch_atcoder_subs(self, username: str) -> list:
        """Fetch AtCoder submissions using the kenkoooo API."""
        import urllib.request, urllib.parse, ssl, time, os
        os.environ['NO_PROXY'] = '*'
        os.environ['no_proxy'] = '*'
        from crawler.base_crawler import Submission

        # Try curl_cffi first
        try:
            from curl_cffi import requests as cf_requests
            _HAS_CF = True
        except ImportError:
            _HAS_CF = False
            raise Exception("AtCoder 同步需要 curl_cffi: pip install curl_cffi")

        def _cf_get(url, headers=None, timeout=30):
            h = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Accept": "application/json"}
            if headers: h.update(headers)
            return cf_requests.get(url, headers=h, impersonate="chrome131", timeout=timeout)

        # Get difficulty map
        r = _cf_get("https://kenkoooo.com/atcoder/resources/merged-problems.json")
        r.raise_for_status()
        diff_map = {p["id"]: p for p in r.json()}

        # Paginate submissions
        subs = []
        from_sec = 0
        page = 0
        while True:
            page += 1
            url = f"https://kenkoooo.com/atcoder/atcoder-api/v3/user/submissions?user={urllib.parse.quote(username)}&from_second={from_sec}"
            if page > 1: time.sleep(0.3)
            r = _cf_get(url)
            if r.status_code == 404: break
            r.raise_for_status()
            batch = r.json()
            if not batch: break
            subs.extend(batch)
            from_sec = batch[-1]["epoch_second"]
            if len(batch) < 500: break

        result = []
        AC_MAP = {"AC":"AC","WA":"WA","TLE":"TLE","RE":"RE","CE":"CE","MLE":"MLE"}
        from datetime import datetime, timezone
        for s in subs:
            verdict = AC_MAP.get(s.get("result",""), s.get("result","?"))
            ts = s.get("epoch_second", 0)
            date = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d") if ts else ""
            pid = s.get("problem_id","")
            info = diff_map.get(pid, {})
            result.append(Submission(
                platform="atcoder", problem_id=pid,
                title=info.get("title", pid),
                difficulty=info.get("difficulty", 0) or 0,
                tags=[], result=verdict, submit_time=date,
                language=s.get("language",""), url=f"https://atcoder.jp/contests/{s.get('contest_id','')}/tasks/{pid}"
            ))
        return result

    def _fetch_luogu_subs(self, uid: str, cookie: str = "") -> list:
        """Fetch Luogu submissions using the internal API."""
        import os
        os.environ['NO_PROXY'] = '*'
        os.environ['no_proxy'] = '*'
        try:
            from curl_cffi import requests as cf_requests
        except ImportError:
            raise Exception("洛谷同步需要 curl_cffi: pip install curl_cffi")

        def _cf_get(url, headers=None, timeout=30, cookies=None):
            h = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Accept": "application/json"}
            if headers: h.update(headers)
            kw = {"impersonate": "chrome131", "timeout": timeout}
            if cookies: kw["cookies"] = cookies
            return cf_requests.get(url, headers=h, **kw)

        headers = {"x-lentille-request": "content-only", "x-luogu-type": "content-only", "Accept": "application/json", "Referer": "https://www.luogu.com.cn/"}
        cookies = {}
        if cookie:
            for part in cookie.split(";"):
                part = part.strip()
                if "=" in part:
                    k, v = part.split("=", 1)
                    cookies[k.strip()] = v.strip()

        from crawler.base_crawler import Submission
        from datetime import datetime, timezone

        submissions = []
        page = 1
        import time as _time
        LG_STATUS = {0:"?",1:"?",2:"CE",3:"RE",4:"MLE",5:"TLE",6:"WA",7:"RE",11:"RE",12:"AC"}
        LG_DIFF = {0:0,1:800,2:1200,3:1600,4:2000,5:2400,6:2800,7:3200}

        while True:
            url = f"https://www.luogu.com.cn/record/list?user={uid}&page={page}&_contentOnly=1"
            r = _cf_get(url, headers=headers, cookies=cookies if cookies else None)
            if r.status_code != 200: break
            try:
                data = r.json()
            except Exception:
                break
            if data.get("instance") == "auth" or data.get("template") == "login":
                raise Exception("洛谷需要登录 Cookie，请在浏览器中重新获取并更新")
            records = []
            for path in [["currentData","records","result"],["currentData","result"],["data","records","result"],["data","result"],["result"]]:
                d = data
                for key in path:
                    d = d.get(key,{}) if isinstance(d,dict) else {}
                if isinstance(d, list) and len(d) > 0:
                    records = d; break
            if not records: break
            for rec in records:
                status = rec.get("status", 0)
                result_v = LG_STATUS.get(status, "?")
                prob = rec.get("problem", {}) or {}
                ts = rec.get("submitTime", 0) or rec.get("time", 0)
                date = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d") if ts else ""
                tags = prob.get("tags", []) or []
                if isinstance(tags, list) and tags and isinstance(tags[0], dict):
                    tags = [t.get("name", str(t)) for t in tags]
                else:
                    tags = [str(t) for t in tags]
                lang = rec.get("language", "")
                if isinstance(lang, int): lang = str(lang)
                submissions.append(Submission(
                    platform="luogu", problem_id=prob.get("pid", rec.get("pid","")),
                    title=prob.get("title",""), difficulty=LG_DIFF.get(prob.get("difficulty",0), 0),
                    tags=[t.lower() for t in tags], result=result_v, submit_time=date,
                    language=lang, url=f"https://www.luogu.com.cn/problem/{prob.get('pid','')}"
                ))
            if len(records) < 20: break
            page += 1
            _time.sleep(0.5)
        return submissions

    def _load_submissions(self, platform: str, username: str) -> list[dict]:
        """Load submissions from new schema — returns old-compatible format."""
        from db.database import get_db
        import json as _json

        db = get_db()
        # Use server's helper if available, otherwise query directly
        try:
            import server as _sv
            return _sv._query_submissions(db, platform=platform, username=username)
        except (ImportError, AttributeError):
            pass

        # Fallback: direct query
        pa_row = db.execute(
            "SELECT id FROM platform_accounts WHERE platform=? AND username=?",
            (platform, username)
        ).fetchone()
        if not pa_row:
            return []

        # Build tag cache
        tag_sql = """
            SELECT p.id, GROUP_CONCAT(t.name_cn, '\x1f') as tag_names
            FROM problems p
            LEFT JOIN problem_tags pt ON pt.problem_id = p.id
            LEFT JOIN tags t ON t.id = pt.tag_id
            GROUP BY p.id
        """
        prob_tags = {}
        for row in db.execute(tag_sql).fetchall():
            prob_tags[row["id"]] = (row["tag_names"] or "").split("\x1f") if row["tag_names"] else []

        rows = db.execute(
            "SELECT s.* FROM submissions s "
            "WHERE s.platform_account_id=? "
            "ORDER BY s.submit_time DESC",
            (pa_row["id"],)
        ).fetchall()

        subs = []
        for r in rows:
            prob_row = db.execute("SELECT * FROM problems WHERE id=?", (r["problem_id"],)).fetchone()
            subs.append({
                "platform": platform,
                "problemId": prob_row["problem_id"] if prob_row else "",
                "name": prob_row["title"] if prob_row else "",
                "difficulty": prob_row["difficulty"] if prob_row else 0,
                "tags": prob_tags.get(r["problem_id"], []),
                "result": r["result"],
                "date": (r["submit_time"] or "")[:10],
                "language": r["language"],
                "url": prob_row["url"] if prob_row else "",
                "recordId": r["record_id"],
            })
        return subs


# 全局单例
_scheduler = None


def get_scheduler() -> WeeklyReportScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = WeeklyReportScheduler()
    return _scheduler
