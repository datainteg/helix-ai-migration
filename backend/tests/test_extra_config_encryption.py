"""SEC-010 — encryption of sensitive `LLMProvider.extra_config` values.

Direct unit-level coverage of the encrypt / decrypt / redact helpers in
`llm_provider_service.py`. No FastAPI client needed — these tests pin the
algorithm, not the HTTP surface.

Round-trip property: a value put in via `encrypt_extra_config` decrypts
back to the original via `decrypt_extra_config`, AND the on-the-wire
representation in between is the `{__encrypted: true, value: <ciphertext>}`
envelope (not the plaintext).
"""

from __future__ import annotations

import json
import os

# Ensure a valid 32-byte url-safe base64 Fernet key for these tests. Other
# tests typically rely on the conftest+settings env, but this module is run
# standalone (no DB / FastAPI setup), so we set our own deterministic key
# before any import of secret_service.
os.environ.setdefault(
    "ENCRYPTION_KEY",
    "WG7nm5O3qWvb6kZbpqXfNYCJQUVlz7iJlOVbF3yqJfA=",
)

import pytest

# Importing `app.services.llm_provider_service` pulls in `app.models.llm`
# which transitively loads `app.db.session`. If the local env can't build
# the SQLAlchemy async engine (e.g. dev box without asyncpg), skip every
# test in this module rather than erroring during collection.
try:
    from app.services.llm_provider_service import (
        _SECRET_KEYS,
        decrypt_extra_config,
        encrypt_extra_config,
        _redact_extra_config,
        _is_encrypted_envelope,
    )
except Exception as _exc:  # noqa: BLE001
    pytest.skip(
        f"llm_provider_service not importable in this env: {_exc}",
        allow_module_level=True,
    )


def test_encrypt_extra_config_seals_aws_secret_access_key():
    plain_cfg = {
        "aws_region": "us-east-1",
        "aws_secret_access_key": "AKIA-SECRET-DO-NOT-LEAK",
    }
    sealed = encrypt_extra_config(plain_cfg)
    # The public key passes through.
    assert sealed["aws_region"] == "us-east-1"
    # The sensitive value is wrapped in the encryption envelope.
    assert _is_encrypted_envelope(sealed["aws_secret_access_key"])
    # Ciphertext is not the plaintext.
    assert sealed["aws_secret_access_key"]["value"] != "AKIA-SECRET-DO-NOT-LEAK"
    # Nor does the plaintext appear anywhere in the rendered JSON.
    assert "AKIA-SECRET-DO-NOT-LEAK" not in json.dumps(sealed)


def test_decrypt_extra_config_unseals_back_to_plaintext():
    plain_cfg = {
        "aws_secret_access_key": "AKIA-SECRET-VALUE",
        "client_secret": "azure-tenant-secret",
        "passphrase": "p@ssw0rd",
    }
    sealed = encrypt_extra_config(plain_cfg)
    out = decrypt_extra_config(sealed)
    assert out["aws_secret_access_key"] == "AKIA-SECRET-VALUE"
    assert out["client_secret"] == "azure-tenant-secret"
    assert out["passphrase"] == "p@ssw0rd"


def test_encrypt_is_idempotent_on_already_encrypted_envelope():
    """Re-encrypting an already-sealed dict must not double-encrypt."""
    sealed = encrypt_extra_config({"aws_secret_access_key": "v1"})
    sealed_again = encrypt_extra_config(sealed)
    # The envelope ciphertext is preserved (not re-sealed → new ciphertext).
    assert sealed_again["aws_secret_access_key"] == sealed["aws_secret_access_key"]
    # Round-trip still works.
    assert decrypt_extra_config(sealed_again)["aws_secret_access_key"] == "v1"


def test_encrypt_passes_through_non_sensitive_keys():
    cfg = {
        "aws_region": "us-east-1",
        "gcp_project": "my-project",
        "azure_endpoint": "https://x.openai.azure.com",
        "deployment_name": "gpt-5.5-prod",
    }
    sealed = encrypt_extra_config(cfg)
    # Nothing in this cfg is in _SECRET_KEYS → all values pass through verbatim.
    assert sealed == cfg


def test_redact_extra_config_masks_sensitive_values():
    cfg = {
        "aws_region": "us-east-1",
        "aws_secret_access_key": "AKIA-SECRET",
        "client_secret": "supersecret",
    }
    redacted = _redact_extra_config(cfg)
    assert redacted["aws_region"] == "us-east-1"
    assert redacted["aws_secret_access_key"] == "***"
    assert redacted["client_secret"] == "***"


def test_redact_also_masks_unencrypted_legacy_values():
    """Belt-and-braces: legacy unmigrated rows must still mask on response."""
    cfg = {"aws_secret_access_key": "PLAINTEXT-LEGACY"}
    redacted = _redact_extra_config(cfg)
    assert redacted["aws_secret_access_key"] == "***"


def test_redact_masks_envelope_form_too():
    cfg = encrypt_extra_config({"aws_secret_access_key": "v"})
    redacted = _redact_extra_config(cfg)
    # Envelope dicts are also non-empty → masked.
    assert redacted["aws_secret_access_key"] == "***"


def test_empty_and_none_handled_gracefully():
    assert encrypt_extra_config(None) is None
    assert encrypt_extra_config({}) == {}
    assert decrypt_extra_config(None) is None
    assert decrypt_extra_config({}) == {}
    assert _redact_extra_config(None) is None


def test_service_account_json_dict_round_trips_through_json_serde():
    """GCP service_account_json is normally a nested dict. Round-trip preserves shape."""
    sa_dict = {"type": "service_account", "project_id": "x", "private_key": "PRIV"}
    sealed = encrypt_extra_config({"service_account_json": sa_dict})
    assert _is_encrypted_envelope(sealed["service_account_json"])
    # The JSON-serialised plaintext is what we encrypted, but the consumer
    # gets the dict back via the json.loads branch in decrypt_extra_config.
    out = decrypt_extra_config(sealed)
    assert isinstance(out["service_account_json"], dict)
    assert out["service_account_json"]["project_id"] == "x"


def test_secret_keys_set_covers_known_credentials():
    """Sanity: the allowlist contains the names we promised in the schema docs."""
    for k in {"aws_secret_access_key", "service_account_json", "client_secret",
              "private_key", "passphrase"}:
        assert k in _SECRET_KEYS, f"{k} must be in _SECRET_KEYS"
