"""Shared algorithm tag mapping."""

# ── TAG_CN: English → Chinese display name (for AI output matching + frontend display) ──
TAG_CN = {
    # Core Codeforces tags
    "dp": "动态规划", "greedy": "贪心", "math": "数学", "graphs": "图论",
    "graph": "图论", "data structures": "数据结构", "implementation": "模拟",
    "constructive algorithms": "构造", "brute force": "暴力枚举",
    "sortings": "排序", "strings": "字符串", "binary search": "二分",
    "number theory": "数学", "combinatorics": "组合数学", "geometry": "计算几何",
    "trees": "树", "dfs and similar": "DFS", "shortest paths": "最短路",
    "two pointers": "双指针", "bitmasks": "位运算", "divide and conquer": "分治",
    "flows": "网络流", "games": "博弈论", "hashing": "哈希", "probabilities": "概率",
    "matrices": "矩阵", "dsu": "并查集",
    "string suffix structures": "后缀结构",
    "ternary search": "三分", "meet-in-the-middle": "折半搜索",
    "fft": "FFT", "interactive": "交互",
    "chinese remainder theorem": "CRT", "expression parsing": "表达式解析",
    "schedules": "调度", "search": "搜索", "simulation": "模拟",
    "prefix sum": "前缀和", "bfs": "BFS", "stl": "STL", "graph matchings": "图匹配",
    "2-sat": "2-SAT",

    # Extended — common Luogu / Chinese OJ concepts (for AI output matching)
    "segment tree": "线段树", "binary indexed tree": "树状数组",
    "fenwick tree": "树状数组", "bit": "树状数组",
    "mo's algorithm": "莫队", "scc": "强连通分量", "tarjan": "Tarjan",
    "lca": "LCA", "kmp": "KMP", "sieve": "筛法",
    "sparse table": "ST 表", "suffix automaton": "SAM", "suffix array": "SA",
    "ntt": "NTT", "convex hull": "凸包", "sweep line": "扫描线",
    "trie": "字典树", "topological sort": "拓扑排序", "toposort": "拓扑排序",
    "mst": "生成树", "minimum spanning tree": "生成树",
    "knapsack": "背包 DP", "digit dp": "数位 DP", "interval dp": "区间 DP",
    "tree dp": "树形 DP", "state compression": "状压 DP",
    "lct": "LCT", "link cut tree": "LCT",
    "heavy light decomposition": "树链剖分", "hld": "树链剖分",
    "centroid decomposition": "点分治",
    "cdq divide and conquer": "CDQ 分治",
    "monotonic queue": "单调队列", "monotonic stack": "单调栈",
    "presum": "前缀和", "difference array": "差分",
    "expectation": "期望",
    "tree diameter": "树的直径", "diameter": "树的直径",
    "virtual tree": "虚树",
    "persistent segment tree": "可持久化线段树", "chairman tree": "主席树",
    "balanced tree": "平衡树", "binary lifting": "倍增",
    "randomization": "随机化",
    "euler tour": "欧拉回路", "euler path": "欧拉回路",
    "bipartite graph": "二分图", "max flow": "网络流", "min cut": "最小割",
    "cost flow": "费用流", "mcmf": "费用流",
    "linear programming": "线性规划",
    "gaussian elimination": "高斯消元", "linear basis": "线性基",
    "matrix exponentiation": "矩阵加速", "matrix multiplication": "矩阵乘法",
    "inclusion exclusion": "容斥原理",
    "generating function": "生成函数", "polynomial": "多项式",
    "discrete log": "BSGS", "quadratic residue": "二次剩余",
    "primitive root": "原根", "modular inverse": "逆元",
    "modular arithmetic": "数论",
    "suffix automaton": "SAM", "suffix array": "SA",
    "palindromic tree": "PAM", "palindromic automaton": "PAM",
    "fast walsh-hadamard transform": "FWT",
    "dynamic connectivity": "LCT",
    "sqrt decomposition": "分块",
    "block decomposition": "分块",
    "hashing": "哈希", "hash": "哈希",
    "string matching": "KMP",
    "minimum cut": "最小割",
    "maximum flow": "网络流",
    "basis": "线性基",
    "functional graph": "基环树",
    "pseudo tree": "基环树",
    "dancing links": "Dancing Links",
    "manacher": "Manacher",
    "floyd": "Floyd", "floyd-warshall": "Floyd",
    "a-star": "A*", "astar": "A*",
    "ad-hoc": "Ad-hoc",
    "wqs binary search": "wqs 二分", "aliens trick": "wqs 二分",
    "slope trick": "斜率维护技巧",
    "little girl and tree": "树剖",
    "merge sort tree": "线段树合并",
    "逆序对": "逆序对",
}


