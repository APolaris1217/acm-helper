"""数据模型 dataclass 定义"""
from dataclasses import dataclass, field


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
    record_id: str = ""


@dataclass
class AnalysisSnapshot:
    id: int = 0
    user_id: int = 0
    snapshot_data: str = "{}"
    generated_at: str = ""
