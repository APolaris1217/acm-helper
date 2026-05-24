"""邮件发送模块 — 通过 SMTP 发送周报到指定邮箱"""
import smtplib
import json
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "email_config.json")

DEFAULT_CONFIG = {
    "smtp_host": "smtp.qq.com",
    "smtp_port": 587,
    "sender_email": "",
    "sender_password": "",  # QQ邮箱用授权码，不是登录密码
    "receiver_email": "",
    "schedule_day": 1,       # 周一=0, 周日=6
    "schedule_hour": 9,      # 上午 9 点
    "enabled": False,
}


def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            # 合并默认值
            for k, v in DEFAULT_CONFIG.items():
                cfg.setdefault(k, v)
            return cfg
    return dict(DEFAULT_CONFIG)


def save_config(cfg: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def send_report(report_markdown: str, subject: str = "") -> bool:
    """发送周报邮件

    Args:
        report_markdown: Markdown 格式的报告正文
        subject: 邮件主题

    Returns:
        True 表示发送成功
    """
    cfg = load_config()
    if not cfg.get("enabled"):
        raise Exception("邮件功能未启用")
    if not cfg.get("sender_email") or not cfg.get("sender_password"):
        raise Exception("发件人邮箱或密码未配置")
    if not cfg.get("receiver_email"):
        raise Exception("收件人邮箱未配置")

    subject = subject or f"ACM 训练周报 - {datetime.now().strftime('%Y-%m-%d')}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = cfg["sender_email"]
    msg["To"] = cfg["receiver_email"]

    # 纯文本备选
    text_part = MIMEText(report_markdown, "plain", "utf-8")
    # HTML（Markdown 直接用，大多数邮件客户端支持）
    html_content = f"""<html><body>
<pre style="font-family: 'Consolas', 'Courier New', monospace; white-space: pre-wrap; line-height: 1.5;">
{report_markdown}
</pre>
</body></html>"""
    html_part = MIMEText(html_content, "html", "utf-8")

    msg.attach(text_part)
    msg.attach(html_part)

    try:
        # 绕过本地代理（HTTP_PROXY 会干扰 SMTP 连接）
        os.environ['NO_PROXY'] = '*'
        os.environ['no_proxy'] = '*'
        # 指定 ASCII hostname，避免 Windows 中文主机名导致 SMTP EHLO 编码错误
        server = smtplib.SMTP(cfg["smtp_host"], cfg["smtp_port"], local_hostname="localhost", timeout=30)
        server.starttls()
        server.login(cfg["sender_email"], cfg["sender_password"])
        server.sendmail(cfg["sender_email"], [cfg["receiver_email"]], msg.as_string())
        server.quit()
        print(f"  [EMAIL] 邮件已发送: {subject} → {cfg['receiver_email']}")
        return True
    except smtplib.SMTPAuthenticationError:
        raise Exception("邮箱认证失败，请检查邮箱地址和授权码（QQ邮箱需使用授权码而非登录密码）")
    except smtplib.SMTPConnectError:
        raise Exception(f"无法连接 SMTP 服务器 {cfg['smtp_host']}:{cfg['smtp_port']}")
    except Exception as e:
        raise Exception(f"邮件发送失败: {e}")
