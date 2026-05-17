# 做题记录与薄弱分析平台

一个本地运行的竞技编程刷题记录工具，支持 **洛谷**、**Codeforces**、**AtCoder** 三大平台的自动同步，并根据提交行为模式进行智能薄弱点分析。

## 功能特性

### 记录管理
- **多平台同步** — 自动从洛谷、Codeforces、AtCoder 拉取提交记录
- **手动录入** — 支持手动添加、编辑、删除题目记录
- **字段完整** — 平台、题号、题目名、难度、标签、结果、日期、耗时、语言、备注
- **筛选与分页** — 表格支持多条件过滤，自动分页
- **导入/导出** — 支持 JSON 格式数据备份与恢复
- **本地存储** — 数据保存在浏览器 localStorage，无需数据库

### 数据总览
- **统计卡片** — 总题数、总提交数、AC 率、周活跃、连续打卡天数
- **年度热力图** — 近 365 天每日提交量可视化
- **平台分布** — 各平台提交占比环形图
- **30 天趋势** — 近期刷题数量柱状图
- **结果分布** — AC / WA / TLE / RE 等结果类型占比

### 薄弱分析
- **行为模式分析** — 基于提交行为而非仅靠通过率评估薄弱点
- **三部分报告**：
  1. **刷题画像** — 编码习惯（CE/RE/盲交）、算法思维（WA/TLE/长间隔）、学习习惯（刷题量极端、疑似依赖题解、未解决问题）
  2. **薄弱排名** — 按标签排名，含加权得分、AC 率、错误分布、典型题目列表
  3. **改进建议** — 针对每个薄弱领域的具体可执行建议
- **可视化** — 标签 AC 率柱状图、难度-AC 率散点图、平台 AC 率雷达图

## 技术栈

| 组件 | 技术 |
|------|------|
| 后端 | Python 3（标准库 `http.server`） |
| 前端 | 单页 HTML + 原生 JavaScript |
| 图表 | Chart.js v4.4.7（CDN 加载） |
| 数据存储 | 浏览器 localStorage + 服务端 JSON 缓存 |
| 平台 API | Codeforces API / kenkoooo AtCoder API / 洛谷内部 API |
| 反爬 | `curl_cffi`（绕过 Cloudflare TLS 指纹检测） |

## 项目结构

```
.
├── server.py              # HTTP 代理服务 + 三大平台 API 抓取器
├── analyzer.py            # 薄弱分析引擎
├── tracker.html           # 主前端页面（含同步 + 行为分析）
├── problem-tracker.html   # 早期简化版前端（仅手动录入）
├── cache.json             # API 响应缓存（key: 平台+用户, TTL: 30-60 分钟）
└── matrix_fast_pow.cpp    # 无关的 C++ 算法题解（矩阵快速幂）
```

## 快速开始

### 环境要求

- Python 3.7+
- （可选）`curl_cffi` — 洛谷和 AtCoder 同步需要，用于绕过 Cloudflare 防护

### 安装

```bash
# 克隆仓库
git clone <repo-url>
cd auto

# 安装可选依赖（如需洛谷/AtCoder 同步）
pip install curl_cffi
```

### 启动

```bash
python server.py
```

服务启动在 `http://localhost:8765`，浏览器打开即可使用。

> **注意**：Codeforces 同步无需任何额外配置。洛谷同步需要提供浏览器 Cookie（详见页面提示），AtCoder 同步需要安装 `curl_cffi`。

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/` | 前端页面 |
| `GET` | `/api/fetch/codeforces?handle={handle}` | 同步 Codeforces 提交 |
| `GET` | `/api/fetch/atcoder?username={username}` | 同步 AtCoder 提交 |
| `GET` | `/api/fetch/luogu?uid={uid}&cookie={cookie}` | 同步洛谷提交 |
| `POST` | `/api/analyze` | 提交 JSON 数组，返回薄弱分析报告 |

## 薄弱分析原理

分析引擎不是简单地按标签通过率排序，而是结合**提交行为模式**进行加权评估：

### 尝试等级分类
每道题根据通过前尝试次数分为 5 个等级：一次过、2-3 次、4-7 次、8+ 次、从未通过。

### 加权惩罚规则
| 行为 | 扣分 |
|------|------|
| WA（答案错误） | 10 |
| TLE（超时） | 15 |
| RE（运行错误） | 12 |
| CE（编译错误） | 8 |
| 盲交（间隔 < 60s） | 20 |
| 长间隔（> 30min） | 5 |
| 疑似抄袭（短时间内大量高难度题一次过） | 40 |
| 疑似参考（标签历史不连续但一次过） | 30 |

### 报告生成
系统汇总每个标签下所有题目的加权得分，生成包含刷题画像、薄弱排名、改进建议的综合报告。

## 统一提交格式

所有平台 API 返回的原始数据被转换为统一的提交记录格式：

```json
{
  "platform": "Codeforces | Luogu | AtCoder",
  "problemId": "题号",
  "name": "题目名称",
  "difficulty": 0,
  "tags": ["标签1", "标签2"],
  "result": "Accepted | Wrong Answer | Time Limit Exceeded | ...",
  "date": "2024-01-15",
  "language": "C++ | Python | ..."
}
```

## 数据缓存

服务端对 API 数据进行文件缓存（`cache.json`），Codeforces 缓存 30 分钟，AtCoder 和洛谷缓存 60 分钟，避免频繁请求触发平台限制。
