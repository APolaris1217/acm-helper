"""爬取任务调度器（内存版，单机部署无需 Redis）"""
import uuid
import threading
from typing import Optional
from .base_crawler import CrawlProgress


class TaskManager:
    """爬取任务生命周期管理

    用法:
        tm = TaskManager()
        task = tm.create("codeforces", "tourist")
        tm.update(task.task_id, status="running", message="fetching...")
        # ... 爬取完成后 ...
        tm.update(task.task_id, status="done", progress=1.0)
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tasks: dict[str, CrawlProgress] = {}
            cls._instance._lock = threading.Lock()
        return cls._instance

    def create(self, platform: str, username: str) -> CrawlProgress:
        task = CrawlProgress(
            task_id=str(uuid.uuid4())[:8],
            platform=platform,
            username=username,
            status="pending",
        )
        with self._lock:
            self._tasks[task.task_id] = task
        return task

    def get(self, task_id: str) -> Optional[CrawlProgress]:
        with self._lock:
            return self._tasks.get(task_id)

    def update(self, task_id: str, **kwargs):
        with self._lock:
            task = self._tasks.get(task_id)
            if task:
                for k, v in kwargs.items():
                    setattr(task, k, v)

    def list_all(self) -> list[CrawlProgress]:
        with self._lock:
            return list(self._tasks.values())

    def cleanup(self, max_age_s: int = 3600):
        """清理超过 max_age_s 的已完成任务"""
        import time
        with self._lock:
            stale = [
                tid for tid, t in self._tasks.items()
                if t.status in ("done", "failed")
            ]
            for tid in stale:
                del self._tasks[tid]
