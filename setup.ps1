# setup.ps1 — ACM Helper 一键启动脚本 (Windows)
# 用法: powershell -ExecutionPolicy Bypass -File setup.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  ACM Helper — 一键启动脚本" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# 1. 检查 Python
Write-Host "[1/4] 检查 Python..." -ForegroundColor Yellow
try {
    $pyVersion = python --version 2>&1
    Write-Host "  ✓ $pyVersion" -ForegroundColor Green
} catch {
    Write-Host "  ✗ 未找到 Python，请先安装 Python 3.10+: https://www.python.org/downloads/" -ForegroundColor Red
    pause
    exit 1
}

# 2. 安装依赖
Write-Host "[2/4] 安装依赖..." -ForegroundColor Yellow

# 必装依赖
python -m pip install --quiet requests beautifulsoup4 markdown
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ✗ 基础依赖安装失败，请检查网络或 Python 环境" -ForegroundColor Red
    pause
    exit 1
}
Write-Host "  ✓ 基础依赖安装完成" -ForegroundColor Green

# 可选依赖（curl_cffi 用于 AtCoder/Luogu Cloudflare 绕过，Windows 编译可能失败）
Write-Host "  ● 尝试安装可选依赖 curl_cffi..." -ForegroundColor Gray
try {
    python -m pip install --quiet curl_cffi 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✓ curl_cffi 安装完成" -ForegroundColor Green
    } else {
        throw "pip 返回非零"
    }
} catch {
    Write-Host "  ! curl_cffi 安装失败（可选，不影响基础功能）" -ForegroundColor DarkYellow
}

# 3. 复制配置文件
Write-Host "[3/4] 检查配置文件..." -ForegroundColor Yellow

$configs = @(
    @{Name="sender_config.json"; Example="sender_config.example.json"},
    @{Name="email_config.json"; Example="email_config.example.json"},
    @{Name="bound_accounts.json"; Example="bound_accounts.example.json"}
)

$needEdit = @()
foreach ($cfg in $configs) {
    if (Test-Path $cfg.Name) {
        Write-Host "  ● $($cfg.Name) 已存在" -ForegroundColor Gray
    } else {
        if (Test-Path $cfg.Example) {
            Copy-Item $cfg.Example $cfg.Name
            Write-Host "  ✓ 已从 $($cfg.Example) 创建 $($cfg.Name)" -ForegroundColor Green
            $needEdit += $cfg.Name
        } else {
            Write-Host "  ✗ 模板 $($cfg.Example) 不存在，跳过" -ForegroundColor Red
        }
    }
}

# 4. 提示填写配置
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  配置提示" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

if ($needEdit.Count -gt 0) {
    Write-Host "以下文件已自动创建，请填入你的真实信息：" -ForegroundColor Yellow
    foreach ($f in $needEdit) {
        Write-Host "  • $f" -ForegroundColor White
    }
}

Write-Host ""
Write-Host "sender_config.json  →  SMTP 发件邮箱 + 授权码（周报推送需要）"
Write-Host "email_config.json   →  收件邮箱 + DeepSeek API Key"
Write-Host "bound_accounts.json →  各 OJ 平台用户名 + Cookie"
Write-Host ""
Write-Host "获取 Cookie 方法：浏览器 F12 → Application → Cookies"
Write-Host "获取 QQ 邮箱授权码：QQ邮箱 → 设置 → 账户 → POP3/SMTP 服务"
Write-Host "获取 DeepSeek Key：platform.deepseek.com → API Keys"
Write-Host ""

$startNow = Read-Host "是否现在启动服务器？(y/n，默认 y)"
if ($startNow -ne "n") {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  启动服务器 http://localhost:8765" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    $env:NO_PROXY = "*"
    python server.py
} else {
    Write-Host ""
    Write-Host "配置好上述文件后，运行以下命令启动：" -ForegroundColor Yellow
    Write-Host "  NO_PROXY=* python server.py" -ForegroundColor White
}

pause
