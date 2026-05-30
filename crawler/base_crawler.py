"""爬虫抽象基类 + 统一数据模型"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
import requests


@dataclass
class Submission:
    """统一提交记录"""
    platform: str
    problem_id: str
    title: str = ""
    difficulty: int = 0
    tags: list = field(default_factory=list)
    result: str = ""
    submit_time: str = ""
    language: str = ""
    code: str = ""
    url: str = ""
    record_id: str = ""

    def __hash__(self):
        return hash((self.platform, self.problem_id))


@dataclass
class CrawlProgress:
    """爬取进度"""
    task_id: str
    platform: str = ""
    username: str = ""
    status: str = "pending"
    progress: float = 0.0
    total_fetched: int = 0
    ac_count: int = 0
    message: str = ""
    error: Optional[str] = None


class BaseCrawler(ABC):
    """爬虫基类"""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = self._build_session()

    def _build_session(self) -> requests.Session:
        s = requests.Session()
        s.headers.update({
            "User-Agent": (
                "ACM-Helper/1.0 (compatible; "
                "+https://github.com/cockroach0401/acm-helper)"
            )
        })
        return s

    @abstractmethod
    def fetch_submissions(self, username: str) -> list[Submission]:
        """爬取用户所有提交记录"""
        ...

    def fetch_ac_problems(self, username: str) -> list[Submission]:
        """爬取 AC 题目（去重，每题只保留首次 AC）"""
        all_subs = self.fetch_submissions(username)
        ac_subs = [s for s in all_subs if s.result == "AC"]
        seen: dict[str, Submission] = {}
        for s in sorted(ac_subs, key=lambda x: x.submit_time):
            if s.problem_id not in seen:
                seen[s.problem_id] = s
        return list(seen.values())

    def _get(self, url: str, **kwargs) -> requests.Response:
        kwargs.setdefault("timeout", self.timeout)
        return self.session.get(url, **kwargs)

    def _post(self, url: str, **kwargs) -> requests.Response:
        kwargs.setdefault("timeout", self.timeout)
        return self.session.post(url, **kwargs)
