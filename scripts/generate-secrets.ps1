# PowerShell version for Windows hosts.
# Mirrors scripts/generate-secrets.sh behaviour.
#
# Usage:
#   .\scripts\generate-secrets.ps1
#   .\scripts\generate-secrets.ps1 -Force
#   .\scripts\generate-secrets.ps1 -Print

param(
    [switch]$Force,
    [switch]$Print
)

$ErrorActionPreference = "Stop"
$RootDir = Resolve-Path (Join-Path $PSScriptRoot "..")
$EnvFile = Join-Path $RootDir ".env"
$EnvLocalFile = Join-Path $RootDir ".env.local"
$EnvExample = Join-Path $RootDir ".env.example"

# Safety: refuse to overwrite a .env that still contains the placeholder
# markers from .env.example (SC-003). Route generated secrets into .env.local
# instead so manual edits are preserved.
if ((Test-Path $EnvFile) -and (-not $Force) -and (-not $Print)) {
    $existing = Get-Content $EnvFile -ErrorAction SilentlyContinue
    if ($existing -and ($existing -match '=change_me|=helix_password')) {
        Write-Warning ("$EnvFile still contains placeholder markers (change_me / helix_password). " +
                      "Refusing to overwrite. Writing generated secrets to $EnvLocalFile " +
                      "instead — merge by hand or re-run with -Force.")
        $EnvFile = $EnvLocalFile
        if (-not (Test-Path $EnvFile)) {
            New-Item -ItemType File -Path $EnvFile | Out-Null
        }
    }
}

function RandHex([int]$ByteLength) {
    $bytes = New-Object byte[] $ByteLength
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    -join ($bytes | ForEach-Object { '{0:x2}' -f $_ })
}

function RandBase64UrlSafe([int]$ByteLength) {
    # General-purpose url-safe base64 WITHOUT padding (for HMAC-style secrets).
    # Do NOT use for ENCRYPTION_KEY — Fernet requires the '=' padding char.
    $bytes = New-Object byte[] $ByteLength
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('/', '_').Replace('+', '-')
}

function RandFernetKey {
    # Produce a valid 44-char Fernet key (32 bytes, url-safe base64 WITH '=' padding).
    # Fernet requires exactly 44 chars — do NOT call TrimEnd('=') here.
    # Priority: python (any) + cryptography > openssl > hard-fail.

    # Try python / python3 with cryptography installed.
    $pythonCmds = @('python', 'python3')
    foreach ($pyCmd in $pythonCmds) {
        $pyPath = Get-Command $pyCmd -ErrorAction SilentlyContinue
        if ($pyPath) {
            try {
                $out = & $pyCmd -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>$null
                if ($LASTEXITCODE -eq 0 -and $out) {
                    return $out.Trim()
                }
            } catch {}
        }
    }

    # Try openssl (Git-for-Windows ships openssl).
    $opensslPath = Get-Command openssl -ErrorAction SilentlyContinue
    if ($opensslPath) {
        try {
            # openssl rand 32 → 32 raw bytes → standard base64 (44 chars with one '=').
            # Replace +/ with -_ for url-safe encoding; keep the trailing '='.
            $b64 = & openssl rand -base64 32 2>$null
            if ($LASTEXITCODE -eq 0 -and $b64) {
                return $b64.Trim().Replace('/', '_').Replace('+', '-')
            }
        } catch {}
    }

    # Neither python+cryptography nor openssl available — hard-fail with instructions.
    Write-Error ("ENCRYPTION_KEY generation needs openssl OR python3-cryptography. " +
                 "Install: `pip install cryptography` OR ensure openssl is on PATH (e.g. Git-for-Windows).")
    exit 1
}

$PostgresPassword     = RandHex 16
$AppSecretKey         = RandHex 32
$JwtSecretKey         = RandHex 32
$EncryptionKey        = RandFernetKey
$AuditHmacKey         = RandHex 32
$TemporalUiPassword   = RandHex 12

if ($Print) {
    Write-Output "POSTGRES_PASSWORD=$PostgresPassword"
    Write-Output "APP_SECRET_KEY=$AppSecretKey"
    Write-Output "JWT_SECRET_KEY=$JwtSecretKey"
    Write-Output "ENCRYPTION_KEY=$EncryptionKey"
    Write-Output "AUDIT_HMAC_KEY=$AuditHmacKey"
    Write-Output "TEMPORAL_UI_PASSWORD=$TemporalUiPassword"
    exit 0
}

if (-not (Test-Path $EnvFile)) {
    if (Test-Path $EnvExample) {
        Copy-Item $EnvExample $EnvFile
        Write-Output "Created .env from .env.example"
    } else {
        New-Item -ItemType File -Path $EnvFile | Out-Null
        Write-Output "Created empty .env"
    }
}

function Upsert($Key, $Value) {
    $lines = Get-Content $EnvFile -ErrorAction SilentlyContinue
    $pattern = "^$Key="
    $matched = $lines | Where-Object { $_ -match $pattern }

    $placeholderPattern = "^$Key=$|=change_me|=change_me_32_byte_key|=$"
    if (-not $matched) {
        Add-Content -Path $EnvFile -Value "$Key=$Value"
        Write-Output "  + set $Key"
    } elseif ($Force -or ($matched -match $placeholderPattern)) {
        $newLines = $lines | ForEach-Object {
            if ($_ -match $pattern) { "$Key=$Value" } else { $_ }
        }
        $newLines | Set-Content $EnvFile
        Write-Output "  ~ updated $Key"
    } else {
        Write-Output "  = kept existing $Key (re-run with -Force to overwrite)"
    }
}

Write-Output "Writing secrets to $EnvFile"
Upsert "POSTGRES_USER"        "helix"
Upsert "POSTGRES_PASSWORD"    $PostgresPassword
Upsert "POSTGRES_DB"          "helix_metadata"
Upsert "APP_SECRET_KEY"       $AppSecretKey
Upsert "JWT_SECRET_KEY"       $JwtSecretKey
Upsert "ENCRYPTION_KEY"       $EncryptionKey
Upsert "AUDIT_HMAC_KEY"       $AuditHmacKey
Upsert "TEMPORAL_UI_PASSWORD" $TemporalUiPassword

$DbUrl = "postgresql://helix:$PostgresPassword@postgres:5432/helix_metadata"
Upsert "DATABASE_URL" $DbUrl

Write-Output "Done. .env is populated with generated secrets."
Write-Output "Temporal UI password: $TemporalUiPassword"
