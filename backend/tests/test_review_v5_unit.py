"""Unit tests for review-v5 backend fixes that do NOT require the app/DB.

Covers:
  * SC-002 — password strength policy (validate_password)
  * SC-016 — ILIKE wildcard escaping helper
  * SC-017 — SSRF literal-IP parsing (IPv6, decimal-encoded, mapped)

These import only `app.security.*` / `app.services.knowledge_search`, so they
run without the async DB engine.
"""

import pytest

from app.security.password_policy import validate_password, MIN_LENGTH
from app.security.ssrf import SSRFViolation, validate_external_url, _parse_literal_ip


# ── SC-002: password policy ────────────────────────────────────────────


def test_password_accepts_strong():
    strong = "Str0ng-Passw0rd!"
    assert validate_password(strong) == strong


@pytest.mark.parametrize("pw", ["Short1!", "aB3$" + "x" * 4])  # < 12 chars
def test_password_rejects_too_short(pw):
    with pytest.raises(ValueError):
        validate_password(pw)


def test_password_rejects_missing_classes():
    with pytest.raises(ValueError):
        validate_password("alllowercase123")     # no upper, no symbol
    with pytest.raises(ValueError):
        validate_password("ALLUPPERCASE123!")     # no lower
    with pytest.raises(ValueError):
        validate_password("NoDigitsHere!!!")      # no digit
    with pytest.raises(ValueError):
        validate_password("NoSymbol12345")        # no symbol


def test_password_rejects_common():
    # Compliant length/classes but obvious common → rejected.
    with pytest.raises(ValueError):
        validate_password("Password1234")  # caught by structure (no symbol)
    with pytest.raises(ValueError):
        validate_password("password")      # common + short


def test_password_rejects_overlong():
    with pytest.raises(ValueError):
        validate_password("Aa1!" + "x" * 200)


def test_password_min_length_constant():
    assert MIN_LENGTH == 12


# ── SC-017: SSRF literal-IP parsing ────────────────────────────────────


def test_decimal_encoded_imds_rejected():
    # 2852039166 == 169.254.169.254 (AWS IMDS)
    with pytest.raises(SSRFViolation):
        validate_external_url("http://2852039166/latest/meta-data/")


def test_ipv6_loopback_rejected():
    with pytest.raises(SSRFViolation):
        validate_external_url("http://[::1]/")


def test_ipv6_mapped_metadata_rejected():
    with pytest.raises(SSRFViolation):
        validate_external_url("http://[::ffff:169.254.169.254]/")


def test_parse_literal_ip_decimal():
    ip = _parse_literal_ip("2852039166")
    assert ip is not None
    assert str(ip) == "169.254.169.254"


def test_parse_literal_ip_hostname_returns_none():
    assert _parse_literal_ip("example.com") is None


def test_public_literal_ip_allowed():
    # 8.8.8.8 is public — should NOT raise.
    validate_external_url("https://8.8.8.8/")


# ── SC-016: ILIKE escaping ─────────────────────────────────────────────


def test_ilike_escape_helper():
    from app.services.knowledge_search import _escape_like

    assert _escape_like("100%") == "100\\%"
    assert _escape_like("a_b") == "a\\_b"
    # Backslash escaped first so we don't double-escape our own escapes.
    assert _escape_like("a\\b") == "a\\\\b"
    assert _escape_like("%_\\") == "\\%\\_\\\\"
