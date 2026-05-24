"""薄弱点分析器 — 编排三套判定策略，输出薄弱标签列表。"""
from collections import defaultdict

from engine.config import AnalysisConfig
from engine.strategies import (
    PassRateStrategy,
    EfficiencyStrategy,
    TrendStrategy,
    WeaknessResult,
    _group_by_problem,
    _ever_ac,
)


class WeaknessAnalyzer:
    """薄弱点判定编排器。

    用法:
        analyzer = WeaknessAnalyzer()
        weaknesses = analyzer.analyze(submissions, config)
    """

    def __init__(self):
        self._strategies = [
            PassRateStrategy(),
            EfficiencyStrategy(),
            TrendStrategy(),
        ]

    def analyze(
        self,
        submissions: list[dict],
        config: AnalysisConfig | None = None,
    ) -> tuple[list[WeaknessResult], dict[str, dict]]:
        """分析所有标签的薄弱情况。

        Args:
            submissions: 统一格式的提交记录列表
            config: 分析配置，None 使用默认值

        Returns:
            (weaknesses, tag_stats):
              weaknesses — 被判定为薄弱的标签列表
              tag_stats — 所有标签的统计信息 {tag: {total, ac, rate, ...}}
        """
        if config is None:
            config = AnalysisConfig()

        tag_groups = self._group_by_tag(submissions)
        tag_stats = self._compute_tag_stats(tag_groups, submissions, config)

        weaknesses: list[WeaknessResult] = []

        for tag, stats in tag_stats.items():
            # 通过率为 0 的标签不参与薄弱判定（未入门 ≠ 薄弱）
            if stats["ac"] == 0:
                continue

            if stats["total"] < config.min_problems_for_analysis:
                continue

            tag_subs = tag_groups[tag]

            for strategy in self._strategies:
                result = strategy.detect(tag, tag_subs, submissions, config)
                if result is not None:
                    self._merge_result(weaknesses, result)

        # 按触发规则数降序排列（触发的规则越多越薄弱）
        weaknesses.sort(key=lambda w: len(w.triggered_rules), reverse=True)

        return weaknesses, tag_stats

    def _group_by_tag(self, submissions: list[dict]) -> dict[str, list[dict]]:
        groups = defaultdict(list)
        for s in submissions:
            for tag in s.get("tags", []) or []:
                tag = tag.lower()
                if tag == "*special":
                    continue
                groups[tag].append(s)
        return dict(groups)

    def _compute_tag_stats(
        self,
        tag_groups: dict[str, list[dict]],
        submissions: list[dict],
        config: AnalysisConfig,
    ) -> dict[str, dict]:
        stats = {}
        for tag, ss in tag_groups.items():
            groups = _group_by_problem(ss)
            total = len(groups)
            ac = sum(1 for _, ps in groups.items() if _ever_ac(ps))
            rate = ac / total if total else 0

            diffs = []
            for _, ps in groups.items():
                d = ps[0].get("difficulty", 0)
                if d:
                    diffs.append(d)

            stats[tag] = {
                "tag": tag,
                "total": total,
                "ac": ac,
                "rate": round(rate, 4),
                "avg_difficulty": round(sum(diffs) / len(diffs)) if diffs else 0,
                "attempts": len(ss),
                "avg_attempts": round(len(ss) / total, 2) if total else 0,
            }
        return stats

    def _merge_result(
        self,
        weaknesses: list[WeaknessResult],
        new_result: WeaknessResult,
    ):
        """如果同标签被多策略触发，合并 triggered_rules 和 detail。"""
        for w in weaknesses:
            if w.tag == new_result.tag:
                w.triggered_rules.extend(new_result.triggered_rules)
                if new_result.pass_rate_detail:
                    w.pass_rate_detail = new_result.pass_rate_detail
                if new_result.efficiency_detail:
                    w.efficiency_detail = new_result.efficiency_detail
                if new_result.trend_detail:
                    w.trend_detail = new_result.trend_detail
                return
        weaknesses.append(new_result)
