"""Symmetric encrypt/decrypt for stored secrets (LLM API keys, webhook
secrets, connector configs).

Key derivation:
  - settings.ENCRYPTION_KEY is validated in core/config as a proper
    base64-encoded 32-byte Fernet key in production. We use it
    directly via `Fernet(settings.ENCRYPTION_KEY.encode())` — no more
    sha256-derivation that silently downgrades the key material and
    breaks key rotation.

Backward compatibility:
  - Historical ciphertext was sealed with `Fernet(b64(sha256(ENC_KEY)))`.
    We wrap both keys in a MultiFernet so encryption ALWAYS uses the
    new direct key (first in the list) and decryption FALLS BACK to
    the legacy sha256 key. Old rows continue to read; new rows are
    sealed with the proper key. On the operator's next opportunistic
    rewrap (e.g. via re_encrypt_all_secrets or an LLM key rotation)
    the ciphertext upgrades to the new key automatically.

See docs/MIGRATION_NOTES.md for the operator-facing rollout note.
"""

from __future__ import annotations

import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from app.core.config import settings

logger = logging.getLogger(__name__)


def _direct_fernet() -> Fernet:
    """Preferred key: the ENCRYPTION_KEY env var is itself a Fernet key."""
    return Fernet(settings.ENCRYPTION_KEY.encode("utf-8"))


def _legacy_fernet() -> Fernet:
    """Backward-compatible key: sha256(ENCRYPTION_KEY) wrapped as Fernet.

    This matched the prior implementation. Kept ONLY so historical
    ciphertext can still be decrypted; never used for fresh writes.
    """
    key = hashlib.sha256(settings.ENCRYPTION_KEY.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def _get_fernet() -> MultiFernet:
    """First key wins on encrypt; both are tried on decrypt."""
    return MultiFernet([_direct_fernet(), _legacy_fernet()])


def encrypt_value(value: str | None) -> str:
    """Encrypt a secret. Empty/None returns "" so providers using ambient
    credentials (AWS Bedrock with IAM role, Vertex AI with ADC) can be stored
    without a key. NOT NULL columns accept the empty string."""
    if not value:
        return ""
    return _get_fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_value(encrypted: str | None) -> str:
    """Decrypt a stored secret. Returns "" for the empty/IAM-auth sentinel.

    Tries the direct key first, then the legacy sha256-derived key. If
    both fail the original InvalidToken propagates.
    """
    if not encrypted:
        return ""
    try:
        return _get_fernet().decrypt(encrypted.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        logger.warning("secret_service: ciphertext failed both direct and legacy keys")
        raise


def rewrap_if_legacy(encrypted: str | None) -> str | None:
    """Return ciphertext re-sealed with the direct key if it was sealed
    with the legacy key; return None when nothing needed re-wrapping
    (already direct, or empty sentinel).

    Operators can call this opportunistically on read paths to migrate
    stored secrets to the new key without a maintenance window.
    """
    if not encrypted:
        return None
    direct = _direct_fernet()
    legacy = _legacy_fernet()
    raw = encrypted.encode("utf-8")
    # Probe the direct key first.
    try:
        direct.decrypt(raw)
        return None  # already sealed with the direct key
    except InvalidToken:
        pass
    try:
        plaintext = legacy.decrypt(raw)
    except InvalidToken:
        return None  # neither key worked; caller decides what to do
    return direct.encrypt(plaintext).decode("utf-8")


def mask_key(key: str, visible_chars: int = 4) -> str:
    if not key:
        return "***"
    if len(key) <= visible_chars * 2:
        return "*" * len(key)
    return key[:visible_chars] + "*" * (len(key) - visible_chars * 2) + key[-visible_chars:]
