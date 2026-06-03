================================================================================
  ACM-Helper 跨平台OJ刷题记录与薄弱分析系统
  系统说明文件 (readme.txt)
================================================================================

一、系统登录信息
--------------------------------------------------------------------------------
  本系统为本地单用户应用，无需登录认证。

  默认用户：默认用户（ID=1）
  密码：无（本地单用户模式，启动即可使用）

  浏览器打开 http://localhost:8765 即可访问全部功能。

  如需支持多用户，可手动在 app_users 表中插入新用户记录，
  并在 platform_accounts 表中关联对应的 OJ 平台账号。


二、OJ 平台账号绑定
--------------------------------------------------------------------------------
  各平台的账号在「账户绑定」页面配置，存储在 bound_accounts.json：

  ┌────────────┬───────────────┬──────────────────────────┐
  │ 平台       │ 用户名格式    │ 是否需要 Cookie          │
  ├────────────┼───────────────┼──────────────────────────┤
  │ Codeforces │ 英文用户名    │ 否                       │
  │ AtCoder    │ 英文用户名    │ 否（需 curl_cffi 绕过 CF）│
  │ Luogu      │ 数字 UID      │ 是（__client_id + _uid） │
  │ NowCoder   │ 数字 UID      │ 是（登录 Cookie）        │
  └────────────┴───────────────┴──────────────────────────┘

  洛谷 Cookie 获取方式：浏览器登录 luogu.com.cn → F12 → Application →
  Cookies → 复制 __client_id 和 _uid 的值。


三、邮件周报配置
--------------------------------------------------------------------------------
  1. 复制 sender_config.example.json 为 sender_config.json
  2. 填入 SMTP 发件邮箱信息：
     {
       "smtp_host": "smtp.qq.com",
       "smtp_port": 465,
       "sender_email": "your_email@qq.com",
       "sender_password": "邮箱授权码（非登录密码）"
     }
  3. 在「报告设置」页面配置收件邮箱、发送时间、DeepSeek API Key
  4. 邮箱授权码获取（以QQ邮箱为例）：
     设置 → 账户 → POP3/SMTP服务 → 开启 → 生成授权码


四、启动方式
--------------------------------------------------------------------------------
  # 1. 安装依赖
  pip install requests beautifulsoup4 curl_cffi markdown

  # 2. 启动服务（注意：必须设置 NO_PROXY=* 避免代理干扰）
  NO_PROXY=* python server.py

  # 3. 浏览器访问
  http://localhost:8765


五、数据库信息
--------------------------------------------------------------------------------
  数据库文件：acm_helper.db（SQLite3）
  数据库表：app_users, platform_accounts, problems, tags, problem_tags,
            submissions, weekly_reports, deepseek_config, analysis_snapshots
  视图：v_daily_activity, v_tag_weakness_ranking, v_user_submission_stats
  触发器：trg_app_users_updated_at, trg_platform_accounts_updated_at

  SQL 脚本位置：sql/ 目录
  ├── schema.sql    — 完整建表 DDL
  ├── seed.sql      — 初始数据
  ├── triggers.sql  — 触发器定义
  ├── views.sql     — 视图定义
  └── all.sql       — 以上全部整合


六、功能模块
--------------------------------------------------------------------------------
  1. 记录管理 — 查看/筛选/编辑/删除跨平台刷题记录
  2. 数据总览 — Chart.js 仪表盘（趋势、分布、AC率）
  3. 薄弱分析 — Top-5 薄弱知识点多维评分排名
  4. 账户绑定 — 绑定各 OJ 平台账号
  5. 报告设置 — AI 周报邮件推送配置


七、注意事项
--------------------------------------------------------------------------------
  • Python 版本：3.10+
  • 本地如启用了 HTTP 代理，必须设置 NO_PROXY=*
  • 洛谷和 AtCoder 需要 curl_cffi 绕过 Cloudflare 防护
  • 洛谷和 NowCoder 的 Cookie 过期后需重新获取
  • 数据库中所有时间字段使用 ISO 8601 格式（UTC）
  • 端口默认 8765，如需修改请编辑 server.py 末尾


八、项目仓库
--------------------------------------------------------------------------------
  GitHub: https://github.com/APolaris1217/acm-helper
  分支说明：
  - master    — 原始版本（基础功能）
  - database  — 数据库课程设计版本（含 SQL 脚本、ORM 模型）
