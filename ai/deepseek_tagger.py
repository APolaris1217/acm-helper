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
]


def get_api_key() -> str:
    """从 email_config.json 获取 DeepSeek API Key"""
    cfg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "email_config.json")
    if os.path.exists(cfg_path):
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            return cfg.get("deepseek_api_key", "")
    return ""


def auto_tag(problem_titles: list[str]) -> list[list[str]]:
    """为题目列表自动推断算法标签

    Args:
        problem_titles: 题目名称列表，如 ["P1001 A+B Problem", "2065E - White Magic"]

    Returns:
        [[tag1, tag2], ...] 每个题目的标签列表
    """
    api_key = get_api_key()
    if not api_key:
        raise Exception("未配置 DeepSeek API Key。请在「周报设置」页面填写 API Key。")

    tag_list = ", ".join(KNOWN_TAGS)
    titles_text = "\n".join(f"{i+1}. {t}" for i, t in enumerate(problem_titles))

    prompt = f"""你是一名算法竞赛专家。请根据以下题目名称，推断每道题涉及的算法标签。

可选标签（只能从以下列表中选择）：
{tag_list}

题目列表：
{titles_text}

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


def auto_tag_batch(problems: list[dict], batch_size: int = 20) -> dict[str, list[str]]:
    """批量自动打标签

    Args:
        problems: [{"problem_id": "P1001", "title": "A+B Problem"}, ...]
        batch_size: 每批处理的题目数

    Returns:
        {"P1001": ["implementation", "math"], ...}
    """
    result = {}
    for i in range(0, len(problems), batch_size):
        batch = problems[i:i + batch_size]
        titles = [p["title"] for p in batch]
        try:
            tags_list = auto_tag(titles)
            for p, tags in zip(batch, tags_list):
                # Filter to only known tags
                valid = [t.lower() for t in tags if t.lower() in KNOWN_TAGS]
                result[p["problem_id"]] = valid
        except Exception as e:
            print(f"  [TAGGER] batch {i // batch_size} failed: {e}")
            for p in batch:
                result[p["problem_id"]] = []
    return result
