# DEPLOY_SECRETS — Secret-generation + `.env.example` one-click deploy audit

> Generated 2026-05-26. Scope: `.env.example`, `scripts/generate-secrets.sh`,
> `scripts/generate-secrets.ps1`, `backend/app/core/config.py`, `docker-compose.yml`,
> `docker-compose.build.yml`, `DEPLOY.md`, `docs/MIGRATION_NOTES.md`.
>
> Cross-references: `docs/review-v2/REVIEW_INFRA.md` INFRA-025..029, INFRA-038..042;
> `docs/review-v4/DEPLOY_SETUP.md` DSETUP-010..016.
>
> Severity legend: 🔴 CRITICAL · 🟠 HIGH · 🟡 MED · 🔵 LOW.

---

## 0. Headline numbers

| Severity | Count |
|---|---|
| 🔴 CRITICAL | **2** |
| 🟠 HIGH | **6** |
| 🟡 MED | **5** |
| 🔵 LOW | **4** |
| **Total** | **17** |

**Verdict:** `needs work ⚠️`. The secret-generation toolchain is well-structured
in intent — it refuses to boot in production with placeholder values, generates
real entropy, and chmods the `.env` file. However two blocking issues make it
unsafe to ship as-is for a one-click Windows deploy: (1) `generate-secrets.ps1`
**always** produces a 43-char `ENCRYPTION_KEY` that the `cryptography` library
rejects at runtime despite passing the startup validator, and (2) the `.sh` shell
fallback has the same bug when `python3+cryptography` is absent. Both silent-failure
paths result in a stack that appears to start (the validator is fooled) but then
crashes on the first `Fernet` call. All other findings are HIGH or below and are
mechanical fixes.

---

## 1. Findings

### 🔴 DS-001 — `generate-secrets.ps1` ALWAYS emits an invalid Fernet key for `ENCRYPTION_KEY`

**File proof.** `scripts/generate-secrets.ps1:34`:
```powershell
$EncryptionKey = RandBase64UrlSafe 32
```
`RandBase64UrlSafe` (lines 25-29) calls
`[Convert]::ToBase64String($bytes).TrimEnd('=').Replace('/', '_').Replace('+', '-')`.
For 32 bytes, `ToBase64String` produces a 44-char standard base64 string with one
trailing `=` (this is deterministic for 32-byte input). `.TrimEnd('=')` strips it to
**43 chars**. `cryptography.fernet.Fernet` requires exactly 44 url-safe base64 chars
(the trailing `=` is mandatory); it raises `ValueError: Fernet key must be 32 url-safe
base64-encoded bytes` on any 43-char string.

**Why the validator is fooled.** `backend/app/core/config.py:111`:
```python
decoded = base64.urlsafe_b64decode(self.ENCRYPTION_KEY + "==")
if len(decoded) != 32:
    raise ValueError
```
Adding `==` before decoding works for both 43-char (missing one pad) and 44-char
(has one pad) strings — both decode to 32 bytes. The validator passes. The backend
starts. The first LLM key storage call fails at runtime inside `Fernet(key)`.

**Blast radius.** On Windows, every operator who runs `generate-secrets.ps1` gets a
stack that boots (validator passes), then crashes with `ValueError` on the first
`encrypt_value()` call — which is hit by the first-admin wizard's LLM provider setup.
No useful error is surfaced to the operator (the exception propagates as a 500 from
a decorator several layers up). The operator cannot store LLM credentials at all.

**Fix.**
```powershell
function RandFernetKey {
    $bytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    # Fernet REQUIRES the trailing '=' — do NOT TrimEnd here.
    $b64 = [Convert]::ToBase64String($bytes).Replace('/', '_').Replace('+', '-')
    # Standard base64 of 32 bytes is always 44 chars with exactly one '='.
    return $b64
}
$EncryptionKey = RandFernetKey
```
The `Replace` calls substitute `+/` for `-_` but do NOT strip the `=`, producing the
required 44-char url-safe base64 string with padding.

---

### 🔴 DS-002 — `generate-secrets.sh` shell fallback emits an invalid Fernet key when `python3+cryptography` unavailable (INFRA-025, DSETUP-011 confirmed)

**File proof.** `scripts/generate-secrets.sh:43-59`:
```bash
rand_base64_urlsafe() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -base64 "$1" | tr '/+' '_-' | tr -d '=\n'
  else
    head -c "$1" /dev/urandom | base64 | tr '/+' '_-' | tr -d '=\n'
  fi
}

rand_fernet_key() {
  if command -v python3 >/dev/null 2>&1; then
    python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null \
      || rand_base64_urlsafe 32
  else
    rand_base64_urlsafe 32
  fi
}
```

The happy path (`python3` + `cryptography` installed) produces the correct 44-char
Fernet key. But:

