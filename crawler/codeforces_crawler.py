"""Codeforces 用户提交爬取器

使用 CF 公开 API: https://codeforces.com/api/user.status
无需认证，无需 curl_cffi。
"""
from .base_crawler import BaseCrawler, Submission
import time

CODEFORCES_API = "https://codeforces.com/api/user.status"


class CodeforcesCrawler(BaseCrawler):
    """Codeforces 用户提交爬取

    用法:
        crawler = CodeforcesCrawler()
        ac_problems = crawler.fetch_ac_problems("tourist")
        all_subs = crawler.fetch_submissions("tourist")
    """

    def fetch_submissions(self, handle: str) -> list[Submission]:
        """获取用户所有提交记录（上限 100000 条）

        CF API 文档: https://codeforces.com/apiHelp/methods#user.status
        """
        params = {"handle": handle, "from": 1, "count": 100000}
        resp = self._get(CODEFORCES_API, params=params)
        data = resp.json()

        if data["status"] != "OK":
            raise Exception(f"CF API 错误: {data.get('comment', '未知')}")

        submissions = []
        for item in data["result"]:
            problem = item.get("problem", {})
            verdict = item.get("verdict", "?")
            CF_VERDICT_MAP = {
                "OK": "AC", "WRONG_ANSWER": "WA", "TIME_LIMIT_EXCEEDED": "TLE",
                "RUNTIME_ERROR": "RE", "COMPILATION_ERROR": "CE",
                "MEMORY_LIMIT_EXCEEDED": "MLE", "PRESENTATION_ERROR": "WA",
                "IDLENESS_LIMIT_EXCEEDED": "TLE",
                "SKIPPED": "unsolved", "CHALLENGED": "unsolved",
            }
            result = CF_VERDICT_MAP.get(verdict, verdict)

            sub = Submission(
                platform="codeforces",
                problem_id=f"{problem.get('contestId', '')}{problem.get('index', '')}",
                title=f"{problem.get('contestId', '')}{problem.get('index', '')} - {problem.get('name', '')}",
                difficulty=problem.get("rating", 0) or 0,
                tags=[t.lower() for t in problem.get("tags", []) if t.lower() != "*special"],
                result=result,
                submit_time=time.strftime(
                    "%Y-%m-%dT%H:%M:%S",
                    time.gmtime(item.get("creationTimeSeconds", 0))
                ),
                language=item.get("programmingLanguage", ""),
                code="",
                url=f"https://codeforces.com/problemset/problem/{problem.get('contestId')}/{problem.get('index')}"
            )
            submissions.append(sub)

        return submissions
