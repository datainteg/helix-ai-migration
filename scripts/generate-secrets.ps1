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
$EnvExample = Join-Path $RootDir ".env.example"

function RandHex([int]$ByteLength) {
    $bytes = New-Object byte[] $ByteLength
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    -join ($bytes | ForEach-Object { '{0:x2}' -f $_ })
}

function RandBase64UrlSafe([int]$ByteLength) {
    $bytes = New-Object byte[] $ByteLength
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('/', '_').Replace('+', '-')
}

$PostgresPassword     = RandHex 16
$AppSecretKey         = RandHex 32
$JwtSecretKey         = RandHex 32
$EncryptionKey        = RandBase64UrlSafe 32
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