# ── TAG_NORMALIZE: canonical tag normalization (English→Chinese + synonym merge) ──
# Applied to every tag before it enters the database, ensuring a single canonical form.
# This is the single source of truth for tag normalization.
TAG_NORMALIZE = {
    # ── English / abbreviation → Chinese ──
    "dp": "动态规划",
    "greedy": "贪心",
    "math": "数学",
    "number theory": "数学",
    "modular arithmetic": "数论",
    "binary search": "二分",
    "strings": "字符串",
    "bitmasks": "位运算",
    "brute force": "暴力枚举",
    "data structures": "数据结构",
    "sortings": "排序",
    "games": "博弈论",
    "two pointers": "双指针",
    "implementation": "模拟",
    "simulation": "模拟",
    "constructive algorithms": "构造",
    "interactive": "交互",
    "graphs": "图论",
    "graph": "图论",
    "trees": "树",
    "geometry": "计算几何",
    "matrices": "矩阵",
    "combinatorics": "组合数学",
    "probabilities": "概率",
    "search": "搜索",
    "flows": "网络流",
    "max flow": "网络流",
    "maximum flow": "网络流",
    "divide and conquer": "分治",
    "dsu": "并查集",
    "fft": "FFT",
    "bfs": "BFS",
    "stl": "STL",
    "schedules": "调度",
    "expression parsing": "表达式解析",
    "meet-in-the-middle": "折半搜索",
    "graph matchings": "图匹配",
    "chinese remainder theorem": "CRT",
    "string suffix structures": "后缀结构",
    "dfs and similar": "DFS",
    "ternary search": "三分",
    "prefix sum": "前缀和",
    "presum": "前缀和",
    "2-sat": "2-SAT",
    "shortest paths": "最短路",
    "segment tree": "线段树",
    "fenwick tree": "树状数组",
    "bit": "树状数组",
    "binary indexed tree": "树状数组",
    "mo's algorithm": "莫队",
    "scc": "强连通分量",
    "tarjan": "Tarjan",
    "lca": "LCA",
    "kmp": "KMP",
    "string matching": "KMP",
    "sieve": "筛法",
    "sparse table": "ST 表",
    "suffix automaton": "SAM",
    "suffix array": "SA",
    "ntt": "NTT",
    "convex hull": "凸包",
    "sweep line": "扫描线",
    "trie": "字典树",
    "topological sort": "拓扑排序",
    "toposort": "拓扑排序",
    "mst": "生成树",
    "minimum spanning tree": "生成树",
    "knapsack": "背包 DP",
    "digit dp": "数位 DP",
    "interval dp": "区间 DP",
    "tree dp": "树形 DP",
    "state compression": "状压 DP",
    "lct": "LCT",
    "link cut tree": "LCT",
    "dynamic connectivity": "LCT",
    "heavy light decomposition": "树链剖分",
    "hld": "树链剖分",
    "centroid decomposition": "点分治",
    "cdq divide and conquer": "CDQ 分治",
    "monotonic queue": "单调队列",
    "monotonic stack": "单调栈",
    "difference array": "差分",
    "expectation": "期望",
    "tree diameter": "树的直径",
    "diameter": "树的直径",
    "virtual tree": "虚树",
    "persistent segment tree": "可持久化线段树",
    "chairman tree": "主席树",
    "balanced tree": "平衡树",
    "binary lifting": "倍增",
    "randomization": "随机化",
    "euler tour": "欧拉回路",
    "euler path": "欧拉回路",
    "bipartite graph": "二分图",
    "min cut": "最小割",
    "minimum cut": "最小割",
    "cost flow": "费用流",
    "mcmf": "费用流",
    "linear programming": "线性规划",
    "gaussian elimination": "高斯消元",
    "linear basis": "线性基",
    "basis": "线性基",
    "matrix exponentiation": "矩阵加速",
    "matrix multiplication": "矩阵乘法",
    "inclusion exclusion": "容斥原理",
    "generating function": "生成函数",
    "polynomial": "多项式",
    "discrete log": "BSGS",
    "quadratic residue": "二次剩余",
    "primitive root": "原根",
    "modular inverse": "逆元",
    "palindromic tree": "PAM",
    "palindromic automaton": "PAM",
    "fast walsh-hadamard transform": "FWT",
    "sqrt decomposition": "分块",
    "block decomposition": "分块",
    "functional graph": "基环树",
    "pseudo tree": "基环树",
    "dancing links": "Dancing Links",
    "manacher": "Manacher",
    "floyd": "Floyd",
    "floyd-warshall": "Floyd",
    "a-star": "A*",
    "astar": "A*",
    "ad-hoc": "Ad-hoc",
    "wqs binary search": "wqs 二分",
    "aliens trick": "wqs 二分",
    "slope trick": "斜率维护技巧",
    "little girl and tree": "树剖",
    "merge sort tree": "线段树合并",
    "hash": "哈希",
    "hashing": "哈希",

    # ── 中文同义词合并 ──
    "枚举": "暴力枚举",
    "哈希表": "哈希",
    "概率论": "概率",
    "排列组合": "组合数学",
    "极角排序": "排序",
    "分类讨论": "构造",
}


