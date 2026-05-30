# Helix Migration — one-click setup (Windows / PowerShell).
#
# Mirrors setup.sh:
#   1. Verifies Docker + Compose v2 (no auto-install on Windows — Docker
#      Desktop is a GUI installer).
#   2. Provisions .env (copy from .env.example if missing).
#   3. Fills generated secrets via scripts/generate-secrets.ps1.
#   4. Detects public host (cloud metadata if VM; -Domain flag for TLS).
#   5. Builds images.
#   6. Starts the stack, runs alembic on backend boot.
#   7. Waits for /api/v1/readyz.
#   8. Prints URLs + first-admin instructions.
#
# Usage:
#   .\setup.ps1                                  # default
#   .\setup.ps1 -NonInteractive                  # accept defaults, never prompt
#   .\setup.ps1 -Domain helix.example.com        # TLS deploy
#   .\setup.ps1 -AdminEmail X -AdminPassword Y   # pre-seed first admin
#   .\setup.ps1 -Rebuild                         # docker compose build --no-cache
#   .\setup.ps1 -RotateSecrets -Force -ConfirmDataLoss
#   .\setup.ps1 -Down                            # stop, keep volumes
#   .\setup.ps1 -Nuke                            # stop + wipe volumes
#
# Requires PowerShell 5.1 or PowerShell 7+. Docker Desktop must be running.

param(
    [switch]$Rebuild,
    [switch]$RotateSecrets,
    [switch]$Force,
    [switch]$ConfirmDataLoss,
    [switch]$Down,
    [switch]$Nuke,
    [switch]$NonInteractive,
    [switch]$SkipDockerInstall,
    [string]$Domain        = "",
    [string]$AdminEmail    = "",
    [string]$AdminPassword = ""
)

$ErrorActionPreference = "Stop"
$RepoUrl = "https://github.com/datainteg/helix-ai-migration"

function Write-Step($msg)    { Write-Host "[>] $msg" -ForegroundColor Cyan }
function Write-Ok($msg)      { Write-Host "[+] $msg" -ForegroundColor Green }
function Write-WarnMsg($msg) { Write-Host "[!] $msg" -ForegroundColor Yellow }
function Write-Err($msg)     { Write-Host "[x] $msg" -ForegroundColor Red }

function Confirm-Or-Default($prompt, $expected) {
    if ($NonInteractive) { return $true }
    $reply = Read-Host $prompt
    return ($reply -eq $expected)
}

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
    Write-WarnMsg "About to remove containers AND persistent volumes."
    if (-not $NonInteractive) {
        if (-not (Confirm-Or-Default "Type 'nuke' to confirm" "nuke")) {
            Write-Err "Aborted."; exit 1
        }
    } else {
        Write-WarnMsg "-NonInteractive set; proceeding without confirmation."
    }
    docker compose @ComposeFiles down -v
    Write-Ok "Stack torn down. All data deleted."
    exit 0
}

# ── Rotate-secrets safety gate ───────────────────────────────────────
if ($RotateSecrets) {
    if (-not $Force -or -not $ConfirmDataLoss) {
        Write-Err "-RotateSecrets refused without both -Force AND -ConfirmDataLoss."
        Write-Err ""
        Write-Err "  Rotating ENCRYPTION_KEY invalidates every encrypted LLM API key,"
        Write-Err "  every connector credential, and breaks the audit-log HMAC chain."
        Write-Err ""
        Write-Err "  If you accept the data loss, re-run:"
        Write-Err "    .\setup.ps1 -RotateSecrets -Force -ConfirmDataLoss"
        exit 2
    }
    Write-WarnMsg "Rotating secrets — encrypted LLM keys + connector creds + audit chain will be invalidated."
}

# ── 1. Preflight ─────────────────────────────────────────────────────
Write-Step "Checking Docker…"
try { docker --version | Out-Null } catch {
    Write-Err "docker not found in PATH. Install Docker Desktop:"
    Write-Err "  https://docs.docker.com/desktop/install/windows-install/"
    exit 1
}
try { docker compose version | Out-Null } catch {
    Write-Err "Docker Compose v2 plugin missing. Upgrade Docker Desktop."
    exit 1
}
$dockerInfoOk = $true
try { docker info 2>$null | Out-Null; if ($LASTEXITCODE -ne 0) { $dockerInfoOk = $false } } catch { $dockerInfoOk = $false }
if (-not $dockerInfoOk) {
    Write-Err "Docker daemon not reachable. Start Docker Desktop and wait for it to be ready."
    exit 1
}
$dockerV = (docker --version) -replace '.*?(\d+\.\d+\.\d+).*','$1'
$composeV = (docker compose version --short)
Write-Ok "Docker $dockerV + Compose $composeV."

