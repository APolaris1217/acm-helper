"""薄弱点判定策略 — 策略模式，每套规则独立为策略类。

统一接口: detect(tag, tag_submissions, all_submissions, config) → WeaknessResult | None
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone

from engine.config import AnalysisConfig


# ── 数据结构 ──

@dataclass
class WeaknessResult:
    """单个标签的薄弱判定结果。"""
    tag: str
    triggered_rules: list[str] = field(default_factory=list)
    pass_rate_detail: dict | None = None
    efficiency_detail: dict | None = None
    trend_detail: dict | None = None


# ── 工具函数 ──

def _group_by_problem(submissions: list[dict]) -> dict[tuple, list[dict]]:
    groups = defaultdict(list)
    for s in submissions:
        key = (s.get("platform", ""), s.get("problemId", ""))
        groups[key].append(s)
    return dict(groups)


def _ever_ac(ss: list[dict]) -> bool:
    return any(s.get("result") == "AC" for s in ss)


def _parse_date(s: dict) -> datetime | None:
    d = (s.get("date") or s.get("submit_time") or "")[:10]
    if not d:
        return None
    try:
        return datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


# ── 基类 ──

class BaseStrategy(ABC):
    """薄弱点判定策略基类。"""

    @abstractmethod
    def detect(
        self,
        tag: str,
        tag_submissions: list[dict],
        all_submissions: list[dict],
        config: AnalysisConfig,
    ) -> WeaknessResult | None:
        """判定该标签是否为薄弱点。返回 None 表示不触发。"""
        ...


# ── 规则1: 通过率策略 ──

class PassRateStrategy(BaseStrategy):
    """基于通过率的判定。

    通过率 = 该标签下AC的题目数 / 该标签下尝试过的题目总数。
    支持难度加权：基础题（低难度）错误扣分更重。
    通过率 < alpha → 薄弱。
    """

    def detect(self, tag, tag_submissions, all_submissions, config):
        groups = _group_by_problem(tag_submissions)
        total = len(groups)
        if total < config.min_problems_for_analysis:
            return None

        ac_count = sum(1 for _, ss in groups.items() if _ever_ac(ss))
        if ac_count == 0:
            return None  # 从未AC → 不参与薄弱判定，见 ReportBuilder 单独归类

        # 难度加权：每道题按"难度倒数"加权。简单题不过关扣分更重。
        if config.difficulty_weighted:
            weighted_ac = 0.0
            weighted_total = 0.0
            for _, ss in groups.items():
                diff = ss[0].get("difficulty", 0) or 0
                w = 1.0 / max(diff, 400)  # 最低 400 分防止除零
                weighted_total += w
                if _ever_ac(ss):
                    weighted_ac += w
            pass_rate = weighted_ac / weighted_total if weighted_total else 0
        else:
            pass_rate = ac_count / total

        if pass_rate < config.alpha:
            return WeaknessResult(
                tag=tag,
                triggered_rules=["pass_rate"],
                pass_rate_detail={
                    "ac": ac_count,
                    "total": total,
                    "rate": round(pass_rate, 4),
                    "threshold": config.alpha,
                    "difficulty_weighted": config.difficulty_weighted,
                },
            )
        return None


# ── 规则2: 时间效率策略 ──

class EfficiencyStrategy(BaseStrategy):
    """基于时间与效率的判定。

    条件1: 该标签平均尝试次数 > gamma
    条件2: 该标签平均解题耗时 > beta × 全局同类题目耗时中位数
    满足任一条件 → 判定为薄弱。
    """

    def detect(self, tag, tag_submissions, all_submissions, config):
        groups = _group_by_problem(tag_submissions)
        total_problems = len(groups)
        if total_problems < config.min_problems_for_analysis:
            return None

        # 该标签平均尝试次数
        total_attempts = sum(len(ss) for ss in groups.values())
        avg_attempts = total_attempts / total_problems

        # 该标签平均解题耗时（每题从首次到末次提交的时间差）
        tag_times = []
        for _, ss in groups.items():
            dates = [_parse_date(s) for s in ss if _parse_date(s)]
            if len(dates) >= 2:
                span_min = (max(dates) - min(dates)).total_seconds() / 60
                tag_times.append(span_min)

        avg_time = sum(tag_times) / len(tag_times) if tag_times else 0

        # 全局中位数耗时
        all_groups = _group_by_problem(all_submissions)
        all_times = []
        for _, ss in all_groups.items():
            dates = [_parse_date(s) for s in ss if _parse_date(s)]
            if len(dates) >= 2:
                span_min = (max(dates) - min(dates)).total_seconds() / 60
                all_times.append(span_min)
        global_median = _median(all_times) if all_times else 0

        triggered = False
        detail = {
            "avg_attempts": round(avg_attempts, 2),
            "attempts_threshold": config.gamma,
            "avg_time_minutes": round(avg_time, 1),
            "global_median_minutes": round(global_median, 1),
            "time_threshold": round(config.beta * global_median, 1),
        }

        if avg_attempts > config.gamma:
            triggered = True

        if avg_time > 0 and global_median > 0 and avg_time > config.beta * global_median:
            triggered = True

        if triggered:
            return WeaknessResult(
                tag=tag,
                triggered_rules=["efficiency"],
                efficiency_detail=detail,
            )
        return None


# ── 规则3: 学习趋势策略 ──

class TrendStrategy(BaseStrategy):
    """基于学习趋势的判定。

    将提交按时间排序后均分为前后半区:
    - 后半区正确率 / 前半区正确率 < threshold → 下降趋势 → 薄弱
    - 线性回归斜率 < slope_threshold → 无进步 → 薄弱
    """

    def detect(self, tag, tag_submissions, all_submissions, config):
        groups = _group_by_problem(tag_submissions)
        total_problems = len(groups)
        if total_problems < config.min_problems_for_analysis:
            return None

        # 按每题首次提交时间排序
        problem_order = []
        for key, ss in groups.items():
            first_date = None
            for s in ss:
                d = _parse_date(s)
                if d:
                    first_date = d
                    break
            problem_order.append((first_date, key, ss))
        problem_order.sort(key=lambda x: x[0] or datetime.min.replace(tzinfo=timezone.utc))

        if len(problem_order) < 4:
            return None  # 样本太少不分析趋势

        # 前后半区
        mid = len(problem_order) // 2
        first_half = problem_order[:mid]
        second_half = problem_order[mid:]

        first_ac = sum(1 for _, _, ss in first_half if _ever_ac(ss))
        second_ac = sum(1 for _, _, ss in second_half if _ever_ac(ss))

        first_rate = first_ac / len(first_half) if first_half else 0
        second_rate = second_ac / len(second_half) if second_half else 0

        triggered = False
        detail = {
            "first_half_ac_rate": round(first_rate, 4),
            "second_half_ac_rate": round(second_rate, 4),
            "ratio": round(second_rate / first_rate, 4) if first_rate > 0 else None,
            "ratio_threshold": config.trend_ratio_threshold,
            "slope": None,
            "slope_threshold": config.trend_slope_threshold,
        }

        # 判定1: 后半区显著下降
        if first_rate > 0 and second_rate / first_rate < config.trend_ratio_threshold:
            triggered = True

        # 判定2: 线性回归斜率过低
        slope = _compute_slope(problem_order, config)
        detail["slope"] = round(slope, 4) if slope is not None else None
        if slope is not None and slope < config.trend_slope_threshold:
            triggered = True

        if triggered:
            return WeaknessResult(
                tag=tag,
                triggered_rules=["trend"],
                trend_detail=detail,
            )
        return None


# ── 线性回归 ──

def _compute_slope(problem_order, config: AnalysisConfig) -> float | None:
    """按周聚合正确率，拟合线性回归斜率。"""
    # 按周分组
    week_buckets = defaultdict(lambda: {"total": 0, "ac": 0})
    for date, _, ss in problem_order:
        if date is None:
            continue
        # 以周一为周标记
        week = date.strftime("%Y-W%W")
        week_buckets[week]["total"] += 1
        if _ever_ac(ss):
            week_buckets[week]["ac"] += 1

    # 按时间排序
    sorted_weeks = sorted(week_buckets.keys())
    if len(sorted_weeks) < config.trend_min_weeks:
        return None

    # 构建 (x=周序号, y=当周AC率) 数据点
    points = []
    for i, w in enumerate(sorted_weeks):
        total = week_buckets[w]["total"]
        ac = week_buckets[w]["ac"]
        points.append((float(i), ac / total if total else 0))

    # 最小二乘法线性回归: y = slope * x + intercept
    n = len(points)
    sum_x = sum(p[0] for p in points)
    sum_y = sum(p[1] for p in points)
    sum_xy = sum(p[0] * p[1] for p in points)
    sum_x2 = sum(p[0] * p[0] for p in points)

    denominator = n * sum_x2 - sum_x * sum_x
    if denominator == 0:
        return None

    slope = (n * sum_xy - sum_x * sum_y) / denominator
    return slope


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    if n % 2:
        return s[n // 2]
    return (s[n // 2 - 1] + s[n // 2]) / 2
