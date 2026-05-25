"""DI-C1 regression: rotate_dek must re-encrypt before deactivating.

Before the DI-C1 fix, rotate_dek flipped the old DEK's is_active=False
and inserted a new one without touching ciphertext. Any subsequent
decrypt_for_org hit the new DEK and failed with InvalidToken.

This test:
  1. Seeds an org with a DEK + a row of ciphertext (via the
     LLMProviderSecret table, the default re_encrypt target).
  2. Calls rotate_dek with the default targets.
  3. Decrypts the row using the post-rotation active DEK and asserts
     the plaintext round-trips.
"""

from __future__ import annotations

import uuid

import pytest

from app.models.encryption import OrgDataEncryptionKey
from app.models.identity import Organization
from app.models.llm import LLMProvider, LLMProviderSecret
from app.services.envelope_encryption_service import (
    decrypt_for_org,
    encrypt_for_org,
    rotate_dek,
)


def _make_org_with_provider(db, org_id: str, plaintext_secret: str) -> str:
    """Create org + LLM provider + encrypted secret, return secret_id."""
    db.add(Organization(id=org_id, name="t", slug=f"t-{uuid.uuid4().hex[:6]}"))
    db.commit()

    provider = LLMProvider(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        provider_type="anthropic",
        name="prod",
        default_model="claude-haiku-4-5",
    )
    db.add(provider)
    db.commit()

    # Encrypt with the org DEK (this also creates the DEK on first call).
    ciphertext = encrypt_for_org(db, org_id, plaintext_secret)
    secret = LLMProviderSecret(
        id=str(uuid.uuid4()),
        provider_id=provider.id,
        encrypted_api_key=ciphertext,
        key_version=1,
    )
    db.add(secret)
    db.commit()
    return secret.id


def test_rotate_dek_preserves_secret_readability(db_session):
    org_id = str(uuid.uuid4())
    plaintext = "sk-test-rotation-canary-12345"
    secret_id = _make_org_with_provider(db_session, org_id, plaintext)

    # Sanity: the encrypted value decrypts back to the original.
    pre_secret = db_session.query(LLMProviderSecret).filter_by(id=secret_id).one()
    assert decrypt_for_org(db_session, org_id, pre_secret.encrypted_api_key) == plaintext

    # Rotate. This should re-encrypt the secret with the new DEK.
    result = rotate_dek(db_session, org_id)
    assert result["created"] is False
    # The default target list includes LLMProviderSecret; verify it
    # was rewrapped.
    assert result["rewrapped"].get("llm_provider_secrets") == 1

    # Pull a fresh row from the DB (post-rewrap).
    db_session.expire_all()
    post_secret = db_session.query(LLMProviderSecret).filter_by(id=secret_id).one()

    # The ciphertext should have changed (different DEK ⇒ different
    # ciphertext even for the same plaintext).
    assert post_secret.encrypted_api_key != pre_secret.encrypted_api_key

    # And it must still decrypt to the original plaintext using the
    # NEW active DEK.
    assert decrypt_for_org(db_session, org_id, post_secret.encrypted_api_key) == plaintext


def test_rotate_dek_marks_old_inactive(db_session):
    org_id = str(uuid.uuid4())
    _make_org_with_provider(db_session, org_id, "anything")

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
