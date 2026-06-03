#!/bin/bash
# setup.sh — ACM Helper 一键启动脚本 (Linux/Mac)
# 用法: bash setup.sh

set -e

echo "========================================"
echo "  ACM Helper — 一键启动脚本"
echo "========================================"
echo ""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 1. 检查 Python
echo "[1/4] 检查 Python..."
if command -v python3 &>/dev/null; then
    PY=python3
elif command -v python &>/dev/null; then
    PY=python
else
    echo "  ✗ 未找到 Python，请先安装 Python 3.10+"
    exit 1
fi
echo "  ✓ $($PY --version)"

# 2. 安装依赖
echo "[2/4] 安装依赖..."
$PY -m pip install --quiet requests beautifulsoup4 curl_cffi markdown
echo "  ✓ 依赖安装完成"

# 3. 复制配置文件
echo "[3/4] 检查配置文件..."

configs=(
    "sender_config.json:sender_config.example.json"
    "email_config.json:email_config.example.json"
    "bound_accounts.json:bound_accounts.example.json"
)

need_edit=()
for pair in "${configs[@]}"; do
    cfg="${pair%%:*}"
    ex="${pair##*:}"
    if [ -f "$cfg" ]; then
        echo "  ● $cfg 已存在"
    else
        if [ -f "$ex" ]; then
            cp "$ex" "$cfg"
            echo "  ✓ 已从 $ex 创建 $cfg"
            need_edit+=("$cfg")
        else
            echo "  ✗ 模板 $ex 不存在，跳过"
        fi
    fi
done

# 4. 提示填写配置
echo ""
echo "========================================"
echo "  配置提示"
echo "========================================"
echo ""

if [ ${#need_edit[@]} -gt 0 ]; then
    echo "以下文件已自动创建，请填入你的真实信息："
    for f in "${need_edit[@]}"; do
        echo "  • $f"
    done
    echo ""
fi

echo "sender_config.json  →  SMTP 发件邮箱 + 授权码（周报推送需要）"
echo "email_config.json   →  收件邮箱 + DeepSeek API Key"
echo "bound_accounts.json →  各 OJ 平台用户名 + Cookie"
echo ""
echo "获取 Cookie 方法：浏览器 F12 → Application → Cookies"
echo "获取 QQ 邮箱授权码：QQ邮箱 → 设置 → 账户 → POP3/SMTP 服务"
echo "获取 DeepSeek Key：platform.deepseek.com → API Keys"
echo ""

read -p "是否现在启动服务器？(y/n，默认 y): " start_now
start_now=${start_now:-y}

if [ "$start_now" != "n" ]; then
    echo ""
    echo "========================================"
    echo "  启动服务器 http://localhost:8765"
    echo "========================================"
    export NO_PROXY="*"
    $PY server.py
else
    echo ""
    echo "配置好上述文件后，运行以下命令启动："
    echo "  NO_PROXY=* python server.py"
fi
