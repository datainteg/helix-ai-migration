"""Tests for ENCRYPTION_KEY generation correctness (DS-001 / DS-002 regression).

Covers:
- Fernet key length is exactly 44 chars (the '=' padding must be present).
- The key decodes to exactly 32 bytes via urlsafe_b64decode (no appended padding).
- The config validator rejects keys that are not exactly 44 chars (43 and 45 both fail).
- Fernet(key) constructs without raising (the ultimate acceptance test).

These tests are standalone — they do not require a running database or FastAPI app.
The config-validator tests patch `APP_ENV=production` so the length guard is executed.
"""

from __future__ import annotations

import base64
import os
import unittest.mock

import pytest

# ---------------------------------------------------------------------------
# Skip entire module if the cryptography package is not installed.
# The fix itself hard-fails in the generation scripts when cryptography is
# absent; these tests verify behaviour that requires it.
# ---------------------------------------------------------------------------
try:
    from cryptography.fernet import Fernet
except ImportError:
    pytest.skip(
        "cryptography package not installed — install with `pip install cryptography`",
        allow_module_level=True,
    )


# ---------------------------------------------------------------------------
# Helper: generate a valid Fernet key the same way config.py does at startup
# (using the _ephemeral_fernet_key fallback path, which always uses Fernet
# directly when cryptography is available).
# ---------------------------------------------------------------------------

def _make_valid_key() -> str:
    """Return a fresh 44-char url-safe base64 Fernet key."""
    return Fernet.generate_key().decode()


# ---------------------------------------------------------------------------
# 1. Generated key structure
# ---------------------------------------------------------------------------

class TestFernetKeyStructure:
    """Verify that a Fernet-generated key has the shape the runtime requires."""

    def test_key_length_is_exactly_44(self):
        key = _make_valid_key()
        assert len(key) == 44, (
            f"Fernet key must be 44 chars (32 bytes base64url with '=' padding); got {len(key)}"
        )

    def test_key_ends_with_equals_sign(self):
        """Standard base64 of 32 bytes always ends in exactly one '='."""
        key = _make_valid_key()
        assert key.endswith("="), (
            "Fernet key must end with '=' padding — stripping it (e.g. via TrimEnd/tr -d) "
            "produces a 43-char invalid key."
        )

    def test_key_decodes_to_32_bytes_without_extra_padding(self):
        """urlsafe_b64decode on the raw 44-char key (no appended '==') → 32 bytes."""
        key = _make_valid_key()
        decoded = base64.urlsafe_b64decode(key)   # no '==' appended
        assert len(decoded) == 32, (
            f"Fernet key should decode to exactly 32 bytes; got {len(decoded)}"
        )

    def test_fernet_constructor_accepts_generated_key(self):
        """Fernet(key) must not raise — this is the ultimate acceptance test."""
        key = _make_valid_key()
        fernet = Fernet(key.encode())   # Fernet accepts bytes or str
        assert fernet is not None

    def test_43_char_key_rejected_by_fernet(self):
        """A 43-char key (padding stripped) must raise ValueError at Fernet construction."""
        key_44 = _make_valid_key()
        assert key_44.endswith("="), "pre-condition: key must end with '='"
        key_43 = key_44.rstrip("=")    # simulate the TrimEnd / tr -d bug
        assert len(key_43) == 43
        with pytest.raises((ValueError, Exception)):
            Fernet(key_43.encode())

    def test_encrypt_decrypt_round_trip_with_generated_key(self):
        """Belt-and-braces: a generated key must encrypt and then decrypt correctly."""
        key = _make_valid_key()
        f = Fernet(key.encode())
        plaintext = b"helix-secret-payload"
        token = f.encrypt(plaintext)
        assert f.decrypt(token) == plaintext


# ---------------------------------------------------------------------------
# 2. Config validator rejects non-44-char keys in production
# ---------------------------------------------------------------------------

class TestConfigEncryptionKeyValidator:
    """Unit-test the Settings.model_post_init length guard for ENCRYPTION_KEY."""

    @staticmethod
    def _make_settings_for_key(key: str):
        """
        Instantiate Settings with APP_ENV=production and the given ENCRYPTION_KEY.
        All other required production fields are given valid values to isolate the
        ENCRYPTION_KEY validation.
        """
        from app.core.config import Settings

        valid_hex_64 = "a" * 64   # 256-bit hex secret
        with unittest.mock.patch.dict(
            os.environ,
            {
                "APP_ENV": "production",
                "ENCRYPTION_KEY": key,
                "JWT_SECRET_KEY": valid_hex_64,
                "APP_SECRET_KEY": valid_hex_64,
                "AUDIT_HMAC_KEY": "b" * 64,   # must differ from JWT_SECRET_KEY
                "CORS_ORIGINS": '["https://example.com"]',
                "CORS_ORIGIN_REGEX": "",       # must be empty in production
            },
            clear=False,
        ):
            return Settings()

    def test_valid_44_char_key_passes_validator(self):
        key = _make_valid_key()
        assert len(key) == 44
        settings = self._make_settings_for_key(key)
        assert settings.ENCRYPTION_KEY == key

    def test_43_char_key_raises_value_error(self):
        """Key with '=' stripped (the DS-001 / DS-002 bug) must fail at startup."""
        key_44 = _make_valid_key()
        key_43 = key_44.rstrip("=")
        assert len(key_43) == 43
        with pytest.raises(ValueError, match="44"):
            self._make_settings_for_key(key_43)

    def test_45_char_key_raises_value_error(self):
        """Key that is one char too long must also fail."""
        key_45 = _make_valid_key() + "X"
        assert len(key_45) == 45
        with pytest.raises(ValueError, match="44"):
            self._make_settings_for_key(key_45)

    def test_short_arbitrary_key_raises_value_error(self):
        """Any key shorter than 44 chars is rejected."""
        with pytest.raises(ValueError, match="44"):
            self._make_settings_for_key("tooshort")

    def test_error_message_includes_actual_length(self):
        """The error message should report the actual bad length for diagnostics."""
        key_43 = _make_valid_key().rstrip("=")
        with pytest.raises(ValueError) as exc_info:
            self._make_settings_for_key(key_43)
        assert "43" in str(exc_info.value), (
            "Error message should include the actual length (43) to help operators diagnose."
        )