- If `python3` is absent → `rand_base64_urlsafe 32` → `tr -d '=\n'` strips the
  trailing `=` → **43 chars → Fernet rejects at runtime**.
- If `python3` is present but `cryptography` is not installed →
  `python3 -c "from cryptography.fernet…"` returns non-zero → `|| rand_base64_urlsafe 32`
  → same 43-char path. This is the default on Ubuntu 24.04 LTS minimal (cryptography
  is not in base Python packages; `python3-cryptography` requires explicit `apt install`).
- The `openssl` path (`openssl rand -base64 32 | tr -d '=\n'`) has the same bug: strips
  the `=` that Fernet requires.

The validator in `config.py` is fooled the same way as in DS-001.

**Fix.** Per the DEPLOY_SETUP.md DSETUP-011 recommendation — preserve the `=` padding
for the Fernet path specifically, and hard-fail if no valid generator is available:
```bash
rand_fernet_key() {
  if command -v python3 >/dev/null 2>&1; then
    if out=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null); then
      printf '%s' "$out"
      return 0
    fi
  fi
  if command -v openssl >/dev/null 2>&1; then
    # 32 random bytes → url-safe base64 WITH the trailing '=' padding intact.
    # Do NOT strip '=' — Fernet requires exactly 44 chars including the pad.
    printf '%s' "$(openssl rand 32 | base64 | tr '/+' '_-' | tr -d '\n')"
    return 0
  fi
  echo "ERROR: Cannot generate a Fernet key — install python3+cryptography or openssl." >&2
  exit 1
}
```
Also: fix the `config.py` validator to use the correct padding arithmetic instead of
appending `==` blindly, so it would catch the 43-char case:
```python
# Strict Fernet check: must be exactly 44 chars and decode to 32 bytes.
if len(self.ENCRYPTION_KEY) != 44:
    raise ValueError(
        "ENCRYPTION_KEY must be exactly 44 chars (32 bytes url-safe base64 with padding). "
        "Generate with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
    )
try:
    decoded = base64.urlsafe_b64decode(self.ENCRYPTION_KEY)
    if len(decoded) != 32:
        raise ValueError
except Exception:
    raise ValueError("ENCRYPTION_KEY is not valid base64.")
```

---

### 🟠 DS-003 — `AUDIT_HMAC_KEY` rotation safety is documented only in `setup.sh` warning text, not in `.env.example` or DEPLOY.md

**File proof.**
- `backend/app/api/audit.py:27,39`: `AUDIT_HMAC_KEY` is used to HMAC every audit chain
  entry. Rotating it invalidates the cryptographic link between all prior entries and
  any new entry.
- `docs/review-v2/REVIEW_INFRA.md:210-216` (INFRA-020) and
  `docs/review-v4/DEPLOY_SETUP.md:271-298` (DSETUP-010) both document the hazard.
- `.env.example:48-50` says "MUST differ from JWT_SECRET_KEY so JWT rotation does not
  invalidate the audit chain" — correct. But the reciprocal constraint is not stated:
  **do not rotate AUDIT_HMAC_KEY after the chain has entries**.
- `DEPLOY.md:138` lists `AUDIT_HMAC_KEY` in the table without any rotation warning.

`config.py:98-101` enforces uniqueness from `JWT_SECRET_KEY` at startup — good. But
there is no runtime barrier preventing an operator from running
`./setup.sh --rotate-secrets` and then finding that
`GET /audit-logs/verify` reports every historical entry as "broken".

**Fix.** Add to `.env.example` under `AUDIT_HMAC_KEY`:
```
# WARNING: Do NOT rotate AUDIT_HMAC_KEY after the chain has been started.
# Rotation invalidates every prior HMAC link. If you must rotate, export
# all audit logs to a signed archive first, then treat the new key as a
# fresh chain start. See docs/MIGRATION_NOTES.md for the DEK/KEK rotation runbook.
```
And in `DEPLOY.md`, flag the rotation table row accordingly.

---

### 🟠 DS-004 — `generate-secrets.ps1` does NOT set file permissions on `.env` (INFRA-028 confirmed)

**File proof.**
- `scripts/generate-secrets.sh:131`: `chmod 600 "$ENV_FILE" 2>/dev/null || true` — Linux
  restricts `.env` to owner-only read/write.
- `scripts/generate-secrets.ps1`: no equivalent `icacls` call. The file is created with
  inherited ACLs from the parent directory, meaning every user account on the machine can
  read it by default.

On a shared Windows developer machine or a GCE Windows Server instance, the cleartext
secrets in `.env` are readable by any local user or service account.

**Fix.** After writing `.env` in `generate-secrets.ps1`:
```powershell
# Restrict .env to current user only (deny Everyone else).
icacls $EnvFile /inheritance:r /grant:r "$env:USERNAME:F" | Out-Null
Write-Output "  .env permissions locked to $env:USERNAME"
```

