"""DI-C1 regression: rotate_dek must complete without IntegrityError
and must keep historical inactive DEK rows so prior ciphertext is
still decryptable via `_get_dek_for_decrypt`'s fallback walk.

This file replaces the original assumption that
`LLMProviderSecret.encrypted_api_key` is rewrapped on rotation. That
column is sealed with `secret_service.encrypt_value` (flat-KEK
MultiFernet over the master KEK), NOT with `encrypt_for_org` (per-org
DEK), so rotation here would silently `InvalidToken`-skip it. See
`docs/MIGRATION_NOTES.md` for the KEK-rotation runbook used to rewrap
flat-KEK ciphertext.

For the per-org-DEK uniqueness / rotate-twice regression coverage,
see also `test_rotate_dek_partial_unique.py`.
"""

from __future__ import annotations

import uuid

from app.models.encryption import OrgDataEncryptionKey
from app.models.identity import Organization
from app.services.envelope_encryption_service import (
    decrypt_for_org,
    encrypt_for_org,
    rotate_dek,
)


def _seed_org(db) -> str:
    org_id = str(uuid.uuid4())
    db.add(Organization(id=org_id, name="t", slug=f"t-{uuid.uuid4().hex[:6]}"))
    db.commit()
    return org_id


def test_rotate_dek_preserves_secret_readability(db_session):
    """Encrypt with the org DEK, rotate, read → still decrypts.

    The default re-encryption target list is empty (no production
    column uses the per-org DEK in HEAD), so the ciphertext is not
    proactively rewrapped. Reads continue to succeed because
    `_get_dek_for_decrypt` walks inactive historical DEKs in reverse
    version order.
    """
    org_id = _seed_org(db_session)
    plaintext = "sk-test-rotation-canary-12345"
    ciphertext = encrypt_for_org(db_session, org_id, plaintext)

    # Sanity: the encrypted value decrypts back to the original.
    assert decrypt_for_org(db_session, org_id, ciphertext) == plaintext

    # Rotate. Must not raise IntegrityError.
    result = rotate_dek(db_session, org_id)
    assert result["created"] is False
    assert result["new_version"] == "2"

    # Same ciphertext (sealed with the prior DEK) still decrypts.
    assert decrypt_for_org(db_session, org_id, ciphertext) == plaintext


def test_rotate_dek_marks_old_inactive(db_session):
    """After rotation: old DEK row persists with is_active=False.

    Critical regression: the prior implementation with `unique=True`
    on `organization_id` could not produce this state (the INSERT for
    the new row failed before the flip took effect). With the partial
    unique on (`organization_id WHERE is_active`), historical rows
    coexist freely.
    """
    org_id = _seed_org(db_session)
    encrypt_for_org(db_session, org_id, "anything")

    rotate_dek(db_session, org_id)

    deks = (
        db_session.query(OrgDataEncryptionKey)
        .filter_by(organization_id=org_id)
        .order_by(OrgDataEncryptionKey.key_version.asc())
        .all()
    )
    # We expect at least one inactive and one active row.
    assert any(not d.is_active for d in deks), "rotation should leave an inactive record"
    assert any(d.is_active for d in deks), "rotation should keep one active record"
    # And rotated_at must be set on the old row.
    inactive = [d for d in deks if not d.is_active]
    assert all(d.rotated_at is not None for d in inactive)
