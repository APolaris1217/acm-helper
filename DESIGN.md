# ACM Helper 二次开发方案：用户名分析 + DeepSeek 集成

## 一、总体架构

```
┌──────────────────────────────────────────────────────────────────────┐
│                     BROWSER EXTENSION (Manifest V3)                   │
│                                                                      │
│  ┌──────────┐  ┌──────────┐  ┌────────────────────────────────────┐ │
│  │ popup/   │  │dashboard/│  │ 新增: analysis/                     │ │
│  │ (弹窗)   │  │ (仪表盘) │  │   用户分析面板                      │ │
│  │ +新增:   │  │ +新增:   │  │   - 平台选择 + 用户名输入           │ │
│  │ 快速分析 │  │ 分析视图 │  │   - 爬取进度展示                    │ │
│  └────┬─────┘  └────┬─────┘  │   - 分析报告可视化                  │ │
│       │             │        └──────────────┬─────────────────────┘ │
│       └─────────────┼───────────────────────┘                       │
│                     │ HTTP (fetch)                                   │
│               ┌─────▼─────┐                                          │
│               │ utils/api │  api_base: http://localhost:8000         │
│               └─────┬─────┘                                          │
└─────────────────────┼────────────────────────────────────────────────┘
                      │
          ┌───────────▼───────────┐
          │   PYTHON BACKEND      │
          │   localhost:8000      │
          │                       │
          │ ┌───────────────────┐ │
          │ │ 新增: crawler/    │ │
          │ │ cf_crawler.py     │ │
          │ │ luogu_crawler.py  │ │
          │ │ nowcoder_crawler.py│ │
          │ │ base_crawler.py   │ │
          │ └───────┬───────────┘ │
          │ ┌───────▼───────────┐ │
          │ │ 新增: analyzer/   │ │
          │ │ stats_engine.py   │ │
          │ │ weakness.py       │ │
          │ │ report_gen.py     │ │
          │ └───────┬───────────┘ │
          │ ┌───────▼───────────┐ │
          │ │ 新增: ai/         │ │
          │ │ deepseek_client.py│ │
          │ │ prompt_templates/ │ │
          │ └───────┬───────────┘ │
          │ ┌───────▼───────────┐ │
          │ │ 原有模块 (保留)   │ │
          │ │ problems/         │ │
          │ │ solutions/        │ │
          │ │ stats/            │ │
          │ │ settings/         │ │
          │ └───────────────────┘ │
          │                       │
          │  SQLite 数据库         │
          │  acm_helper.db        │
          └───────────────────────┘
```

## 二、后端模块设计

### 2.1 目录结构（新增部分）

```
backend/
├── server.py                    # FastAPI 入口（保留，新增路由注册）
├── crawler/                     # 新增：多平台用户爬取模块
│   ├── __init__.py
│   ├── base_crawler.py          # 抽象基类 + 通用工具
│   ├── codeforces_crawler.py    # CF 用户状态 API 爬取
│   ├── luogu_crawler.py         # 洛谷用户记录爬取
│   ├── nowcoder_crawler.py      # 牛客用户练习记录爬取
│   └── task_manager.py          # 爬取任务调度 + 进度管理
├── analyzer/                    # 新增：做题分析引擎
│   ├── __init__.py
│   ├── stats_engine.py          # 基础统计（总数/难度/标签/趋势）
│   ├── weakness.py              # 弱项识别算法
│   └── report_gen.py            # Markdown 报告生成
├── ai/                          # 新增：DeepSeek AI 模块
│   ├── __init__.py
│   ├── deepseek_client.py       # DeepSeek API 客户端
│   ├── solution_gen.py          # 题解生成（保留原逻辑）
│   ├── suggest_gen.py           # 刷题建议生成（新增）
│   └── prompts/                 # 提示词模板目录
│       ├── solution.md          # 题解生成模板
│       ├── suggest.md           # 建议生成模板
│       └── weekly_report.md     # 周报模板
├── db/                          # 新增：数据库层
│   ├── __init__.py
│   ├── database.py              # SQLite 连接管理
│   ├── models.py                # 数据模型定义
│   └── migrations.py            # 数据库迁移
├── api/                         # 新增：API 路由模块化
│   ├── __init__.py
│   ├── crawl.py                 # 爬取相关路由
│   ├── analysis.py              # 分析相关路由
│   └── deepseek.py              # DeepSeek 相关路由
└── requirements.txt             # 新增依赖
```

### 2.2 爬取模块详细设计

#### base_crawler.py — 抽象基类

```python
"""爬虫抽象基类 + 通用工具"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
import time
import hashlib
import json

@dataclass
class Submission:
    """统一提交记录"""
    platform: str           # codeforces / luogu / nowcoder
    problem_id: str         # 平台内唯一 ID
    title: str              # 题目名称
    difficulty: int = 0     # 难度评分（归一化 0-3500）
    tags: list[str] = field(default_factory=list)
    result: str = ""        # AC / WA / TLE / RE / CE / MLE
    submit_time: str = ""   # ISO 8601
    language: str = ""
    code: str = ""
    url: str = ""

    def __hash__(self):
        return hash((self.platform, self.problem_id))

@dataclass
class CrawlProgress:
    """爬取进度"""
    task_id: str
    status: str             # pending / running / done / failed
    total_fetched: int = 0
    ac_count: int = 0
    message: str = ""
    error: Optional[str] = None

class BaseCrawler(ABC):
    """爬虫基类"""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = self._build_session()

    def _build_session(self):
        import requests
        s = requests.Session()
        s.headers.update({
            "User-Agent": "ACM-Helper/5.0 (compatible; +https://github.com/cockroach0401/acm-helper)"
        })
        return s

    @abstractmethod
    def fetch_submissions(self, username: str) -> list[Submission]:
        """爬取用户所有提交记录"""
        ...

    @abstractmethod
    def fetch_ac_problems(self, username: str) -> list[Submission]:
        """爬取用户 AC 的题目（去重，每题只保留首次 AC 记录）"""
        ...

    def normalize_difficulty(self, raw_difficulty) -> int:
        """难度归一化到 0-3500 区间"""
        ...

    def _get(self, url: str, **kwargs) -> requests.Response:
        kwargs.setdefault("timeout", self.timeout)
        return self.session.get(url, **kwargs)

    def _post(self, url: str, **kwargs) -> requests.Response:
        kwargs.setdefault("timeout", self.timeout)
        return self.session.post(url, **kwargs)
```

#### codeforces_crawler.py — CF 用户爬取