---

### 🟠 DS-005 — `CORS_ORIGINS` default left as `["http://localhost:3000"]` — operator must change for GCP but there is no prompt or validator for the production value (INFRA-038 confirmed)

**File proof.**
- `.env.example:55-57`: `CORS_ORIGINS=["http://localhost:3000"]`
- `backend/app/core/config.py:103-107`: production blocks `*` and requires
  `CORS_ORIGIN_REGEX` to be empty. But the `localhost` default passes both checks
  if `APP_ENV=production` is set — the backend starts, the admin UI loads, but
  **every browser request from the operator's real domain is rejected by the CORS
  middleware** (`app/main.py:166`) with a 403.
- `CORS_ORIGIN_REGEX` default in config.py is the permissive regex
  `^https?://(localhost|127\.0\.0\.1)(:\d+)?$` — but the production validator
  (`config.py:106-107`) raises `ValueError` if `CORS_ORIGIN_REGEX` is non-empty
  in production. This means the default regex would prevent production boot if
  `APP_ENV=production` is set and `CORS_ORIGIN_REGEX` was left in `.env`.

**GCP single-VM scenario.** The operator's browser hits `http://<VM-IP>:3000`.
The frontend makes API calls to `http://<VM-IP>:8000`. `CORS_ORIGINS` must be set
to `["http://<VM-IP>:3000"]` (or the real domain once HTTPS is set up). The
`.env.example` says to set this but does not tell the operator what the right value
is for their IP — the setup script does not prompt for it.

**Fix.** `setup.sh` should detect the host's public IP (via `curl -s ifconfig.me`
or `hostname -I`) and pre-fill `CORS_ORIGINS` and `NEXT_PUBLIC_API_URL` with the
correct value, or at minimum prompt the operator.

---

### 🟠 DS-006 — `TEMPORAL_UI_USERNAME=admin` shipped as hardcoded default in `.env.example` with `TEMPORAL_AUTH_ENABLED=false` in compose (INFRA-039 confirmed)

**File proof.**
- `.env.example:39`: `TEMPORAL_UI_USERNAME=admin`
- `.env.example:40`: `TEMPORAL_UI_PASSWORD=` (blank until generated)
- `docker-compose.yml:102`: `TEMPORAL_AUTH_ENABLED=${TEMPORAL_AUTH_ENABLED:-false}`
  defaults to **disabled**.
- `docker-compose.yml:93`: `profiles: ["debug"]` — temporal-ui only starts when
  `--profile debug` is passed. This mitigates the immediate risk.

However the design is still problematic: when the operator does enable the profile (as
the workflow debugging docs advise), auth is disabled unless they explicitly set
`TEMPORAL_AUTH_ENABLED=true`. The hardcoded `admin` username adds no security but
gives the false impression that auth is on.

**Fix.**
1. Remove `TEMPORAL_UI_USERNAME=admin` from `.env.example` or change its comment to
   say "username is only used when TEMPORAL_AUTH_ENABLED=true".
2. Change the compose default: `TEMPORAL_AUTH_ENABLED=${TEMPORAL_AUTH_ENABLED:-true}`.
3. `generate-secrets.sh` already generates a random `TEMPORAL_UI_PASSWORD` — document
   that both `TEMPORAL_AUTH_ENABLED=true` and `TEMPORAL_UI_PASSWORD` must be set to
   protect the UI.

---

### 🟠 DS-007 — `NEXT_PUBLIC_API_URL` is baked into the frontend image at build time; no GCP/arbitrary-IP guidance in `.env.example` or `setup.sh`

**File proof.**
- `docker-compose.build.yml:27`: `NEXT_PUBLIC_API_URL: ${NEXT_PUBLIC_API_URL:-http://localhost:8000}`
  — baked as a Next.js build arg.
- `docker-compose.yml:172`: runtime env also set but **ignored** for Next.js `NEXT_PUBLIC_*`
  vars (they are statically compiled at build time, not runtime).
- `.env.example:63`: `NEXT_PUBLIC_API_URL=http://localhost:8000` — the default is
  localhost, which is wrong for any non-local deployment.
- `DEPLOY.md:144`: "Production: `https://api.yourdomain.com`" — but there is no
  instruction to rebuild after changing this value.

On a GCP single-VM setup:
- If the operator changes `NEXT_PUBLIC_API_URL` in `.env` **after** building the image,
  the frontend image still has `localhost:8000` baked in. Browser calls fail with CORS
  or network errors.
- If the operator does `docker compose up` without the build overlay (pull mode), the
  image was built with a different URL and the operator cannot patch it without
  rebuilding.

