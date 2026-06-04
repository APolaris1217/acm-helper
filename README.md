# ACM Helper

跨平台 OJ 刷题记录与薄弱分析工具。自动同步 **Codeforces、洛谷、AtCoder、NowCoder** 四平台提交数据，多维度薄弱知识点评分，支持 AI 周报邮件推送。

纯本地运行，浏览器访问 `http://localhost:8765`，无需联网（同步/推送时除外）。

---

## 目录

- [环境要求](#环境要求)
- [快速开始（推荐）](#快速开始推荐)
- [手动安装](#手动安装)
- [配置文件详解](#配置文件详解)
- [使用流程](#使用流程)
- [功能模块](#功能模块)
- [薄弱评分规则](#薄弱评分规则)
- [常见问题](#常见问题)
- [项目结构](#项目结构)
- [参考项目](#参考项目)

---

## 环境要求

| 依赖 | 版本 | 说明 |
|------|------|------|
| Python | 3.10+ | 必须包含 pip |
| 浏览器 | Chrome / Edge / Firefox | 访问前端界面 |
| Git | 任意版本 | 仅克隆项目时需要 |

可选依赖（不影响基础功能）：

| 依赖 | 用途 |
|------|------|
| `curl_cffi` | 绕过 AtCoder/洛谷的 Cloudflare 防护 |

---

## 快速开始（推荐）

### 第一步：克隆项目

```bash
git clone https://github.com/APolaris1217/acm-helper.git
cd acm-helper
```

### 第二步：运行一键启动脚本

**Windows**（在 PowerShell 终端中运行）：

```powershell
# 1. 如果脚本执行被系统阻止，先临时放行（仅本次有效）：
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# 2. 运行脚本：
.\setup.ps1
```

> ⚠️ **不要在命令前加 `powershell`**。如果已经在 PowerShell 里（提示符以 `PS` 开头），直接运行 `.\setup.ps1` 即可。
>
> 如果当前在 CMD（提示符是 `>`），先输入 `powershell` 回车进入 PowerShell，再执行上述命令。
>
> `powershell -ExecutionPolicy Bypass -File setup.ps1` 这个写法**只用于 CMD**，在 PowerShell 内部无效。

脚本会自动完成：查找可用的 Python → 安装依赖 → 复制配置文件模板 → 询问是否启动服务器。

**Linux / Mac**：

```bash
bash setup.sh
```

### 第三步：打开浏览器

访问 `http://localhost:8765`。

---

## 手动安装

如果一键脚本不适用你的环境，可以手动执行：

```bash
# 1. 安装依赖
python -m pip install requests beautifulsoup4 markdown

# 2. （可选）安装 curl_cffi 以支持 AtCoder/洛谷
python -m pip install curl_cffi

# 3. 复制配置文件模板
cp sender_config.example.json sender_config.json
cp email_config.example.json email_config.json
cp bound_accounts.example.json bound_accounts.json

# 4. 启动服务器
NO_PROXY=* python server.py
```

> **注意**：如果在 PowerShell 中，`cp` 应替换为 `Copy-Item`，`NO_PROXY=*` 应替换为 `$env:NO_PROXY = "*"`。

---

## 配置文件详解

以下三个配置文件首次运行时会自动从 `.example.json` 模板创建。**不配置也可以使用基础功能**（查看记录、手动录入、薄弱分析），仅同步 OJ 平台和邮件推送需要配置。

### bound_accounts.json — OJ 平台账户

```json
{
  "codeforces": {
    "username": "你的Codeforces用户名",
    "cookie": ""
  },
  "atcoder": {
    "username": "你的AtCoder用户名",
    "cookie": ""
  },
  "luogu": {
    "username": "你的洛谷UID（数字）",
    "cookie": "__client_id=你的client_id; _uid=你的UID"
  },
  "nowcoder": {
    "username": "你的NowCoder用户ID",
    "cookie": "你的登录Cookie"
  }
}
```

| 平台 | 是否需要 Cookie | 获取方式 |
|------|:--:|------|
| Codeforces | 否 | 填用户名即可 |
| AtCoder | 否 | 填用户名即可（需 `curl_cffi` 绕过 Cloudflare） |
| 洛谷 | **是** | 浏览器登录 → F12 → Application → Cookies → 复制 `__client_id` 和 `_uid` |
| NowCoder | **是** | 浏览器登录 → F12 → Application → Cookies → 复制全部 Cookie |

Cookie 过期后需重新获取。

### sender_config.json — SMTP 发件邮箱

```json
{
  "smtp_host": "smtp.qq.com",
  "smtp_port": 587,
  "sender_email": "你的QQ号@qq.com",
  "sender_password": "QQ邮箱授权码（不是QQ登录密码）"
}
```

**QQ 邮箱授权码获取**：登录 QQ 邮箱 → 设置 → 账户 → POP3/SMTP 服务 → 开启 → 生成授权码。

其他邮箱（163、Gmail 等）请填写对应的 SMTP 服务器地址和端口。

### email_config.json — 收件邮箱 + 周报调度 + AI Key

```json
{
  "receiver_email": "接收周报的邮箱@qq.com",
  "schedule_day": 1,
  "schedule_hour": 9,
  "enabled": false,
  "deepseek_api_key": "sk-你的DeepSeek-API-Key"
}
```

| 字段 | 说明 |
|------|------|
| `receiver_email` | 接收 AI 周报的邮箱地址 |
| `schedule_day` | 每周几发送（1=周一，7=周日） |
| `schedule_hour` | 发送时间（0-23，整点） |
| `enabled` | 是否启用定时发送（`true` / `false`） |
| `deepseek_api_key` | DeepSeek API Key，用于 AI 标签推断 + 周报生成 |

**DeepSeek API Key 获取**：访问 [platform.deepseek.com](https://platform.deepseek.com) → API Keys → 创建新 Key。不需要 AI 功能可跳过。

---

## 使用流程

1. **绑定账户** — 启动服务后，浏览器打开 `http://localhost:8765`，点击「账户绑定」卡片，填写各平台用户名和 Cookie，点击保存。
2. **同步数据** — 点击「同步全部已绑定账户」，等待进度完成。服务器启动时也会自动同步一轮。
3. **查看记录** — 在「记录管理」页面查看、筛选、编辑所有同步的刷题记录。
4. **数据分析** — 切到「数据总览」查看图表仪表盘（趋势、分布、AC 率），切到「薄弱分析」查看 Top-5 薄弱知识点。
5. **周报推送** — 在「报告设置」页面配置邮箱和 API Key 后，可预览或发送 AI 生成的训练周报。

---

## 功能模块

| 模块 | 功能 |
|------|------|
| 记录管理 | 查看 / 筛选 / 编辑 / 删除跨平台刷题记录 |
| 数据总览 | Chart.js 仪表盘（提交趋势、标签分布、AC 率） |
| 薄弱分析 | Top-5 薄弱知识点多维评分排名 |
| 账户绑定 | 绑定各 OJ 平台账号（Codeforces / AtCoder / 洛谷 / NowCoder） |
| 报告设置 | AI 周报配置（收件邮箱、发送时间、DeepSeek Key、手动预览/发送） |

---

## 薄弱评分规则

五维度加权评分，结果经过样本量修正，过滤不足 5 题的知识点：

| 维度 | 权重 | 说明 |
|------|:---:|------|
| AC 率 | 40% | 越低越薄弱 |
| 平均尝试次数 | 20% | 越多越薄弱（Min-Max 归一化） |
| 解题耗时 | 15% | 越长越薄弱 |
| 后半区失衡 | 15% | 前后半区正确率差距（检测"会做但容易后面出错"的模式） |
| 学习斜率 | 10% | 每周 AC 率的线性回归斜率（衡量进步趋势） |

```
最终分数 = 原始分数 × min(1, 题目数量 / 20)
```

---

## 常见问题

### Q: 运行 `.\setup.ps1` 提示"无法加载...禁止运行脚本"

在 PowerShell 中先执行：
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```
然后再运行 `.\setup.ps1`。这只是临时放行，关掉窗口后恢复。

### Q: 安装依赖时报错 `No module named pip`

你的 Python 版本不包含 pip。可以尝试：
```powershell
python -m ensurepip --default-pip
```
如果还不行，建议从 [python.org](https://www.python.org/downloads/) 重新安装 Python（安装时勾选"Add Python to PATH"和"pip"）。

### Q: 系统有多个 Python，脚本选错了

脚本会自动跳过 msys64/mingw/cygwin 等精简版 Python，优先选择包含 pip 的官方版本。如果你安装了 `py` 启动器，会优先使用 `py -3` 指向的最新版。

### Q: 启动时报 `Address already in use`

端口 8765 被占用，通常是上次运行没正常退出。在 PowerShell 中：
```powershell
taskkill /F /IM python.exe
```
然后重新启动。

### Q: 同步数据失败 / 超时

1. 检查是否设置了 `NO_PROXY=*`（如果你开了代理软件）
2. 洛谷和 AtCoder 需要 `curl_cffi`（`python -m pip install curl_cffi`）
3. 洛谷和 NowCoder 需要有效的登录 Cookie（Cookie 过期后需重新获取）

### Q: Cookie 怎么获取

1. 用浏览器登录对应 OJ 平台
2. 按 `F12` 打开开发者工具
3. 切到 `Application`（应用程序）标签
4. 左侧找到 `Cookies`，点击对应域名
5. 复制需要的 cookie 名称和值，按格式填入 `bound_accounts.json`

### Q: 如何清除所有数据重新开始

删除以下文件后重启服务：
- `acm_helper.db` — 数据库
- `cache.json` — 缓存
- `bound_accounts.json` — 账户绑定
- `email_config.json` — 邮箱配置

或者点击界面中的「清除数据」按钮。

### Q: 端口想换成别的

编辑 `server.py` 末尾，将 `8765` 改成你想要的端口号。

---

## 项目结构

```
├── server.py              # HTTP 服务 + API 路由 + 平台抓取
├── tracker.html           # 前端单页应用（vanilla JS + Chart.js + marked）
├── scheduler.py           # 定时调度器（周报 + 定时同步）
├── report_generator.py    # AI 周报生成（DeepSeek）
├── email_sender.py        # SMTP 邮件发送
├── analyzer.py            # v1 薄弱分析（行为模式加权）
├── weakness_scorer.py     # v2 薄弱评分（五维加权）
├── tag_map.py             # 中英文标签映射
├── requirement.rm         # 周报 Prompt 模板
├── setup.ps1              # Windows 一键启动脚本
├── setup.sh               # Linux/Mac 一键启动脚本
├── crawler/               # 多平台爬虫 + 任务管理器
├── db/                    # SQLite 数据库层
├── engine/                # v2 分析策略引擎（多规则）
├── ai/                    # DeepSeek 标签推断
├── sql/                   # 数据库 SQL 脚本（schema / seed / triggers / views）
└── *.example.json         # 配置文件模板
```

---

## 参考项目

本项目参考了以下两个优秀项目，在此致谢：

- [cockroach0401/acm-helper](https://github.com/cockroach0401/acm-helper) — 原始 ACM Helper 项目，提供了前端界面框架与多平台抓取的基础架构
- [Liu233w/acm-statistics](https://github.com/Liu233w/acm-statistics) — ACM 竞赛统计数据可视化项目，为数据分析与图表展示提供了参考
