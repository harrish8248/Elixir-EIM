# ==============================================================================
# Elixir Enterprise Information Management (Elixir EIM) - Master Startup Script
# Performs: Docker health checks -> Alembic migrations -> Service readiness verification
# -> Backend (uvicorn) + Frontend (Vite dev server) OR Test Suite (-Test)
# ==============================================================================

param(
    [switch]$SkipDocker,       # Skip Docker container checks (for CI environments)
    [switch]$NoBrowser,        # Don't auto-open browser
    [switch]$Test,             # Run test suite with REQUIRE_POSTGRES=1 and exit
    [switch]$Demo,             # Seed 7 demo GST invoices + EICAR test via live upload API
    [switch]$ResetDemo         # Wipe capture_jobs and re-seed clean IDP demo state
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$PythonCmd = Join-Path $Root ".venv\Scripts\python.exe"
$env:PATH = "$env:LOCALAPPDATA\Programs\nodejs;$env:PATH"

function Write-Header($msg) {
    Write-Host ""
    Write-Host "===========================================================" -ForegroundColor Blue
    Write-Host "  $msg" -ForegroundColor Cyan
    Write-Host "===========================================================" -ForegroundColor Blue
}

function Write-StatusTable($rows) {
    $width = 44
    Write-Host ("+" + "-" * $width + "+--------+") -ForegroundColor DarkGray
    Write-Host ("| {0,-42} | {1,-6} |" -f "Service", "Status") -ForegroundColor White
    Write-Host ("+" + "-" * $width + "+--------+") -ForegroundColor DarkGray
    foreach ($row in $rows) {
        $color = if ($row.Status -eq "PASS") { "Green" } elseif ($row.Status -eq "WARN") { "Yellow" } else { "Red" }
        Write-Host ("| {0,-42} | " -f $row.Service) -NoNewline -ForegroundColor White
        Write-Host ("{0,-6}" -f $row.Status) -NoNewline -ForegroundColor $color
        Write-Host " |" -ForegroundColor White
    }
    Write-Host ("+" + "-" * $width + "+--------+") -ForegroundColor DarkGray
}

function Test-Http($url, $timeoutSec = 3) {
    try {
        $resp = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec $timeoutSec -ErrorAction SilentlyContinue
        return $resp.StatusCode -lt 400
    } catch { return $false }
}

function Test-TcpPort($targetHost, $port, $timeoutMs = 2000) {
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $conn = $tcp.BeginConnect($targetHost, $port, $null, $null)
        $wait = $conn.AsyncWaitHandle.WaitOne($timeoutMs, $false)
        if ($wait) {
            $tcp.EndConnect($conn)
            $tcp.Close()
            return $true
        }
        $tcp.Close()
        return $false
    } catch { return $false }
}

function Test-PostgresLogin($url) {
    try {
        $pyCode = "import psycopg; conn = psycopg.connect('" + $url + "', connect_timeout=5); cur = conn.cursor(); cur.execute('SELECT current_user, version()'); res = cur.fetchone(); print('USER:' + str(res[0])); conn.close()"
        $out = & $PythonCmd -c $pyCode 2>&1
        if ($LASTEXITCODE -eq 0 -and $out -match "USER:") {
            return $true
        }
        return $false
    } catch { return $false }
}

# ------------------------------------------------------------------------------
# STEP 0: Announce
# ------------------------------------------------------------------------------
Write-Header "Starting Elixir Enterprise Information Management (Elixir EIM) v1.0"

# ------------------------------------------------------------------------------
# STEP 1: Python Virtual Environment
# ------------------------------------------------------------------------------
Write-Host "[1/5] Checking Python virtual environment..." -ForegroundColor Cyan
if (-not (Test-Path $PythonCmd)) {
    Write-Host "  [!] .venv not found. Creating..." -ForegroundColor Yellow
    python -m venv .venv
    & $PythonCmd -m pip install -e ".[dev]" -q
    Write-Host "  [OK] Virtual environment created and dependencies installed." -ForegroundColor Green
} else {
    Write-Host "  [OK] Virtual environment found: $PythonCmd" -ForegroundColor Green
}

# ------------------------------------------------------------------------------
# STEP 2: Docker Container Health Checks
# ------------------------------------------------------------------------------
Write-Host "`n[2/5] Checking Docker backing services..." -ForegroundColor Cyan
if (-not $SkipDocker) {
    try {
        # Ensure WSL keepalive is present if running under WSL2 backend
        if (Get-Command wsl -ErrorAction SilentlyContinue) {
            $null = Start-Process -FilePath "wsl" -ArgumentList "sleep infinity" -WindowStyle Hidden -ErrorAction SilentlyContinue
        }

        $expectedContainers = @("elixir-postgres","elixir-redis","elixir-minio","elixir-keycloak","elixir-opa","elixir-gotenberg","elixir-clamav")
        $runningContainers = (docker ps --format '{{.Names}}' 2>&1) -split "`n" | ForEach-Object { $_.Trim() }

        $missingContainers = $expectedContainers | Where-Object { $_ -notin $runningContainers }
        if ($missingContainers.Count -gt 0) {
            Write-Host "  [!] Missing containers: $($missingContainers -join ', '). Starting Docker Compose..." -ForegroundColor Yellow
            docker compose -f "$Root\deployment\docker-compose.yml" up -d
            Write-Host "  [OK] Docker Compose started. Waiting 10s for services to boot..." -ForegroundColor Green
            Start-Sleep -Seconds 10
        } else {
            Write-Host "  [OK] All 7 Docker containers are running." -ForegroundColor Green
        }
    } catch {
        Write-Host "  [WARN] Docker check failed: $_. Proceeding anyway." -ForegroundColor Yellow
    }
}