**Fix.** Add a comment block to `.env.example` explaining the bake-time constraint:
```
# NEXT_PUBLIC_API_URL — MUST be set BEFORE building the frontend image.
# For a GCP single-VM with a public IP:
#   NEXT_PUBLIC_API_URL=http://<YOUR-VM-IP>:8000   (or https://api.yourdomain.com)
# After changing this value, rebuild the frontend image:
#   docker compose -f docker-compose.yml -f docker-compose.build.yml build frontend
#   docker compose up -d frontend
```

---

### 🟠 DS-008 — `upsert` placeholder regex over-matches, silently overwriting operator-set values (INFRA-027, DSETUP-012 confirmed)

**File proof.** `scripts/generate-secrets.sh:102`:
```bash
local placeholder_re='^'"$key"'=$|=change_me|=change_me_32_byte_key|=$'
```
The second alternative `=change_me` is an unanchored substring match. A value like
`POSTGRES_PASSWORD=changeme_really_strong_2026!` matches `=change_me` and is silently
overwritten on the next `./setup.sh` run. The third alternative `=$` is redundant with
the first (`^key=$`) but also matches values like `REDIS_URL=redis://redis:6379/0`
partially — it is the rightmost alternative and `grep -Eq` would match if the VALUE
portion of any other line ends with `=`. This could in theory over-match in a
multi-line `grep` context, though in practice `grep` on a single extracted line is safe.
The real hazard is the unanchored `=change_me`.

The PS1 equivalent (`scripts/generate-secrets.ps1:63`) has the same unanchored pattern:
`$placeholderPattern = "^$Key=$|=change_me|=change_me_32_byte_key|=$"`.

**Fix.**
```bash
local placeholder_re="^${key}=\$|^${key}=change_me\$|^${key}=change_me_32_byte_key\$"
```
And in PS1:
```powershell
$placeholderPattern = "^$Key=$|^$Key=change_me$|^$Key=change_me_32_byte_key$"
```

---

### 🟡 DS-009 — `SAFE_EXECUTION_MODE` valid enum not documented in `.env.example` or SECURITY.md (INFRA-042 confirmed)

**File proof.**
- `.env.example:97`: `SAFE_EXECUTION_MODE=analysis_only`
- `backend/app/core/config.py:63`: `SAFE_EXECUTION_MODE: str = "analysis_only"` — no
  enum validator, no Literal type, no `Enum` subclass.
- `SECURITY.md:51`: "SAFE_EXECUTION_MODE=analysis_only by default — never set to
  `execute`" — mentions `execute` as a forbidden value, but no full list.
- No code validates the value at startup or at runtime — an operator who sets
  `SAFE_EXECUTION_MODE=exec` (a typo) would get a silently wrong behavior.

The valid enum values need to be determined from the consuming code:

**Fix.** Enumerate in `.env.example`:
```
# Valid values: analysis_only | dry_run | execute
# analysis_only (default): agents read and plan only; no DDL/DML executed.
# dry_run: generates migration SQL but does not apply it.
# execute: applies DDL/DML to the target database. ONLY use in a staging env.
# NEVER set to `execute` in production unless you have confirmed rollback capability.
SAFE_EXECUTION_MODE=analysis_only
```
And add a `Literal` constraint in config.py:
```python
from typing import Literal
SAFE_EXECUTION_MODE: Literal["analysis_only", "dry_run", "execute"] = "analysis_only"
```

---

### 🟡 DS-010 — `HELIX_PROVIDER_RATES_JSON` missing example value (INFRA-040 confirmed)

**File proof.** `.env.example:127-132`:
```
# JSON map of "{provider}:{model}" → [input_usd_per_1m, output_usd_per_1m].
HELIX_PROVIDER_RATES_JSON=
```
No example value. `backend/app/services/cost_service.py:31-53` shows the expected
format and the default keys (e.g. `"openai:gpt-4.1": (3.0, 10.0)`). An operator
trying to override Anthropic pricing has to read `cost_service.py` to discover the
key format.

**Fix.** Add a commented example:
```
# Optional: override per-model pricing. JSON map of "provider:model" → [input_$/1M, output_$/1M]
# Example: HELIX_PROVIDER_RATES_JSON={"openai:gpt-4.1":[2.50,10.0],"anthropic:claude-sonnet-4-6":[2.50,12.0]}
HELIX_PROVIDER_RATES_JSON=
```

---

### 🟡 DS-011 — `SMTP_USERNAME` in `.env.example` vs `SMTP_USER` in `config.py` — silent name mismatch; email delivery silently broken

**File proof.**
- `.env.example:102`: `SMTP_USERNAME=`
- `backend/app/core/config.py:74`: `SMTP_USER: str = ""`

`pydantic-settings` loads env vars by field name. The field is `SMTP_USER` so
`SMTP_USERNAME` in `.env` is silently ignored — Pydantic's `extra="ignore"` swallows
the unknown var. An operator who sets `SMTP_USERNAME=user@example.com` in `.env` sees
no error but SMTP auth fails because the SMTP client uses `settings.SMTP_USER` which
is empty.

