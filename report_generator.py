"""周报生成器 — 填充 requirement.rm 模板并调用 DeepSeek 生成分析报告"""
import json
import os
import re
import requests
from datetime import datetime
from collections import defaultdict
from tag_map import cn_tag

TEMPLATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "requirement.rm")
REFLECTION_PATTERNS = [
    (r"(思路|不会|没想到|想不到|没想|想不出|无从下手|不知如何|卡|懵逼|蒙|无思路|没有思路|没思路|不会做)", "思路卡点"),
    (r"(细节|粗心|漏|边界|特判|corner|越界|下标|空指针|null|初始化|忘记|忘了|写错|打错|笔误)", "实现细节与边界遗漏"),
    (r"(TLE|超时|tle|timeout|复杂|暴力|优化|效率|常数|剪枝|预处理)", "TLE/复杂度与优化"),
    (r"(RE|运行时|runtime|段错误|segmentation|数组|溢出|栈|递归|递归深度)", "运行时错误"),
    (r"(WA|错误|错|不对|wrong|答案|精度|浮点|小数|四舍五入|取模|模|mod)", "逻辑与答案错误"),
    (r"(看题解|题解|参考|抄|借鉴|搜|查|百度|google|gpt|ai)", "依赖题解/外部参考"),
    (r"(调|debug|调试|print|输出|打印|gdb|断点)", "调试困难"),
]


def load_template() -> str:
    if os.path.exists(TEMPLATE_FILE):
        with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
            return f.read()
    raise FileNotFoundError(f"模板文件不存在: {TEMPLATE_FILE}")


def _get_api_key() -> str:
    cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "email_config.json")
    if os.path.exists(cfg_path):
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            return cfg.get("deepseek_api_key", "")
    return ""


def _call_deepseek(prompt: str, api_key: str) -> str | None:
    """调用 DeepSeek API 生成报告。失败返回 None。"""
    try:
        resp = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 4096,
            },
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=120,
        )
        data = resp.json()
        if "error" in data:
            print(f"  [REPORT] DeepSeek API 错误: {data['error']}")
            return None
        content = data["choices"][0]["message"]["content"]
        return content
    except Exception as e:
        print(f"  [REPORT] DeepSeek 调用失败: {e}")
        return None


def _analyze_reflections(submissions: list[dict]) -> dict:
    """分析反思内容，归类困难模式。"""
    reflections = [s.get("reflection", "") for s in submissions if s.get("reflection", "").strip()]
    if not reflections:
        return {"total": 0, "categories": [], "patterns": [], "summary": ""}

    categories = defaultdict(list)
    for r in reflections:
        matched = False
        for pattern, cat in REFLECTION_PATTERNS:
            if re.search(pattern, r, re.IGNORECASE):
                categories[cat].append(r)
                matched = True
                break
        if not matched:
            categories["其他/未分类"].append(r)

    # 按出现频率排序
    sorted_cats = sorted(categories.items(), key=lambda x: len(x[1]), reverse=True)

    # 找出重复出现≥3次的类别 → 模式性问题
    patterns = []
    for cat, items in sorted_cats:
        if len(items) >= 3:
            patterns.append({
                "category": cat,
                "count": len(items),
                "samples": items[:3],
                "is_systematic": len(items) >= 5,
            })

    # 生成摘要
    total = len(reflections)
    systematic = [p for p in patterns if p["is_systematic"]]
    occasional = [p for p in patterns if not p["is_systematic"]]

    summary_parts = []
    if systematic:
        names = "、".join(f"{p['category']}({p['count']}次)" for p in systematic)
        summary_parts.append(f"系统性问题: {names}")
    if occasional:
        names = "、".join(f"{p['category']}({p['count']}次)" for p in occasional)
        summary_parts.append(f"偶发问题: {names}")
    if not systematic and not occasional:
        summary_parts.append("各类困难分散，未形成显著模式")

    return {
        "total": total,
        "categories": sorted_cats,
        "patterns": patterns,
        "summary": "；".join(summary_parts) if summary_parts else "暂无显著模式",
    }


