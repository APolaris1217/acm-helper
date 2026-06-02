"""薄弱知识点 Top5 评分模块

基于多维度加权评分 + 样本量修正，找出用户最薄弱的 5 个知识点。

评分维度:
  - AC率 (权重 0.40): 越低越薄弱
  - 尝试次数 (权重 0.20): 越多越薄弱
  - 耗时 (权重 0.15): 越长越薄弱
  - 后半区失衡 (权重 0.15): 前后半区正确率差距越大越薄弱
  - 学习斜率 (权重 0.10): 越平/越负越薄弱

所有连续型指标先 Min-Max 归一化到 0~100 再加权。
最终分数乘以样本量修正因子 min(1, problemCount/20)。
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime, timedelta


@dataclass
class KnowledgePoint:
    """单个知识点的统计数据"""
    id: str
    name: str
    problem_count: int = 0
    ac_rate: float = 0.0
    avg_attempts: float = 0.0
    avg_time_minutes: float = 0.0
    first_half_accuracy: float = 0.0
    second_half_accuracy: float = 0.0
    learning_slope: float = 0.0


@dataclass
class WeaknessResult:
    """薄弱分析结果"""
    id: str
    name: str
    score: float
    level: str  # "严重薄弱" | "需要加强" | "一般" | "掌握较好"
    reasons: list[str] = field(default_factory=list)
    # Detailed scores for frontend display
    ac_rate: float = 0.0
    ac_rate_pct: int = 0
    problem_count: int = 0
    avg_attempts: float = 0.0
    rule_count: int = 0


def _safe_div(a: float, b: float, default: float = 0.0) -> float:
    """安全除法，避免除零"""
    return a / b if b != 0 else default


def _min_max_normalize(values: list[float]) -> list[float]:
    """Min-Max 归一化到 0~100，避免除零。所有值相同时返回全 0。"""
    if not values:
        return []
    vmin, vmax = min(values), max(values)
    if vmax == vmin:
        return [0.0] * len(values)
    return [(v - vmin) / (vmax - vmin) * 100 for v in values]


def _compute_week_key(d: datetime) -> str:
    """返回 ISO 周键，如 '2026-W22'"""
    return f"{d.year}-W{d.isocalendar()[1]:02d}"


def compute_knowledge_points(submissions: list[dict]) -> list[KnowledgePoint]:
    """从原始提交数据聚合计知识点统计数据。

    Args:
        submissions: 统一格式的提交列表，每项需包含:
            problemId, result, tags, submitTime, date

    Returns:
        KnowledgePoint 列表
    """
    if not submissions:
        return []

    # 1. 确定全局时间范围（用于前后半区划分）
    dates = []
    for s in submissions:
        d = s.get("date", "") or (s.get("submitTime", "")[:10] if s.get("submitTime") else "")
        if d:
            try:
                dates.append(datetime.strptime(d, "%Y-%m-%d"))
            except ValueError:
                pass
    if not dates:
        return []

    dates.sort()
    mid_date = dates[len(dates) // 2]  # 中位数日期作为前后半分界

    # 2. 按标签分组
    tag_problems: dict[str, set] = {}       # tag -> set of problem_id
    tag_results: dict[str, list[str]] = {}  # tag -> list of result
    tag_attempts: dict[str, list[int]] = {} # tag -> list of attempt_count per problem
    tag_times: dict[str, list[float]] = {}  # tag -> list of time_spent per problem (minutes)
    tag_first_results: dict[str, list[str]] = {}  # first half
    tag_second_results: dict[str, list[str]] = {} # second half
    tag_week_ac: dict[str, dict[str, list[int]]] = {}  # tag -> week_key -> [1/0 for AC]

    # Per-problem tracking for attempt counting
    problem_info: dict[str, dict] = {}  # (tag, problem_id) -> {results, times, date}

    for s in submissions:
        tags = s.get("tags", []) or []
        pid = s.get("problemId", "")
        result = s.get("result", "")
        d_str = s.get("date", "") or (s.get("submitTime", "")[:10] if s.get("submitTime") else "")

        for t in tags:
            t = str(t).strip()
            if not t or t == "*special":
                continue

            key = (t, pid)
            if key not in problem_info:
                problem_info[key] = {"results": [], "times": [], "date": d_str}
            info = problem_info[key]
            info["results"].append(result)

            # Collect per-tag weekly AC data
            if d_str:
                try:
                    dt = datetime.strptime(d_str, "%Y-%m-%d")
                    wk = _compute_week_key(dt)
                    if t not in tag_week_ac:
                        tag_week_ac[t] = {}
                    if wk not in tag_week_ac[t]:
                        tag_week_ac[t][wk] = []
                    tag_week_ac[t][wk].append(1 if result == "AC" else 0)

                    # First/second half split
                    if dt <= mid_date:
                        if t not in tag_first_results:
                            tag_first_results[t] = []
                        tag_first_results[t].append(result)
                    else:
                        if t not in tag_second_results:
                            tag_second_results[t] = []
                        tag_second_results[t].append(result)
                except ValueError:
                    pass

            if t not in tag_problems:
                tag_problems[t] = set()
            tag_problems[t].add(pid)

    # 3. Aggregate per-tag per-problem data
    tag_attempt_counts: dict[str, list[int]] = {}
    tag_time_list: dict[str, list[float]] = {}
    for (t, pid), info in problem_info.items():
        if t not in tag_attempt_counts:
            tag_attempt_counts[t] = []
        if t not in tag_time_list:
            tag_time_list[t] = []
        tag_attempt_counts[t].append(len(info["results"]))
        # time estimation is approximate; we set 0 if no data
        tag_time_list[t].append(0.0)

    # 4. Build KnowledgePoint list
    points: list[KnowledgePoint] = []
    for tag, problems in tag_problems.items():
        problem_count = len(problems)
        if problem_count == 0:
            continue

        # Total attempts across all problems of this tag
        attempts = tag_attempt_counts.get(tag, [])
        total_attempts = sum(attempts) if attempts else 0

        # AC rate
        ac_count = sum(1 for a in attempts if a > 0) if attempts else 0
        ac_rate = _safe_div(ac_count, total_attempts) if total_attempts > 0 else 0.0

        # Average attempts per problem
        avg_attempts = _safe_div(total_attempts, problem_count)

        # Average time (not reliably available, set 0)
        times = tag_time_list.get(tag, [])
        avg_time = sum(times) / len(times) if times else 0.0

        # First/second half accuracy
        first_results = tag_first_results.get(tag, [])
        second_results = tag_second_results.get(tag, [])
        first_ac = sum(1 for r in first_results if r == "AC") if first_results else 0
        second_ac = sum(1 for r in second_results if r == "AC") if second_results else 0
        first_half_acc = _safe_div(first_ac, len(first_results))
        second_half_acc = _safe_div(second_ac, len(second_results))

        # Learning slope: linear regression on weekly AC rates
        weekly_data = tag_week_ac.get(tag, {})
        slope = _compute_learning_slope(weekly_data)

        points.append(KnowledgePoint(
            id=tag,
            name=tag,  # Will be mapped to Chinese name later
            problem_count=problem_count,
            ac_rate=ac_rate,
            avg_attempts=avg_attempts,
            avg_time_minutes=avg_time,
            first_half_accuracy=first_half_acc,
            second_half_accuracy=second_half_acc,
            learning_slope=slope,
        ))

    return points


def _compute_learning_slope(weekly_data: dict[str, list[int]]) -> float:
    """从每周 AC 数据计算学习斜率（线性回归）。

    Args:
        weekly_data: {week_key: [0,1,0,1,...]}  0=非AC, 1=AC

    Returns:
        斜率 (正值=进步, 负值=退步, 0=不变)
    """
    if not weekly_data:
        return 0.0

    # Convert to sorted (week_index, ac_rate) pairs
    weeks = sorted(weekly_data.keys())
    if len(weeks) < 2:
        return 0.0

    points = []
    for i, wk in enumerate(weeks):
        vals = weekly_data[wk]
        if vals:
            points.append((float(i), sum(vals) / len(vals)))

    if len(points) < 2:
        return 0.0

    n = len(points)
    sum_x = sum(p[0] for p in points)
    sum_y = sum(p[1] for p in points)
    sum_xy = sum(p[0] * p[1] for p in points)
    sum_x2 = sum(p[0] ** 2 for p in points)

    denom = n * sum_x2 - sum_x ** 2
    if denom == 0:
        return 0.0

    return (n * sum_xy - sum_x * sum_y) / denom


def calculate_weakness_top5(points: list[KnowledgePoint]) -> list[WeaknessResult]:
    """计算薄弱知识点 Top5。

    综合 5 个维度评分，样本量修正，过滤题目数 < 5 的知识点。

    Args:
        points: KnowledgePoint 列表

    Returns:
        排序后的 Top5 WeaknessResult 列表
    """
    if not points:
        return []

    # Filter: problemCount >= 5
    filtered = [p for p in points if p.problem_count >= 5]
    if not filtered:
        return []

    n = len(filtered)

    # Extract raw values
    ac_rates = [p.ac_rate for p in filtered]
    attempts = [p.avg_attempts for p in filtered]
    times = [p.avg_time_minutes for p in filtered]
    gaps = [max(0.0, p.first_half_accuracy - p.second_half_accuracy) for p in filtered]
    slopes = [p.learning_slope for p in filtered]

    # Min-Max normalization (higher = worse for attempts, times, gaps; lower = worse for ac_rate, slope)
    norm_attempts = _min_max_normalize(attempts)
    norm_times = _min_max_normalize(times)
    norm_gaps = _min_max_normalize(gaps)

    # For AC rate: lower is worse, so we use (1 - acRate) directly (already 0~100)
    ac_scores = [(1.0 - r) * 100 for r in ac_rates]

    # For learning slope: higher (more positive) is better
    # Normalize slope to 0~100 then invert
    norm_slopes_raw = _min_max_normalize(slopes)
    learning_scores = [100.0 - s for s in norm_slopes_raw]

    # Weighted score
    results: list[WeaknessResult] = []
    for i, p in enumerate(filtered):
        raw_score = (
            0.40 * ac_scores[i] +
            0.20 * norm_attempts[i] +
            0.15 * norm_times[i] +
            0.15 * norm_gaps[i] +
            0.10 * learning_scores[i]
        )

        # Confidence correction
        confidence = min(1.0, p.problem_count / 20.0)
        final_score = raw_score * confidence

        # Determine level
        if final_score >= 60:
            level = "严重薄弱"
        elif final_score >= 35:
            level = "需要加强"
        elif final_score >= 15:
            level = "一般"
        else:
            level = "掌握较好"

        # Generate reasons (up to 3)
        reasons = _generate_reasons(
            ac_scores[i], norm_attempts[i], norm_times[i],
            gaps[i], slopes[i], p.problem_count
        )

        results.append(WeaknessResult(
            id=p.id,
            name=p.name,
            score=round(final_score, 2),
            level=level,
            reasons=reasons,
            ac_rate=p.ac_rate,
            ac_rate_pct=round(p.ac_rate * 100),
            problem_count=p.problem_count,
            avg_attempts=p.avg_attempts,
            rule_count=len(reasons),
        ))

    # Sort by score descending, stable sort
    results.sort(key=lambda r: r.score, reverse=True)
    return results[:5]


def _generate_reasons(
    ac_score: float,
    attempt_score: float,
    time_score: float,
    gap: float,
    slope: float,
    problem_count: int,
) -> list[str]:
    """根据各维度得分生成最多 3 个薄弱原因。

    判断阈值:
      - AC率得分 > 30  → AC率明显偏低
      - 尝试得分 > 30  → 平均尝试次数较高
      - 耗时得分 > 30  → 解题耗时较长 (time_score may be 0 if no data)
      - gap > 0.1      → 经常卡在后半部分
      - slope < -0.01   → 近期进步较慢
    """
    candidates: list[tuple[float, str]] = []

    if ac_score > 30:
        candidates.append((ac_score, "AC率明显偏低"))
    if attempt_score > 30:
        candidates.append((attempt_score, "平均尝试次数较高"))
    if time_score > 30 and time_score > 0:
        candidates.append((time_score, "解题耗时较长"))
    if gap > 0.1:
        candidates.append((gap * 100, "经常卡在后半部分"))
    if slope < -0.01:
        candidates.append((abs(slope) * 1000, "近期进步较慢"))

    # Sort by severity, take top 3
    candidates.sort(key=lambda x: x[0], reverse=True)
    reasons = [c[1] for c in candidates[:3]]

    # If no reasons triggered, provide a fallback
    if not reasons:
        if problem_count < 10:
            reasons.append("做题量较少，数据仅供参考")
        else:
            reasons.append("各维度表现均衡，可针对性强化")

    return reasons
