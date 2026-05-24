"""分析引擎配置 — 所有阈值集中管理，支持构造时覆盖。"""
from dataclasses import dataclass, field


@dataclass
class AnalysisConfig:
    """薄弱点分析的可配置阈值。

    所有阈值都可以在构造时覆盖，例如:
        config = AnalysisConfig(alpha=0.25, gamma=4.0)
    """

    # ── 规则1: 通过率策略 ──
    alpha: float = 0.3
    """通过率阈值。标签通过率 < alpha 时判定为薄弱。"""
    min_problems_for_analysis: int = 3
    """最少题目数。标签下题目数不足时不参与分析。"""
    difficulty_weighted: bool = True
    """是否启用难度加权。基础题错扣更多分，使得真正简单题错更凸显薄弱。"""

    # ── 规则2: 时间效率策略 ──
    gamma: float = 3.0
    """平均尝试次数阈值。标签下每题平均提交次数 > gamma 时判定为低效。"""
    beta: float = 1.5
    """耗时倍数阈值。标签平均耗时 > beta × 全局中位数时判定为低效。"""
    submission_overhead_minutes: int = 5
    """每题基础思考+编码时间（分钟），从总耗时中扣除后再比较。"""

    # ── 规则3: 学习趋势策略 ──
    trend_ratio_threshold: float = 0.8
    """前后半区正确率比值阈值。后半区/前半区 < 此值时判定为下降趋势。"""
    trend_slope_threshold: float = 0.05
    """线性回归斜率阈值。周正确率斜率 < 此值时判定为无进步。"""
    trend_min_weeks: int = 4
    """线性回归最少周数。不足时不计算斜率。"""
