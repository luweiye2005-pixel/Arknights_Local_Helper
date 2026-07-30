param(
  [Parameter(Mandatory = $false)]
  [switch]$SkipFrontend
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path "$Root\scripts")) { $Root = $PSScriptRoot }

Write-Host "==> 明日方舟本地数据面板" -ForegroundColor Cyan
Write-Host "仓库: $Root"

$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"

$Venv = Join-Path $Backend ".venv"
if (-not (Test-Path $Venv)) {
  Write-Host "==> 创建 Python venv..."
  python -m venv $Venv
}
$Py = Join-Path $Venv "Scripts\python.exe"
$Pip = Join-Path $Venv "Scripts\pip.exe"

Write-Host "==> 安装后端依赖..."
& $Pip install -r (Join-Path $Backend "requirements.txt") -i https://pypi.tuna.tsinghua.edu.cn/simple

if (-not $SkipFrontend) {
  Write-Host "==> 安装前端依赖..."
  Push-Location $Frontend
  npm install --registry=https://registry.npmmirror.com
  Pop-Location
}

Write-Host "==> 启动后端 http://127.0.0.1:8000"
Start-Process -FilePath $Py -ArgumentList "-m","uvicorn","app.main:app","--reload","--host","127.0.0.1","--port","8000" -WorkingDirectory $Backend

if (-not $SkipFrontend) {
  Start-Sleep -Seconds 2
  Write-Host "==> 启动前端 http://127.0.0.1:5173"
  Start-Process -FilePath "npm" -ArgumentList "run","dev","--","--host","127.0.0.1","--port","5173" -WorkingDirectory $Frontend
}

Write-Host ""
Write-Host "浏览器打开: http://127.0.0.1:5173"
Write-Host "API 文档: http://127.0.0.1:8000/docs"
Write-Host "请先在「数据管理」确认内存与数据库计数一致。"
