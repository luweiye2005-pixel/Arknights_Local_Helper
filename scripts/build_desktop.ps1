param([switch]$AllowPending)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$env:npm_config_cache = Join-Path $Root ".npm-cache"
$Python = Join-Path $Root "backend\.venv\Scripts\python.exe"
function Invoke-Native {
  param([string]$Command, [Parameter(ValueFromRemainingArguments=$true)][string[]]$Arguments)
  & $Command @Arguments
  if ($LASTEXITCODE -ne 0) { throw "命令执行失败（$LASTEXITCODE）：$Command $($Arguments -join ' ')" }
}
if (-not (Test-Path $Python)) { throw "请先创建 backend/.venv 并安装 requirements.txt" }
if (-not (Test-Path (Join-Path $Root "vendor\WebView2"))) {
  throw "缺少 vendor/WebView2：请从微软官方下载并解压 x64 Fixed Version Runtime"
}

Push-Location (Join-Path $Root "frontend")
$tsc = Join-Path $Root "frontend\node_modules\.bin\tsc.cmd"
$vite = Join-Path $Root "frontend\node_modules\.bin\vite.cmd"
if (-not (Test-Path -LiteralPath $tsc) -or -not (Test-Path -LiteralPath $vite)) {
  Invoke-Native npm.cmd ci
}
Invoke-Native npm.cmd test -- --run
Invoke-Native npm.cmd run build
Pop-Location

$args = @((Join-Path $Root "scripts\desktop_data.py"), "build-data", "--output", (Join-Path $Root "release_data"))
if ($AllowPending) { $args += "--allow-pending" }
Invoke-Native $Python @args
# 发布硬断言：pending_in_source==0 + SHA-256 校验
Invoke-Native $Python (Join-Path $Root "scripts\desktop_data.py") validate
$testTemp = Join-Path $Root ".desktop-pytest-temp"
New-Item -ItemType Directory -Force -Path $testTemp | Out-Null
$env:TEMP = $testTemp
$env:TMP = $testTemp
$pytestArgs = @("-m", "pytest", (Join-Path $Root "backend\tests"), "-q", "-p", "no:cacheprovider", "--basetemp", (Join-Path $testTemp "run"))
Invoke-Native $Python @pytestArgs
$pyinstallerArgs = @("-m", "PyInstaller", "--clean", "--noconfirm", (Join-Path $Root "desktop.spec"))
Invoke-Native $Python @pyinstallerArgs

$portable = Join-Path $Root "dist\ArknightsOfflinePanel"
$smoke = Start-Process -FilePath (Join-Path $portable "ArknightsOfflinePanel.exe") -ArgumentList "--release-smoke-test" -Wait -PassThru
if ($smoke.ExitCode -ne 0) { throw "桌面发布产物冒烟测试失败：$($smoke.ExitCode)" }
Compress-Archive -LiteralPath $portable -DestinationPath (Join-Path $Root "dist\ArknightsOfflinePanel-win64.zip") -Force
Write-Host "已生成 dist\ArknightsOfflinePanel-win64.zip"