```python
"""Codeforces 用户提交爬取器"""
from .base_crawler import BaseCrawler, Submission, CrawlProgress
import time

CODEFORCES_API = "https://codeforces.com/api/user.status"

class CodeforcesCrawler(BaseCrawler):

    # CF 难度范围: 800-3500
    def normalize_difficulty(self, raw: int) -> int:
        return max(0, min(3500, raw))

    def fetch_submissions(self, handle: str) -> list[Submission]:
        """使用 CF 公开 API 获取所有提交

        API 文档: https://codeforces.com/apiHelp/methods#user.status
        参数: handle (必填), from (可选), count (可选)
        返回: 最多 100000 条提交记录
        """
        submissions = []
        params = {"handle": handle, "from": 1, "count": 100000}

        resp = self._get(CODEFORCES_API, params=params)
        data = resp.json()

        if data["status"] != "OK":
            raise Exception(f"CF API 错误: {data.get('comment', '未知')}")

        for item in data["result"]:
            problem = item.get("problem", {})
            sub = Submission(
                platform="codeforces",
                problem_id=f"{problem.get('contestId', '')}{problem.get('index', '')}",
                title=f"{problem.get('contestId', '')}{problem.get('index', '')} - {problem.get('name', '')}",
                difficulty=problem.get("rating", 0),
                tags=problem.get("tags", []),
                result="AC" if item.get("verdict") == "OK" else item.get("verdict", "?"),
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

    def fetch_ac_problems(self, handle: str) -> list[Submission]:
        """获取 AC 题目（去重，每题首次 AC）"""
        all_subs = self.fetch_submissions(handle)
        ac_subs = [s for s in all_subs if s.result == "AC"]

        # 按 problem_id 去重，保留首次 AC
        seen = {}
        for s in sorted(ac_subs, key=lambda x: x.submit_time):
            if s.problem_id not in seen:
                seen[s.problem_id] = s

        return list(seen.values())
```

#### luogu_crawler.py — 洛谷用户爬取

```python
"""洛谷用户做题记录爬取器

说明: 洛谷没有公开的提交记录 API。
方案: 解析用户个人主页 + 记录页，或调用内部 AJAX 接口。
需要用户提供浏览器 Cookie（__client_id + _uid）。
"""
from .base_crawler import BaseCrawler, Submission
import re
import time

LUOGU_RECORD_API = "https://www.luogu.com.cn/record/list"
LUOGU_PROBLEM_API = "https://www.luogu.com.cn/problem/{pid}"

class LuoguCrawler(BaseCrawler):

    def __init__(self, cookie: str = "", timeout: int = 30):
        super().__init__(timeout)
        if cookie:
            self.session.headers["Cookie"] = cookie
        # 洛谷需要特定的 X-CSRF-Token (从 cookie 中提取或首页获取)
        self._setup_csrf()

    def _setup_csrf(self):
        """从洛谷首页获取 CSRF Token"""
        resp = self._get("https://www.luogu.com.cn/")
        # 从响应中提取 C3VK 或 _contentOnly 中的 token
        ...

    def fetch_submissions(self, uid: str) -> list[Submission]:
        """分页获取洛谷提交记录

        洛谷 /record/list API:
        - POST, payload: {"page": N, "_contentOnly": 1}
        - 需要 Cookie 认证
        - 每页 20 条
        - 通过 result 字段过滤非 AC: {"type": "AC"} 或检查 score=100
        """
        submissions = []
        page = 1
        max_pages = 500  # 安全上限

        while page <= max_pages:
            payload = {"page": page, "_contentOnly": 1}
            headers = {
                "Content-Type": "application/json",
                "X-CSRF-TOKEN": getattr(self, "csrf_token", ""),
                "X-Requested-With": "XMLHttpRequest",
                "Referer": f"https://www.luogu.com.cn/user/{uid}",
            }

            try:
                resp = self._post(
                    f"{LUOGU_RECORD_API}?user={uid}&_contentOnly=1",
                    json=payload, headers=headers
                )
                data = resp.json()

                records = data.get("currentData", {}).get("records", {}).get("result", [])
                if not records:
                    break

                for item in records:
                    problem = item.get("problem", {})
                    sub = Submission(
                        platform="luogu",
                        problem_id=problem.get("pid", ""),
                        title=problem.get("title", ""),
                        difficulty=problem.get("difficulty", 0),
                        tags=problem.get("tags", []),
                        result="AC" if item.get("status") == 12 or item.get("score", 0) >= 100 else "?",
                        submit_time=time.strftime(
                            "%Y-%m-%dT%H:%M:%S",
                            time.localtime(item.get("submitTime", 0))
                        ),
                        language=item.get("language", ""),
                        code="",
                        url=f"https://www.luogu.com.cn/problem/{problem.get('pid', '')}"
                    )
                    submissions.append(sub)

                # 检查是否还有下一页
                total = data.get("currentData", {}).get("records", {}).get("count", 0)
                if page * 20 >= total:
                    break
                page += 1

            except Exception as e:
                # 可能触发了 Cloudflare 验证
                raise Exception(f"洛谷爬取失败(page={page}): {e}")

        return submissions

    def fetch_ac_problems(self, uid: str) -> list[Submission]:
        all_subs = self.fetch_submissions(uid)
        ac_subs = [s for s in all_subs if s.result == "AC"]

        seen = {}
        for s in ac_subs:
            if s.problem_id not in seen:
                seen[s.problem_id] = s

        return list(seen.values())
```

#### nowcoder_crawler.py — 牛客用户爬取

```python
"""牛客用户练习记录爬取器

方案:
1. 优先使用牛客公开 API (如果存在)
2. 解析个人主页刷题记录页
3. 调用内部接口
"""
from .base_crawler import BaseCrawler, Submission
import time

NOWCODER_PROFILE_API = "https://ac.nowcoder.com/acm/home/{uid}"
NOWCODER_PRACTICE_API = "https://ac.nowcoder.com/acm/problem/profile"
NOWCODER_STATUS_API = "https://ac.nowcoder.com/acm/contest/status-list"

class NowcoderCrawler(BaseCrawler):

    def __init__(self, cookie: str = "", timeout: int = 30):
        super().__init__(timeout)
        if cookie:
            self.session.headers["Cookie"] = cookie

    def fetch_submissions(self, uid: str) -> list[Submission]:
        """爬取牛客用户提交记录

        策略:
        1. 调用 /acm/problem/profile?uid={uid} 获取个人统计
        2. 遍历已通过的题目列表
        3. 每道题获取详情（难度、标签）
        """
        submissions = []
        page = 1

        while True:
            params = {"uid": uid, "page": page, "pageSize": 50}
            resp = self._get(NOWCODER_PROFILE_API, params=params)
            html = resp.text

            # 解析 HTML 获取题目列表
            # 牛客页面结构: 使用 Vue 渲染，数据通常在 script 标签中
            # 或使用 __NEXT_DATA__ / JSON 内嵌

            page_submissions = self._parse_profile_page(html)
            if not page_submissions:
                break

            submissions.extend(page_submissions)
            page += 1

        return submissions

    def _parse_profile_page(self, html: str) -> list[Submission]:
        """解析牛客个人主页 HTML"""
        from bs4 import BeautifulSoup
        import re
        import json

        soup = BeautifulSoup(html, "html.parser")
        submissions = []

        # 尝试从内嵌 JSON 提取
        for script in soup.find_all("script"):
            if "profileData" in script.text or "problemList" in script.text:
                try:
                    match = re.search(r'profileData\s*[:=]\s*(\{.+?\});', script.text, re.DOTALL)
                    if match:
                        data = json.loads(match.group(1))
                        for item in data.get("problemList", []):
                            sub = Submission(
                                platform="nowcoder",
                                problem_id=f"NC{item.get('problemId', '')}",
                                title=item.get("title", ""),
                                difficulty=self._nc_difficulty_to_score(item.get("difficulty", "")),
                                tags=item.get("tags", []),
                                result="AC" if item.get("isPassed") else "?",
                                submit_time=item.get("acTime", ""),
                                language="",
                                code="",
                                url=f"https://ac.nowcoder.com/acm/problem/{item.get('problemId', '')}"
                            )
                            submissions.append(sub)
                    break
                except (json.JSONDecodeError, AttributeError):
                    continue

        # 回退: 解析 DOM
        if not submissions:
            # 查找题目列表 DOM
            problem_items = soup.select(".problem-item, .question-item, [class*='problem']")
            for item in problem_items:
                title_el = item.select_one("a.title, .problem-name")
                if title_el:
                    submissions.append(Submission(
                        platform="nowcoder",
                        problem_id=title_el.get("href", "").split("/")[-1],
                        title=title_el.text.strip(),
                    ))

        return submissions

    def _nc_difficulty_to_score(self, diff: str) -> int:
        """牛客难度映射到数值"""
        mapping = {"入门": 300, "简单": 800, "中等": 1500, "较难": 2200, "困难": 3000}
        return mapping.get(diff, 0)

    def fetch_ac_problems(self, uid: str) -> list[Submission]:
        """获取牛客 AC 题目"""
        return self.fetch_submissions(uid)
```