def _build_filled_prompt(
    target: str,
    from_date: str,
    to_date: str,
    submissions: list[dict],
) -> str:
    """填充模板占位符，返回完整 prompt。"""
    template = load_template()

    # 做题量时序数据
    daily_counts = defaultdict(lambda: {"total": 0, "ac": 0})
    for s in submissions:
        d = (s.get("date") or "")[:10]
        if d:
            daily_counts[d]["total"] += 1
            if s.get("result") == "AC":
                daily_counts[d]["ac"] += 1

    stats_points = [
        {"date": d, **daily_counts[d]}
        for d in sorted(daily_counts.keys())
    ]

    # 题目明细
    problem_list = []
    for s in submissions[:200]:
        problem_list.append({
            "pid": s.get("problemId", ""),
            "title": s.get("name", ""),
            "difficulty": s.get("difficulty", 0),
            "tags": s.get("tags", []),
            "result": s.get("result", ""),
            "date": (s.get("date") or "")[:10],
            "reflection": s.get("reflection", ""),
        })

    prompt = template
    prompt = prompt.replace("{{target}}", target)
    prompt = prompt.replace("{{period}}", f"{from_date} 至 {to_date}")
    prompt = prompt.replace("{{from_date}}", from_date)
    prompt = prompt.replace("{{to_date}}", to_date)
    prompt = prompt.replace("{{stats_points_json}}", json.dumps(stats_points, ensure_ascii=False, indent=2))
    prompt = prompt.replace("{{problem_list_json}}", json.dumps(problem_list, ensure_ascii=False, indent=2))

    return prompt


