# Helix Migration — one-click setup (Windows / PowerShell).
#
# Mirrors setup.sh:
#   1. Verifies Docker + Compose v2.
#   2. Provisions .env (copy from .env.example if missing).
#   3. Fills generated secrets via scripts/generate-secrets.ps1.
#   4. Builds images.
#   5. Starts the stack, runs alembic on backend boot.
#   6. Waits for /api/v1/readyz.
#   7. Prints URLs + first-admin instructions.
#
# Usage:
#   .\setup.ps1                    # default — first-time install
#   .\setup.ps1 -Rebuild           # docker compose build --no-cache
#   .\setup.ps1 -RotateSecrets     # overwrite existing secrets
#   .\setup.ps1 -Down              # stop the stack (keeps volumes)
#   .\setup.ps1 -Nuke              # stop + remove containers + volumes
#
# Requires PowerShell 5.1 or PowerShell 7+. Docker Desktop must be running.

param(
    [switch]$Rebuild,
    [switch]$RotateSecrets,
    [switch]$Down,
    [switch]$Nuke
)

$ErrorActionPreference = "Stop"

function Write-Step($msg)  { Write-Host "[>] $msg" -ForegroundColor Cyan }
function Write-Ok($msg)    { Write-Host "[+] $msg" -ForegroundColor Green }
function Write-WarnMsg($msg) { Write-Host "[!] $msg" -ForegroundColor Yellow }
function Write-Err($msg)   { Write-Host "[x] $msg" -ForegroundColor Red }

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptRoot

$ComposeFiles = @("-f", "docker-compose.yml", "-f", "docker-compose.build.yml")

# ── Stop/teardown ────────────────────────────────────────────────────
if ($Down) {
    Write-Step "Stopping the stack…"
    docker compose @ComposeFiles down
    Write-Ok "Stopped. Volumes preserved."
    exit 0
}
if ($Nuke) {
    Write-WarnMsg "About to remove containers AND persistent volumes (Postgres, Redis, artifacts)."
    $confirm = Read-Host "Type 'nuke' to confirm"
    if ($confirm -ne "nuke") {
        Write-Err "Aborted."
        exit 1
    }
    docker compose @ComposeFiles down -v
    Write-Ok "Stack torn down. All data deleted."
    exit 0
}

# ── 1. Preflight ─────────────────────────────────────────────────────
Write-Step "Checking Docker…"
try { docker --version | Out-Null } catch {
    Write-Err "docker not found in PATH. Install Docker Desktop and ensure it is running."
    exit 1
}
try { docker compose version | Out-Null } catch {
    Write-Err "Docker Compose v2 plugin missing. Upgrade Docker Desktop."
    exit 1
}
try { docker info 2>$null | Out-Null } catch {}
if ($LASTEXITCODE -ne 0) {
    Write-Err "Docker daemon not reachable. Start Docker Desktop."
    exit 1
}
$dockerV = (docker --version) -replace '.*?(\d+\.\d+\.\d+).*','$1'
$composeV = (docker compose version --short)
Write-Ok "Docker $dockerV + Compose $composeV."

# ── 2. .env + secrets ────────────────────────────────────────────────
Write-Step "Provisioning .env…"
if (-not (Test-Path ".env")) {
    if (-not (Test-Path ".env.example")) {
        Write-Err ".env.example missing — fork looks incomplete. Cannot proceed."
        exit 1
    }
    Copy-Item .env.example .env
    Write-Ok "Created .env from .env.example."
} else {
    Write-Ok ".env already present — keeping existing values."
}

if ($RotateSecrets) {
    Write-WarnMsg "Rotating secrets — existing JWT tokens + audit chains will be invalidated."
    & .\scripts\generate-secrets.ps1 -Force
} else {
    & .\scripts\generate-secrets.ps1
}

