# Migration Notes — Data-Integrity Hardening (2026-05-26)

Operator-facing notes for the data-integrity fix batch. Read before
applying `alembic upgrade head` to a populated production database.

## ENCRYPTION_KEY derivation change (v2-B1)

### What changed
`backend/app/services/secret_service.py` and
`backend/app/services/envelope_encryption_service.py` now use
`settings.ENCRYPTION_KEY` directly as the Fernet key, not
`sha256(settings.ENCRYPTION_KEY)`.

### Why
The previous code threw away the Fernet-key validation in
`core/config.py` (which checks for a base64-encoded 32-byte key) by
hashing the key first. Effects:
- Operators who rotated `ENCRYPTION_KEY` silently broke every
  ciphertext (decryption would fail).
- The "envelope encryption" layer's KEK could not interoperate with
  any external key-management tool that expects a real Fernet key.
- The configured length/format validation was bypassed at runtime.

### Backward compatibility
Both services now use `MultiFernet([direct_key, legacy_sha256_key])`:
- **Encryption** always uses the direct key (first in the list).
- **Decryption** tries the direct key first; on failure it tries the
  legacy sha256-derived key. Existing ciphertext continues to read.

This means:
- No downtime to flip the switch.
- No bulk re-encryption is required up front.
- New writes start using the direct key immediately.

