"""Shared algorithm tag → Chinese display name mapping."""
TAG_CN = {
    "dp": "动态规划", "greedy": "贪心", "math": "数学", "graphs": "图论",
    "graph": "图论", "data structures": "数据结构", "implementation": "模拟",
    "constructive algorithms": "构造", "brute force": "暴力枚举",
    "sortings": "排序", "strings": "字符串", "binary search": "二分",
    "number theory": "数学", "combinatorics": "组合数学", "geometry": "计算几何",
    "trees": "树", "dfs and similar": "DFS", "shortest paths": "最短路",
    "two pointers": "双指针", "bitmasks": "位运算", "divide and conquer": "分治",
    "flows": "网络流", "games": "博弈论", "hashing": "哈希", "probabilities": "概率",
    "matrices": "矩阵", "string suffix structures": "后缀结构",
    "dsu": "并查集", "schedules": "调度", "chinese remainder theorem": "中国剩余定理",
    "ternary search": "三分", "meet-in-the-middle": "二分",
    "fft": "FFT", "interactive": "交互", "expression parsing": "表达式解析",
    "search": "搜索", "simulation": "模拟", "prefix sum": "前缀和",
    "bfs": "BFS", "stl": "STL",
    "graph matchings": "图匹配",
}


def cn_tag(tag: str) -> str:
    """Return Chinese display name for a tag, or the original if unknown."""
    return TAG_CN.get(tag.lower(), tag)
