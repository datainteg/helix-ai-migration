import base64
import hashlib

from cryptography.fernet import Fernet

from app.core.config import settings


def _get_fernet() -> Fernet:
    key = hashlib.sha256(settings.ENCRYPTION_KEY.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_value(value: str | None) -> str:
    """Encrypt a secret. Empty/None returns "" so providers using ambient
    credentials (AWS Bedrock with IAM role, Vertex AI with ADC) can be stored
    without a key. NOT NULL columns accept the empty string."""
    if not value:
        return ""
    f = _get_fernet()
    return f.encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_value(encrypted: str | None) -> str:
    """Decrypt a stored secret. Returns "" for the empty/IAM-auth sentinel."""
    if not encrypted:
        return ""
    f = _get_fernet()
    return f.decrypt(encrypted.encode("utf-8")).decode("utf-8")


def mask_key(key: str, visible_chars: int = 4) -> str:
    if not key:
        return "***"
    if len(key) <= visible_chars * 2:
        return "*" * len(key)
    return key[:visible_chars] + "*" * (len(key) - visible_chars * 2) + key[-visible_chars:]