Additionally, `.env.example` has `SMTP_FROM_EMAIL`, `SMTP_USE_TLS`, `SMTP_USE_STARTTLS`,
`SMTP_FROM_NAME` — none of which have corresponding fields in `Settings`. The fields
in `Settings` are `EMAIL_FROM`, `SMTP_TLS`, `EMAIL_FROM_NAME`, `EMAIL_ENABLED` —
completely different names.

**Fix.** Align `.env.example` with `config.py` field names (the authoritative source).
Either:
1. Rename the config fields to match `.env.example` (more operator-friendly), or
2. Update `.env.example` to use the exact `Settings` field names.

The mismatch should be caught by a startup validation test:
`assert settings.SMTP_USER != ""` when the `.env` has `SMTP_USERNAME` set.

---

### 🟡 DS-012 — `POSTGRES_PASSWORD` entropy is 128 bits while all other secrets are 256 bits (INFRA-026, DSETUP-015 confirmed)

**File proof.** `scripts/generate-secrets.sh:64`:
```bash
POSTGRES_PASSWORD_VAL="$(rand_hex 16)"   # 32 hex chars = 128 bits
```
All other secrets: `rand_hex 32` = 256 bits. `POSTGRES_PASSWORD` is used only for
internal service-to-service auth (Postgres is not exposed to the host network in prod
compose) so 128 bits is operationally fine, but the inconsistency creates confusion when
auditors compare entropy levels.

**Fix.** Change to `rand_hex 32` for parity.

---

### 🟡 DS-013 — DEK rotation (`/admin/org/rotate-dek`) requires no new env var, but operator runbook for KEK migration not linked from `.env.example` or `DEPLOY.md`

**File proof.** `docs/MIGRATION_NOTES.md:50-138`: the DEK rotation runbook is
comprehensive. The key points:
- DEK rotation is triggered via API only; no new env var is needed.
- `ENCRYPTION_KEY` (the master KEK) is used via `MultiFernet([direct_key, legacy_sha256_key])`
  after the wave-1 fix — existing legacy ciphertext can still be decrypted during
  transition.
- `rotate_kek_secrets()` rewraps flat-KEK columns from the legacy sha256-derived path to
  the direct-key path.

Neither `.env.example` nor `DEPLOY.md` links to this runbook or warns that the direct
Fernet path (wave-1 fix) requires a one-time `rotate_kek_secrets()` run on existing
deployments upgrading from the sha256-derive path.

**Fix.** Add a comment in `.env.example` under `ENCRYPTION_KEY`:
```
# After upgrading from a pre-wave-1 deployment: run `rotate_kek_secrets()` once
# to rewrap stored ciphertext to the direct-Fernet path. See docs/MIGRATION_NOTES.md.
```

---

### 🔵 DS-014 — Idempotency Redis uses the same `REDIS_URL` as the JWT revocation cache — documented nowhere

**File proof.**
- `backend/app/utils/idempotency.py:111-118`: calls `get_redis()` which uses
  `settings.REDIS_URL`.
- `backend/app/core/config.py:43`: `REDIS_URL: str = "redis://localhost:6379/0"`
- No separate `IDEMPOTENCY_REDIS_URL` or `REVOCATION_REDIS_URL` field in `Settings`.

Both the JWT revocation set and the idempotency cache share `redis://redis:6379/0`. This
is fine for single-VM installs but means a Redis flush (e.g. for debugging or a Redis
restart) simultaneously invalidates all revoked tokens and replays all idempotency
windows — a security + correctness hazard for any operator who follows the common
"flush Redis to reset state" workflow.

**Fix.** Document in `.env.example` that `REDIS_URL` is shared for all Redis uses and
that flushing it invalidates JWT revocations. If operators need isolation, add optional
`REDIS_REVOCATION_URL` and `REDIS_IDEMPOTENCY_URL` fields that fall back to `REDIS_URL`.

---

### 🔵 DS-015 — Bootstrap LLM API keys (`OPENAI_API_KEY` etc.) are plaintext in `.env`; admin-UI path encrypts at rest — trade-off not documented (INFRA-041 confirmed)

**File proof.** `.env.example:71-79`: bootstrap keys are clearly marked `# Optional`.
But there is no warning that unlike admin-UI-configured keys (which are encrypted by
`secret_service.encrypt_value`), these env vars sit in cleartext in `.env` and in the
process environment of every Docker container that loads `env_file: .env`.

**Fix.** Add to the bootstrap keys section:
```
# NOTE: These bootstrap keys are stored in cleartext in .env and visible to all
# containers. The admin UI path (recommended) encrypts keys at rest with ENCRYPTION_KEY.
# Remove these vars once you have configured the provider via the admin UI.
```

---

### 🔵 DS-016 — `--print` mode leaks secrets to shell history without warning (INFRA-029 confirmed)

