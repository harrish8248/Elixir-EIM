# ==============================================================================
# Elixir Enterprise Information Management (Elixir EIM) - Master Startup Script
# ==============================================================================

Write-Host "==========================================================" -ForegroundColor Blue
Write-Host " Starting Elixir Enterprise Information Management (Elixir EIM)" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Blue

$env:PATH = "$env:LOCALAPPDATA\Programs\nodejs;$env:PATH"

# 1. Check Python
$pythonCmd = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $pythonCmd)) {
    Write-Host "[!] Virtual environment not found. Creating .venv..." -ForegroundColor Yellow
    python -m venv .venv
    & $pythonCmd -m pip install -e ".[dev]"
}

# 2. Run Preflight Check
Write-Host "`n[1/3] Running Upgrade Preflight Checks..." -ForegroundColor Cyan
& $pythonCmd -m cli.elixir_admin.main check-upgrade

# 3. Apply Schema Migrations
Write-Host "`n[2/3] Applying Expand/Contract Database Migrations..." -ForegroundColor Cyan
& $pythonCmd -m cli.elixir_admin.main migrate

# 4. Start Services
Write-Host "`n[3/3] Launching API and Web Services..." -ForegroundColor Green
Write-Host " -> Backend API:  http://localhost:8000 (Docs: http://localhost:8000/docs)" -ForegroundColor White
Write-Host " -> Frontend Web: http://localhost:5173" -ForegroundColor White
Write-Host "==========================================================" -ForegroundColor Blue

# Start backend in background job and web in foreground
Start-Process -FilePath $pythonCmd -ArgumentList "-m uvicorn apps.api.app.main:app --host 0.0.0.0 --port 8000 --reload"
Set-Location apps\web
npm run dev