#### task_manager.py — 爬取任务调度

```python
"""爬取任务调度与进度管理"""
import uuid
import threading
from typing import Optional
from dataclasses import dataclass, field

@dataclass
class CrawlTask:
    task_id: str
    platform: str
    username: str
    status: str = "pending"       # pending / running / done / failed
    progress: float = 0.0         # 0.0 - 1.0
    message: str = ""
    result_count: int = 0
    error: Optional[str] = None

class TaskManager:
    """内存中的任务管理器（单机部署，无需 Redis）"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tasks = {}
            cls._instance._lock = threading.Lock()
        return cls._instance

    def create_task(self, platform: str, username: str) -> CrawlTask:
        task = CrawlTask(
            task_id=str(uuid.uuid4())[:8],
            platform=platform,
            username=username,
        )
        with self._lock:
            self._tasks[task.task_id] = task
        return task

    def get_task(self, task_id: str) -> Optional[CrawlTask]:
        with self._lock:
            return self._tasks.get(task_id)

    def update_task(self, task_id: str, **kwargs):
        with self._lock:
            task = self._tasks.get(task_id)
            if task:
                for k, v in kwargs.items():
                    setattr(task, k, v)

    def list_tasks(self) -> list[CrawlTask]:
        with self._lock:
            return list(self._tasks.values())
```

### 2.3 分析引擎设计

#### stats_engine.py — 基础统计引擎

```python
"""做题数据统计分析引擎"""
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Optional
import math

class StatsEngine:

    def __init__(self, submissions: list):
        """初始化

        Args:
            submissions: 统一格式的提交记录列表
        """
        self.submissions = submissions
        self.ac_submissions = [s for s in submissions if s.result == "AC"]

    def basic_stats(self) -> dict:
        """基础统计"""
        ac_problems = self._unique_ac_problems()
        total_subs = len(self.submissions)
        ac_count = len([s for s in self.submissions if s.result == "AC"])

        return {
            "total_ac_problems": len(ac_problems),
            "total_submissions": total_subs,
            "ac_count": ac_count,
            "ac_rate": round(ac_count / total_subs * 100, 1) if total_subs > 0 else 0,
            "active_days": self._count_active_days(),
            "avg_per_day": round(len(ac_problems) / max(1, self._count_active_days()), 1),
            "max_streak": self._calc_max_streak(),
        }

    def difficulty_distribution(self) -> dict:
        """难度分布"""
        buckets = {
            "入门 (0-800)": 0,
            "普及 (800-1200)": 0,
            "提高 (1200-1600)": 0,
            "省选 (1600-2000)": 0,
            "NOI (2000-2400)": 0,
            "IOI (2400-3000)": 0,
            "3000+": 0,
        }
        for p in self._unique_ac_problems():
            d = p.difficulty
            if d < 800: buckets["入门 (0-800)"] += 1
            elif d < 1200: buckets["普及 (800-1200)"] += 1
            elif d < 1600: buckets["提高 (1200-1600)"] += 1
            elif d < 2000: buckets["省选 (1600-2000)"] += 1
            elif d < 2400: buckets["NOI (2000-2400)"] += 1
            elif d < 3000: buckets["IOI (2400-3000)"] += 1
            else: buckets["3000+"] += 1
        return buckets

    def tag_distribution(self) -> dict:
        """标签分布: 每个标签的题目数、AC 率、平均难度"""
        ac_problems = self._unique_ac_problems()
        tag_stats = defaultdict(lambda: {"count": 0, "total_difficulty": 0, "ac_rate": 0.0})

        # 统计每题标签
        for p in ac_problems:
            for tag in p.tags:
                tag_stats[tag]["count"] += 1
                tag_stats[tag]["total_difficulty"] += p.difficulty

        # 计算每个标签的 AC 率
        for tag in tag_stats:
            total = sum(1 for s in self.submissions
                       if any(t == tag for t in s.tags))
            ac = sum(1 for s in self.submissions
                    if any(t == tag for t in s.tags) and s.result == "AC")
            tag_stats[tag]["ac_rate"] = round(ac / total * 100, 1) if total > 0 else 0
            tag_stats[tag]["avg_difficulty"] = round(
                tag_stats[tag]["total_difficulty"] / tag_stats[tag]["count"]
            ) if tag_stats[tag]["count"] > 0 else 0

        return dict(tag_stats)

    def monthly_trend(self) -> dict:
        """月度刷题趋势

        Returns:
            { "2024-01": {"ac_count": 23, "total_subs": 45}, ... }
        """
        trend = defaultdict(lambda: {"ac_count": 0, "total_subs": 0})
        for s in self.ac_submissions:
            month = s.submit_time[:7]  # "2024-01"
            trend[month]["ac_count"] += 1
        for s in self.submissions:
            trend[s.submit_time[:7]]["total_subs"] += 1
        return dict(sorted(trend.items()))

    def activity_heatmap(self, days: int = 365) -> list[dict]:
        """活动热力图数据（对标 GitHub 热力图）

        Returns:
            [{"date": "2024-01-15", "count": 5}, ...]
        """
        date_counts = Counter()
        for s in self.ac_submissions:
            date = s.submit_time[:10]
            date_counts[date] += 1

        today = datetime.now().date()
        result = []
        for i in range(days):
            d = today - timedelta(days=days - 1 - i)
            date_str = d.strftime("%Y-%m-%d")
            result.append({"date": date_str, "count": date_counts.get(date_str, 0)})
        return result

    def _unique_ac_problems(self) -> list:
        """去重 AC 题目（每题只保留首次 AC）"""
        seen = {}
        for s in sorted(self.ac_submissions, key=lambda x: x.submit_time):
            if s.problem_id not in seen:
                seen[s.problem_id] = s
        return list(seen.values())

    def _count_active_days(self) -> int:
        """统计有提交的天数"""
        days = set(s.submit_time[:10] for s in self.submissions)
        return len(days)

    def _calc_max_streak(self) -> int:
        """最长连续刷题天数"""
        ac_dates = sorted(set(s.submit_time[:10] for s in self.ac_submissions))
        if not ac_dates:
            return 0

        max_streak = 1
        current = 1
        for i in range(1, len(ac_dates)):
            prev = datetime.strptime(ac_dates[i-1], "%Y-%m-%d")
            curr = datetime.strptime(ac_dates[i], "%Y-%m-%d")
            if (curr - prev).days == 1:
                current += 1
                max_streak = max(max_streak, current)
            else:
                current = 1
        return max_streak
```

