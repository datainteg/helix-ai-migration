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

`POST /admin/org/rotate-dek` is now safe to call: it re-encrypts every
per-org ciphertext column inside the same transaction before the old
DEK is marked inactive. Reads during the rotation continue to succeed
via `_get_dek_for_decrypt`, which walks historical DEKs in reverse
version order.

If the re-encryption pass fails, the transaction rolls back and the
old DEK remains active — no data is bricked.

Operators adding a new per-org-encrypted column MUST extend
`envelope_encryption_service.re_encrypt_all_secrets`'s default
`targets` list so rotation includes the new column. Silent omission
would leave the new column un-rewrappable on rotation.

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

## Cost-service commit batching (cost_service)

`record_usage` is now non-committing (`db.add` + `db.flush` only).
The caller is responsible for committing the surrounding transaction.
A `record_usage_immediate` helper is provided for legacy single-shot
call sites that want the old commit semantics.

This unlocks a bulk-LLM-job pattern where 13+ agent calls × N steps
commit in one round-trip instead of 30+ individual commits.

If you have third-party code that imported `record_usage` and
expected an immediate commit, swap to `record_usage_immediate` (same
arguments).
