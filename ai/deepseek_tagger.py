"""DeepSeek AI 自动打标签 — 为无标签题目推断算法标签"""
import json
import requests
import os

DEEPSEEK_BASE = "https://api.deepseek.com/v1"

# Standard ACM algorithm tags that DeepSeek can choose from
KNOWN_TAGS = [
    "dp", "greedy", "math", "graphs", "data structures", "implementation",
    "constructive algorithms", "brute force", "sortings", "strings",
    "binary search", "number theory", "combinatorics", "geometry", "trees",
    "dfs and similar", "shortest paths", "two pointers", "bitmasks",
    "divide and conquer", "flows", "games", "hashing", "probabilities",
    "matrices", "dsu", "fft", "interactive", "ternary search",
    "meet-in-the-middle", "chinese remainder theorem", "expression parsing",
    "string suffix structures", "schedules",
    "search", "simulation", "prefix sum", "bfs", "stl",
    "graph", "graph matchings", "2-sat",
    # Extended tags for broader algorithm coverage
    "segment tree", "binary indexed tree", "fenwick tree",
    "scc", "tarjan", "lca", "kmp", "sieve",
    "sparse table", "suffix automaton", "suffix array", "trie",
    "topological sort", "mst", "minimum spanning tree",
    "knapsack", "digit dp", "interval dp", "tree dp",
    "state compression", "lct", "link cut tree",
    "heavy light decomposition", "centroid decomposition",
    "monotonic queue", "monotonic stack",
    "expectation", "tree diameter", "virtual tree",
    "binary lifting", "randomization", "euler tour",
    "bipartite graph", "min cut", "cost flow", "mcmf",
    "gaussian elimination", "linear basis",
    "matrix exponentiation", "matrix multiplication",
    "inclusion exclusion", "generating function", "polynomial",
    "sqrt decomposition", "convex hull", "sweep line",
    "balanced tree", "chairman tree", "persistent segment tree",
    "difference array", "cdq divide and conquer",
    "mo's algorithm", "discrete log", "convex hull trick",
    "functional graph", "floyd", "floyd-warshall",
    "manacher", "a-star", "palindromic tree",
    "wqs binary search", "slope trick", "ad-hoc",
]


def get_api_key() -> str:
    """从 email_config.json 获取 DeepSeek API Key"""
    cfg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "email_config.json")
    if os.path.exists(cfg_path):
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            return cfg.get("deepseek_api_key", "")
    return ""


def auto_tag(problems: list[dict]) -> list[list[str]]:
    """为题目列表自动推断算法标签

    Args:
        problems: [{"title": "A+B Problem", "content": "题目描述...", "platform": "atcoder", "difficulty": 1200}, ...]
                  content 字段可选，有则传入题目正文供 AI 分析

    Returns:
        [[tag1, tag2], ...] 每个题目的标签列表
    """
    api_key = get_api_key()
    if not api_key:
        raise Exception("未配置 DeepSeek API Key。请在同步弹窗中填写 API Key。")

    tag_list = ", ".join(KNOWN_TAGS)

    # Build problem list text with content when available
    lines = []
    for i, p in enumerate(problems):
        title = p.get("title", p) if isinstance(p, dict) else str(p)
        content = p.get("content", "") if isinstance(p, dict) else ""
        diff = p.get("difficulty", 0) if isinstance(p, dict) else 0
        plat = p.get("platform", "") if isinstance(p, dict) else ""

        line = f"{i+1}. {title}"
        extra = []
        if diff: extra.append(f"难度: {diff}")
        if plat: extra.append(f"平台: {plat}")
        if extra: line += f" ({', '.join(extra)})"
        if content:
            line += f"\n   题目内容: {content[:1500]}"  # Limit to 1500 chars
        lines.append(line)

    problems_text = "\n\n".join(lines)

    prompt = f"""你是一名算法竞赛专家。请根据题目信息（标题、难度、题目内容），推断每道题涉及的算法标签。

可选标签（只能从以下列表中选择）：
{tag_list}

题目列表：
{problems_text}

请返回 JSON 数组，每个元素是对应题目的标签列表（小写英文）：
```json
[
  ["dp", "greedy"],
  ["math", "number theory"],
  ...
]
```

只返回 JSON，不要解释。"""

    resp = requests.post(
        f"{DEEPSEEK_BASE}/chat/completions",
        json={
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 2048,
        },
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=60,
    )
    data = resp.json()
    if "error" in data:
        raise Exception(f"DeepSeek API 错误: {data['error']}")

    content = data["choices"][0]["message"]["content"]
    # Extract JSON from response (may be wrapped in ```json ... ```)
    if "```" in content:
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    return json.loads(content)


def auto_tag_batch(problems: list[dict], batch_size: int = 15) -> dict[str, list[str]]:
    """批量自动打标签

    Args:
        problems: [{"problem_id": "P1001", "title": "A+B Problem", "content": "...", "platform": "atcoder"}, ...]
        batch_size: 每批处理的题目数 (带 content 时减小批次避免超 token)

    Returns:
        {"P1001": ["implementation", "math"], ...}
    """
    result = {}
    for i in range(0, len(problems), batch_size):
        batch = problems[i:i + batch_size]
        # Use smaller batches when content is included (more tokens per problem)
        has_content = any(p.get("content") for p in batch)
        effective_batch = max(5, batch_size // 3) if has_content else batch_size

        # Re-chunk if needed
        sub_batches = []
        for j in range(0, len(batch), effective_batch):
            sub_batches.append(batch[j:j + effective_batch])

        for sub in sub_batches:
            try:
                tags_list = auto_tag(sub)
                for p, tags in zip(sub, tags_list):
                    # Filter to only known tags
                    valid = [t.lower() for t in tags if t.lower() in KNOWN_TAGS]
                    result[p["problem_id"]] = valid
            except Exception as e:
                print(f"  [TAGGER] batch failed: {e}")
                for p in sub:
                    result[p["problem_id"]] = []
    return result
