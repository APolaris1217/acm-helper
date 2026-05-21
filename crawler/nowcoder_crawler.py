"""牛客网 (ac.nowcoder.com) 用户提交爬取器

牛客网的提交记录是 SSR 渲染的 HTML table，没有独立 JSON API。
通过抓取 /acm/contest/profile/{uid}/practice-coding 页面并解析 HTML 获取数据。
"""
from .base_crawler import BaseCrawler, Submission
import re
import time as _time


NOWCODER_STATUS_MAP = {
    "答案正确": "AC",
    "答案错误": "WA",
    "运行超时": "TLE",
    "运行错误": "RE",
    "编译错误": "CE",
    "内存超限": "MLE",
    "格式错误": "WA",
    "输出超限": "RE",
    "内部错误": "unsolved",
    "等待评测": "unsolved",
    "正在评测": "unsolved",
    "正在编译": "unsolved",
}


class NowCoderCrawler(BaseCrawler):
    """牛客网提交爬取 — 通过 HTML 页面抓取"""

    def __init__(self, cookie: str = ""):
        super().__init__()
        self.cookie = cookie

    def _parse_cookies(self, cookie_str: str) -> dict:
        cookies = {}
        if cookie_str:
            for part in cookie_str.split(";"):
                part = part.strip()
                if "=" in part:
                    k, v = part.split("=", 1)
                    cookies[k.strip()] = v.strip()
        return cookies

    def _request(self, url: str):
        from curl_cffi import requests as cf_requests

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://ac.nowcoder.com/",
        }
        kwargs = {"headers": headers, "impersonate": "chrome131", "timeout": 30}
        if self.cookie:
            kwargs["cookies"] = self._parse_cookies(self.cookie)
        return cf_requests.get(url, **kwargs)

    def _resolve_status(self, text: str) -> str:
        text = text.strip()
        return NOWCODER_STATUS_MAP.get(text, "unsolved")

    def _parse_page(self, html: str, page: int) -> list:
        """Parse submission rows from the practice-coding HTML page."""
        submissions = []
        tbody_match = re.search(r"<tbody>(.*?)</tbody>", html, re.DOTALL)
        if not tbody_match:
            return submissions
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", tbody_match.group(1), re.DOTALL)
        for tr in rows:
            tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.DOTALL)
            if len(tds) < 9:
                continue
            # col0: submission ID, with link
            sub_id = self._strip_tags(tds[0])
            # col1: problem name + link, extract problem ID from href
            pid = ""
            pid_m = re.search(r'/acm/problem/(\d+)', tds[1])
            if pid_m:
                pid = pid_m.group(1)
            name = self._strip_tags(tds[1])
            # col2: status
            status_text = self._strip_tags(tds[2])
            result = self._resolve_status(status_text)
            # col3: score (ignore)
            # col4: runtime
            # col5: memory
            # col6: code length
            # col7: language
            lang = self._strip_tags(tds[7])
            # col8: submit time
            date = self._strip_tags(tds[8]).strip()

            if page == 1 and not submissions:
                print(f"  [NC] DEBUG first row: sub_id={sub_id} pid={pid} name={name} status='{status_text}' result={result} date={date} lang={lang}")

            sub = Submission(
                platform="nowcoder",
                problem_id=pid,
                title=name,
                difficulty=0,
                tags=[],
                result=result,
                submit_time=date,  # "2026-03-23 20:27:53" full timestamp
                language=lang,
                code="",
                url=f"https://ac.nowcoder.com/acm/problem/{pid}"
            )
            submissions.append(sub)
        return submissions

    @staticmethod
    def _strip_tags(html: str) -> str:
        return re.sub(r"<[^>]+>", "", html).strip()

    def fetch_submissions(self, uid_or_username: str) -> list[Submission]:
        uid = uid_or_username.strip()
        submissions = []
        page = 1

        while True:
            url = (
                f"https://ac.nowcoder.com/acm/contest/profile/{uid}/practice-coding"
                f"?pageSize=50&search=&statusTypeFilter=-1"
                f"&languageCategoryFilter=-1&orderType=DESC&page={page}"
            )
            print(f"  [NC] Fetching page {page}...")
            resp = self._request(url)
            if resp.status_code != 200:
                print(f"  [NC] Non-200 status: {resp.status_code}, stopping.")
                break

            html = resp.text
            if "页面找不到" in html:
                print(f"  [NC] Page not found. Check UID: {uid}")
                break

            rows = self._parse_page(html, page)
            if not rows:
                print(f"  [NC] No rows found on page {page}.")
                break

            submissions.extend(rows)
            print(f"  [NC] Page {page}: {len(rows)} records (total {len(submissions)})")
            if len(rows) < 50:
                break
            page += 1
            _time.sleep(0.5)

        print(f"  [NC] Total: {len(submissions)} records")

        # Enrich with difficulty from JSON API
        self._enrich_difficulty(submissions)

        return submissions

    def _enrich_difficulty(self, submissions: list):
        """Query NowCoder problem list JSON API to get difficulty for each unique problem."""
        import json as _json, os
        cache_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "nc_diff_cache.json")
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                diff_map = _json.load(f)
        except Exception:
            diff_map = {}

        from curl_cffi import requests as cf_requests
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        }
        kwargs = {"headers": headers, "impersonate": "chrome131", "timeout": 15}
        if self.cookie:
            kwargs["cookies"] = self._parse_cookies(self.cookie)

        # Unique problem IDs to look up
        need = set()
        for s in submissions:
            if s.problem_id and s.problem_id not in diff_map:
                need.add(s.problem_id)

        if need:
            print(f"  [NC] Looking up difficulty for {len(need)} new problems...")
        for i, pid in enumerate(need):
            try:
                url = f"https://ac.nowcoder.com/acm/problem/list/json?keyword={pid}&page=1&pageSize=3"
                resp = cf_requests.get(url, **kwargs)
                d = resp.json()
                sets = d.get("data", {}).get("problemSets", [])
                for item in sets:
                    if str(item.get("problemId")) == str(pid):
                        diff_map[pid] = item.get("difficulty", 0)
                        break
                else:
                    if sets:
                        diff_map[pid] = sets[0].get("difficulty", 0)
                if i % 10 == 0 and len(need) > 10:
                    print(f"    [{i+1}/{len(need)}] pid={pid}")
                _time.sleep(0.3)
            except Exception:
                continue

        # Apply difficulty to submissions
        enriched = 0
        for s in submissions:
            d = diff_map.get(s.problem_id, 0)
            if d and not s.difficulty:
                s.difficulty = d
                enriched += 1
        if enriched:
            print(f"  [NC] Enriched {enriched} submissions with difficulty")

        # Save cache
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                _json.dump(diff_map, f, ensure_ascii=False)
        except Exception:
            pass