def _build_local_analysis(
    target: str,
    from_date: str,
    to_date: str,
    submissions: list[dict],
) -> str:
    """本地深度分析 — 当 DeepSeek 不可用时的 fallback。"""
    from analyzer import analyze as behavior_analyze  # lazy import 避免循环依赖

    ac_subs = [s for s in submissions if s.get("result") == "AC"]
    all_dates = sorted(set((s.get("date") or "")[:10] for s in submissions if s.get("date")))

    # 按题目分组
    groups = defaultdict(list)
    for s in submissions:
        key = (s.get("platform", ""), s.get("problemId", ""))
        groups[key].append(s)

    total_problems = len(groups)
    ac_problems = sum(1 for _, ss in groups.items() if any(x.get("result") == "AC" for x in ss))

    # 每日活跃
    daily_counts = defaultdict(lambda: {"total": 0, "ac": 0})
    for s in submissions:
        d = (s.get("date") or "")[:10]
        if d:
            daily_counts[d]["total"] += 1
            if s.get("result") == "AC":
                daily_counts[d]["ac"] += 1
    active_days = len(daily_counts)
    sorted_days = sorted(daily_counts.keys())

    # 行为分析
    behavior = behavior_analyze(submissions)
    b = behavior.get("behavior", {})
    wr = behavior.get("weakness_ranking", [])
    sg = behavior.get("suggestions", [])

    # 反思分析
    reflection_analysis = _analyze_reflections(submissions)

    report = f"""# 训练洞察报告

## 元信息

**分析对象**: {target}
**统计周期**: {from_date} 至 {to_date}

---

## 1. 数据概览与趋势诊断

| 指标 | 数值 |
|------|------|
| 总提交数 | {len(submissions)} |
| 涉及题目数 | {total_problems} |
| AC 题目数 | {ac_problems} |
| 题目通过率 | {round(ac_problems / total_problems * 100, 1) if total_problems else 0}% |
| 活跃天数 | {active_days} |
| 日均提交 | {round(len(submissions) / max(1, active_days), 1)} |
| 日均 AC | {round(len(ac_subs) / max(1, active_days), 1)} |

"""

    # 趋势分析
    if len(sorted_days) >= 4:
        mid = len(sorted_days) // 2
        first_ac = sum(daily_counts[d]["ac"] for d in sorted_days[:mid])
        second_ac = sum(daily_counts[d]["ac"] for d in sorted_days[mid:])
        first_total = sum(daily_counts[d]["total"] for d in sorted_days[:mid])
        second_total = sum(daily_counts[d]["total"] for d in sorted_days[mid:])

        report += f"**趋势诊断**:\n\n"
        if second_total > first_total:
            report += f"- 后半周期提交量 ({second_total}) 较前半 ({first_total}) {'增长' if second_total > first_total else '下降'}，"
        else:
            report += f"- 后半周期提交量下降，训练强度有所降低。\n"

        if first_total > 0 and second_total > 0:
            ratio = (second_ac / second_total) / (first_ac / first_total) if first_ac > 0 else 1
            if ratio < 0.8:
                report += f"- 后半周期通过率显著下降（比值 {ratio:.2f}），可能存在疲劳积累或题目难度攀升。\n"
            elif ratio > 1.2:
                report += f"- 后半周期通过率提升（比值 {ratio:.2f}），状态进入上升期。\n"
            else:
                report += f"- 前后半周期通过率保持稳定（比值 {ratio:.2f}），训练状态平稳。\n"

        # 日间波动
        daily_ac = [daily_counts[d]["ac"] for d in sorted_days]
        if len(daily_ac) >= 4:
            avg_ac = sum(daily_ac) / len(daily_ac)
            high_days = [sorted_days[i] for i, v in enumerate(daily_ac) if v >= avg_ac * 2]
            zero_days = [sorted_days[i] for i, v in enumerate(daily_ac) if v == 0]
            if high_days:
                report += f"- 高产日: {', '.join(high_days)}（AC量>均值 2x），建议分析高产日的训练条件。\n"
            if zero_days:
                report += f"- 空窗日: {', '.join(zero_days)}，共 {len(zero_days)} 天无提交，注意节奏持续性。\n"

        report += "\n"

    # 每日趋势表
    report += "**每日提交趋势：**\n\n| 日期 | 总提交 | AC | 通过率 |\n|------|--------|-----|--------|\n"
    for d in sorted_days:
        dc = daily_counts[d]
        rate = round(dc["ac"] / dc["total"] * 100, 1) if dc["total"] else 0
        report += f"| {d} | {dc['total']} | {dc['ac']} | {rate}% |\n"

    # --- Section 2: 专题掌握度 ---
    report += "\n## 2. 专题掌握度分析\n\n"

    # 从行为分析获取标签数据
    if wr:
        report += "### 标签得分概览\n\n"
        report += "| 专题 | AC率 | 题目数 | 评估 | 错误类型 |\n|------|------|--------|------|----------|\n"

        for item in wr[:12]:
            ac_rate = item.get("ac_rate", 0)
            total = item.get("total", 0)
            errs = item.get("error_detail", {})
            err_parts = []
            if errs.get("WA"):
                err_parts.append(f"WA×{errs['WA']}")
            if errs.get("TLE"):
                err_parts.append(f"TLE×{errs['TLE']}")
            if errs.get("RE"):
                err_parts.append(f"RE×{errs['RE']}")

            blind = item.get("blind_count", 0)
            if blind > 2:
                err_parts.append(f"盲目提交×{blind}")

            if ac_rate >= 0.7 and total >= 5:
                level = "稳定掌握"
            elif ac_rate >= 0.5 and total >= 3:
                level = "突破边缘"
            elif total >= 3:
                level = "系统性短板"
            elif total >= 1:
                level = "数据不足"
            else:
                level = "—"

            report += f"| {item['tag']} | {round(ac_rate*100)}% | {total} | {level} | {' '.join(err_parts) if err_parts else '—'} |\n"

    # 专题分类
    if wr:
        stable = [w for w in wr if w.get("ac_rate", 0) >= 0.7 and w.get("total", 0) >= 5]
        edge = [w for w in wr if 0.3 < w.get("ac_rate", 0) < 0.7 and w.get("total", 0) >= 3]
        weak = [w for w in wr if w.get("ac_rate", 0) <= 0.3 and w.get("total", 0) >= 3]

        report += "\n### 分类评估\n\n"

        if stable:
            names = "、".join(w["tag"] for w in stable[:5])
            report += f"**稳定能力**: {names}。这些专题已形成较高的稳定正确率，可作为优势领域继续深化。\n\n"

        if edge:
            names = "、".join(w["tag"] for w in edge[:5])
            report += f"**突破边缘**: {names}。这些专题有一定基础但尚不稳定，需要集中练习巩固，是短期内最易见效的方向。\n\n"

        if weak:
            names = "、".join(w["tag"] for w in weak[:5])
            report += f"**系统性短板**: {names}。这些专题通过率极低，存在系统性知识或能力缺口，需从基础重新构建。\n\n"

    # 如果数据足够，计算平均尝试次数
    if wr:
        report += "### 难度感知辅助\n\n"
        report += "| 专题 | 平均尝试/题 | 盲提次数 | 疑似参考 | 含义 |\n|------|-------------|----------|----------|------|\n"
        for item in wr[:8]:
            total = item.get("total", 0)
            avg = round(sum(p.get("attempts", 0) for p in item.get("problems", [])) / max(1, total), 1)
            blind = item.get("blind_count", 0)
            suspected = (item.get("suspected_copy", 0) or 0) + (item.get("suspected_reference", 0) or 0)
            if avg <= 1.5 and suspected > 0:
                meaning = "注意：尝试少但疑似参考题解"
            elif avg >= 4:
                meaning = "多次提交才AC，建模/调试效率低"
            elif avg <= 1.5:
                meaning = "解题效率较高"
            else:
                meaning = "正常范围"
            report += f"| {item['tag']} | {avg} | {blind} | {suspected} | {meaning} |\n"

    # --- Section 3: 反思综合 ---
    report += "\n## 3. 反思内容综合\n\n"

    if reflection_analysis["total"] > 0:
        report += f"本周期共 {reflection_analysis['total']} 条反思记录。\n\n"
        report += f"**模式识别**: {reflection_analysis['summary']}\n\n"

        patterns = reflection_analysis.get("patterns", [])
        if patterns:
            report += "### 困难类型分布\n\n"
            report += "| 类别 | 出现次数 | 性质 |\n|------|----------|------|\n"
            for p in patterns:
                nature = "系统性问题（需专项突破）" if p["is_systematic"] else "偶发问题（注意即可）"
                report += f"| {p['category']} | {p['count']} | {nature} |\n"

            # 展示样例
            report += "\n### 典型反思摘录\n\n"
            for p in patterns[:5]:
                report += f"**{p['category']}**（{p['count']}次）:\n"
                for sample in p["samples"][:2]:
                    report += f"- \"{sample[:150]}{'...' if len(sample) > 150 else ''}\"\n"
                report += "\n"
    else:
        report += "> 本周期内无反思记录。建议每道 AC 题后补充简短反思（1-2句），记录卡点和关键 insight，以便持续跟踪思维盲区。\n"

    # --- Section 4: 行为分析 ---
    report += "\n## 4. 个人行为画像\n\n"

    # 摘要
    report += f"{b.get('summary', '')}\n\n"

    # 编码习惯
    report += "### 编码习惯\n"
    if b.get("coding"):
        for line in b["coding"]:
            report += f"- {line}\n"
    else:
        report += "编码习惯整体良好。\n"

    # 算法思维
    report += "\n### 算法思维\n"
    if b.get("algorithm"):
        for line in b["algorithm"]:
            report += f"- {line}\n"
    else:
        report += "算法思维整体良好。\n"

    # 学习习惯
    report += "\n### 学习习惯\n"
    if b.get("learning"):
        for line in b["learning"]:
            report += f"- {line}\n"
    else:
        report += "学习习惯整体良好。\n"

    # --- Section 5: 下阶段行动建议 ---
    report += "\n## 5. 下阶段行动建议\n\n"

    # 优先强化
    if sg:
        report += "### 优先强化专题\n\n"
        for item in sg[:5]:
            report += f"**{item['tag']}**（得分: {item['score']}，AC率: {item['ac_rate']}%）：\n"
            for advice in item.get("advice", []):
                report += f"- {advice}\n"
            report += "\n"

    # 训练节奏建议
    daily_ac_target = max(2, round(len(ac_subs) / max(1, active_days)))
    report += f"### 每日训练节奏\n\n"
    report += f"- 保持每日至少 **{daily_ac_target}** 道 AC 题目\n"
    report += "- 在 Codeforces 按薄弱标签筛选对应难度区间题目（参考专题分析中的平均难度）\n"

    # 针对反思问题的建议
    if reflection_analysis["patterns"]:
        systematic = [p for p in reflection_analysis["patterns"] if p["is_systematic"]]
        if systematic:
            report += "\n### 针对反思问题的专项策略\n\n"
            for p in systematic[:3]:
                cat = p["category"]
                if "思路" in cat:
                    report += f'- **{cat}**: 遇到无思路的题，先看题目标签提示，思考≥30分钟仍无思路再读题解。读题解重点理解“为什么想到这个解法”，而非“解法是什么”。读完题解后关闭原题，独立重写一遍。\n'
                elif "细节" in cat or "边界" in cat:
                    report += f'- **{cat}**: 提交前执行 Checklist：①数组/下标范围 ②空值/边界情况 ③题目特殊约束。每道题至少构造 3 组边界样例（最小值、最大值、随机），本地通过后再提交。\n'
                elif "TLE" in cat or "优化" in cat:
                    report += f'- **{cat}**: 写代码前先估算时间复杂度。对比数据范围：n≤100→O(n³)，n≤10³→O(n²)，n≤10⁵→O(n log n)，n≤10⁶→O(n)。若暴力复杂度超限，先设计优化方案再编码。\n'
                elif "题解" in cat or "参考" in cat:
                    report += f'- **{cat}**: 克制立即看题解的冲动。每道题至少独立思考 30 分钟，记录自己的尝试方向（即使失败）。看题解后做同类变体题验证是否真正掌握，而非假性理解。\n'

    report += f"\n\n---\n*报告由 ACM Helper 自动生成于 {datetime.now().strftime('%Y-%m-%d %H:%M')}*"
    return report