# ── 2. .env + secrets ────────────────────────────────────────────────
Write-Step "Provisioning .env…"
if (-not (Test-Path ".env")) {
    if (-not (Test-Path ".env.example")) {
        Write-Err ".env.example missing — fork looks incomplete."
        Write-Err "Clone the canonical repo: $RepoUrl"
        exit 1
    }
    Copy-Item .env.example .env
    Write-Ok "Created .env from .env.example."
} else {
    Write-Ok ".env already present — keeping existing values."
}

if ($RotateSecrets) {
    & .\scripts\generate-secrets.ps1 -Force
} else {
    & .\scripts\generate-secrets.ps1
}

# ACL down to current user (chmod 600 equivalent).
try {
    icacls .env /inheritance:r /grant:r "$($env:USERNAME):R" /grant:r "BUILTIN\Administrators:F" /grant:r "NT AUTHORITY\SYSTEM:F" | Out-Null
    Write-Ok "Locked down .env ACL to $env:USERNAME (read-only) + Administrators."
} catch {
    Write-WarnMsg "icacls failed — .env permissions not hardened."
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

# Source .env into the current PowerShell session so docker compose +
# our health probes see the operator-configured values.
foreach ($line in (Get-Content .env)) {
    if ($line -match '^\s*#') { continue }
    if ($line -match '^\s*$') { continue }
    if ($line -match '^([A-Za-z_][A-Za-z0-9_]*)=(.*)$') {
        $name = $Matches[1]
        $value = $Matches[2].Trim('"')
        Set-Item -Path "env:$name" -Value $value
    }
}

# ── 2b. Public-host detection ────────────────────────────────────────
function Get-PublicIp {
    # GCE
    try {
        $resp = Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 `
                -Uri "http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip" `
                -Headers @{ "Metadata-Flavor" = "Google" }
        if ($resp.StatusCode -eq 200 -and $resp.Content) { return $resp.Content.Trim() }
    } catch {}
    # AWS IMDSv2
    try {
        $token = (Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 -Method PUT `
                  -Uri "http://169.254.169.254/latest/api/token" `
                  -Headers @{ "X-aws-ec2-metadata-token-ttl-seconds" = "60" }).Content
        $resp = Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 `
                -Uri "http://169.254.169.254/latest/meta-data/public-ipv4" `
                -Headers @{ "X-aws-ec2-metadata-token" = $token }
        if ($resp.StatusCode -eq 200 -and $resp.Content) { return $resp.Content.Trim() }
    } catch {}
    return $null
}

$PublicHost = ""
if ($Domain) {
    $PublicHost = $Domain
    Write-Step "Using -Domain $Domain as the public host."
    $existing = (Get-Content .env) | Where-Object { $_ -notmatch '^HELIX_PUBLIC_DOMAIN=' }
    $existing += "HELIX_PUBLIC_DOMAIN=$Domain"
    [System.IO.File]::WriteAllLines((Resolve-Path .env), $existing, (New-Object System.Text.UTF8Encoding($false)))
} else {
    $detected = Get-PublicIp
    if ($detected) {
        $PublicHost = $detected
        Write-Step "Detected public IP: $detected"
    } else {
        $PublicHost = "localhost"
        Write-Step "No cloud metadata reachable; NEXT_PUBLIC_API_URL defaults to localhost."
    }
}

# NEXT_PUBLIC_API_URL: default EMPTY (relative, same-origin). The browser calls
# /api/* on the frontend origin, proxied to the backend (Next rewrite locally,
# Caddy for a TLS domain). Relative works for both and keeps the cookie
# same-origin. Never clobber an operator-set value; only seed when unset/empty.
$existingNpau = (((Get-Content .env) | Where-Object { $_ -match '^NEXT_PUBLIC_API_URL=' } | Select-Object -First 1) -replace '^NEXT_PUBLIC_API_URL=', '')
if ($existingNpau) {
    Write-Step "Keeping operator-set NEXT_PUBLIC_API_URL=$existingNpau"
    $NextPublicApiUrl = $existingNpau
} else {
    Write-Step "NEXT_PUBLIC_API_URL left empty (relative same-origin /api proxy)."
    $NextPublicApiUrl = ""
    $lines = (Get-Content .env) | Where-Object { $_ -notmatch '^NEXT_PUBLIC_API_URL=' }
    $lines += "NEXT_PUBLIC_API_URL="
    # Force UTF-8 *without* BOM so python-dotenv/compose can parse the file.
    [System.IO.File]::WriteAllLines((Resolve-Path .env), $lines, (New-Object System.Text.UTF8Encoding($false)))
}
$env:NEXT_PUBLIC_API_URL = $NextPublicApiUrl

# ── 2c. First-admin pre-seed ─────────────────────────────────────────
if ($AdminEmail -or $AdminPassword) {
    if (-not $AdminEmail -or -not $AdminPassword) {
        Write-Err "Both -AdminEmail and -AdminPassword must be supplied together."
        exit 1
    }
    if (-not (Test-Path ".helix")) { New-Item -ItemType Directory -Path ".helix" | Out-Null }
    $now = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    $sentinel = @{
        email      = $AdminEmail
        password   = $AdminPassword
        created_by = "setup.ps1"
        created_at = $now
    } | ConvertTo-Json -Compress
    [System.IO.File]::WriteAllText(".helix\first-admin.json", $sentinel, (New-Object System.Text.UTF8Encoding($false)))
    try {
        icacls ".helix\first-admin.json" /inheritance:r /grant:r "$($env:USERNAME):R" /grant:r "BUILTIN\Administrators:F" /grant:r "NT AUTHORITY\SYSTEM:F" | Out-Null
    } catch {}
    Write-Ok "First-admin credentials staged at .helix\first-admin.json (wave-3 'helix admin bootstrap' will consume)."
}

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
$pgUser = if ($env:POSTGRES_USER) { $env:POSTGRES_USER } else { "helix" }
for ($i = 1; $i -le 30; $i++) {
    docker compose @ComposeFiles exec -T postgres pg_isready -U $pgUser 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { $pgReady = $true; break }
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
        if ($resp.StatusCode -eq 200) { $ready = $true; break }
    } catch { }
    Start-Sleep -Seconds 2
}
if (-not $ready) {
    Write-Err "Backend did not pass /readyz within 120s. Recent logs:"
    docker compose @ComposeFiles logs --tail=80 backend
    exit 1
}
Write-Ok "Backend ready."

