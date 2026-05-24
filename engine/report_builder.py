"""分析报告生成器 — 整合指标、薄弱点、建议，输出结构化报告。"""
from tag_map import cn_tag

from engine.config import AnalysisConfig
from engine.metrics import MetricsCalculator
from engine.analyzer import WeaknessAnalyzer


class ReportBuilder:
    """结构化分析报告生成器。

    用法:
        builder = ReportBuilder()
        report = builder.build(submissions, config, total_tag_count=50)
    """

    def build(
        self,
        submissions: list[dict],
        config: AnalysisConfig | None = None,
        total_tag_count: int | None = None,
    ) -> dict:
        """生成完整的分析报告数据对象。

        Returns:
            { summary, metrics, weaknesses, recommendations, unstarted_tags }
        """
        if config is None:
            config = AnalysisConfig()

        # 1. 行为指标
        metrics = MetricsCalculator.calculate(submissions, total_tag_count)

        # 2. 薄弱点分析
        analyzer = WeaknessAnalyzer()
        weaknesses, tag_stats = analyzer.analyze(submissions, config)

        # 3. 优势标签 (通过率 >= 70% 且题目数 >= 3)
        strengths = [
            {"tag": cn_tag(t), "tag_raw": t, "rate": s["rate"], "total": s["total"]}
            for t, s in tag_stats.items()
            if s["ac"] > 0 and s["rate"] >= 0.7 and s["total"] >= 3
        ]
        strengths.sort(key=lambda x: x["rate"], reverse=True)

        # 4. 未入门标签（通过率=0）
        unstarted = [
            {"tag": cn_tag(t), "tag_raw": t, "total": s["total"]}
            for t, s in tag_stats.items()
            if s["ac"] == 0 and s["total"] >= 1
        ]
        unstarted.sort(key=lambda x: x["total"], reverse=True)

        # 5. 摘要
        summary = self._build_summary(metrics, weaknesses, strengths)

        # 6. 建议
        recommendations = self._build_recommendations(
            weaknesses, tag_stats, unstarted, config
        )

        # 转换 weaknesses 为前端格式
        weaknesses_data = []
        for w in weaknesses:
            wdata = {
                "tag": cn_tag(w.tag),
                "tag_raw": w.tag,
                "triggered_rules": w.triggered_rules,
                "pass_rate_detail": w.pass_rate_detail,
                "efficiency_detail": w.efficiency_detail,
                "trend_detail": w.trend_detail,
                "stats": tag_stats.get(w.tag, {}),
            }
            weaknesses_data.append(wdata)

        return {
            "summary": summary,
            "metrics": metrics,
            "weaknesses": weaknesses_data,
            "strengths": strengths,
            "unstarted_tags": unstarted,
            "recommendations": recommendations,
            "tag_stats": {cn_tag(t): s for t, s in tag_stats.items()},
        }

    def _build_summary(self, metrics, weaknesses, strengths) -> dict:
        lines = []
        lines.append(
            f"共分析 {metrics['total_problems']} 道题目、{metrics['total_submissions']} 次提交，"
            f"总体通过率 {metrics['pass_rate']:.1%}。"
        )

        if strengths:
            top3 = strengths[:3]
            names = ", ".join(s["tag"] for s in top3)
            lines.append(f"优势标签：{names} 掌握良好。")

        if weaknesses:
            lines.append(
                f"识别出 {len(weaknesses)} 个薄弱知识点："
                + "、".join(cn_tag(w.tag) for w in weaknesses[:5])
                + ("..." if len(weaknesses) > 5 else "")
            )
        else:
            lines.append("未识别出明显薄弱知识点。")

        strengths_text = (
            f"优势（top-{min(3, len(strengths))}）: "
            + "、".join(
                f"{s['tag']}({s['rate']:.0%})" for s in strengths[:3]
            )
            if strengths
            else "暂无显著优势标签"
        )

        weaknesses_text = (
            f"薄弱（{len(weaknesses)}个）: "
            + "、".join(cn_tag(w.tag) for w in weaknesses[:5])
            if weaknesses
            else "无明显薄弱点"
        )

        return {
            "overview": " ".join(lines),
            "strengths_summary": strengths_text,
            "weaknesses_summary": weaknesses_text,
            "total_problems": metrics["total_problems"],
            "total_submissions": metrics["total_submissions"],
            "ac_count": metrics["ac_problems"],
        }

    def _build_recommendations(
        self, weaknesses, tag_stats, unstarted, config
    ) -> list[dict]:
        recs = []

        for w in weaknesses:
            raw_tag = w.tag
            stats = tag_stats.get(raw_tag, {})
            avg_diff = stats.get("avg_difficulty", 0)
            advice = []
            priority = "medium"

            # 通过率低 → 区分基础题/高难度题
            if "pass_rate" in w.triggered_rules:
                if avg_diff <= 1600:
                    advice.append(
                        "该知识点基础题通过率低，建议回归教材/入门题，巩固基础概念和模板。"
                    )
                    priority = "high"
                else:
                    advice.append(
                        "该知识点高难度题通过率低，建议先刷中等难度题建立信心，再挑战难题。"
                    )
                    priority = "medium"

            # 效率低 → 耗时/尝试多
            if "efficiency" in w.triggered_rules:
                detail = w.efficiency_detail or {}
                if detail.get("avg_attempts", 0) > config.gamma:
                    advice.append(
                        f"每题平均尝试 {detail['avg_attempts']} 次（阈值 {config.gamma}），"
                        "习惯'提交→WA→改→提交'循环。建议减少盲目提交，先本地自测边界情况。"
                    )
                if detail.get("avg_time_minutes", 0) > 0:
                    advice.append(
                        f"每题平均耗时 {detail['avg_time_minutes']:.0f} 分钟，"
                        "解题思路不够清晰。建议先设计算法再编码，遇到死磕先暂停回顾同类题型。"
                    )
                priority = "high" if not advice else priority

            # 趋势下降
            if "trend" in w.triggered_rules:
                td = w.trend_detail or {}
                ratio = td.get("ratio")
                slope = td.get("slope")
                if ratio is not None and ratio < config.trend_ratio_threshold:
                    advice.append(
                        f"后期正确率显著下降（比值 {ratio:.2f} < {config.trend_ratio_threshold}），"
                        "可能存在遗忘或知识点混淆，建议每周做该知识点复习题。"
                    )
                if slope is not None and slope < config.trend_slope_threshold:
                    advice.append(
                        f"学习曲线近乎平坦（斜率 {slope:.4f} < {config.trend_slope_threshold}），"
                        "陷入瓶颈期。建议更换学习材料或寻求题解思路启发。"
                    )
                priority = "high"

            if not advice:
                advice.append("多做该知识点的中等难度题，保持手感。")

            recs.append({
                "tag": cn_tag(raw_tag),
                "tag_raw": raw_tag,
                "priority": priority,
                "advice": advice,
            })

        # 未入门标签的建议
        for u in unstarted[:5]:
            recs.append({
                "tag": u["tag"],
                "tag_raw": u["tag_raw"],
                "priority": "info",
                "advice": [
                    f"该知识点 {u['total']} 题从未 AC，属于尚未掌握领域。"
                    "建议从入门题开始，先理解核心概念和基础模板。"
                ],
            })

        recs.sort(
            key=lambda r: {"high": 0, "medium": 1, "low": 2, "info": 3}[r["priority"]]
        )
        return recs
