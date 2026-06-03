"""Data model dataclasses for the new 7-table schema."""
from dataclasses import dataclass, field


@dataclass
class AppUser:
    """Application user (multi-user support)."""
    id: int = 0
    username: str = ""
    email: str = ""
    password_hash: str = ""
    created_at: str = ""
    updated_at: str = ""


@dataclass
class PlatformAccount:
    """OJ platform account binding for an app user."""
    id: int = 0
    app_user_id: int = 0
    platform: str = ""
    username: str = ""
    cookie: str = ""
    last_crawl_at: str = ""
    crawl_count: int = 0
    created_at: str = ""
    updated_at: str = ""


@dataclass
class Problem:
    """Problem entry in the problem library."""
    id: int = 0
    platform: str = ""
    problem_id: str = ""
    title: str = ""
    difficulty: int = 0
    url: str = ""
    content_snippet: str = ""
    created_at: str = ""
    tags: list[str] = field(default_factory=list)  # populated on load, not stored directly


@dataclass
class Tag:
    """Tag dictionary entry."""
    id: int = 0
    name_en: str = ""
    name_cn: str = ""
    category: str = ""
    created_at: str = ""


@dataclass
class WeeklyReport:
    """Persisted weekly report."""
    id: int = 0
    app_user_id: int = 0
    report_content: str = ""
    period_start: str = ""
    period_end: str = ""
    platforms_covered: str = ""
    generated_at: str = ""
    created_at: str = ""


@dataclass
class SubmissionRecord:
    """Submission record (updated: references problem FK + platform_account FK)."""
    id: int = 0
    platform_account_id: int = 0
    problem_id: int = 0         # FK to problems.id
    result: str = ""
    submit_time: str = ""
    language: str = ""
    code: str = ""
    record_id: str = ""
    created_at: str = ""


@dataclass
class AnalysisSnapshot:
    """Legacy analysis snapshot."""
    id: int = 0
    user_id: int = 0
    snapshot_data: str = "{}"
    generated_at: str = ""
