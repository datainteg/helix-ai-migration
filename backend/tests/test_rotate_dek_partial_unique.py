"""DI-C1 regression — `rotate_dek` must not violate the active-DEK
uniqueness invariant and must keep historical inactive rows around so
ciphertext sealed with the prior DEK is still readable.

Before the partial-unique fix:
  - `OrgDataEncryptionKey.organization_id` was `unique=True`. The
    rotate flow flipped the old row to `is_active=False` and INSERTed
    a new row for the same org — guaranteed `IntegrityError` on
    flush, so rotation never completed.

After the fix (model + migration `2af2b45b4051`):
  - At most ONE active DEK per org (partial unique index on
    `organization_id WHERE is_active`).
  - Any number of inactive historical DEKs may coexist.

These tests cover the three points raised by the reviewer:
  1. Encrypt → rotate → decrypt succeeds via the legacy-DEK fallback
     walk in `_get_dek_for_decrypt`.
  2. Two rotations in a row produce no IntegrityError.
  3. The old DEK row still exists with `is_active=False` after rotation.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

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


def test_rotate_dek_preserves_decrypt_via_legacy_fallback(db_session):
    """Encrypt with the org DEK, rotate, decrypt → succeeds.

    With the default empty per-org-DEK targets list, the ciphertext is
    NOT proactively rewrapped — but `_get_dek_for_decrypt` walks the
    inactive historical DEKs so reads still succeed.
    """
    org_id = _seed_org(db_session)
    plaintext = "sk-test-canary-rotation-12345"

    ciphertext = encrypt_for_org(db_session, org_id, plaintext)

    # Sanity: round-trips through the active DEK.
    assert decrypt_for_org(db_session, org_id, ciphertext) == plaintext

    # Rotate. Default targets is empty (no per-org DEK columns wired
    # in HEAD), so re-encryption count is zero — but the rotation
    # itself must complete without IntegrityError.
    result = rotate_dek(db_session, org_id)
    assert result["created"] is False
    assert result["new_version"] == "2"

    # Same ciphertext, now decrypted via the historical-DEK walk
    # (active DEK is the freshly-rotated one; it cannot decrypt this
    # value because that value was sealed with the prior DEK).
    assert decrypt_for_org(db_session, org_id, ciphertext) == plaintext


def test_rotate_dek_twice_no_integrity_error(db_session):
    """Back-to-back rotations must not violate the partial unique index.

    Two rotations produce three DEK rows: 1 active (v3) and 2 inactive
    (v1, v2). The partial unique only checks active rows; inactives
    coexist freely.
    """
    org_id = _seed_org(db_session)
    # Bootstrap the org's first DEK so we have something to rotate.
    encrypt_for_org(db_session, org_id, "anything")

    rotate_dek(db_session, org_id)
    # If the partial unique fix didn't land, the second rotation
    # would fail with IntegrityError on flush.
    rotate_dek(db_session, org_id)

    db_session.expire_all()
    deks = (
        db_session.query(OrgDataEncryptionKey)
        .filter_by(organization_id=org_id)
        .all()
    )
    active = [d for d in deks if d.is_active]
    inactive = [d for d in deks if not d.is_active]

    assert len(active) == 1, f"exactly one active DEK; got {[d.key_version for d in active]}"
    assert len(inactive) == 2, f"two historical inactive DEKs; got {[d.key_version for d in inactive]}"
    # The newest active row carries the highest version.
    assert active[0].key_version == "3"
    # All inactives have rotated_at stamped.
    assert all(d.rotated_at is not None for d in inactive)


def test_rotate_dek_keeps_old_row_with_is_active_false(db_session):
    """After one rotation: 1 active + 1 inactive row coexist."""
    org_id = _seed_org(db_session)
    encrypt_for_org(db_session, org_id, "anything")

    rotate_dek(db_session, org_id)

    db_session.expire_all()
    deks = (
        db_session.query(OrgDataEncryptionKey)
        .filter_by(organization_id=org_id)
        .order_by(OrgDataEncryptionKey.key_version.asc())
        .all()
    )

    assert len(deks) == 2, f"rotation should leave both rows; got {len(deks)}"
    assert any(not d.is_active for d in deks), "old DEK row must persist (is_active=False)"
    assert any(d.is_active for d in deks), "new DEK row must be the active one"

    inactive = [d for d in deks if not d.is_active]
    assert all(d.rotated_at is not None for d in inactive), "old row must have rotated_at set"


def test_partial_unique_blocks_second_active_dek(db_session):
    """Sanity: inserting a second active DEK for the same org fails.

    Confirms the partial unique index is doing its job. Two ACTIVE
    rows for the same org should violate `uq_org_dek_active_per_org`.
    """
    org_id = _seed_org(db_session)
    encrypt_for_org(db_session, org_id, "anything")

    # Trying to add a second active DEK without flipping the first
    # must raise IntegrityError at flush.
    extra = OrgDataEncryptionKey(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        encrypted_dek="not-a-real-ciphertext-but-fits-varchar512",
        key_version="99",
        is_active=True,
    )
    db_session.add(extra)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()