# Luogu Chinese tag name → canonical Chinese name normalization
# Only non-identity entries: if a tag is not in this dict, it's already canonical.
LG_TAG_NORMALIZE = {
    # ---- Rule 1: known abbreviations → use abbreviation ----
    "广度优先搜索 BFS": "BFS",
    "深度优先搜索 DFS": "DFS",
    "快速傅里叶变换 FFT": "FFT",
    "最近公共祖先 LCA": "LCA",
    "后缀自动机 SAM": "SAM",
    "后缀数组 SA": "SA",
    "启发式迭代加深搜索 IDA*": "IDA*",
    "快速数论变换 NTT": "NTT",
    "中国剩余定理 CRT": "CRT",
    "快速沃尔什变换 FWT": "FWT",
    "快速莫比乌斯变换 FMT": "FMT",
    "回文自动机 PAM": "PAM",
    "动态树 LCT": "LCT",
    "大步小步算法 BSGS": "BSGS",
    "KMP 算法": "KMP",
    "Manacher 算法": "Manacher",
    "Floyd 算法": "Floyd",
    "A*  算法": "A*",
    "KTT / Kinetic Tournament Tree": "KTT",

    # ---- Rule 2a: strip trailing English suffix ----
    "动态规划 DP": "动态规划",
    "哈希 hashing": "哈希",
    "最大公约数 gcd": "最大公约数",
    "字典树 Trie": "字典树",
    "双指针 two-pointer": "双指针",
    "爬山算法 Local search": "爬山算法",
    "cdq 分治": "CDQ 分治",
    "吉司机线段树 segment tree beats": "吉司机线段树",
    "折半搜索 meet in the middle": "折半搜索",
    "随机游走 Markov Chain": "随机游走",
    "斜率维护技巧 slope trick": "斜率维护技巧",
    "闵可夫斯基和 Minkowski sum": "闵可夫斯基和",

    # ---- Rule 2b: parenthesized — prefer inner concept name ----
    "颜色段均摊（珂朵莉树 ODT）": "珂朵莉树",
    "凸完全单调性（wqs 二分）": "wqs 二分",
    "二区间合并（猫树分治）": "猫树分治",
    "字符串（入门）": "字符串",
    "Berlekamp-Massey(BM) 算法": "BM 算法",
}


def _normalize_single(tag: str) -> str:
    """Normalize one tag: LG_TAG_NORMALIZE first, then TAG_NORMALIZE."""
    tag = tag.strip()
    if not tag or tag == "*special":
        return ""
    # Step 1: Luogu-specific normalization (abbreviation preference, strip suffixes)
    tag = LG_TAG_NORMALIZE.get(tag, tag)
    # Step 2: global English→Chinese + synonym merge
    tag = TAG_NORMALIZE.get(tag.lower(), tag)
    return tag


# Monster tags that should be split into multiple tags
_MONSTER_SPLIT = {
    "素数判断,质数,筛法": ["素数判断", "筛法"],
}


def normalize_tags(tags: list[str]) -> list[str]:
    """Normalize a list of tags: deduplicate, merge synonyms, split monster tags."""
    seen = set()
    result = []
    for t in tags:
        t = t.strip()
        if not t or t == "*special":
            continue
        # Check for monster tag split first
        if t in _MONSTER_SPLIT:
            for split_tag in _MONSTER_SPLIT[t]:
                split_tag = _normalize_single(split_tag)
                if split_tag and split_tag not in seen:
                    seen.add(split_tag)
                    result.append(split_tag)
            continue
        canonical = _normalize_single(t)
        if canonical and canonical not in seen:
            seen.add(canonical)
            result.append(canonical)
    return result


def cn_tag(tag: str) -> str:
    """Return Chinese display name for a tag, or the original if unknown."""
    return TAG_CN.get(tag.lower(), tag)

