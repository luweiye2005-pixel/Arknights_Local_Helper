$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$started = @()

function Test-Port([int]$Port) {
  return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}
function Wait-Url([string]$Url, [int]$Seconds = 45) {
  $until = (Get-Date).AddSeconds($Seconds)
  do {
    try { Invoke-WebRequest -UseBasicParsing $Url -TimeoutSec 2 | Out-Null; return }
    catch { Start-Sleep -Milliseconds 500 }
  } while ((Get-Date) -lt $until)
  throw "Timed out waiting for $Url"
}

try {
  if (-not (Test-Port 8000)) {
    $p = Start-Process -FilePath "$repo\backend\.venv\Scripts\python.exe" -ArgumentList "-m","uvicorn","app.main:app","--host","127.0.0.1","--port","8000" -WorkingDirectory "$repo\backend" -WindowStyle Hidden -PassThru
    $started += $p
  }
  if (-not (Test-Port 5173)) {
    $p = Start-Process -FilePath "npm.cmd" -ArgumentList "run","dev","--","--host","127.0.0.1","--port","5173" -WorkingDirectory "$repo\frontend" -WindowStyle Hidden -PassThru
    $started += $p
  }
  Wait-Url "http://127.0.0.1:8000/health"
  Wait-Url "http://127.0.0.1:5173/"
  & "$repo\frontend\node_modules\.bin\vite-node.cmd" "$repo\scripts\audit_skill_autofill.ts"
  if ($LASTEXITCODE -ne 0) { throw "Audit exited with code $LASTEXITCODE" }
}
finally {
  foreach ($process in $started) {
    Stop-Process -Id $process.Id -ErrorAction SilentlyContinue
  }
}
