# ACM Helper

跨平台 OJ 刷题记录与薄弱分析工具。自动同步 Codeforces、洛谷、AtCoder、NowCoder 四平台提交，多维度薄弱知识点评分，支持 AI 周报邮件推送。

## 快速开始

```bash
git clone https://github.com/APolaris1217/acm-helper.git
cd acm-helper
```

### 一键启动（推荐）

```powershell
# Windows:
powershell -ExecutionPolicy Bypass -File setup.ps1

# Linux/Mac:
bash setup.sh
```

### 手动配置

```bash
# 1. 安装依赖
pip install requests beautifulsoup4 curl_cffi markdown

# 2. 复制配置文件模板
cp sender_config.example.json sender_config.json
cp email_config.example.json email_config.json
cp bound_accounts.example.json bound_accounts.json

# 3. 编辑配置文件（可选，不影响基础功能）
#    sender_config.json  → SMTP 发件信息
#    email_config.json   → 收件邮箱 + DeepSeek Key
#    bound_accounts.json → OJ 平台用户名

# 4. 启动
NO_PROXY=* python server.py
```

浏览器打开 `http://localhost:8765`。

## 项目结构

```
├── server.py              # HTTP 服务 + API 路由 + 平台抓取
├── tracker.html           # 前端单页 (vanilla JS + Chart.js + marked)
├── scheduler.py           # 定时调度 (周报 + 定时同步)
├── report_generator.py    # AI 周报生成 (DeepSeek)
├── email_sender.py        # SMTP 邮件发送
├── analyzer.py            # v1 薄弱分析 (行为模式加权)
├── weakness_scorer.py     # v2 薄弱评分 (五维加权)
├── tag_map.py             # 中英文标签映射
├── requirement.rm         # 周报 Prompt 模板
├── crawler/               # 多平台爬虫 + 任务管理
├── db/                    # SQLite 数据层
├── engine/                # v2 策略引擎 (多规则)
└── ai/                    # DeepSeek 标签推断
```

## 使用流程

1. **绑定账户** — 在「账户绑定」页面添加各平台用户名/Cookie
2. **同步数据** — 点击「同步全部已绑定账户」（服务器启动时也会自动同步）
3. **查看分析** — 切到「数据总览」「薄弱分析」查看图表和 Top5
4. **周报推送** — 配置邮箱后可预览/发送 AI 生成的训练周报

## 薄弱知识点评分规则

五维度加权评分，样本量修正，过滤 <5 题的知识点：

| 维度 | 权重 | 说明 |
|---|---|---|
| AC 率 | 40% | 越低越薄弱 |
| 平均尝试次数 | 20% | 越多越薄弱 (Min-Max 归一化) |
| 解题耗时 | 15% | 越长越薄弱 |
| 后半区失衡 | 15% | 前后半区正确率差距 |
| 学习斜率 | 10% | 每周 AC 率线性回归 |

`finalScore = rawScore × min(1, problemCount / 20)`

## 配置说明

| 文件 | 用途 | 模板文件 | Git |
|---|---|---|---|
| `sender_config.json` | SMTP 服务器/发件邮箱/授权码 | `sender_config.example.json` | ❌ 不入库 |
| `email_config.json` | 收件邮箱/调度/DeepSeek Key | `email_config.example.json` | ❌ 不入库 |
| `bound_accounts.json` | 各平台账户/Cookie | `bound_accounts.example.json` | ❌ 不入库 |
| `acm_helper.db` | SQLite 数据 | (首次启动自动创建) | ❌ 不入库 |

## 注意事项

- 需要 Python 3.10+
- 洛谷和 AtCoder 需要 `curl_cffi` 绕过 Cloudflare
- 洛谷和 NowCoder 需要登录 Cookie
- 本地启用了 HTTP 代理时需设置 `NO_PROXY=*`
- Chart.js 和 marked.js 已本地化，无需外网 CDN
