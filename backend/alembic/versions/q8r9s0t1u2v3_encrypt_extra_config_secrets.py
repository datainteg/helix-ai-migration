"""sec — encrypt secret values inside llm_providers.extra_config (SEC-010)

`LLMProvider.extra_config` is a JSON column that historically stored
Bedrock / Vertex / Azure long-lived credentials (`aws_secret_access_key`,
`service_account_json`, `client_secret`, `private_key`, `passphrase`) in
plain text. Anyone with DB read access or a backup file could exfiltrate
them.

The application path now wraps every value whose key matches the
`_SECRET_KEYS` allowlist as `{"__encrypted": true, "value": "<ciphertext>"}`
before insert/update. This migration sweeps every existing row and rewraps
plaintext values in place — idempotent (rows already in the envelope shape
are skipped). Reads (`decrypt_extra_config`) open the envelope on the way
out, so no behavioural change for adapters.

Safe to re-run: the envelope-detection check makes the upgrade idempotent.

Revision ID: q8r9s0t1u2v3
Revises: p7q8r9s0t1u2
Create Date: 2026-05-26
"""

from __future__ import annotations

import json
import logging

from alembic import op
import sqlalchemy as sa


revision = "q8r9s0t1u2v3"
down_revision = "p7q8r9s0t1u2"


# Mirror of `_SECRET_KEYS` in `app/services/llm_provider_service.py`. Kept
# duplicated (not imported) so the migration runs even if the app package
# layout changes in the future.
_SECRET_KEYS = {
    "aws_secret_access_key",
    "aws_session_token",
    "service_account_json",
    "client_secret",
    "private_key",
    "passphrase",
    "gcp_service_account_json",
    "azure_client_secret",
}

_ENC_FLAG = "__encrypted"


def _is_envelope(value):
    return isinstance(value, dict) and value.get(_ENC_FLAG) is True and "value" in value


def upgrade():
    """Rewrap plaintext secret values inside extra_config in place."""
    logger = logging.getLogger("alembic.migration.q8r9s0t1u2v3")

    # Import lazily so alembic offline mode (autogenerate) doesn't crash if
    # the cryptography backend isn't initialised. Online upgrades always
    # have the app package importable.
    try:
        from app.services.secret_service import encrypt_value
    except Exception as exc:  # noqa: BLE001
        logger.warning("Skipping extra_config rewrap — secret_service unimportable: %s", exc)
        return

    bind = op.get_bind()
    rows = bind.execute(sa.text(
        "SELECT id, extra_config FROM llm_providers WHERE extra_config IS NOT NULL"
    )).fetchall()

    rewritten = 0
    for row in rows:
        # SQLAlchemy may hand back the JSON column as dict (Postgres JSONB)
        # or as raw string (SQLite). Normalise to dict.
        raw = row[1]
        if isinstance(raw, (bytes, bytearray)):
            raw = raw.decode("utf-8")
        if isinstance(raw, str):
            try:
                cfg = json.loads(raw)
            except Exception:
                continue
        elif isinstance(raw, dict):
            cfg = raw
        else:
            continue

        if not cfg:
            continue

        changed = False
        new_cfg = {}
        for k, v in cfg.items():
            if k in _SECRET_KEYS and v not in (None, "", {}) and not _is_envelope(v):
                # Serialise dict/list values to JSON first so decrypt can recover shape
                if not isinstance(v, str):
                    plain = json.dumps(v, sort_keys=True)
                else:
                    plain = v
                new_cfg[k] = {_ENC_FLAG: True, "value": encrypt_value(plain)}
                changed = True
            else:
                new_cfg[k] = v

        if changed:
            bind.execute(
                sa.text("UPDATE llm_providers SET extra_config = :cfg WHERE id = :id"),
                {"cfg": json.dumps(new_cfg), "id": row[0]},
            )
            rewritten += 1

    logger.info("SEC-010 extra_config rewrap complete: %d provider rows updated", rewritten)


def downgrade():
    """Unwrap encrypted envelopes back to plaintext (reverses upgrade).

    Provided for parity. Operators rolling back to a pre-SEC-010 schema
    should be aware: this puts plaintext credentials back into the DB.
    """
    logger = logging.getLogger("alembic.migration.q8r9s0t1u2v3")
    try:
        from app.services.secret_service import decrypt_value
    except Exception as exc:  # noqa: BLE001
        logger.warning("Skipping extra_config unwrap — secret_service unimportable: %s", exc)
        return

    bind = op.get_bind()
    rows = bind.execute(sa.text(
        "SELECT id, extra_config FROM llm_providers WHERE extra_config IS NOT NULL"
    )).fetchall()

    for row in rows:
        raw = row[1]
        if isinstance(raw, (bytes, bytearray)):
            raw = raw.decode("utf-8")
        if isinstance(raw, str):
            try:
                cfg = json.loads(raw)
            except Exception:
                continue
        elif isinstance(raw, dict):
            cfg = raw
        else:
            continue

        if not cfg:
            continue

        changed = False
        new_cfg = {}
        for k, v in cfg.items():
            if k in _SECRET_KEYS and _is_envelope(v):
                try:
                    plain = decrypt_value(v.get("value", ""))
                except Exception:
                    plain = ""
                if k in {"service_account_json", "gcp_service_account_json"}:
                    try:
                        plain = json.loads(plain)
                    except Exception:
                        pass
                new_cfg[k] = plain
                changed = True
            else:
                new_cfg[k] = v

        if changed:
            bind.execute(
                sa.text("UPDATE llm_providers SET extra_config = :cfg WHERE id = :id"),
                {"cfg": json.dumps(new_cfg), "id": row[0]},
            )
