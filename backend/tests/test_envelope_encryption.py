"""Tests for per-org envelope encryption service."""

import pytest


def test_encrypt_decrypt_roundtrip(db_session):
    """Encrypt then decrypt should return original plaintext."""
    from app.services.envelope_encryption_service import encrypt_for_org, decrypt_for_org

    org_id = "test-org-enc-001"
    plaintext = "super-secret-api-key-abc123"

    ciphertext = encrypt_for_org(db_session, org_id, plaintext)
    assert ciphertext != plaintext
    assert len(ciphertext) > 0

    recovered = decrypt_for_org(db_session, org_id, ciphertext)
    assert recovered == plaintext


def test_different_orgs_get_different_deks(db_session):
    """Two orgs should produce different ciphertexts for same plaintext."""
    from app.services.envelope_encryption_service import encrypt_for_org

    plaintext = "same-secret"
    ct1 = encrypt_for_org(db_session, "org-a-001", plaintext)
    ct2 = encrypt_for_org(db_session, "org-b-001", plaintext)
    assert ct1 != ct2


def test_dek_reused_for_same_org(db_session):
    """Same org reuses its DEK (same DB record)."""
    from app.models.encryption import OrgDataEncryptionKey
    from app.services.envelope_encryption_service import encrypt_for_org

    org_id = "org-reuse-001"
    encrypt_for_org(db_session, org_id, "value1")
    encrypt_for_org(db_session, org_id, "value2")

    count = db_session.query(OrgDataEncryptionKey).filter(
        OrgDataEncryptionKey.organization_id == org_id,
        OrgDataEncryptionKey.is_active == True,
    ).count()
    assert count == 1


def test_dek_rotation_creates_new_key(db_session):
    """Rotation deactivates old DEK and creates a new active one."""
    from app.models.encryption import OrgDataEncryptionKey
    from app.services.envelope_encryption_service import encrypt_for_org, rotate_dek

    org_id = "org-rotate-001"
    encrypt_for_org(db_session, org_id, "initial-value")

    rotate_dek(db_session, org_id)

    active = db_session.query(OrgDataEncryptionKey).filter(
        OrgDataEncryptionKey.organization_id == org_id,
        OrgDataEncryptionKey.is_active == True,
    ).all()
    inactive = db_session.query(OrgDataEncryptionKey).filter(
        OrgDataEncryptionKey.organization_id == org_id,
        OrgDataEncryptionKey.is_active == False,
    ).all()

    assert len(active) == 1
    assert len(inactive) == 1
    assert active[0].key_version == "2"
