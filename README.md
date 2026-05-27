# ACM Helper

本地竞技编程（OJ）刷题记录与薄弱分析平台，支持 Codeforces、洛谷、AtCoder、NowCoder 多平台提交自动同步，基于提交行为模式进行智能弱点分析，支持每周 AI 报告邮件推送。

## 快速开始

```bash
pip install requests beautifulsoup4 curl_cffi
NO_PROXY=* python server.py
```

浏览器打开 `http://localhost:8765`。

## 项目结构

```
├── server.py              # HTTP 服务 + API 路由 + 平台抓取器
├── tracker.html           # 前端单页 (vanilla JS + Chart.js)
├── analyzer.py            # 薄弱分析引擎 (行为模式加权)
├── scheduler.py           # 每周报告定时调度
├── report_generator.py    # Markdown 报告生成
├── email_sender.py        # SMTP 邮件发送
├── tag_map.py             # 中英文算法标签映射
├── requirement.rm         # 报告模板
├── crawler/               # 多平台爬虫 + 任务管理
├── db/                    # SQLite 数据层
├── engine/                # 新版分析引擎 (策略模式)
└── ai/                    # DeepSeek API 自动标签推断
```

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/` | 前端页面 |
| `GET` | `/api/v2/submissions` | 获取已存储的提交记录 |
| `POST` | `/api/v2/sync-all` | 同步所有绑定账号 |
| `POST` | `/api/v2/crawl/start` | 启动爬虫任务 |
| `GET` | `/api/v2/crawl/progress/{id}` | 查询爬虫进度 |
| `GET` | `/api/v2/analysis/{platform}/{username}` | 薄弱分析 |
| `POST` | `/api/accounts/bind` | 绑定/解绑平台账号 |
| `POST` | `/api/auto-tag` | AI 标签推断 |
| `POST` | `/api/email-config` | SMTP + API Key 配置 |
| `POST` | `/api/scheduler/trigger` | 触发定时报告 |
| `POST` | `/api/analyze` | 薄弱分析 (旧版) |

## 数据流

1. **绑定账号** → POST `/api/accounts/bind`
2. **同步** → POST `/api/v2/sync-all` → 后台线程爬取各平台 → 写入 SQLite
3. **前端加载** → `loadFromServer()` → 合并到 `localStorage.problem_tracker_data`
4. **分析** → 基于 WA/TLE/CE/盲交等行为加权评分 → 生成薄弱报告