#### weakness.py — 弱项识别算法

```python
"""弱项识别引擎

基于行为模式加权评分，识别用户薄弱领域。
"""
from collections import defaultdict
from typing import Optional

class WeaknessAnalyzer:

    # 错误类型权重
    ERROR_WEIGHTS = {
        "WA": 10,   # 答案错误 — 算法思维问题
        "TLE": 15,  # 超时 — 复杂度分析薄弱
        "RE": 12,   # 运行时错误 — 边界条件/编码习惯
        "CE": 8,    # 编译错误 — 语法不熟练
        "MLE": 10,  # 内存超限 — 空间优化意识
    }

    def __init__(self, submissions: list):
        self.submissions = submissions

    def analyze(self, weak_threshold: float = 60.0) -> dict:
        """执行弱项分析

        Args:
            weak_threshold: AC 率低于此百分比视为弱项

        Returns:
            {
                "tag_weakness": [...],       # 按标签的弱项排名
                "behavior_profile": {...},   # 刷题行为画像
                "suggestions": [...]         # 改进建议
            }
        """
        tag_stats = self._aggregate_by_tag()

        # 过滤出弱项标签（AC 率低于阈值或高权重错误集中）
        weak_tags = []
        for tag, stats in tag_stats.items():
            weakness_score = self._calc_weakness_score(stats)
            if stats["ac_rate"] < weak_threshold or weakness_score > 50:
                weak_tags.append({
                    "tag": tag,
                    "ac_rate": stats["ac_rate"],
                    "total": stats["total"],
                    "error_breakdown": stats["error_breakdown"],
                    "weakness_score": weakness_score,
                    "avg_difficulty": stats.get("avg_difficulty", 0),
                    "problem_list": stats.get("problem_ids", []),
                })

        weak_tags.sort(key=lambda x: x["weakness_score"], reverse=True)

        # 行为画像
        behavior = self._build_behavior_profile()

        # 建议生成
        suggestions = self._generate_suggestions(weak_tags, behavior)

        return {
            "tag_weakness": weak_tags,
            "behavior_profile": behavior,
            "suggestions": suggestions,
        }

    def _aggregate_by_tag(self) -> dict:
        """按标签聚合提交数据"""
        tags = defaultdict(lambda: {
            "total": 0, "ac": 0, "wa": 0, "tle": 0, "re": 0,
            "ce": 0, "mle": 0, "total_difficulty": 0,
            "problem_ids": [], "ac_rate": 0.0, "avg_difficulty": 0,
            "error_breakdown": {},
        })

        # 按题目分组，每题只算一次
        problem_results = {}
        for s in self.submissions:
            key = (s.platform, s.problem_id)
            if key not in problem_results:
                problem_results[key] = {"tags": s.tags, "best": s.result, "difficulty": s.difficulty}

            current = problem_results[key]
            if s.result == "AC":
                current["best"] = "AC"
            elif current["best"] != "AC":
                current["best"] = s.result

        for key, info in problem_results.items():
            for tag in info["tags"]:
                stats = tags[tag]
                stats["total"] += 1
                if info["best"] == "AC":
                    stats["ac"] += 1
                elif info["best"] == "WA":
                    stats["wa"] += 1
                elif info["best"] in ("TLE", "TIME_LIMIT_EXCEEDED"):
                    stats["tle"] += 1
                elif info["best"] in ("RE", "RUNTIME_ERROR"):
                    stats["re"] += 1
                elif info["best"] in ("CE", "COMPILATION_ERROR"):
                    stats["ce"] += 1
                elif info["best"] in ("MLE", "MEMORY_LIMIT_EXCEEDED"):
                    stats["mle"] += 1

                stats["total_difficulty"] += info.get("difficulty", 0)
                stats["problem_ids"].append(f"{key[0]}:{key[1]}")

        # 计算 AC 率
        for tag, stats in tags.items():
            stats["ac_rate"] = round(stats["ac"] / stats["total"] * 100, 1) if stats["total"] > 0 else 0
            stats["avg_difficulty"] = round(stats["total_difficulty"] / stats["total"]) if stats["total"] > 0 else 0
            stats["error_breakdown"] = {
                "WA": stats["wa"], "TLE": stats["tle"],
                "RE": stats["re"], "CE": stats["ce"], "MLE": stats["mle"]
            }

        return dict(tags)

    def _calc_weakness_score(self, stats: dict) -> float:
        """计算弱项得分（越高越弱）"""
        score = 0
        score += stats.get("wa", 0) * self.ERROR_WEIGHTS["WA"]
        score += stats.get("tle", 0) * self.ERROR_WEIGHTS["TLE"]
        score += stats.get("re", 0) * self.ERROR_WEIGHTS["RE"]
        score += stats.get("ce", 0) * self.ERROR_WEIGHTS["CE"]
        score += stats.get("mle", 0) * self.ERROR_WEIGHTS["MLE"]

        # AC 率惩罚
        ac_rate = stats.get("ac_rate", 0)
        if ac_rate < 30: score += 100
        elif ac_rate < 50: score += 60
        elif ac_rate < 70: score += 30

        # 题目量少惩罚（样本不足）
        if stats.get("total", 0) <= 3: score *= 0.5

        return round(score, 1)

    def _build_behavior_profile(self) -> dict:
        """构建刷题行为画像"""
        ac_problems = self._unique_ac()
        total_subs = len(self.submissions)

        # 盲交检测（两次提交间隔 < 60s）
        sorted_subs = sorted(self.submissions, key=lambda x: x.submit_time)
        blind_count = 0
        for i in range(1, len(sorted_subs)):
            from datetime import datetime
            try:
                t1 = datetime.fromisoformat(sorted_subs[i-1].submit_time)
                t2 = datetime.fromisoformat(sorted_subs[i].submit_time)
                if (t2 - t1).total_seconds() < 60:
                    blind_count += 1
            except (ValueError, TypeError):
                pass

        return {
            "total_unique_ac": len(ac_problems),
            "total_submissions": total_subs,
            "blind_submissions": blind_count,
            "ce_count": sum(1 for s in self.submissions if s.result in ("CE", "COMPILATION_ERROR")),
            "re_count": sum(1 for s in self.submissions if s.result in ("RE", "RUNTIME_ERROR")),
            "blind_submit_ratio": round(blind_count / total_subs * 100, 1) if total_subs > 0 else 0,
        }

    def _unique_ac(self) -> list:
        seen = set()
        result = []
        for s in sorted(self.submissions, key=lambda x: x.submit_time):
            if s.result == "AC" and s.problem_id not in seen:
                seen.add(s.problem_id)
                result.append(s)
        return result

    def _generate_suggestions(self, weak_tags: list, behavior: dict) -> list:
        """生成改进建议"""
        suggestions = []
        for item in weak_tags[:5]:
            if item["weakness_score"] > 100:
                suggestions.append({
                    "level": "critical",
                    "tag": item["tag"],
                    "advice": f"「{item['tag']}」AC 率仅 {item['ac_rate']}%，建议从该标签的基础题开始系统性练习，优先练习中等难度题目。",
                    "recommended_count": max(10, item["total"] // 3),
                })
            elif item["weakness_score"] > 50:
                suggestions.append({
                    "level": "warning",
                    "tag": item["tag"],
                    "advice": f"「{item['tag']}」存在改善空间，建议针对该标签的常见题型进行专项训练。",
                    "recommended_count": max(5, item["total"] // 5),
                })

        if behavior.get("blind_submit_ratio", 0) > 20:
            suggestions.append({
                "level": "warning",
                "tag": "刷题习惯",
                "advice": "盲交率较高，建议提交前先本地测试，提高一次通过率。",
            })

        if behavior.get("ce_count", 0) > behavior.get("total_submissions", 1) * 0.05:
            suggestions.append({
                "level": "info",
                "tag": "编码习惯",
                "advice": "编译错误较频繁，建议提交前本地编译检查语法。",
            })

        return suggestions
```

