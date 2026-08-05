param(
  [switch]$SkipFrontendBuild,
  [switch]$SmokeOnly
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$env:npm_config_cache = Join-Path $Root ".npm-cache"
$Python = Join-Path $Root "backend\.venv\Scripts\python.exe"
$Desktop = Join-Path $Root "backend\desktop.py"
$Frontend = Join-Path $Root "frontend"
$FrontendIndex = Join-Path $Frontend "dist\index.html"
$Manifest = Join-Path $Root "release_data\manifest.json"
$Payload = Join-Path $Root "release_data\data.json.gz"
$WebView = Join-Path $Root "vendor\WebView2\msedgewebview2.exe"

function Invoke-Native {
  param([string]$Command, [Parameter(ValueFromRemainingArguments=$true)][string[]]$Arguments)
  & $Command @Arguments
  if ($LASTEXITCODE -ne 0) {
    throw "Command failed ($LASTEXITCODE): $Command $($Arguments -join ' ')"
  }
}

if (-not (Test-Path -LiteralPath $Python)) {
  throw "Missing backend/.venv. Create it and install backend/requirements.txt first."
}
if (-not (Test-Path -LiteralPath $Manifest) -or -not (Test-Path -LiteralPath $Payload)) {
  throw "Missing release_data bundle. Run scripts/desktop_data.py build-data first."
}
if (-not (Test-Path -LiteralPath $WebView)) {
  Write-Warning "Bundled WebView2 was not found; the system runtime will be used."
}

if (-not $SkipFrontendBuild) {
  $NeedsBuild = -not (Test-Path -LiteralPath $FrontendIndex)
  if (-not $NeedsBuild) {
    $BuildTime = (Get-Item -LiteralPath $FrontendIndex).LastWriteTimeUtc
    $Inputs = Get-ChildItem -Path (Join-Path $Frontend "src") -Recurse -File
    $Inputs += Get-Item (Join-Path $Frontend "package.json"), (Join-Path $Frontend "package-lock.json"), (Join-Path $Frontend "vite.config.ts")
    $NeedsBuild = [bool]($Inputs | Where-Object LastWriteTimeUtc -gt $BuildTime | Select-Object -First 1)
  }
  if ($NeedsBuild) {
    Write-Host "[1/3] Frontend changed; building..." -ForegroundColor Cyan
    Push-Location $Frontend
    try {
      $Tsc = Join-Path $Frontend "node_modules\.bin\tsc.cmd"
      $Vite = Join-Path $Frontend "node_modules\.bin\vite.cmd"
      if (-not (Test-Path -LiteralPath $Tsc) -or -not (Test-Path -LiteralPath $Vite)) {
        Write-Host "Frontend dependencies are missing or incomplete; running npm ci..." -ForegroundColor Yellow
        Invoke-Native npm.cmd ci
      }
      Invoke-Native npm.cmd run build
    }
    finally {
      Pop-Location
    }
  }
  else {
    Write-Host "[1/3] Frontend unchanged; using existing build." -ForegroundColor DarkGray
  }
}
elseif (-not (Test-Path -LiteralPath $FrontendIndex)) {
  throw "frontend/dist is missing; -SkipFrontendBuild cannot be used."
}

Write-Host "[2/3] Validating offline resources..." -ForegroundColor Cyan
Invoke-Native $Python $Desktop --smoke-test
if ($SmokeOnly) {
  Write-Host "Resource validation passed." -ForegroundColor Green
  exit 0
}

Write-Host "[3/3] Starting desktop development app..." -ForegroundColor Green
Write-Host "Close the desktop window to stop, or press Ctrl+C."
Push-Location (Join-Path $Root "backend")
try {
  Invoke-Native $Python $Desktop
}
finally {
  Pop-Location
}
