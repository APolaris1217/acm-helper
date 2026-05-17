"""
Submission behavior analysis engine.

Takes a list of unified submission records (the same format returned by the
fetch endpoints) and produces a three-section weakness report.

Core design principle:
  Do NOT judge weakness by tag pass-rate alone.
  Judge by submission behavior patterns: attempt count, pre-AC error sequence,
  time interval between submissions, and historical ability continuity.
"""

from collections import defaultdict
from datetime import datetime, timezone, timedelta
import math

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Submission attempt count tiers (per problem)
TIER_1 = 1        # one-pass — needs genuineness check
TIER_2_3 = (2, 3)  # minor issues
TIER_4_7 = (4, 7)  # modeling weak
TIER_8_PLUS = 8     # fundamental misunderstanding

# Time-interval thresholds (seconds)
BLIND_INTERVAL = 60        # < 60 s — blind submission, no self-testing
NORMAL_INTERVAL = 300      # 1-5 min — normal fix
LONG_INTERVAL = 1800       # > 30 min — stuck, weak problem-solving

# Suspicious one-pass detection
MIN_READ_TIME = 120         # minimum seconds from first access to first submit
BATCH_SUSPICIOUS_COUNT = 3  # if N+ hard problems all AC in one sitting
BATCH_SUSPICIOUS_WINDOW = 3600  # within 1 hour

# Difficulty thresholds
HARD_DIFFICULTY = 2000

# Penalty weights for weakness scoring
PENALTY = {
    # Base attempt-tier penalty
    "tier_1": 0,
    "tier_2_3": 30,
    "tier_4_7": 60,
    "tier_8_plus": 100,
    "never_ac": 150,

    # Per-occurrence error-type penalty
    "wa": 10,
    "tle": 15,
    "re": 12,
    "ce": 8,
    "mle": 10,

    # Behavior penalty
    "blind_submit": 20,        # interval < 60s
    "long_gap": 5,             # interval > 30min

    # Genuineness penalty (applied to tag-level)
    "suspected_copy": 40,      # likely copy-paste / cheating
    "suspected_reference": 30, # likely referenced solution
}