### 2.4 DeepSeek AI 模块设计

#### deepseek_client.py — DeepSeek API 客户端

```python
"""DeepSeek API 客户端

API 文档: https://platform.deepseek.com/api-docs
DeepSeek API 兼容 OpenAI 格式:
  - Base URL: https://api.deepseek.com/v1
  - 模型: deepseek-chat, deepseek-coder
  - 认证: Authorization: Bearer {API_KEY}
"""
import json
import requests
from typing import Optional, Generator

DEEPSEEK_BASE = "https://api.deepseek.com/v1"
DEFAULT_MODEL = "deepseek-chat"
DEFAULT_TIMEOUT = 600  # 10 分钟

class DeepSeekClient:
    """DeepSeek API 客户端

    兼容 OpenAI SDK 调用格式，可直接替换 openai 库。
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = DEEPSEEK_BASE,
        model: str = DEFAULT_MODEL,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout

    def chat(
        self,
        messages: list[dict],
        system: Optional[str] = None,
        stream: bool = False,
        **kwargs,
    ) -> dict | Generator:
        """发送聊天请求

        Args:
            messages: [{"role": "user", "content": "..."}, ...]
            system: 系统提示词
            stream: 是否流式返回
            **kwargs: 覆盖默认参数

        Returns:
            dict: {
                "content": "回答文本",
                "model": "deepseek-chat",
                "usage": {"prompt_tokens": 100, "completion_tokens": 200, "total_tokens": 300}
            }
        """
        full_messages = []
        if system:
            full_messages.append({"role": "system", "content": system})
        full_messages.extend(messages)

        payload = {
            "model": kwargs.get("model", self.model),
            "messages": full_messages,
            "temperature": kwargs.get("temperature", self.temperature),
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "stream": stream,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        if stream:
            return self._stream_chat(headers, payload)

        resp = requests.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            headers=headers,
            timeout=self.timeout,
        )
        data = resp.json()

        if "error" in data:
            raise Exception(f"DeepSeek API 错误: {data['error']}")

        return {
            "content": data["choices"][0]["message"]["content"],
            "model": data.get("model", self.model),
            "usage": data.get("usage", {}),
        }

    def _stream_chat(self, headers: dict, payload: dict) -> Generator:
        """流式聊天"""
        import sseclient  # pip install sseclient-py

        resp = requests.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            headers=headers,
            stream=True,
            timeout=self.timeout,
        )

        client = sseclient.SSEClient(resp)
        for event in client.events():
            if event.data == "[DONE]":
                break
            try:
                delta = json.loads(event.data)
                content = delta["choices"][0].get("delta", {}).get("content", "")
                if content:
                    yield {"content": content}
            except json.JSONDecodeError:
                continue

    def test_connection(self) -> bool:
        """测试 API 连接"""
        try:
            result = self.chat(
                messages=[{"role": "user", "content": "Hello, reply with 'OK'."}],
                max_tokens=10,
            )
            return "OK" in result.get("content", "")
        except Exception:
            return False
```

#### solution_gen.py — 题解生成

```python
"""基于 DeepSeek 的题解生成器"""
from pathlib import Path
from .deepseek_client import DeepSeekClient

class SolutionGenerator:
    """题解生成器

    支持:
    - 自定义提示词模板（从 prompts/solution.md 加载）
    - 模板变量替换
    - AC 代码 + 题目描述作为上下文
    """

    def __init__(self, client: DeepSeekClient):
        self.client = client
        self.template = self._load_template()

    def _load_template(self) -> str:
        template_path = Path(__file__).parent / "prompts" / "solution.md"
        if template_path.exists():
            return template_path.read_text(encoding="utf-8")
        return self._default_template()

    def _default_template(self) -> str:
        return """## 题目: {{title}}

{{problem_description}}

### 解题思路

请分析以下题目并生成题解。要求：
1. 时间复杂度和空间复杂度分析
2. 核心算法说明
3. 关键代码片段解释
4. 易错点提醒

**题目内容:**
{{content}}

**输入格式:**
{{input_format}}

**输出格式:**
{{output_format}}

**限制条件:**
{{constraints}}

**我的 AC 代码 ({{language}}):**
```{{language}}
{{ac_code}}
```

**参考题解风格:** {{style_prompt}}
"""

    def generate(self, problem: dict, ac_code: str = "", language: str = "cpp", style_prompt: str = "") -> str:
        """生成题解

        Args:
            problem: 题目信息字典 (title, content, input_format, output_format, constraints, tags)
            ac_code: AC 代码
            language: 编程语言
            style_prompt: 风格提示词注入

        Returns:
            生成的 Markdown 题解
        """
        # 变量替换
        prompt = self.template
        replacements = {
            "{{title}}": problem.get("title", ""),
            "{{problem_description}}": problem.get("content", "")[:2000],
            "{{content}}": problem.get("content", ""),
            "{{input_format}}": problem.get("input_format", ""),
            "{{output_format}}": problem.get("output_format", ""),
            "{{constraints}}": problem.get("constraints", ""),
            "{{language}}": language,
            "{{ac_code}}": ac_code,
            "{{style_prompt}}": style_prompt or "请提供严谨、清晰的题解，包含完整的推导过程和复杂度分析。",
        }
        for k, v in replacements.items():
            prompt = prompt.replace(k, v)

        system = "你是一名算法竞赛教练，擅长用清晰、严谨的方式讲解算法题。使用中文回答。"
        result = self.client.chat(
            messages=[{"role": "user", "content": prompt}],
            system=system,
            temperature=0.2,
            max_tokens=4096,
        )
        return result["content"]
```

