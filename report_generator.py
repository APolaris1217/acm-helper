"""周报生成器 — 填充 requirement.rm 模板"""
import json
import os
from datetime import datetime
from collections import defaultdict
from tag_map import cn_tag

TEMPLATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "requirement.rm")


def load_template() -> str:
    if os.path.exists(TEMPLATE_FILE):
        with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
            return f.read()
    raise FileNotFoundError(f"模板文件不存在: {TEMPLATE_FILE}")


def generate_report(
    target: str,
    from_date: str,
    to_date: str,
    submissions: list[dict],
) -> str:
    """基于提交数据生成周报 Markdown

    Args:
        target: 分析对象名（如 "Codeforces: tourist"）
        from_date: 周期起始日 "2024-01-08"
        to_date: 周期结束日 "2024-01-14"
        submissions: 统一格式的提交记录列表

    Returns:
        完整的 Markdown 报告
    """
    template = load_template()

    # ---- 数据聚合 ----
    ac_subs = [s for s in submissions if s.get("result") == "AC"]
    all_dates = sorted(set(s.get("date", "")[:10] for s in submissions if s.get("date")))
    unique_ac = {}
    for s in ac_subs:
        pid = s.get("problemId", "")
        if pid not in unique_ac:
            unique_ac[pid] = s

    # 做题量时序（按日聚合）
    daily_counts = defaultdict(lambda: {"total": 0, "ac": 0})
    for s in submissions:
        d = (s.get("date") or "")[:10]
        if d:
            daily_counts[d]["total"] += 1
            if s.get("result") == "AC":
                daily_counts[d]["ac"] += 1

    # 专题统计
    tag_stats = defaultdict(lambda: {"total": 0, "ac": 0, "difficulties": []})
    for s in submissions:
        for tag in s.get("tags", []):
            tag = tag.lower()
            tag_stats[tag]["total"] += 1
            if s.get("result") == "AC":
                tag_stats[tag]["ac"] += 1
            if s.get("difficulty"):
                tag_stats[tag]["difficulties"].append(s["difficulty"])

    # 反思提取（如果有 reflection 字段）

    # ---- 填充模板 ----
    stats_points = []
    for d in sorted(daily_counts.keys()):
        stats_points.append({"date": d, **daily_counts[d]})

    problem_list = []
    for s in submissions[:200]:  # 最多 200 条明细
        problem_list.append({
            "pid": s.get("problemId", ""),
            "title": s.get("name", ""),
            "difficulty": s.get("difficulty", 0),
            "tags": s.get("tags", []),
            "result": s.get("result", ""),
            "date": (s.get("date") or "")[:10],
            "reflection": s.get("reflection", ""),
        })

    report = template
    report = report.replace("{{target}}", target)
    period_text = f"{from_date} 至 {to_date}"
    report = report.replace("{{period}}", period_text)
    report = report.replace("{{from_date}}", from_date)
    report = report.replace("{{to_date}}", to_date)
    report = report.replace("{{stats_points_json}}", json.dumps(stats_points, ensure_ascii=False, indent=2))
    report = report.replace("{{problem_list_json}}", json.dumps(problem_list, ensure_ascii=False, indent=2))

    # ---- 生成分析内容 ----
    # 1. 数据概览
    total_subs = len(submissions)
    total_ac = len(ac_subs)
    unique_ac_count = len(unique_ac)
    active_days = len(daily_counts)
    report += f"""

---
## 自动分析结果

### 1. 数据概览与趋势诊断

| 指标 | 数值 |
|------|------|
| 总提交数 | {total_subs} |
| AC 提交数 | {total_ac} |
| 通过率 | {round(total_ac/total_subs*100,1) if total_subs else 0}% |
| 去重 AC 题数 | {unique_ac_count} |
| 活跃天数 | {active_days} |
| 日均 AC | {round(total_ac/max(1,active_days), 1)} |

"""

    # 每日趋势
    if daily_counts:
        report += "**每日提交趋势：**\n\n"
        report += "| 日期 | 总提交 | AC |\n|------|--------|-----|\n"
        for d in sorted(daily_counts.keys()):
            dc = daily_counts[d]
            report += f"| {d} | {dc['total']} | {dc['ac']} |\n"

    # 2. 专题掌握度
    report += "\n### 2. 专题掌握度分析\n\n"
    report += "| 专题 | 提交数 | AC 率 | 平均难度 | 掌握评估 |\n|------|--------|-------|----------|----------|\n"

    for tag, stats in sorted(tag_stats.items(), key=lambda x: x[1]["total"], reverse=True)[:15]:
        ac_rate = round(stats["ac"] / stats["total"] * 100, 1) if stats["total"] else 0
        avg_diff = round(sum(stats["difficulties"]) / len(stats["difficulties"])) if stats["difficulties"] else 0

        if ac_rate >= 80 and stats["total"] >= 5:
            level = "稳定掌握"
        elif ac_rate >= 60:
            level = "突破中"
        elif stats["total"] >= 3:
            level = "系统性短板"
        else:
            level = "数据不足"

        report += f"| {cn_tag(tag)} | {stats['total']} | {ac_rate}% | {avg_diff} | {level} |\n"

    # 3. 反思综合
    report += "\n### 3. 反思内容综合\n\n"
    reflections = [s.get("reflection", "") for s in submissions if s.get("reflection")]
    if reflections:
        report += "训练者反思记录：\n\n"
        for r in reflections[:10]:
            report += f"- {r[:200]}\n"
    else:
        report += "> 本周期内无反思记录。建议每道 AC 题后补充简短反思，以便持续跟踪思维盲区。\n"

    # 4. 行动建议
    report += "\n### 4. 下阶段行动建议\n\n"

    weak_tags = [(tag, s) for tag, s in tag_stats.items()
                 if s["total"] >= 3 and (s["ac"] / s["total"]) < 0.6]
    weak_tags.sort(key=lambda x: x[1]["ac"] / max(1, x[1]["total"]))

    if weak_tags:
        report += "**优先强化专题：**\n\n"
        for tag, stats in weak_tags[:5]:
            ac_rate = round(stats["ac"] / stats["total"] * 100, 1)
            tcn = cn_tag(tag)
            report += f"- **{tcn}**：AC 率仅 {ac_rate}%，{stats['total']} 次提交中仅 {stats['ac']} 次通过。建议在对应 OJ 平台按 {tcn} 标签筛选中等难度题专项练习。\n"

    report += f"\n**每日训练节奏建议：**\n- 保持每日 {max(2, round(unique_ac_count / max(1, active_days)))} 道 AC 题目的节奏\n"
    report += "- 每道题提交前本地测试边界样例，减少 WA 次数\n"
    report += "- AC 后写简短反思（1-2 句），记录卡点和关键 insight\n"

    report += f"\n\n---\n*报告由 ACM Helper 自动生成于 {datetime.now().strftime('%Y-%m-%d %H:%M')}*"

    return report
