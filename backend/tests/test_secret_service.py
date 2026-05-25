"""Secret encryption helper tests.

Regression coverage for the 2026-05-25 review finding that empty api_key
values raised ValueError, blocking Bedrock + Vertex IAM-auth providers.
"""

from app.services.secret_service import decrypt_value, encrypt_value, mask_key


def test_round_trip():
    plain = "sk-test-abcdef123456"
    enc = encrypt_value(plain)
    assert enc != plain
    assert decrypt_value(enc) == plain


def test_empty_value_returns_empty():
    """Empty/None must NOT raise — Bedrock/Vertex providers use ambient creds."""
    assert encrypt_value("") == ""
    assert encrypt_value(None) == ""
    assert decrypt_value("") == ""
    assert decrypt_value(None) == ""


def test_mask_key_short():
    assert mask_key("") == "***"
    assert mask_key("ab") == "**"


def test_mask_key_long():
    masked = mask_key("sk-test-abcdef123456")
    assert masked.startswith("sk-t")
    assert masked.endswith("3456")
    assert "*" in masked
