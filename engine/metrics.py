"""行为指标计算器 — 输入全部提交记录，输出 7 项标准化指标。"""
from collections import defaultdict
from engine.config import AnalysisConfig


class MetricsCalculator:
    """计算用户行为指标（与具体标签无关，全局统计）。"""

    @staticmethod
    def calculate(submissions: list[dict], total_tag_count: int | None = None) -> dict:
        """计算所有行为指标。

        Args:
            submissions: 统一格式的提交记录列表 [{platform, problemId, result, date, tags, ...}]
            total_tag_count: 平台总标签库数量。传入 None 则用用户标签数代替。

        Returns:
            dict with keys: pass_rate, avg_attempts, give_up_rate, regression_rate,
                            one_shot_ac_rate, tag_coverage, result_distribution
        """
        if not submissions:
            return _empty_metrics()

        groups = _group_by_problem(submissions)

        total_problems = len(groups)
        total_subs = len(submissions)

        # AC 题目数
        ac_problems = sum(1 for _, ss in groups.items() if _ever_ac(ss))

        # 总提交次数 / 尝试题目数
        avg_attempts = round(total_subs / total_problems, 2) if total_problems else 0

        # 放弃率: 尝试过但从未AC的题目 / 总尝试题目
        given_up = sum(1 for _, ss in groups.items() if not _ever_ac(ss))
        give_up_rate = round(given_up / total_problems, 4) if total_problems else 0

        # 回归率: (提交>1且最终AC的题目) / 总AC的题目
        regressed = sum(1 for _, ss in groups.items() if len(ss) > 1 and _ever_ac(ss))
        regression_rate = round(regressed / ac_problems, 4) if ac_problems else 0

        # 一发入魂: 仅1次提交就AC / 总尝试题目
        one_shot = sum(1 for _, ss in groups.items() if len(ss) == 1 and _ever_ac(ss))
        one_shot_ac_rate = round(one_shot / total_problems, 4) if total_problems else 0

        # 标签覆盖度: 用户做过的标签 / 总标签库
        user_tags = set()
        for s in submissions:
            for t in s.get("tags", []) or []:
                user_tags.add(t.lower())
        total_tags = total_tag_count or max(len(user_tags), 1)
        tag_coverage = round(len(user_tags) / total_tags, 4)

        # 结果分布
        result_dist = {"AC": 0, "WA": 0, "TLE": 0, "RE": 0, "CE": 0, "MLE": 0, "unsolved": 0}
        for s in submissions:
            r = s.get("result", "unsolved") or "unsolved"
            if r in result_dist:
                result_dist[r] += 1
            else:
                result_dist["unsolved"] += 1

        return {
            "pass_rate": round(ac_problems / total_problems, 4) if total_problems else 0,
            "avg_attempts": avg_attempts,
            "give_up_rate": give_up_rate,
            "regression_rate": regression_rate,
            "one_shot_ac_rate": one_shot_ac_rate,
            "tag_coverage": tag_coverage,
            "user_tag_count": len(user_tags),
            "total_tag_count": total_tags,
            "result_distribution": result_dist,
            "total_problems": total_problems,
            "total_submissions": total_subs,
            "ac_problems": ac_problems,
        }


def _group_by_problem(submissions):
    """按 (platform, problemId) 分组，保留原始顺序。"""
    groups = defaultdict(list)
    for s in submissions:
        key = (s.get("platform", ""), s.get("problemId", ""))
        groups[key].append(s)
    return dict(groups)


def _ever_ac(ss):
    return any(s.get("result") == "AC" for s in ss)


def _empty_metrics():
    return {
        "pass_rate": 0, "avg_attempts": 0, "give_up_rate": 0,
        "regression_rate": 0, "one_shot_ac_rate": 0,
        "tag_coverage": 0, "user_tag_count": 0, "total_tag_count": 0,
        "result_distribution": {},
        "total_problems": 0, "total_submissions": 0, "ac_problems": 0,
    }
