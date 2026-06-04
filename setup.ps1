# setup.ps1 -- ACM Helper one-click setup (Windows)
# Usage: .\setup.ps1
# Note: Must run from PowerShell, not CMD

# Switch console to UTF-8 for correct output
chcp 65001 > $null 2>&1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  ACM Helper -- One-Click Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# 1. Find a working Python (skip msys64/mingw/cygwin/WindowsApps)
Write-Host "[1/4] Looking for Python..." -ForegroundColor Yellow

$PythonExe = $null
$PythonVer = $null

# Strategy 1: py launcher (installed by official Python for Windows)
try {
    $ver = py -3 --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        $PythonExe = "py"
        $PythonVer = $ver.Trim()
    }
} catch {}

# Strategy 2: scan ALL python.exe in PATH, pick first that has pip
if (-not $PythonExe) {
    $allPythons = @(where.exe python 2>$null)
    $allPythons += @(where.exe python3 2>$null)
    $allPythons = $allPythons | Where-Object { $_ } | Sort-Object -Unique

    foreach ($pyPath in $allPythons) {
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
    Write-Host "  X Python not found (need 3.10+ with pip)" -ForegroundColor Red
    Write-Host "  Download: https://www.python.org/downloads/" -ForegroundColor Yellow
    pause
    exit 1
}

Write-Host "  OK $PythonVer ($PythonExe)" -ForegroundColor Green

# 2. Install dependencies
Write-Host "[2/4] Installing dependencies..." -ForegroundColor Yellow

# Required
& $PythonExe -m pip install --quiet requests beautifulsoup4 markdown
if ($LASTEXITCODE -ne 0) {
    Write-Host "  X Required dependencies failed, check network" -ForegroundColor Red
    pause
    exit 1
}
Write-Host "  OK requests, beautifulsoup4, markdown" -ForegroundColor Green

# Optional (curl_cffi for AtCoder/Luogu Cloudflare bypass)
Write-Host "  - Trying optional curl_cffi..." -ForegroundColor Gray
try {
    & $PythonExe -m pip install --quiet curl_cffi 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  OK curl_cffi installed" -ForegroundColor Green
    } else {
        throw "pip non-zero exit"
    }
} catch {
    Write-Host "  !  curl_cffi skipped (optional, won't affect basic features)" -ForegroundColor DarkYellow
}

# 3. Create config files from templates
Write-Host "[3/4] Checking config files..." -ForegroundColor Yellow

$configs = @(
    @{Name="sender_config.json"; Example="sender_config.example.json"},
    @{Name="email_config.json"; Example="email_config.example.json"},
    @{Name="bound_accounts.json"; Example="bound_accounts.example.json"}
)

$needEdit = @()
foreach ($cfg in $configs) {
    if (Test-Path $cfg.Name) {
        Write-Host "  - $($cfg.Name) already exists" -ForegroundColor Gray
    } else {
        if (Test-Path $cfg.Example) {
            Copy-Item $cfg.Example $cfg.Name
            Write-Host "  OK Created $($cfg.Name) from $($cfg.Example)" -ForegroundColor Green
            $needEdit += $cfg.Name
        } else {
            Write-Host "  X Template $($cfg.Example) not found, skipped" -ForegroundColor Red
        }
    }
}

# 4. Config guide
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Configuration Guide" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

if ($needEdit.Count -gt 0) {
    Write-Host "The following files were created from templates." -ForegroundColor Yellow
    Write-Host "Please edit them with your real credentials:" -ForegroundColor Yellow
    foreach ($f in $needEdit) {
        Write-Host "  * $f" -ForegroundColor White
    }
    Write-Host ""
}

Write-Host "sender_config.json  -> SMTP server + sender email + auth code"
Write-Host "email_config.json   -> receiver email + DeepSeek API Key"
Write-Host "bound_accounts.json -> OJ platform usernames + cookies"
Write-Host ""
Write-Host "How to get QQ email auth code: QQ Mail -> Settings -> Account -> POP3/SMTP"
Write-Host "How to get DeepSeek Key: platform.deepseek.com -> API Keys"
Write-Host "How to get cookies: Browser F12 -> Application -> Cookies"
Write-Host ""

$startNow = Read-Host "Start server now? (y/n, default y)"
if ($startNow -ne "n") {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  Starting http://localhost:8765" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    $env:NO_PROXY = "*"
    & $PythonExe server.py
} else {
    Write-Host ""
    Write-Host "When ready, run this script again to start the server:" -ForegroundColor Yellow
    Write-Host "  .\setup.ps1" -ForegroundColor White
}

pause
