"""邮件发送模块 — 通过 SMTP 发送周报到指定邮箱"""
import smtplib
import json
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "email_config.json")
SENDER_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sender_config.json")

DEFAULT_CONFIG = {
    "receiver_email": "",
    "schedule_day": 1,
    "schedule_hour": 9,
    "enabled": False,
    "deepseek_api_key": "",
}

DEFAULT_SENDER = {
    "smtp_host": "smtp.qq.com",
    "smtp_port": 587,
    "sender_email": "",
    "sender_password": "",
}


def load_config() -> dict:
    """加载用户配置（收件人、调度、AI Key）"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            for k, v in DEFAULT_CONFIG.items():
                cfg.setdefault(k, v)
            return cfg
    return dict(DEFAULT_CONFIG)


def load_sender_config() -> dict:
    """加载发件人配置（SMTP 服务器、邮箱、授权码），后端预置，不暴露给前端"""
    if os.path.exists(SENDER_FILE):
        with open(SENDER_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            for k, v in DEFAULT_SENDER.items():
                cfg.setdefault(k, v)
            return cfg
    return dict(DEFAULT_SENDER)


def save_config(cfg: dict):
    """保存用户配置，自动去除发件人字段（它们在后端专属文件中）"""
    clean = {k: v for k, v in cfg.items() if k in DEFAULT_CONFIG}
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(clean, f, ensure_ascii=False, indent=2)


def send_report(report_markdown: str, subject: str = "") -> bool:
    """发送周报邮件

    Args:
        report_markdown: Markdown 格式的报告正文
        subject: 邮件主题

    Returns:
        True 表示发送成功
    """
    user_cfg = load_config()
    sender_cfg = load_sender_config()

    if not sender_cfg.get("sender_email") or not sender_cfg.get("sender_password"):
        raise Exception("发件人邮箱或授权码未配置（请联系作者配置 sender_config.json）")
    if not user_cfg.get("receiver_email"):
        raise Exception("收件人邮箱未配置")

    subject = subject or f"ACM 训练周报 - {datetime.now().strftime('%Y-%m-%d')}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender_cfg["sender_email"]
    msg["To"] = user_cfg["receiver_email"]

    # 纯文本备选（markdown 作为纯文本可读）
    text_part = MIMEText(report_markdown, "plain", "utf-8")

    # HTML 版本：将 markdown 转换为美观的 HTML 邮件
    try:
        import markdown as md
        md_body = md.markdown(
            report_markdown,
            extensions=['tables', 'fenced_code', 'codehilite', 'nl2br']
        )
    except Exception:
        # 回退：如果 markdown 库不可用，用 <pre> 包裹
        md_body = f"<pre>{report_markdown}</pre>"

    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f3f4f6;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;padding:24px 0;">
<tr><td align="center">
<table width="640" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:10px;overflow:hidden;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
<tr><td style="background:#0d9488;padding:24px 32px;">
<h1 style="color:#fff;margin:0;font-size:20px;">ACM 训练周报</h1>
<p style="color:rgba(255,255,255,0.8);margin:4px 0 0;font-size:13px;">{subject}</p>
</td></tr>
<tr><td style="padding:24px 32px;color:#1e293b;font-size:14px;line-height:1.8;">
<style>
.md-body h1 {{ font-size:18px; border-bottom:2px solid #0d9488; padding-bottom:6px; margin:16px 0 10px; }}
.md-body h2 {{ font-size:15px; color:#0d9488; margin:18px 0 8px; }}
.md-body h3 {{ font-size:14px; margin:14px 0 6px; }}
.md-body ul, .md-body ol {{ padding-left:20px; margin:6px 0; }}
.md-body li {{ margin:3px 0; }}
.md-body code {{ background:#f1f5f9; padding:1px 5px; border-radius:3px; font-family:'Consolas','Courier New',monospace; font-size:12px; }}
.md-body pre {{ background:#1e293b; color:#e2e8f0; padding:12px 16px; border-radius:6px; overflow-x:auto; }}
.md-body pre code {{ background:none; padding:0; color:inherit; }}
.md-body blockquote {{ border-left:3px solid #0d9488; padding:6px 14px; color:#64748b; background:#f0fdfa; border-radius:0 6px 6px 0; margin:8px 0; }}
.md-body table {{ border-collapse:collapse; width:100%; margin:10px 0; }}
.md-body th, .md-body td {{ border:1px solid #e2e8f0; padding:6px 10px; text-align:left; font-size:13px; }}
.md-body th {{ background:#f8fafc; font-weight:600; }}
.md-body strong {{ color:#0f766e; }}
.md-body hr {{ border:none; border-top:1px solid #e2e8f0; margin:16px 0; }}
.md-body a {{ color:#0d9488; }}
</style>
<div class="md-body">
{md_body}
</div>
</td></tr>
<tr><td style="background:#f8fafc;padding:14px 32px;text-align:center;font-size:11px;color:#94a3b8;">
由 ACM Helper 自动生成 &middot; {datetime.now().strftime('%Y-%m-%d %H:%M')}
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>"""
    html_part = MIMEText(html_content, "html", "utf-8")

    msg.attach(text_part)
    msg.attach(html_part)

    try:
        # 绕过本地代理（HTTP_PROXY 会干扰 SMTP 连接）
        os.environ['NO_PROXY'] = '*'
        os.environ['no_proxy'] = '*'
        # 指定 ASCII hostname，避免 Windows 中文主机名导致 SMTP EHLO 编码错误
        server = smtplib.SMTP(sender_cfg["smtp_host"], sender_cfg["smtp_port"], local_hostname="localhost", timeout=30)
        server.starttls()
        server.login(sender_cfg["sender_email"], sender_cfg["sender_password"])
        server.sendmail(sender_cfg["sender_email"], [user_cfg["receiver_email"]], msg.as_string())
        server.quit()
        print(f"  [EMAIL] 邮件已发送: {subject} → {user_cfg['receiver_email']}")
        return True
    except smtplib.SMTPAuthenticationError:
        raise Exception("邮箱认证失败，请检查邮箱地址和授权码（多数邮箱需使用授权码/应用专用密码而非登录密码）")
    except smtplib.SMTPConnectError:
        raise Exception(f"无法连接 SMTP 服务器 {cfg['smtp_host']}:{cfg['smtp_port']}")
    except Exception as e:
        raise Exception(f"邮件发送失败: {e}")