def generate_report(
    target: str,
    from_date: str,
    to_date: str,
    submissions: list[dict],
) -> str:
    """基于提交数据生成周报 Markdown。

    流程:
      1. 填充 requirement.rm 模板（作为 LLM prompt）
      2. 如果 DeepSeek API Key 已配置，调用 DeepSeek 按模板规则生成完整报告
      3. 如果 Key 未配置，使用本地深度分析（整合 behavior analyzer）作为 fallback

    Args:
        target: 分析对象名（如 "Codeforces: tourist"）
        from_date: 周期起始日
        to_date: 周期结束日
        submissions: 统一格式的提交记录列表

    Returns:
        完整的 Markdown 报告
    """
    if not submissions:
        return f"""# 训练洞察报告

## 元信息
**分析对象**: {target}
**统计周期**: {from_date} 至 {to_date}

---

## 1. 数据概览
> 本周期内无提交数据，无法生成分析报告。

---
*报告由 ACM Helper 自动生成于 {datetime.now().strftime('%Y-%m-%d %H:%M')}*
"""

    # Step 1: 尝试 DeepSeek API
    api_key = _get_api_key()
    if api_key:
        print(f"  [REPORT] 使用 DeepSeek API 生成报告...")
        try:
            prompt = _build_filled_prompt(target, from_date, to_date, submissions)
            result = _call_deepseek(prompt, api_key)
            if result:
                # DeepSeek 返回的已经是按模板规则生成的完整报告
                # 在末尾追加生成时间戳
                result += f"\n\n---\n*报告由 ACM Helper 调用 DeepSeek 自动生成于 {datetime.now().strftime('%Y-%m-%d %H:%M')}*"
                return result
        except Exception as e:
            print(f"  [REPORT] DeepSeek 失败，降级到本地分析: {e}")

    # Step 2: Fallback — 本地深度分析
    print(f"  [REPORT] 使用本地分析引擎生成报告...")
    return _build_local_analysis(target, from_date, to_date, submissions)