**File proof.** `scripts/generate-secrets.sh:71-81`: `--print` writes secrets to stdout
with no warning. Shell history captures the command; if stdout is also logged (e.g. via
`tee` to a CI log, a systemd journal, or a terminal session recorder), all six secrets
are leaked.

**Fix.** Add a warning line at the top of the `--print` output:
```
echo "# WARNING: These secrets will appear in your terminal and shell history."
echo "# Pipe to a file or use write mode (omit --print) for production deploys."
```

---

### 🔵 DS-017 — `APP_SECRET_KEY` is generated but does not appear in the `DEPLOY.md` secrets table — operators may not know it is required

**File proof.**
- `scripts/generate-secrets.sh:65`: `APP_SECRET_KEY_VAL="$(rand_hex 32)"`
- `backend/app/core/config.py:89-90`: production blocks `change_me` or ephemeral default.
- `DEPLOY.md:133-138`: the secrets table lists `POSTGRES_PASSWORD`, `APP_SECRET_KEY`,
  `JWT_SECRET_KEY`, `ENCRYPTION_KEY`, `TEMPORAL_UI_PASSWORD` — `APP_SECRET_KEY` IS
  listed. OK.
- But `AUDIT_HMAC_KEY` is **not in the DEPLOY.md table** even though it is REQUIRED
  (config.py:91-92 blocks startup without it in production).

**Fix.** Add `AUDIT_HMAC_KEY` to `DEPLOY.md:133` secrets table.

---

## 2. Diff: env vars read by `config.py` vs `.env.example` vs `generate-secrets.*`

### 2.1 Required secrets: coverage matrix

| Variable | `.env.example` | `config.py` default | Generated by `.sh` | Generated by `.ps1` | Valid format |
|---|---|---|---|---|---|
| `APP_SECRET_KEY` | `=` (blank, REQUIRED) | ephemeral hex | `rand_hex 32` (64 hex) | `RandHex 32` (64 hex) | ✅ |
| `POSTGRES_PASSWORD` | `=` (blank, REQUIRED) | `"helix_password"` (hardcoded!) | `rand_hex 16` (32 hex) | `RandHex 16` (32 hex) | ✅ (128 bit) |
| `JWT_SECRET_KEY` | `=` (blank, REQUIRED) | ephemeral hex | `rand_hex 32` (64 hex) | `RandHex 32` (64 hex) | ✅ |
| `ENCRYPTION_KEY` | `=` (blank, REQUIRED) | ephemeral Fernet | `Fernet.generate_key()` or broken fallback | `RandBase64UrlSafe 32` (43 chars) | 🔴 PS1 always wrong |
| `AUDIT_HMAC_KEY` | `=` (blank, REQUIRED) | ephemeral hex | `rand_hex 32` (64 hex) | `RandHex 32` (64 hex) | ✅ |
| `DATABASE_URL` | `=` (blank, constructed) | hardcoded localhost URL | constructed from password | constructed from password | ✅ |
| `TEMPORAL_UI_PASSWORD` | `=` (blank, optional) | not in config.py | `rand_hex 12` (24 hex) | `RandHex 12` (24 hex) | ✅ |

**Note on `POSTGRES_PASSWORD` in `config.py`:** The field `DATABASE_URL` has a hardcoded
default `"postgresql://helix:helix_password@localhost:5432/helix_metadata"` at
`config.py:41`. This means in development (non-production), the app will use
`helix_password` as the DB password if `DATABASE_URL` is not set. This is a dev-only
risk (production blocks it via the ephemeral check) but the hardcoded value should be
documented as dev-only.

### 2.2 Vars in `.env.example` with no matching `config.py` field

These vars are consumed by other services (Postgres, Docker Compose, frontend) or are
not yet wired into the backend `Settings` class:

| Variable | Consumed by | Risk |
|---|---|---|
| `POSTGRES_USER`, `POSTGRES_DB` | docker-compose.yml environment | OK — compose reads directly |
| `TEMPORAL_UI_USERNAME`, `TEMPORAL_UI_PASSWORD` | docker-compose.yml temporal-ui service | OK — not a backend setting |
| `NEXT_PUBLIC_API_URL` | Next.js build arg | 🟠 Must be correct before build (bake-time) |
| `OPENAI_API_KEY` etc. | Optional bootstrap — passed via env_file | 🔵 Plaintext in env |
| `S3_BUCKET`, `S3_REGION` etc. | Consumed by `boto3` chain, not Settings | 🔵 Not validated at startup |
| `HELIX_SLACK_USER_MAP`, `HELIX_SLACK_DEFAULT_USER`, `SLACK_SIGNING_SECRET` | `backend/app/api/integrations.py` | 🔵 OK — read via `os.getenv` |
| `HELIX_PROVIDER_RATES_JSON` | `backend/app/services/cost_service.py` | 🟡 No example value (DS-010) |
| `DATABASE_READ_URL` | Not referenced in Settings or any current API | 🟡 Dead var — no reader in code |
| `SMTP_USERNAME`, `SMTP_FROM_EMAIL`, `SMTP_FROM_NAME`, `SMTP_USE_TLS`, `SMTP_USE_STARTTLS` | Misnamed — should be `SMTP_USER`, `EMAIL_FROM`, `EMAIL_FROM_NAME`, `SMTP_TLS` | 🟠 Silent mismatch (DS-011) |