### Optional: opportunistic rewrap
`secret_service.rewrap_if_legacy(ciphertext)` returns a fresh
ciphertext sealed with the direct key if the input was sealed with
the legacy key (else returns `None`). Wire this into hot read paths
(e.g. when an LLM provider's key is read for outbound calls) to
migrate stored secrets to the new key without a maintenance window.

### Removing legacy support (future)
Once `SELECT count(*) FROM llm_provider_secrets WHERE
encrypted_api_key IS NOT NULL` has been fully rewrapped (track via
the optional `rewrap_if_legacy` audit), drop `_kek_legacy` /
`_legacy_fernet` in a follow-up release. Until then keep both keys
available — removing the legacy key strands any unrewrapped
ciphertext.

## Per-org DEK rotation (DI-C1)

`POST /admin/org/rotate-dek` is now safe to call. The rotation flow:

1. Flips the prior active DEK row to `is_active=False` and stamps
   `rotated_at`.
2. Inserts a new DEK row (`is_active=True`, `key_version` bumped).
3. Walks the per-org DEK target list and rewraps each ciphertext
   column from old DEK -> new DEK.
4. Commits.

If the re-encryption pass fails, the entire transaction rolls back
and the old DEK remains the active one — no data is bricked. Reads
during the rotation continue to succeed via `_get_dek_for_decrypt`,
which walks historical (inactive) DEKs in reverse version order.

### Uniqueness model (DI-C1 follow-up)

Originally `org_data_encryption_keys.organization_id` was `UNIQUE`,
which guaranteed `IntegrityError` on the second-row insert that
rotation requires. Migration `2af2b45b4051_dek_partial_unique_active`
replaces the full unique with a **partial unique index** on
`(organization_id) WHERE is_active = true`:

- At most ONE active DEK per org (still enforced at the DB layer).
- Any number of inactive historical DEKs may coexist (required so
  the legacy-DEK decrypt walk keeps working).

The model declaration in `app/models/encryption.py` mirrors this with
an `Index(..., unique=True, postgresql_where=is_active==True,
sqlite_where=is_active==True)` so `Base.metadata.create_all` (used by
the test suite) produces the same shape.

### Per-org-DEK targets vs flat-KEK targets

There are TWO encryption paths in the codebase, and rotation handles
them via different functions:

| Path | Sealed via | Rotated via |
| --- | --- | --- |
| Per-org DEK | `encrypt_for_org` / `decrypt_for_org` | `rotate_dek` -> `re_encrypt_all_secrets` |
| Flat KEK (master) | `secret_service.encrypt_value` (MultiFernet) | `rotate_kek_secrets` (opportunistic rewrap via `rewrap_if_legacy`) |

`re_encrypt_all_secrets`'s default `targets` list is **empty** in
HEAD: no production column uses the per-org DEK yet
(`LLMProviderSecret.encrypted_api_key` is sealed via the flat KEK).
Mixing the two paths is the original DI-C1 bug — passing a
flat-KEK column to `re_encrypt_all_secrets` gets `InvalidToken` on
every row and silently rewraps nothing.

When a new column starts using `encrypt_for_org`, register it in the
`_DEFAULT_PER_ORG_DEK_TARGETS` list at the top of
`envelope_encryption_service.py`. Silent omission would leave the new
column un-rewrappable on rotation.

### Operator runbook — rotating the DEK

```sh
# 1. Take a logical backup (PITR snapshot or pg_dump) of
#    public.org_data_encryption_keys plus every table listed in
#    _DEFAULT_PER_ORG_DEK_TARGETS BEFORE rotation. The rotation is
#    transactional, but a corrupted KEK or external surprise would
#    leave you needing this.
pg_dump -t org_data_encryption_keys -t llm_provider_secrets ...

# 2. Apply the schema fix (drops full unique, adds partial unique).
cd backend && alembic upgrade head

# 3. Trigger the rotation for one org via the admin API.
curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
     -H "X-Org-Id: $ORG_ID" \
     "$API/admin/org/rotate-dek"

# 4. Confirm the response. Expected shape:
#    {"created": false, "rewrapped": {...}, "new_version": "2"}
#
#    For HEAD, "rewrapped" will be {} until a per-org-DEK column is
#    registered. That is expected and not a bug — the flat-KEK
#    columns rotate via `rotate_kek_secrets` instead.

# 5. Spot-check that the prior row is preserved.
psql -c "SELECT key_version, is_active, rotated_at
           FROM org_data_encryption_keys
          WHERE organization_id = '$ORG_ID'
          ORDER BY key_version::int;"

# Expected: 2 rows -- version 1 (is_active=f, rotated_at NOT NULL),
#                     version 2 (is_active=t, rotated_at NULL).
```

### Operator runbook — rewrapping flat-KEK ciphertext

If the master `ENCRYPTION_KEY` is being promoted away from the legacy
sha256-derived key, walk every flat-KEK column with the opportunistic
rewrap helper:

```py
from app.db.session import SessionLocal
from app.services.envelope_encryption_service import rotate_kek_secrets

with SessionLocal() as db:
    counts = rotate_kek_secrets(db)
    print(counts)   # {"llm_provider_secrets": <N>}
```

`rewrap_if_legacy` (in `secret_service.py`) returns `None` for
ciphertext that's already direct-key-sealed, so this is idempotent
and safe to re-run.

## UUID -> String(36) alignment (DI-C5)

Migration `8f881cfc333e` ALTERs the identity-table UUID columns to
`VARCHAR(36)` so they match the model declarations. On Postgres the
migration:
1. Drops every FK on the affected dependent tables (reflected at
   migration time so the names match what's in the live DB).
2. ALTERs the column types using `USING col::text` (preserves data
   as hyphenated UUID text).
3. Recreates each FK with its original name + `ondelete` behaviour.

Downgrade is intentionally a no-op. To revert, restore from a backup
taken before the migration ran.

The migration is a no-op on SQLite (test runners + dev fallback).

## `workflow_steps.parsed_output_json` Text -> JSONB (DI-C4)

Migration `eadec18c9cfc` converts the column to JSONB after NULLing
any row whose stored value isn't valid JSON (e.g. rows that were
written as Python dict-repr `{'key': ...}`). Inspect those rows
beforehand with:

```sql
SELECT id, workflow_run_id
  FROM workflow_steps
 WHERE parsed_output_json IS NOT NULL
   AND (parsed_output_json !~ '^\s*[\{\[]'
        OR parsed_output_json ~ E'^\s*\{[^"]*''[^"]*');
```

Anything returned will be NULLed by the migration. If those rows
matter, dump them first.

## Wave-3: `--rotate-secrets` CLI orchestrator (app.cli.rotate)

### What was added

`backend/app/cli/rotate.py` provides three admin commands that wire the
library functions (`rotate_kek_secrets`, `rotate_dek`) into a CLI you
can invoke directly in the container.  All commands are **dry-run by
default**; you must pass `--confirm` to commit changes.

### One-off: remove the legacy MultiFernet fallback slot

After installing wave-3, run once per deployment to rewrap every flat-KEK
ciphertext row to the direct Fernet key:

```sh
docker compose exec backend python -m app.cli.rotate rotate-keks --confirm
```

Expected output:

```
[OK] rotate-keks complete. Rows rewrapped: {'llm_provider_secrets': <N>}  (total=<N>)
[INFO] When all legacy rows are gone you may remove the
       MultiFernet legacy-key slot from secret_service._get_fernet().
```

Dry-run first (no `--confirm`) to preview the count:

```sh
docker compose exec backend python -m app.cli.rotate rotate-keks
# [DRY-RUN] rows that WOULD be rewrapped: {'llm_provider_secrets': <N>}
# [DRY-RUN] No changes written (omit --confirm to keep dry-run).
```

### ENCRYPTION_KEY rotation

When the `ENCRYPTION_KEY` env var is being rotated to a new value:

1. Change the `.env` / secrets-manager value.
2. Restart the backend (new key is now the primary; old key is the legacy
   fallback via `MultiFernet`).
3. Run the rewrap command to migrate all stored ciphertext to the new key:

```sh
docker compose exec backend python -m app.cli.rotate rotate-keks --confirm
```

Once all rows are rewrapped, the legacy-key fallback slot is no longer
needed and can be removed in a follow-up release.

### Per-org DEK rotation

Rotate the DEK for a single organisation:

```sh
docker compose exec backend python -m app.cli.rotate rotate-dek \
    --org-id <ORG_UUID> --confirm
```

Rotate every organisation's DEK (resumable via `--start-from`):

```sh
# Full run
docker compose exec backend python -m app.cli.rotate rotate-all-deks --confirm

# Resume from a specific org if a previous run was interrupted
docker compose exec backend python -m app.cli.rotate rotate-all-deks \
    --start-from <ORG_UUID> --confirm
```

### Command reference

| Command | Description |
|---|---|
| `rotate-keks [--confirm]` | Rewrap flat-KEK ciphertext from legacy to direct key |
| `rotate-dek --org-id <ID> [--confirm]` | Rotate per-org DEK for one org |
| `rotate-all-deks [--start-from <ID>] [--confirm]` | Rotate DEK for all orgs |

All commands exit 0 on success, 1 on any per-row/per-org failure (with a
summary printed to stderr).

---

## Cost-service commit batching (cost_service)

Default `record_usage(...)` semantics are unchanged — it still
commits immediately so existing UI-driven call sites and tests work
without modification.

Two new options unlock batched commits on hot paths:

- `record_usage(..., defer_commit=True)` flushes the row but skips
  the commit + refresh. The caller (e.g. a per-node workflow
  activity) owns the surrounding transaction and is responsible for
  `db.commit()` at the end of the batch.
- `record_usage_batch(db, rows=[...])` accepts a list of usage-kwarg
  dicts and inserts them all in a single commit via `add_all`.

The BMAD executor and per-node workflow path should migrate to the
batch helper to coalesce 13+ rows-per-workflow into one round-trip,
unblocking the 3+2 worker DB pool. The migration is opt-in — leaving
the existing call sites on `record_usage(...)` is safe; they just
keep the per-row commit cost.

## ENCRYPTION_KEY 43-char invalid-key fix (DS-001 / DS-002)

### Background

`scripts/generate-secrets.ps1` (all versions before this fix) and
`scripts/generate-secrets.sh` (when `python3+cryptography` was absent)
both produced a **43-char** `ENCRYPTION_KEY` because the base64 url-safe
encoder stripped the mandatory Fernet trailing `=`. The backend startup
validator was fooled (it prepended `==` before decoding, so both 43-char
and 44-char strings decoded to 32 bytes). The backend appeared to start
normally but crashed with `ValueError` on the first `encrypt_value()` call
(i.e. the first LLM provider credential save via the admin wizard).

### What changed

- `scripts/generate-secrets.ps1`: new `RandFernetKey` function that
  converts `+/` to `-_` but does **not** call `.TrimEnd('=')`. Produces
  the correct 44-char key.
- `scripts/generate-secrets.sh`: `rand_fernet_key` now hard-fails with an
  actionable error message when neither `python3+cryptography` nor `openssl`
  is available; the `openssl` fallback path preserves `=` by using
  `openssl rand 32 | base64` (raw bytes → standard base64) rather than
  `openssl rand -base64 32 | tr -d '='`.
- `backend/app/core/config.py`: validator now checks `len(key) == 44`
  **before** attempting to decode, so a 43-char key raises `ValueError` at
  startup with a clear message rather than silently starting and crashing
  later.

### Operator action required

**If you generated secrets before this fix and have NOT yet stored any
encrypted data** (i.e. no LLM provider credentials have been saved via the
admin UI), you can safely regenerate:

```sh
./scripts/generate-secrets.sh --rotate ENCRYPTION_KEY
# or on Windows:
.\scripts\generate-secrets.ps1 -Force
```

**If encrypted data already exists** (LLM provider keys, connector
credentials): stop. Do NOT rotate `ENCRYPTION_KEY` without a re-encryption
migration — rotating the key strands all existing ciphertext. Contact
support. A re-encryption migration via `rotate_kek_secrets()` is required
(see "Operator runbook — rewrapping flat-KEK ciphertext" above).

**To check whether you have a bad key** currently in `.env`:

```sh
python3 -c "
import os, base64
key = open('.env').read()
for line in key.splitlines():
    if line.startswith('ENCRYPTION_KEY='):
        val = line.split('=', 1)[1].strip()
        print(f'len={len(val)} (want 44)')
        print('OK' if len(val) == 44 else 'BAD — re-generate before first use')
"
```