# Error-type → interpretation mapping
ERROR_MEANING = {
    "WA": "逻辑不严谨、边界与特殊样例考虑缺失",
    "TLE": "复杂度不会估算、只会暴力、缺少优化思维",
    "RE": "数组越界、下标粗心、代码鲁棒性差",
    "CE": "语法不熟练、编码粗心、模版不稳固",
    "MLE": "空间复杂度意识不足",
}

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _ts_to_datetime(ts_str):
    """Parse ISO date string to datetime (naive UTC)."""
    if not ts_str:
        return None
    try:
        return datetime.strptime(ts_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        try:
            return datetime.fromisoformat(ts_str)
        except (ValueError, TypeError):
            return None


def _group_by_problem(submissions):
    """Group submissions by (platform, problemId)."""
    groups = defaultdict(list)
    for s in submissions:
        key = (s.get("platform", ""), s.get("problemId", ""))
        groups[key].append(s)
    return dict(groups)


def _sort_by_date(submissions):
    """Sort submissions by date ascending."""
    def _key(s):
        d = _ts_to_datetime(s.get("date", ""))
        return d.timestamp() if d else 0
    return sorted(submissions, key=_key)


# ---------------------------------------------------------------------------
# Per-problem analysis
# ---------------------------------------------------------------------------

def analyze_problem(ss):
    """
    Analyze a single problem's submission history.

    ss: list of submissions for one (platform, problemId), sorted by date.

    Returns dict with:
      - attempt_count, ac_attempt_index, ever_ac
      - pre_ac_errors: list of result strings before first AC
      - intervals: list of (seconds, blind, normal, long) between adjacent subs
      - tier: 1 | 2_3 | 4_7 | 8_plus | never
      - genuineness: 'genuine' | 'suspected_copy' | 'suspected_reference' | 'unknown'
      - score: per-problem weakness score
    """
    ss = _sort_by_date(ss)
    n = len(ss)

    results = [s.get("result", "unsolved") for s in ss]
    ever_ac = "AC" in results
    ac_idx = results.index("AC") if ever_ac else None

    # Pre-AC error sequence
    pre_ac_errors = results[:ac_idx] if ever_ac else results

    # Time intervals
    dates = [_ts_to_datetime(s.get("date", "")) for s in ss]
    intervals = []
    for i in range(1, len(dates)):
        if dates[i] and dates[i-1]:
            sec = (dates[i] - dates[i-1]).total_seconds()
            intervals.append({
                "seconds": sec,
                "blind": sec < BLIND_INTERVAL,
                "normal": BLIND_INTERVAL <= sec <= NORMAL_INTERVAL,
                "long": sec > LONG_INTERVAL,
            })

    # Attempt tier
    if not ever_ac:
        tier = "never"
    elif n == 1:
        tier = "tier_1"
    elif n <= 3:
        tier = "tier_2_3"
    elif n <= 7:
        tier = "tier_4_7"
    else:
        tier = "tier_8_plus"

    # Error counts in pre-AC phase
    error_counts = {"WA": 0, "TLE": 0, "RE": 0, "CE": 0, "MLE": 0}
    for e in pre_ac_errors:
        if e in error_counts:
            error_counts[e] += 1

    # Blind submissions
    blind_count = sum(1 for iv in intervals if iv["blind"])
    long_gap_count = sum(1 for iv in intervals if iv["long"])

    # Per-problem score
    base = PENALTY.get(tier, 0)
    detail = base
    detail += error_counts["WA"] * PENALTY["wa"]
    detail += error_counts["TLE"] * PENALTY["tle"]
    detail += error_counts["RE"] * PENALTY["re"]
    detail += error_counts["CE"] * PENALTY["ce"]
    detail += error_counts["MLE"] * PENALTY["mle"]
    detail += blind_count * PENALTY["blind_submit"]
    detail += long_gap_count * PENALTY["long_gap"]

    return {
        "attempt_count": n,
        "ever_ac": ever_ac,
        "ac_index": ac_idx,
        "pre_ac_errors": pre_ac_errors,
        "error_counts": error_counts,
        "intervals": intervals,
        "blind_count": blind_count,
        "long_gap_count": long_gap_count,
        "tier": tier,
        "genuineness": "unknown",  # set later by cross-problem analysis
        "score": detail,
    }


# ---------------------------------------------------------------------------
# Genuineness detection for "one-pass AC" problems
# ---------------------------------------------------------------------------

def detect_suspicious_batch(problem_analyses, submissions):
    """
    Detect batch suspicious behavior:
    Multiple hard problems all AC'd in one pass within a short time window
    → likely copied or referenced.
    """
    # Group one-pass ACs by date
    one_pass_by_date = defaultdict(list)
    for (platform, pid), analysis in problem_analyses.items():
        if analysis["tier"] != "tier_1":
            continue
        # Find the date of this submission
        ss = [s for s in submissions if s.get("platform") == platform and s.get("problemId") == pid]
        if not ss:
            continue
        date = ss[0].get("date", "")
        one_pass_by_date[date].append((platform, pid))

    suspicious_set = set()
    for date, pids in one_pass_by_date.items():
        if len(pids) >= BATCH_SUSPICIOUS_COUNT:
            for pid in pids:
                suspicious_set.add(pid)

    return suspicious_set


def assess_genuineness(problem_analyses, submissions):
    """
    For each tier-1 (one-pass AC) problem, determine if it was:
      - genuine: true independent solve
      - suspected_copy: likely copy-pasted
      - suspected_reference: likely referenced solution
    """
    # 1. Detect batch suspicious
    batch_suspicious = detect_suspicious_batch(problem_analyses, submissions)

    # 2. Build tag-level history for continuity check
    tag_history = _build_tag_history(problem_analyses, submissions)

    for key, analysis in problem_analyses.items():
        if analysis["tier"] != "tier_1":
            continue

        platform, pid = key

        # Get the submission
        ss = [s for s in submissions if s.get("platform") == platform and s.get("problemId") == pid]
        if not ss:
            continue
        s = ss[0]
        diff = s.get("difficulty", 0) or 0
        tags = s.get("tags", []) or []

        # Check 1: batch suspicious → likely copy
        if key in batch_suspicious and diff >= HARD_DIFFICULTY:
            analysis["genuineness"] = "suspected_copy"
            continue

        # Check 2: tag history continuity
        # If same-tag same-difficulty problems historically had many attempts/failures,
        # and this one passed first try → ability gap → suspected reference
        continuity_gap = False
        for tag in tags:
            hist = tag_history.get(tag, {})
            # Look at problems in similar difficulty range (±400)
            similar_problems = hist.get("by_difficulty", {}).get(diff // 400 * 400, [])
            if similar_problems:
                avg_attempts = sum(p["attempts"] for p in similar_problems) / len(similar_problems)
                ac_rate = sum(1 for p in similar_problems if p["ever_ac"]) / len(similar_problems)
                # Historically struggled on similar problems
                if avg_attempts >= 4 and ac_rate <= 0.5:
                    continuity_gap = True
                    break

        if continuity_gap:
            analysis["genuineness"] = "suspected_reference"
        else:
            analysis["genuineness"] = "genuine"


def _build_tag_history(problem_analyses, submissions):
    """Build per-tag historical stats for continuity checking."""
    tag_history = defaultdict(lambda: {"by_difficulty": defaultdict(list), "total": 0, "ac": 0})

    for key, analysis in problem_analyses.items():
        platform, pid = key
        ss = [s for s in submissions if s.get("platform") == platform and s.get("problemId") == pid]
        if not ss:
            continue
        tags = ss[0].get("tags", []) or []
        diff = ss[0].get("difficulty", 0) or 0
        bucket = diff // 400 * 400

        for tag in tags:
            tag_history[tag]["total"] += 1
            if analysis["ever_ac"]:
                tag_history[tag]["ac"] += 1
            tag_history[tag]["by_difficulty"][bucket].append({
                "attempts": analysis["attempt_count"],
                "ever_ac": analysis["ever_ac"],
                "tier": analysis["tier"],
            })

    return dict(tag_history)


# ---------------------------------------------------------------------------
# Tag-level weakness scoring
# ---------------------------------------------------------------------------

def score_tags(problem_analyses, submissions):
    """
    Aggregate per-problem scores by tag.
    Returns list of {tag, score, ac_count, total_count, problems, ...} sorted by score desc.
    """
    tag_scores = defaultdict(lambda: {
        "score": 0,
        "total": 0,
        "ac": 0,
        "problems": [],
        "error_detail": {"WA": 0, "TLE": 0, "RE": 0, "CE": 0, "MLE": 0},
        "blind_count": 0,
        "long_gap_count": 0,
        "suspected_copy": 0,
        "suspected_reference": 0,
    })

    for key, analysis in problem_analyses.items():
        platform, pid = key
        ss = [s for s in submissions if s.get("platform") == platform and s.get("problemId") == pid]
        if not ss:
            continue
        tags = ss[0].get("tags", []) or []
        if not tags:
            continue

        base_score = analysis["score"]

        # Genuineness penalty
        genuineness_penalty = 0
        if analysis["genuineness"] == "suspected_copy":
            genuineness_penalty = PENALTY["suspected_copy"]
        elif analysis["genuineness"] == "suspected_reference":
            genuineness_penalty = PENALTY["suspected_reference"]

        for tag in tags:
            ts = tag_scores[tag]
            ts["score"] += base_score + genuineness_penalty
            ts["total"] += 1
            if analysis["ever_ac"]:
                ts["ac"] += 1
            ts["problems"].append({
                "platform": platform,
                "problemId": pid,
                "name": ss[0].get("name", ""),
                "attempts": analysis["attempt_count"],
                "tier": analysis["tier"],
                "genuineness": analysis["genuineness"],
                "score": base_score + genuineness_penalty,
            })
            ts["blind_count"] += analysis["blind_count"]
            ts["long_gap_count"] += analysis["long_gap_count"]
            for err in ("WA", "TLE", "RE", "CE", "MLE"):
                ts["error_detail"][err] += analysis["error_counts"].get(err, 0)
            if analysis["genuineness"] == "suspected_copy":
                ts["suspected_copy"] += 1
            elif analysis["genuineness"] == "suspected_reference":
                ts["suspected_reference"] += 1

    result = []
    for tag, data in tag_scores.items():
        result.append({
            "tag": tag,
            "score": data["score"],
            "total": data["total"],
            "ac": data["ac"],
            "ac_rate": data["ac"] / data["total"] if data["total"] > 0 else 0,
            "problems": sorted(data["problems"], key=lambda x: x["score"], reverse=True),
            "error_detail": data["error_detail"],
            "blind_count": data["blind_count"],
            "long_gap_count": data["long_gap_count"],
            "suspected_copy": data["suspected_copy"],
            "suspected_reference": data["suspected_reference"],
        })

    result.sort(key=lambda x: x["score"], reverse=True)
    return result


# ---------------------------------------------------------------------------
# Behavior profile
# ---------------------------------------------------------------------------

def build_behavior_profile(problem_analyses, submissions):
    """
    Build three-aspect behavior profile:
      1. Coding habits (CE, RE, blind submit, carelessness)
      2. Algorithm thinking (boundary, complexity, modeling)
      3. Learning habits (over-persist, solution dependence, lack of independent thinking)
    """
    all_errors = {"WA": 0, "TLE": 0, "RE": 0, "CE": 0, "MLE": 0}
    total_blind = 0
    total_long_gap = 0
    total_suspected_copy = 0
    total_suspected_reference = 0
    total_problems = len(problem_analyses)
    total_submissions = len(submissions)

    extreme_grind = 0  # problems with 8+ attempts
    tier_counts = defaultdict(int)

    for key, analysis in problem_analyses.items():
        for err in ("WA", "TLE", "RE", "CE", "MLE"):
            all_errors[err] += analysis["error_counts"].get(err, 0)
        total_blind += analysis["blind_count"]
        total_long_gap += analysis["long_gap_count"]
        tier_counts[analysis["tier"]] += 1
        if analysis["tier"] in ("tier_8_plus", "never"):
            extreme_grind += 1
        if analysis["genuineness"] == "suspected_copy":
            total_suspected_copy += 1
        elif analysis["genuineness"] == "suspected_reference":
            total_suspected_reference += 1

    # 1. Coding habits
    coding_issues = []
    if all_errors["CE"] > total_problems * 0.05:
        coding_issues.append(f"编译错误 {all_errors['CE']} 次，语法熟练度不足，建议加强基础语法练习")
    if all_errors["RE"] > total_problems * 0.08:
        coding_issues.append(f"运行时错误 {all_errors['RE']} 次，数组越界/空指针问题频发，建议代码提交前做自测")
    if total_blind > total_problems * 0.1:
        coding_issues.append(f"盲目提交 {total_blind} 次（间隔<60秒），不自测不推演，依赖OJ判题碰运气，建议提交前本地构造边界样例自测")
    if all_errors["CE"] + all_errors["RE"] > total_problems * 0.15:
        coding_issues.append("编码粗心问题突出，建议形成提交前checklist：边界/空值/下标/输出格式")

    # 2. Algorithm thinking
    algo_issues = []
    wa_count = all_errors["WA"]
    tle_count = all_errors["TLE"]
    if wa_count > total_problems * 0.3:
        algo_issues.append(f"逻辑错误 {wa_count} 次，边界条件与特殊样例考虑不足，建议每道题先列举所有边界情况再写代码")
    if tle_count > total_problems * 0.15:
        algo_issues.append(f"超时 {tle_count} 次，复杂度不会估算、习惯暴力解法，建议每次提交前估算最坏时间复杂度")
    if tier_counts.get("tier_4_7", 0) + tier_counts.get("tier_8_plus", 0) > total_problems * 0.15:
        algo_issues.append(f"高提交次数题目 {tier_counts.get('tier_4_7', 0) + tier_counts.get('tier_8_plus', 0)} 道，算法建模能力弱、思路摇摆，建议培养'先设计后编码'习惯")
    if total_long_gap > total_problems * 0.1:
        algo_issues.append(f"长时间卡壳 {total_long_gap} 次（间隔>30分钟），问题拆解能力弱，建议30分钟无思路先看题目标签提示")

    # 3. Learning habits
    learn_issues = []
    if extreme_grind > total_problems * 0.05:
        learn_issues.append(f"极端死磕 {extreme_grind} 道题（8+次提交），死磕不复盘效率低，建议提交3次仍错后暂停，先分析错误模式再继续")
    if total_suspected_copy + total_suspected_reference > 0:
        learn_issues.append(f"疑似参考题解/复制 {total_suspected_copy + total_suspected_reference} 道题（一次AC但历史同类题水平不连续），独立思考能力待提升，建议关闭题解独立完成同类题")
    if tier_counts.get("never", 0) > total_problems * 0.05:
        learn_issues.append(f"多次提交未AC {tier_counts.get('never', 0)} 道题，存在完全不会的知识点盲区，建议回归基础学习而非继续尝试")
    if total_suspected_reference > total_problems * 0.1:
        learn_issues.append("过度依赖题解，建议先独立思考至少30分钟，形成自己的思路后再对答案，重点理解'为什么想到这个解法'而非'这个解法是什么'")

    # Build tier descriptions
    tier_desc_parts = []
    if tier_counts.get("tier_1", 0) > 0:
        tier_desc_parts.append(f"{tier_counts['tier_1']}道一遍AC")
    if tier_counts.get("tier_2_3", 0) > 0:
        tier_desc_parts.append(f"{tier_counts['tier_2_3']}道2-3次AC")
    if tier_counts.get("tier_4_7", 0) > 0:
        tier_desc_parts.append(f"{tier_counts['tier_4_7']}道4-7次AC")
    if tier_counts.get("tier_8_plus", 0) > 0:
        tier_desc_parts.append(f"{tier_counts['tier_8_plus']}道8次以上AC")
    if tier_counts.get("never", 0) > 0:
        tier_desc_parts.append(f"{tier_counts['never']}道始终未AC")

    return {
        "summary": f"共分析 {total_problems} 道题目、{total_submissions} 次提交。" + "、".join(tier_desc_parts) + "。",
        "coding": coding_issues if coding_issues else ["编码习惯整体良好，未发现明显的粗心/语法问题。"],
        "algorithm": algo_issues if algo_issues else ["算法思维整体良好，边界处理和复杂度估算能力较好。"],
        "learning": learn_issues if learn_issues else ["学习习惯整体良好，独立思考能力较强。"],
        "stats": {
            "total_problems": total_problems,
            "total_submissions": total_submissions,
            "tier_counts": dict(tier_counts),
            "error_counts": dict(all_errors),
            "blind_count": total_blind,
            "long_gap_count": total_long_gap,
            "suspected_copy": total_suspected_copy,
            "suspected_reference": total_suspected_reference,
        }
    }


# ---------------------------------------------------------------------------
# Improvement suggestions
# ---------------------------------------------------------------------------

def generate_suggestions(tag_scores, behavior_profile):
    """Generate specific actionable suggestions for each weak area."""
    suggestions = []
    for item in tag_scores[:8]:  # top 8 weakest
        tag = item["tag"]
        score = item["score"]
        ac_rate = item["ac_rate"]
        problems = item["problems"]
        errors = item["error_detail"]

        advice = []

        # Find the specific weakness pattern
        if errors["WA"] > errors.get("TLE", 0) and errors["WA"] > errors.get("RE", 0):
            advice.append("重点练习边界条件与特殊样例构造")
        if errors.get("TLE", 0) > errors.get("WA", 0):
            advice.append("重点学习时间复杂度分析与优化技巧，从暴力→优化的思维路径")
        if errors.get("RE", 0) > 2:
            advice.append("注意数组越界、空指针、下标计算，写完代码后自查边界情况")
        if errors.get("CE", 0) > 2:
            advice.append("加强语法基础，熟记常用模板，减少编译错误")

        if item["blind_count"] > 2:
            advice.append("改掉盲目提交习惯，每次修改后先本地用边界样例自测")
        if item["long_gap_count"] > 2:
            advice.append("遇到卡壳不要死磕，30分钟无思路先看标签提示，回顾同类题型思路")

        # Based on attempt tier distribution
        tier2_3 = sum(1 for p in problems if p["tier"] == "tier_2_3")
        tier4_7 = sum(1 for p in problems if p["tier"] == "tier_4_7")
        tier8 = sum(1 for p in problems if p["tier"] == "tier_8_plus") + sum(1 for p in problems if p["tier"] == "never")

        if tier8 > tier4_7:
            advice.append(f"该标签下 {tier8} 道题大量提交才AC或始终未AC，建议回归基础：找该知识点入门题反复练习，建立正确思维模型后再做难题")
        elif tier4_7 > tier2_3:
            advice.append(f"该标签下 {tier4_7} 道题需要多次提交才AC，建议每道题做完后总结'我错在哪里、正确思路是什么'")

        if item["suspected_copy"] > 0:
            advice.append(f"疑似复制/秒过 {item['suspected_copy']} 道题，不计入掌握。建议找同知识点同难度题目重新独立完成")
        if item["suspected_reference"] > 0:
            advice.append(f"疑似参考题解 {item['suspected_reference']} 道题，建议关闭题解做同类型变体题，检验是否真正理解")

        if not advice:
            advice.append("多做该知识点的中等难度题，保持手感")

        # Suggest specific problem difficulty range
        # Find the difficulty where user struggles most
        diff_scores = defaultdict(lambda: {"total": 0, "ac": 0})
        for p in problems:
            # Find the problem's difficulty from the submissions
            pass  # difficulty is in the submission itself

        suggestions.append({
            "tag": tag,
            "score": score,
            "ac_rate": round(ac_rate * 100, 1),
            "problem_count": len(problems),
            "advice": advice,
        })

    return suggestions


# ---------------------------------------------------------------------------
# Main analysis entry point
# ---------------------------------------------------------------------------

def analyze(submissions):
    """
    Main entry point. Takes a list of unified submission records and returns
    a complete analysis report.

    Returns dict with three sections:
      - behavior: personal behavior & thinking weakness summary
      - weakness_ranking: ranked list of weak knowledge areas
      - suggestions: specific actionable improvement suggestions per weak area
    """
    if not submissions:
        return {
            "behavior": {
                "summary": "暂无提交数据，无法分析。",
                "coding": [],
                "algorithm": [],
                "learning": [],
                "stats": {},
            },
            "weakness_ranking": [],
            "suggestions": [],
        }

    # Group by problem
    groups = _group_by_problem(submissions)

    # Per-problem analysis
    problem_analyses = {}
    for key, ss in groups.items():
        problem_analyses[key] = analyze_problem(ss)

    # Genuineness check for one-pass ACs
    assess_genuineness(problem_analyses, submissions)

    # Tag-level scoring
    tag_scores = score_tags(problem_analyses, submissions)

    # Behavior profile
    behavior = build_behavior_profile(problem_analyses, submissions)

    # Suggestions
    suggestions = generate_suggestions(tag_scores, behavior)

    return {
        "behavior": behavior,
        "weakness_ranking": tag_scores,
        "suggestions": suggestions,
    }


# ---------------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Quick self-test with synthetic data
    test_data = [
        {"platform": "cf", "problemId": "100A", "name": "Test A", "difficulty": 1200, "tags": ["dp", "math"], "result": "WA", "date": "2026-05-10", "language": "C++"},
        {"platform": "cf", "problemId": "100A", "name": "Test A", "difficulty": 1200, "tags": ["dp", "math"], "result": "TLE", "date": "2026-05-10", "language": "C++"},
        {"platform": "cf", "problemId": "100A", "name": "Test A", "difficulty": 1200, "tags": ["dp", "math"], "result": "WA", "date": "2026-05-10", "language": "C++"},
        {"platform": "cf", "problemId": "100A", "name": "Test A", "difficulty": 1200, "tags": ["dp", "math"], "result": "AC", "date": "2026-05-10", "language": "C++"},
        {"platform": "cf", "problemId": "200B", "name": "Test B", "difficulty": 800, "tags": ["greedy"], "result": "AC", "date": "2026-05-11", "language": "C++"},
        {"platform": "cf", "problemId": "300C", "name": "Test C", "difficulty": 2400, "tags": ["dp"], "result": "WA", "date": "2026-05-12", "language": "C++"},
        {"platform": "cf", "problemId": "300C", "name": "Test C", "difficulty": 2400, "tags": ["dp"], "result": "WA", "date": "2026-05-12", "language": "C++"},
        {"platform": "cf", "problemId": "300C", "name": "Test C", "difficulty": 2400, "tags": ["dp"], "result": "unsolved", "date": "2026-05-12", "language": "C++"},
    ]
    report = analyze(test_data)
    print("=== BEHAVIOR PROFILE ===")
    print(report["behavior"]["summary"])
    for cat, title in [("coding", "编码习惯"), ("algorithm", "算法思维"), ("learning", "学习习惯")]:
        print(f"\n[{title}]")
        for line in report["behavior"][cat]:
            print(f"  • {line}")
    print("\n=== WEAKNESS RANKING ===")
    for item in report["weakness_ranking"][:5]:
        print(f"  {item['tag']}: score={item['score']}, AC率={item['ac_rate']:.0%}, 共{item['total']}题")
    print("\n=== SUGGESTIONS ===")
    for item in report["suggestions"][:3]:
        print(f"  [{item['tag']}] (score={item['score']})")
        for a in item["advice"]:
            print(f"    → {a}")