### 2.3 Vars in `config.py` with no `.env.example` entry

These are undocumented to operators:

| Variable | Default | Risk |
|---|---|---|
| `BACKEND_HOST` | `"0.0.0.0"` | 🟡 Not documented; relevant for bind hardening |
| `BACKEND_PORT` | `8000` | 🔵 Low — compose override via `BACKEND_HOST_PORT` |
| `EMAIL_ENABLED` | `False` | 🟡 Operators don't know to set `EMAIL_ENABLED=true` for SMTP |
| `EMAIL_FROM` | `"noreply@helix-migration.app"` | 🔵 Low |
| `EMAIL_FROM_NAME` | `"Helix Migration"` | 🔵 Low |
| `SENDGRID_API_KEY` | `""` | 🟡 SendGrid path completely undocumented |
| `SMTP_TLS` / `SMTP_USER` | `True` / `""` | 🟠 Misnamed in `.env.example` (DS-011) |

---

## 3. Full variable table: required, optional, example values, rotation cadence

### 3.1 REQUIRED — must be set before production boot

| Variable | Example value | Entropy | Generated by | Rotation cadence | Notes |
|---|---|---|---|---|---|
| `APP_SECRET_KEY` | `a3b1...` (64 hex chars) | 256 bit | `generate-secrets.*` | Annual or on compromise | General app signing |
| `POSTGRES_PASSWORD` | `4f2a...` (32 hex chars) | 128 bit | `generate-secrets.*` | Annual; requires `DATABASE_URL` update | 128 bit is acceptable for internal-only DB |
| `JWT_SECRET_KEY` | `9c8d...` (64 hex chars) | 256 bit | `generate-secrets.*` | On suspected compromise; invalidates all sessions | Must differ from `AUDIT_HMAC_KEY` |
| `ENCRYPTION_KEY` | `dGVzdA...=` (44 chars, url-safe base64) | 256 bit | `generate-secrets.*` (sh: python3 path only) | On KEK compromise; requires full re-encryption of all stored secrets before rotation | 🔴 PS1 currently generates invalid key (DS-001) |
| `AUDIT_HMAC_KEY` | `7b4e...` (64 hex chars) | 256 bit | `generate-secrets.*` | Do NOT rotate unless full chain export first | Rotation breaks all prior HMAC chain links |
| `DATABASE_URL` | `postgresql://helix:<PASS>@postgres:5432/helix_metadata` | N/A | `generate-secrets.*` (constructed) | When `POSTGRES_PASSWORD` rotates | Must stay in sync with `POSTGRES_PASSWORD` |
| `CORS_ORIGINS` | `["https://helix.example.com"]` | N/A | Manual | When frontend domain changes | `*` blocked in production; localhost default wrong for non-local |
| `NEXT_PUBLIC_API_URL` | `https://api.example.com` | N/A | Manual; baked at build time | When API domain changes (requires image rebuild) | Bake-time only — runtime env ignored |

### 3.2 STRONGLY RECOMMENDED — not strictly required to boot, but needed for a secure deployment

| Variable | Example value | Generated by | Rotation cadence | Notes |
|---|---|---|---|---|
| `TEMPORAL_UI_PASSWORD` | `3fa8...` (24 hex chars) | `generate-secrets.*` | Annual | Only active when `TEMPORAL_AUTH_ENABLED=true` |
| `TEMPORAL_AUTH_ENABLED` | `true` | Manual | N/A | Default is `false` — change before exposing port 8233 |
| `APP_ENV` | `production` | Manual | N/A | Enables all production validators in `config.py` |
| `FRONTEND_URL` | `https://helix.example.com` | Manual | When domain changes | Used in invitation + reset emails |

### 3.3 OPTIONAL — feature-gated