#### suggest_gen.py — 刷题建议生成

```python
"""基于用户数据的 AI 刷题建议生成器"""
from .deepseek_client import DeepSeekClient
from pathlib import Path

class SuggestGenerator:
    """AI 刷题建议生成

    基于做题统计数据 + 弱项分析结果，调用 DeepSeek 生成个性化建议。
    """

    def __init__(self, client: DeepSeekClient):
        self.client = client

    def generate(self, stats: dict, weakness: dict) -> str:
        """生成个性化刷题建议

        Args:
            stats: stats_engine.basic_stats() 返回值
            weakness: WeaknessAnalyzer.analyze() 返回值

        Returns:
            AI 生成的个性化建议文本（Markdown）
        """
        import json

        prompt = self._build_prompt(stats, weakness)

        system = """你是一名资深算法竞赛教练，擅长分析学生的刷题数据并给出精准的提分建议。
你需要：
1. 基于用户的刷题数据，指出最需要改进的 3 个方向
2. 给出具体的练习计划（包括推荐题量、难度范围、练习重点）
3. 针对用户的弱项标签，推荐典型题目类型
4. 指出用户刷题习惯中的问题
使用中文输出，结构化格式。"""

        result = self.client.chat(
            messages=[{"role": "user", "content": prompt}],
            system=system,
            temperature=0.3,
            max_tokens=2048,
        )
        return result["content"]

    def _build_prompt(self, stats: dict, weakness: dict) -> str:
        import json
        return f"""请根据以下用户的刷题数据，给出个性化刷题建议。

## 用户统计
{json.dumps(stats, ensure_ascii=False, indent=2)}

## 弱项分析
{json.dumps(weakness.get('tag_weakness', [])[:5], ensure_ascii=False, indent=2)}

## 行为画像
{json.dumps(weakness.get('behavior_profile', {}), ensure_ascii=False, indent=2)}

## 输出要求
请输出以下内容：
### 1. 当前水平评估
### 2. 弱项诊断（按优先级排序）
### 3. 下阶段训练计划（具体到每周题量、推荐难度区间）
### 4. 刷题习惯改进建议
"""
```

## 三、API 接口设计

### 3.1 爬取相关接口

```
POST /api/v2/crawl/start
  描述: 启动用户提交记录爬取
  请求体: {
    "platform": "codeforces | luogu | nowcoder",
    "username": "tourist",
    "cookie": ""          // 可选，洛谷/牛客需要
  }
  响应: {
    "task_id": "abc12345",
    "status": "running",
    "message": "开始爬取..."
  }

GET /api/v2/crawl/progress/{task_id}
  描述: 查询爬取进度
  响应: {
    "task_id": "abc12345",
    "status": "running | done | failed",
    "progress": 0.65,
    "message": "已获取 350/500 条记录...",
    "result_count": 350,
    "error": null
  }

GET /api/v2/crawl/tasks
  描述: 列出所有爬取任务
  响应: {
    "tasks": [...]
  }
```

### 3.2 分析相关接口

```
GET /api/v2/analysis/{platform}/{username}
  描述: 获取用户做题分析报告
  查询参数:
    - refresh: true | false (是否强制重新分析)
  响应: {
    "platform": "codeforces",
    "username": "tourist",
    "basic_stats": {
      "total_ac_problems": 500,
      "total_submissions": 800,
      "ac_rate": 62.5,
      "active_days": 200,
      "avg_per_day": 2.5,
      "max_streak": 45
    },
    "difficulty_distribution": {...},
    "tag_distribution": {...},
    "monthly_trend": {...},
    "activity_heatmap": [...],
    "weakness": {
      "tag_weakness": [...],
      "behavior_profile": {...},
      "suggestions": [...]
    }
  }

GET /api/v2/analysis/{platform}/{username}/report
  描述: 导出 Markdown 分析报告
  响应: Markdown 文本 (Content-Type: text/markdown)
```

### 3.3 DeepSeek 相关接口

```
POST /api/v2/deepseek/solve
  描述: 生成题目题解
  请求体: {
    "problem": { ... },
    "ac_code": "...",
    "language": "cpp",
    "style": "rigorous"
  }
  响应: {
    "solution": "# 题解内容 (Markdown)...",
    "model": "deepseek-chat",
    "tokens_used": 1500
  }

POST /api/v2/deepseek/suggest
  描述: 生成个性化刷题建议
  请求体: {
    "platform": "codeforces",
    "username": "tourist"
  }
  响应: {
    "suggestion": "## 个性化建议...",
    "model": "deepseek-chat",
    "tokens_used": 800
  }

POST /api/v2/deepseek/test
  描述: 测试 DeepSeek API 连接
  请求体: { "api_key": "sk-...", "model": "deepseek-chat" }
  响应: { "ok": true, "model": "deepseek-chat" }

POST /api/v2/deepseek/batch-solve
  描述: 批量生成题解
  请求体: {
    "problem_ids": ["CF:123A", "P1001"],
    "style": "concise",
    "concurrency": 3    // 并发数
  }
  响应: { "task_id": "batch_xxx" }
```

### 3.4 兼容原有接口

所有原有 `/api/problems/*`、`/api/dashboard/*`、`/api/settings/*`、`/api/solutions/*` 路由保持不变，新接口使用 `/api/v2/` 前缀，无冲突。

## 四、数据库设计

### 4.1 SQLite 表结构