$required = @("POSTGRES_PASSWORD", "JWT_SECRET_KEY", "ENCRYPTION_KEY", "AUDIT_HMAC_KEY")
$missing = @()
$envContent = Get-Content .env
foreach ($k in $required) {
    $line = $envContent | Where-Object { $_ -match "^$k=.+" }
    if (-not $line) { $missing += $k }
}
if ($missing.Count -gt 0) {
    Write-Err "Missing required env vars after secret generation: $($missing -join ', ')"
    exit 1
}
Write-Ok "All required secrets present."

# ── 3. Build ─────────────────────────────────────────────────────────
Write-Step "Building container images (5-10 min on first run)…"
if ($Rebuild) {
    docker compose @ComposeFiles build --no-cache --pull
} else {
    docker compose @ComposeFiles build
}
Write-Ok "Images built."

# ── 4. Start core ────────────────────────────────────────────────────
Write-Step "Starting Postgres + Redis + Temporal…"
docker compose @ComposeFiles up -d postgres redis temporal

Write-Step "Waiting for Postgres to accept connections…"
$pgReady = $false
for ($i = 1; $i -le 30; $i++) {
    docker compose @ComposeFiles exec -T postgres pg_isready -U helix 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
        $pgReady = $true
        break
    }
    Start-Sleep -Seconds 2
}
if (-not $pgReady) {
    Write-Err "Postgres did not become ready within 60s. Check: docker compose logs postgres"
    exit 1
}
Write-Ok "Postgres ready."

# ── 5. App + readiness gate ──────────────────────────────────────────
Write-Step "Bringing up backend (alembic runs on startup)…"
docker compose @ComposeFiles up -d backend worker frontend

Write-Step "Waiting for backend /api/v1/readyz…"
$backendPort = if ($env:BACKEND_HOST_PORT) { $env:BACKEND_HOST_PORT } else { "8000" }
$frontendPort = if ($env:FRONTEND_HOST_PORT) { $env:FRONTEND_HOST_PORT } else { "3000" }
$backendUrl = "http://localhost:$backendPort/api/v1/readyz"
$ready = $false
for ($i = 1; $i -le 60; $i++) {
    try {
        $resp = Invoke-WebRequest -Uri $backendUrl -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
        if ($resp.StatusCode -eq 200) {
            $ready = $true
            break
        }
    } catch { }
    Start-Sleep -Seconds 2
}
if (-not $ready) {
    Write-Err "Backend did not pass /readyz within 120s. Tail logs:"
    Write-Err "  docker compose logs --tail=80 backend"
    exit 1
}
Write-Ok "Backend ready."

# ── 6. Summary ───────────────────────────────────────────────────────
Write-Host ""
Write-Host "Helix is up." -ForegroundColor Green
Write-Host ""
Write-Host "  Frontend   http://localhost:$frontendPort"
Write-Host "  Backend    http://localhost:$backendPort"
Write-Host "  OpenAPI    http://localhost:$backendPort/docs"
Write-Host "  Health     http://localhost:$backendPort/api/v1/health"
Write-Host "  Ready      http://localhost:$backendPort/api/v1/readyz"
Write-Host "  Metrics    http://localhost:$backendPort/metrics"
Write-Host ""
Write-Host "First-time setup — open the frontend and walk through the wizard:" -ForegroundColor DarkGray
Write-Host "  http://localhost:$frontendPort/setup/first-admin" -ForegroundColor DarkGray
Write-Host ""
Write-Host "Common ops:" -ForegroundColor DarkGray
Write-Host "  docker compose -f docker-compose.yml -f docker-compose.build.yml logs -f backend worker" -ForegroundColor DarkGray
Write-Host "  .\setup.ps1 -Down            # stop, keep data" -ForegroundColor DarkGray
Write-Host "  .\setup.ps1 -RotateSecrets   # rotate JWT/encryption keys" -ForegroundColor DarkGray
Write-Host "  docker compose --profile debug up -d temporal-ui  # opt-in Temporal UI on 127.0.0.1:8233" -ForegroundColor DarkGray
Write-Host ""