| Variable | Example value | Notes |
|---|---|---|
| `OPENAI_API_KEY` | `sk-...` | Bootstrap only; use admin UI to avoid cleartext in env |
| `ANTHROPIC_API_KEY` | `sk-ant-...` | Same |
| `GOOGLE_GEMINI_API_KEY` | `AIzaSy...` | Same |
| `DEEPSEEK_API_KEY` | `sk-...` | Same |
| `OPENROUTER_API_KEY` | `sk-or-...` | Same |
| `CUSTOM_LLM_BASE_URL` | `http://ollama:11434/v1` | Same |
| `CUSTOM_LLM_API_KEY` | (blank for local) | Same |
| `SMTP_HOST` | `smtp.sendgrid.net` | Required if `EMAIL_ENABLED=true` |
| `SMTP_PORT` | `587` | Required if `EMAIL_ENABLED=true` |
| `SMTP_USER` | `apikey` | Note: `.env.example` incorrectly names this `SMTP_USERNAME` |
| `SMTP_PASSWORD` | `SG...` | Required if `EMAIL_ENABLED=true` |
| `EMAIL_ENABLED` | `true` | Must be set to enable SMTP; absent from `.env.example` |
| `EMAIL_FROM` | `noreply@example.com` | Absent from `.env.example` (listed as `SMTP_FROM_EMAIL`) |
| `SENDGRID_API_KEY` | `SG...` | Alternative to SMTP; absent from `.env.example` |
| `SENTRY_DSN` | `https://...@sentry.io/...` | Optional observability |
| `OTEL_ENDPOINT` | `https://otel.example.com:4318` | Optional OTel exporter |
| `SLACK_SIGNING_SECRET` | `abc123...` | Required for Slack slash-command integration |
| `HELIX_SLACK_USER_MAP` | `/etc/helix/slack-user-map.json` | Slack user → Helix user mapping |
| `HELIX_SLACK_DEFAULT_USER` | `user-uuid-here` | Fallback Slack → Helix user |
| `HELIX_PROVIDER_RATES_JSON` | `{"openai:gpt-4.1":[2.5,10.0]}` | Override model pricing |
| `DATABASE_READ_URL` | `postgresql://...` | Optional read replica |
| `ARTIFACT_STORAGE_PROVIDER` | `s3` | `local` (default) or `s3` |
| `S3_BUCKET` | `helix-artifacts` | Required if `ARTIFACT_STORAGE_PROVIDER=s3` |
| `S3_REGION` | `us-east-1` | Required if `ARTIFACT_STORAGE_PROVIDER=s3` |
| `SAFE_EXECUTION_MODE` | `analysis_only` | Valid: `analysis_only`, `dry_run`, `execute` |

---

## 4. Verdict

**Two CRITICAL issues block a safe one-click Windows deploy and a safe Linux deploy on
systems where `python3+cryptography` is absent.**

The most important fix is DS-001/DS-002: the `ENCRYPTION_KEY` generator is broken in
two of its three code paths. The validator in `config.py` is too permissive (adds `==`
padding before checking), allowing a structurally invalid key to reach runtime. The
result is a silent failure mode: the backend starts, passes the first-admin flow, then
crashes with `ValueError` on the first LLM credential storage. On Windows this affects
every operator.

The HIGH findings (DS-003 through DS-008) are documentation and configuration fixes —
none require code changes beyond the generators. DS-004 (PS1 missing `icacls`) and
DS-005/DS-007 (GCP operator guidance) are the most likely to be hit on day-1 by an
operator following the `DEPLOY.md` guide.

The MED findings (DS-009 through DS-013) are cleanup items that improve auditability
and reduce operator confusion.

**Prioritized fix order:**
1. 🔴 DS-001 — Fix `generate-secrets.ps1` to produce 44-char Fernet key (preserving `=`).
2. 🔴 DS-002 — Fix `generate-secrets.sh` Fernet fallback to preserve `=`; hard-fail if neither `python3+cryptography` nor `openssl` is present.
3. 🔴 DS-001/DS-002 (coupled) — Tighten `config.py` validator to require exactly 44 chars.
4. 🟠 DS-004 — Add `icacls` ACL restriction in `generate-secrets.ps1`.
5. 🟠 DS-008 — Fix `upsert` placeholder regex over-matching (both `.sh` and `.ps1`).
6. 🟠 DS-011 — Align `.env.example` SMTP var names with `config.py` field names (`SMTP_USERNAME` → `SMTP_USER`, etc.).
7. 🟠 DS-005 — Add GCP/arbitrary-IP CORS guidance to `.env.example` and `setup.sh`.
8. 🟠 DS-006 — Change `TEMPORAL_AUTH_ENABLED` default to `true`; document in `.env.example`.
9. 🟠 DS-007 — Document `NEXT_PUBLIC_API_URL` bake-time constraint prominently.
10. 🟡 DS-009 — Enumerate `SAFE_EXECUTION_MODE` in `.env.example` and add `Literal` type in config.
11. 🟡 DS-010 — Add `HELIX_PROVIDER_RATES_JSON` example value.
12. 🟡 DS-013 — Link DEK/KEK migration runbook from `.env.example`.
13. 🔵 DS-014..017 — Redis sharing note, LLM key plaintext warning, `--print` warning, `AUDIT_HMAC_KEY` in DEPLOY.md table.

---

*End of DEPLOY_SECRETS.md.*
