# Run both backend (FastAPI) and frontend (Next.js) for local dev.
# Usage:  ./dev.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

$py = Join-Path $root "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) { Write-Error "Python venv not found. Run: cd backend; python -m venv .venv; .\.venv\Scripts\python -m pip install -r requirements.txt" }

$jobs = @()
$jobs += Start-Job -Name "backend" -ScriptBlock {
  param($r) Set-Location "$r\backend"; & "$r\backend\.venv\Scripts\python.exe" -m uvicorn app.main:app --reload --port 8000
} -ArgumentList $root
$jobs += Start-Job -Name "frontend" -ScriptBlock {
  param($r) Set-Location "$r\frontend"; & npm run dev
} -ArgumentList $root

Write-Host "Backend  -> http://localhost:8000  (docs: /docs)"
Write-Host "Frontend -> http://localhost:3000"
Write-Host "Ctrl+C to stop both."

try {
  while ($true) {
    foreach ($j in $jobs) {
      $out = Receive-Job $j 2>$null
      if ($out) { $out | ForEach-Object { Write-Host "[$($j.Name)] $_" } }
    }
    Start-Sleep -Milliseconds 500
  }
} finally {
  $jobs | Stop-Job -ErrorAction SilentlyContinue
  $jobs | Remove-Job -ErrorAction SilentlyContinue
}