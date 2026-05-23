"""Envelope encryption: per-org DEK encrypted with master KEK.

Flow:
  encrypt_for_org(org_id, plaintext)
    → fetch/create DEK for org
    → decrypt DEK with KEK (master Fernet)
    → encrypt plaintext with DEK
    → return ciphertext

  decrypt_for_org(org_id, ciphertext)
    → fetch DEK for org
    → decrypt DEK with KEK
    → decrypt ciphertext with DEK
"""

from __future__ import annotations

import base64
import hashlib
import logging

from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.encryption import OrgDataEncryptionKey

logger = logging.getLogger(__name__)


def _kek() -> Fernet:
    """Master Key Encryption Key derived from settings.ENCRYPTION_KEY."""
    raw = hashlib.sha256(settings.ENCRYPTION_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(raw))


def _get_or_create_dek(db: Session, org_id: str) -> bytes:
    """Return plaintext DEK bytes for org. Creates and persists new DEK if absent."""
    record = db.query(OrgDataEncryptionKey).filter(
        OrgDataEncryptionKey.organization_id == org_id,
        OrgDataEncryptionKey.is_active == True,
    ).first()

    if record:
        return _kek().decrypt(record.encrypted_dek.encode())

    # Generate and persist new DEK
    plaintext_dek = Fernet.generate_key()
    encrypted_dek = _kek().encrypt(plaintext_dek).decode()
    record = OrgDataEncryptionKey(
        organization_id=org_id,
        encrypted_dek=encrypted_dek,
    )
    db.add(record)
    db.commit()
    logger.info("org_dek_created org_id=%s", org_id)
    return plaintext_dek


def encrypt_for_org(db: Session, org_id: str, plaintext: str) -> str:
    """Encrypt plaintext with org-specific DEK."""
    dek = _get_or_create_dek(db, org_id)
    return Fernet(dek).encrypt(plaintext.encode()).decode()


def decrypt_for_org(db: Session, org_id: str, ciphertext: str) -> str:
    """Decrypt ciphertext using org-specific DEK."""
    dek = _get_or_create_dek(db, org_id)
    return Fernet(dek).decrypt(ciphertext.encode()).decode()


def rotate_dek(db: Session, org_id: str) -> None:
    """Rotate DEK for org. Marks old record inactive, creates new one."""
    from datetime import datetime, timezone
    old = db.query(OrgDataEncryptionKey).filter(
        OrgDataEncryptionKey.organization_id == org_id,
        OrgDataEncryptionKey.is_active == True,
    ).first()
    if old:
        old.is_active = False
        old.rotated_at = datetime.now(timezone.utc)

    new_dek = Fernet.generate_key()
    version = str((int(old.key_version) + 1) if old else 1)
    record = OrgDataEncryptionKey(
        organization_id=org_id,
        encrypted_dek=_kek().encrypt(new_dek).decode(),
        key_version=version,
    )
    db.add(record)
    db.commit()
    logger.info("org_dek_rotated org_id=%s new_version=%s", org_id, version)