# ------------------------------------------------------------------------------
# STEP 3: Alembic Database Migrations
# ------------------------------------------------------------------------------
Write-Host "`n[3/5] Applying database migrations (Alembic)..." -ForegroundColor Cyan
try {
    $alembicIni = Join-Path $Root "migrations\alembic.ini"
    $prevEAP = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $null = & $PythonCmd -m alembic -c "$alembicIni" upgrade head
    $ErrorActionPreference = $prevEAP
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK] Alembic migrations applied successfully." -ForegroundColor Green
    } else {
        Write-Host "  [WARN] Alembic migration exited with code $LASTEXITCODE." -ForegroundColor Yellow
    }
} catch {
    Write-Host "  [WARN] Alembic execution failed: $_" -ForegroundColor Yellow
}

# ------------------------------------------------------------------------------
# STEP 4: Service Readiness Verification
# ------------------------------------------------------------------------------
Write-Host "`n[4/5] Verifying all service readiness..." -ForegroundColor Cyan
Start-Sleep -Seconds 1

$pgUrl = "postgresql://elixir:elixir_secure_pass@localhost:5432/elixir_eim"
$pgOk = Test-PostgresLogin $pgUrl

$statusRows = @(
    [PSCustomObject]@{ Service = "PostgreSQL 16 (psycopg login: 5432)"; Status = $(if ($pgOk) { "PASS" } else { "FAIL" }) },
    [PSCustomObject]@{ Service = "Redis 7 (port 6379)";                 Status = $(if (Test-TcpPort "localhost" 6379) { "PASS" } else { "FAIL" }) },
    [PSCustomObject]@{ Service = "MinIO S3 (port 9000)";                Status = $(if (Test-Http "http://localhost:9000/minio/health/live") { "PASS" } else { "FAIL" }) },
    [PSCustomObject]@{ Service = "MinIO Console (port 9001)";           Status = $(if (Test-TcpPort "localhost" 9001) { "PASS" } else { "FAIL" }) },
    [PSCustomObject]@{ Service = "Keycloak 26 (port 8080)";             Status = $(if (Test-Http "http://localhost:8080/realms/elixir/.well-known/openid-configuration") { "PASS" } else { "FAIL" }) },
    [PSCustomObject]@{ Service = "OPA Policy Engine (port 8181)";       Status = $(if (Test-Http "http://localhost:8181/health") { "PASS" } else { "FAIL" }) },
    [PSCustomObject]@{ Service = "Gotenberg PDF Engine (port 3000)";    Status = $(if (Test-Http "http://localhost:3000/health") { "PASS" } else { "FAIL" }) },
    [PSCustomObject]@{ Service = "ClamAV Antimalware (port 3310)";      Status = $(if (Test-TcpPort "localhost" 3310) { "PASS" } else { "FAIL" }) }
)

Write-StatusTable $statusRows

$failedServices = $statusRows | Where-Object { $_.Status -eq "FAIL" }
if ($failedServices.Count -gt 0) {
    Write-Host "`n  [WARN] $($failedServices.Count) service(s) not reachable. Check Docker logs." -ForegroundColor Yellow
} else {
    Write-Host "`n  [OK] All 8 services are healthy and reachable." -ForegroundColor Green
}

# ------------------------------------------------------------------------------
# STEP 5: Run Tests (-Test) OR Launch Backend API + Frontend Dev Server
# ------------------------------------------------------------------------------
if ($Test) {
    Write-Header "Executing Test Suite with REQUIRE_POSTGRES=1"
    $env:REQUIRE_POSTGRES = "1"
    $env:DATABASE_URL_SYNC = $pgUrl
    & $PythonCmd -m pytest -v -rs
    exit $LASTEXITCODE
}

Write-Host "`n[5/5] Launching API and Web services..." -ForegroundColor Cyan
Write-Host "  -> Backend API:  http://localhost:8000  (Docs: http://localhost:8000/docs)" -ForegroundColor White
Write-Host "  -> Frontend Web: http://localhost:5173" -ForegroundColor White
Write-Host "  -> Keycloak:     http://localhost:8080  (admin / admin_secure_pass)" -ForegroundColor White
Write-Host "  -> MinIO:        http://localhost:9001  (minioadmin / minioadmin_secure)" -ForegroundColor White
Write-Host ""

# Start backend in a background job
$backendJob = Start-Process -FilePath $PythonCmd `
    -ArgumentList "-m uvicorn apps.api.app.main:app --host 0.0.0.0 --port 8000 --reload" `
    -WorkingDirectory $Root `
    -PassThru

Write-Host "  [OK] Backend API started (PID: $($backendJob.Id))" -ForegroundColor Green

# Wait for backend to be ready
Write-Host "  Waiting for backend to be ready..." -ForegroundColor DarkGray
$retries = 0
while ($retries -lt 15) {
    if (Test-Http "http://localhost:8000/api/v1/system/health/live") {
        Write-Host "  [OK] Backend API is responding at http://localhost:8000" -ForegroundColor Green
        break
    }
    $retries++
    Start-Sleep -Seconds 1
}
if ($retries -eq 15) {
    Write-Host "  [WARN] Backend API did not respond in 15s. Check logs." -ForegroundColor Yellow
}

if ($ResetDemo -or $Demo) {
    Write-Host "`n  [*] Seeding live IDP demo invoices via API..." -ForegroundColor Cyan
    & $PythonCmd -m cli.elixir_admin.main seed-idp-demo
}

Write-Header "Elixir EIM is running - press Ctrl+C in the frontend window to stop"

# Start frontend (foreground - this blocks until user quits)
Set-Location "$Root\apps\web"
npm run dev