```sql
-- 用户表：记录爬取过的用户
CREATE TABLE users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    platform      TEXT NOT NULL,           -- codeforces / luogu / nowcoder
    username      TEXT NOT NULL,           -- 平台用户名
    last_crawl_at TEXT,                    -- 最后爬取时间 ISO8601
    crawl_count   INTEGER DEFAULT 0,       -- 爬取次数
    created_at    TEXT DEFAULT (datetime('now')),
    UNIQUE(platform, username)
);

-- 提交记录表
CREATE TABLE submissions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL REFERENCES users(id),
    platform      TEXT NOT NULL,
    problem_id    TEXT NOT NULL,
    title         TEXT DEFAULT '',
    difficulty    INTEGER DEFAULT 0,
    tags          TEXT DEFAULT '[]',       -- JSON 数组
    result        TEXT DEFAULT '',
    submit_time   TEXT DEFAULT '',
    language      TEXT DEFAULT '',
    code          TEXT DEFAULT '',
    url           TEXT DEFAULT '',
    created_at    TEXT DEFAULT (datetime('now')),
    UNIQUE(user_id, platform, problem_id, submit_time)
);

-- 索引：加速查询
CREATE INDEX idx_submissions_user ON submissions(user_id);
CREATE INDEX idx_submissions_result ON submissions(user_id, result);
CREATE INDEX idx_submissions_time ON submissions(user_id, submit_time);
CREATE INDEX idx_submissions_tags ON submissions(user_id) WHERE json_array_length(tags) > 0;

-- 分析快照表：缓存分析结果，避免重复计算
CREATE TABLE analysis_snapshots (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL REFERENCES users(id),
    snapshot_data TEXT NOT NULL,           -- JSON: 完整分析结果
    generated_at  TEXT DEFAULT (datetime('now')),
    UNIQUE(user_id)
);

-- DeepSeek 调用记录表
CREATE TABLE deepseek_logs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    request_type  TEXT NOT NULL,           -- solve / suggest / test
    model         TEXT NOT NULL,
    tokens_in     INTEGER DEFAULT 0,
    tokens_out    INTEGER DEFAULT 0,
    cost_estimate REAL DEFAULT 0.0,        -- 费用估算 ($)
    created_at    TEXT DEFAULT (datetime('now'))
);

-- DeepSeek 配置表（单一记录，覆盖原有 AI profiles 中 DeepSeek 专属项）
CREATE TABLE deepseek_config (
    id            INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    api_key       TEXT DEFAULT '',
    model         TEXT DEFAULT 'deepseek-chat',
    temperature   REAL DEFAULT 0.2,
    max_tokens    INTEGER DEFAULT 4096,
    timeout_s     INTEGER DEFAULT 600,
    base_url      TEXT DEFAULT 'https://api.deepseek.com/v1',
    updated_at    TEXT DEFAULT (datetime('now'))
);
```

### 4.2 数据模型类

```python
"""db/models.py"""
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class User:
    id: int = 0
    platform: str = ""
    username: str = ""
    last_crawl_at: str = ""
    crawl_count: int = 0
    created_at: str = ""

@dataclass
class SubmissionRecord:
    id: int = 0
    user_id: int = 0
    platform: str = ""
    problem_id: str = ""
    title: str = ""
    difficulty: int = 0
    tags: list[str] = field(default_factory=list)
    result: str = ""
    submit_time: str = ""
    language: str = ""
    code: str = ""
    url: str = ""

@dataclass
class AnalysisSnapshot:
    id: int = 0
    user_id: int = 0
    snapshot_data: str = "{}"   # JSON
    generated_at: str = ""

@dataclass
class DeepSeekConfig:
    api_key: str = ""
    model: str = "deepseek-chat"
    temperature: float = 0.2
    max_tokens: int = 4096
    timeout_s: int = 600
    base_url: str = "https://api.deepseek.com/v1"
```

## 五、浏览器扩展改造

### 5.1 新增文件清单

```
acm-helper-extension/
├── manifest.json                    # 修改: 新增 content_security_policy
├── analysis/                        # 新增: 用户分析模块
│   ├── analysis.html                #   分析面板页面
│   ├── analysis.css                 #   分析面板样式
│   └── analysis.js                  #   分析面板逻辑
├── popup/
│   ├── popup.html                   # 修改: 新增快捷入口
│   ├── popup.js                     # 修改: 新增快速分析按钮
│   └── popup.css                    # 修改: 新按钮样式
├── dashboard/
│   ├── dashboard.html               # 修改: 新增分析视图导航
│   ├── dashboard.js                 # 修改: 集成分析报告渲染
│   └── dashboard.css                # 修改: 分析视图样式
├── utils/
│   └── api.js                       # 修改: 新增爬取/分析/DeepSeek 接口函数
└── assets/
    └── analysis-icon.svg            # 新增: 分析图标
```

### 5.2 manifest.json 修改

在原 `manifest.json` 基础上：

```json
{
  "manifest_version": 3,
  "name": "ACM Helper",
  "version": "5.0.0",
  "description": "做题记录管理 + 用户名分析 + DeepSeek AI",
  "permissions": [
    "storage",
    "activeTab",
    "scripting",
    "webRequest"
  ],
  "host_permissions": [
    "http://localhost:8000/*",
    "https://codeforces.com/*",
    "https://www.luogu.com.cn/*",
    "https://ac.nowcoder.com/*",
    "https://atcoder.jp/*",
    "https://api.deepseek.com/*"
  ],
  "action": {
    "default_popup": "popup/popup.html",
    "default_icon": "1.png"
  },
  "background": {
    "service_worker": "background/background.js",
    "type": "module"
  },
  "content_scripts": [
    {
      "matches": ["https://codeforces.com/*"],
      "js": ["content/codeforces_scraper.js"]
    }
    // ... 原有 content_scripts 保留
  ]
}
```

### 5.3 analysis.js — 用户分析面板核心逻辑

