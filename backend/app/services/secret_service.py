import base64
import hashlib

from cryptography.fernet import Fernet

from app.core.config import settings


def _get_fernet() -> Fernet:
    key = hashlib.sha256(settings.ENCRYPTION_KEY.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_value(value: str) -> str:
    if not value:
        raise ValueError("Cannot encrypt empty value")
    f = _get_fernet()
    return f.encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_value(encrypted: str) -> str:
    if not encrypted:
        raise ValueError("Cannot decrypt empty value")
    f = _get_fernet()
    return f.decrypt(encrypted.encode("utf-8")).decode("utf-8")


def mask_key(key: str, visible_chars: int = 4) -> str:
    if not key:
        return "***"
    if len(key) <= visible_chars * 2:
        return "*" * len(key)
    return key[:visible_chars] + "*" * (len(key) - visible_chars * 2) + key[-visible_chars:]
