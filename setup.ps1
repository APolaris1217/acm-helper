# setup.ps1 — ACM Helper 一键启动脚本 (Windows)
# 用法: powershell -ExecutionPolicy Bypass -File setup.ps1

# 切换控制台编码为 UTF-8，避免中文乱码
chcp 65001 > $null 2>&1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  ACM Helper — 一键启动脚本" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# 1. 查找可用的 Python（跳过 msys64/mingw/cygwin/WindowsApps 等无 pip 的精简版）
Write-Host "[1/4] 查找可用的 Python..." -ForegroundColor Yellow

$PythonExe = $null
$PythonVer = $null

# 策略1: py launcher（Windows 官方 Python 自带，自动选最新版）
try {
    $ver = py -3 --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        $PythonExe = "py"
        $PythonVer = $ver.Trim()
    }
} catch {}

# 策略2: 扫描 PATH 中所有 python.exe，找第一个有 pip 的
if (-not $PythonExe) {
    # where.exe 返回 PATH 中所有匹配项，不像 Get-Command 只返回第一个
    $allPythons = @(where.exe python 2>$null)
    $allPythons += @(where.exe python3 2>$null)
    $allPythons = $allPythons | Where-Object { $_ } | Sort-Object -Unique

    foreach ($pyPath in $allPythons) {
        # 跳过 msys64/mingw/cygwin/WindowsApps（通常无 pip 或功能受限）
        if ($pyPath -match 'msys|mingw|cygwin|WindowsApps') {
            continue
        }
        $result = & $pyPath -c "import pip" 2>&1
        if ($LASTEXITCODE -eq 0) {
            $PythonExe = $pyPath
            $out = & $pyPath --version 2>&1
            $PythonVer = $out.Trim()
            break
        }
    }
}

if (-not $PythonExe) {
    Write-Host "  x 未找到可用的 Python（需 Python 3.10+ 且包含 pip）" -ForegroundColor Red
    Write-Host "  安装地址: https://www.python.org/downloads/" -ForegroundColor Yellow
    pause
    exit 1
}

Write-Host "  v $PythonVer ($PythonExe)" -ForegroundColor Green

# 2. 安装依赖
Write-Host "[2/4] 安装依赖..." -ForegroundColor Yellow

# 必装依赖
& $PythonExe -m pip install --quiet requests beautifulsoup4 markdown
if ($LASTEXITCODE -ne 0) {
    Write-Host "  x 基础依赖安装失败，请检查网络" -ForegroundColor Red
    pause
    exit 1
}
Write-Host "  v 基础依赖安装完成" -ForegroundColor Green

# 可选依赖（curl_cffi 用于 AtCoder/Luogu Cloudflare 绕过，Windows 编译可能失败）
Write-Host "  o 尝试安装可选依赖 curl_cffi..." -ForegroundColor Gray
try {
    & $PythonExe -m pip install --quiet curl_cffi 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  v curl_cffi 安装完成" -ForegroundColor Green
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
        Write-Host "  o $($cfg.Name) 已存在" -ForegroundColor Gray
    } else {
        if (Test-Path $cfg.Example) {
            Copy-Item $cfg.Example $cfg.Name
            Write-Host "  v 已从 $($cfg.Example) 创建 $($cfg.Name)" -ForegroundColor Green
            $needEdit += $cfg.Name
        } else {
            Write-Host "  x 模板 $($cfg.Example) 不存在，跳过" -ForegroundColor Red
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
        Write-Host "  * $f" -ForegroundColor White
    }
    Write-Host ""
}

Write-Host "sender_config.json  ->  SMTP 发件邮箱 + 授权码（周报推送需要）"
Write-Host "email_config.json   ->  收件邮箱 + DeepSeek API Key"
Write-Host "bound_accounts.json ->  各 OJ 平台用户名 + Cookie"
Write-Host ""
Write-Host "获取 Cookie 方法：浏览器 F12 -> Application -> Cookies"
Write-Host "获取 QQ 邮箱授权码：QQ邮箱 -> 设置 -> 账户 -> POP3/SMTP 服务"
Write-Host "获取 DeepSeek Key：platform.deepseek.com -> API Keys"
Write-Host ""

$startNow = Read-Host "是否现在启动服务器？(y/n，默认 y)"
if ($startNow -ne "n") {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  启动服务器 http://localhost:8765" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    $env:NO_PROXY = "*"
    & $PythonExe server.py
} else {
    Write-Host ""
    Write-Host "配置好上述文件后，运行以下命令启动：" -ForegroundColor Yellow
    Write-Host "  .\setup.ps1" -ForegroundColor White
}

pause