# ── 6. Summary ───────────────────────────────────────────────────────
if ($Domain) {
    $PublicFrontend = "https://$Domain"
    $PublicBackend  = "https://$Domain"
} else {
    $PublicFrontend = "http://${PublicHost}:$frontendPort"
    $PublicBackend  = "http://${PublicHost}:$backendPort"
}

Write-Host ""
Write-Host "Helix is up." -ForegroundColor Green
Write-Host ""
Write-Host "  Frontend   $PublicFrontend"
Write-Host "  Backend    $PublicBackend"
Write-Host "  OpenAPI    $PublicBackend/docs"
Write-Host "  Health     $PublicBackend/api/v1/health"
Write-Host "  Ready      $PublicBackend/api/v1/readyz"
Write-Host "  Metrics    $PublicBackend/metrics"
Write-Host ""
Write-Host "First-time setup — open the frontend and walk through the wizard:" -ForegroundColor DarkGray
Write-Host "  $PublicFrontend/setup/first-admin" -ForegroundColor DarkGray
Write-Host ""
Write-Host "Repo: $RepoUrl" -ForegroundColor DarkGray
Write-Host "Common ops:" -ForegroundColor DarkGray
Write-Host "  docker compose -f docker-compose.yml -f docker-compose.build.yml logs -f backend worker" -ForegroundColor DarkGray
Write-Host "  .\setup.ps1 -Down            # stop, keep data" -ForegroundColor DarkGray
Write-Host "  .\setup.ps1 -RotateSecrets -Force -ConfirmDataLoss" -ForegroundColor DarkGray
Write-Host "  docker compose --profile debug up -d temporal-ui  # opt-in Temporal UI on 127.0.0.1:8233" -ForegroundColor DarkGray
Write-Host ""