```javascript
// analysis/analysis.js
// 用户分析面板：输入用户名 → 爬取 → 分析 → 展示

class UserAnalysisPanel {
    constructor() {
        this.currentTaskId = null;
        this.pollInterval = null;
        this.charts = {};
        this._bindEvents();
    }

    // ---- 爬取流程 ----

    async startCrawl() {
        const platform = document.getElementById('platform-select').value;
        const username = document.getElementById('username-input').value.trim();
        const cookie = document.getElementById('cookie-input')?.value.trim() || '';

        if (!username) {
            this._showError('请输入用户名');
            return;
        }

        this._setCrawlState('running');

        try {
            const resp = await api.post('/api/v2/crawl/start', {
                platform, username, cookie
            });
            this.currentTaskId = resp.task_id;
            this._pollProgress();
        } catch (e) {
            this._setCrawlState('error', e.message);
        }
    }

    _pollProgress() {
        this.pollInterval = setInterval(async () => {
            try {
                const resp = await api.get(`/api/v2/crawl/progress/${this.currentTaskId}`);

                this._updateProgressBar(resp.progress);
                this._updateStatusText(resp.message);

                if (resp.status === 'done') {
                    clearInterval(this.pollInterval);
                    this._setCrawlState('done');
                    // 自动触发分析
                    await this.loadAnalysis();
                } else if (resp.status === 'failed') {
                    clearInterval(this.pollInterval);
                    this._setCrawlState('error', resp.error);
                }
            } catch (e) {
                clearInterval(this.pollInterval);
                this._setCrawlState('error', e.message);
            }
        }, 1000);
    }

    // ---- 分析报告加载 ----

    async loadAnalysis() {
        const platform = document.getElementById('platform-select').value;
        const username = document.getElementById('username-input').value.trim();

        this._showLoading('正在生成分析报告...');

        try {
            const data = await api.get(
                `/api/v2/analysis/${platform}/${username}?refresh=true`
            );
            this._renderReport(data);
        } catch (e) {
            this._showError(`分析失败: ${e.message}`);
        }
    }

    // ---- 报告渲染 ----

    _renderReport(data) {
        this._renderBasicStats(data.basic_stats);
        this._renderDifficultyChart(data.difficulty_distribution);
        this._renderTagChart(data.tag_distribution);
        this._renderActivityHeatmap(data.activity_heatmap);
        this._renderTrendChart(data.monthly_trend);
        this._renderWeakness(data.weakness);
        this._renderSuggestions(data.weakness.suggestions);
    }

    _renderBasicStats(stats) {
        const container = document.getElementById('basic-stats');
        container.innerHTML = `
            <div class="stat-grid">
                <div class="stat-card">
                    <div class="stat-value">${stats.total_ac_problems}</div>
                    <div class="stat-label">AC 题目数</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">${stats.ac_rate}%</div>
                    <div class="stat-label">通过率</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">${stats.active_days}</div>
                    <div class="stat-label">活跃天数</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">${stats.max_streak} 天</div>
                    <div class="stat-label">最长连续</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">${stats.avg_per_day}</div>
                    <div class="stat-label">日均 AC</div>
                </div>
            </div>
        `;
    }

    _renderDifficultyChart(distribution) {
        // 使用 Chart.js 渲染难度分布柱状图
        const ctx = document.getElementById('difficulty-chart').getContext('2d');
        if (this.charts.difficulty) this.charts.difficulty.destroy();

        this.charts.difficulty = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: Object.keys(distribution),
                datasets: [{
                    label: '题目数',
                    data: Object.values(distribution),
                    backgroundColor: this._gradientArray(Object.keys(distribution).length),
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    title: { display: true, text: '难度分布' }
                }
            }
        });
    }

    _renderActivityHeatmap(data) {
        // 复用原项目 dashboard.js 的 renderActivityHeatmap 逻辑
        // 或使用简化版 SVG 热力图
        const container = document.getElementById('heatmap-container');
        const weeks = this._groupByWeek(data);
        container.innerHTML = this._buildHeatmapSVG(weeks);
    }

    _renderWeakness(weakness) {
        const container = document.getElementById('weakness-section');
        const top5 = weakness.tag_weakness.slice(0, 5);

        container.innerHTML = `
            <h3>弱项排名</h3>
            <div class="weakness-list">
                ${top5.map((w, i) => `
                    <div class="weakness-item rank-${i + 1}">
                        <span class="rank-badge">#${i + 1}</span>
                        <span class="tag-name">${w.tag}</span>
                        <span class="ac-rate ${this._rateClass(w.ac_rate)}">${w.ac_rate}%</span>
                        <span class="weakness-score">得分: ${w.weakness_score}</span>
                        <div class="error-bar">
                            <span class="wa">WA:${w.error_breakdown.WA}</span>
                            <span class="tle">TLE:${w.error_breakdown.TLE}</span>
                            <span class="re">RE:${w.error_breakdown.RE}</span>
                        </div>
                    </div>
                `).join('')}
            </div>
        `;
    }

    _renderSuggestions(suggestions) {
        const container = document.getElementById('suggestions-section');
        container.innerHTML = `
            <h3>改进建议</h3>
            ${suggestions.map(s => `
                <div class="suggestion-card level-${s.level}">
                    <span class="level-badge ${s.level}">${
                        s.level === 'critical' ? '严重' : s.level === 'warning' ? '注意' : '提示'
                    }</span>
                    <p>${s.advice}</p>
                    ${s.recommended_count ? `<span class="rec-count">建议练习 ${s.recommended_count} 题</span>` : ''}
                </div>
            `).join('')}
        `;
    }

    // ---- AI 建议 ----

    async generateAISuggestions() {
        const platform = document.getElementById('platform-select').value;
        const username = document.getElementById('username-input').value.trim();

        this._showLoading('AI 正在生成个性化建议...');

        try {
            const resp = await api.post('/api/v2/deepseek/suggest', {
                platform, username
            });
            document.getElementById('ai-suggestions').innerHTML =
                this._markdownToHTML(resp.suggestion);
        } catch (e) {
            this._showError(`AI 建议生成失败: ${e.message}`);
        }
    }

    // ---- UI 工具方法 ----

    _bindEvents() {
        document.getElementById('btn-start').addEventListener('click', () => this.startCrawl());
        document.getElementById('btn-ai-suggest').addEventListener('click', () => this.generateAISuggestions());
        document.getElementById('btn-export-report').addEventListener('click', () => this.exportReport());
    }

    _setCrawlState(state, message = '') {
        const statusEl = document.getElementById('crawl-status');
        statusEl.className = `crawl-status ${state}`;
        statusEl.textContent = message || {
            running: '正在爬取...', done: '爬取完成', error: '爬取失败', idle: ''
        }[state] || '';
    }

    _updateProgressBar(progress) {
        document.getElementById('progress-fill').style.width = `${progress * 100}%`;
    }

    _updateStatusText(text) {
        document.getElementById('status-text').textContent = text;
    }

    _showError(msg) { /* toast 错误提示 */ }
    _showLoading(msg) { /* loading 状态 */ }
    _groupByWeek(data) { /* 按周分组 */ return []; }
    _buildHeatmapSVG(weeks) { /* SVG 热力图 */ return ''; }
    _gradientArray(n) { return []; }
    _rateClass(rate) { return rate >= 70 ? 'good' : rate >= 40 ? 'medium' : 'bad'; }
    _markdownToHTML(md) { /* 简单的 Markdown 转 HTML */ return md; }

    async exportReport() { /* 导出 Markdown 报告 */ }
}

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    new UserAnalysisPanel();
});
```

### 5.4 api.js 新增方法

```javascript
// utils/api.js 追加方法

const api = {
    // ... 原有方法保留

    // ---- 爬取相关 ----
    async startCrawl(platform, username, cookie = '') {
        return this.post('/api/v2/crawl/start', { platform, username, cookie });
    },

    async getCrawlProgress(taskId) {
        return this.get(`/api/v2/crawl/progress/${taskId}`);
    },

    // ---- 分析相关 ----
    async getAnalysis(platform, username, refresh = false) {
        return this.get(`/api/v2/analysis/${platform}/${username}?refresh=${refresh}`);
    },

    async exportReport(platform, username) {
        return this.get(`/api/v2/analysis/${platform}/${username}/report`);
    },

    // ---- DeepSeek 相关 ----
    async generateSolution(problem, acCode, language, style) {
        return this.post('/api/v2/deepseek/solve', {
            problem, ac_code: acCode, language, style
        });
    },

    async generateSuggestions(platform, username) {
        return this.post('/api/v2/deepseek/suggest', { platform, username });
    },

    async testDeepSeek(apiKey, model = 'deepseek-chat') {
        return this.post('/api/v2/deepseek/test', { api_key: apiKey, model });
    },
};
```

### 5.5 popup.html 修改 — 新增快速分析入口

在 popup.html 原有导航中新增：

```html
<!-- 快速分析区域 -->
<div class="quick-analysis">
    <select id="quick-platform">
        <option value="codeforces">Codeforces</option>
        <option value="luogu">洛谷</option>
        <option value="nowcoder">牛客</option>
    </select>
    <input type="text" id="quick-username" placeholder="输入用户名" />
    <button id="quick-analyze-btn">快速分析</button>
    <span id="quick-status"></span>
</div>
```

【继续】
