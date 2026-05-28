"""Password strength policy (SC-002).

Single source of truth for password-acceptance rules. Apply via a Pydantic
``@field_validator`` on every schema where a *new* password is being chosen
— ``FirstAdminSetup``, ``AcceptInviteRequest``, ``PasswordResetConfirm`` and
any future user-create flow.

Do NOT apply this to ``UserLogin``: existing accounts may still carry legacy
weak passwords from before the policy was tightened, and the login surface
must keep accepting them so those users can reach a reset flow.

Rules
-----
* min length 12, max length 128 (bcrypt's effective input cap is 72 bytes,
  but a max enforced here bounds bcrypt CPU on adversarial inputs)
* must contain at least one upper-case ASCII letter
* must contain at least one lower-case ASCII letter
* must contain at least one digit
* must contain at least one non-alphanumeric symbol
* rejects a small in-code list of obvious commons
"""

from __future__ import annotations

import string

MIN_LENGTH = 12
MAX_LENGTH = 128

# Deliberately small in-code denylist — no external dep.  These are the
# top-of-mind credentials from every breached-password corpus; combined with
# the structural rules they catch ~all of the worst beginner choices.
_COMMON_PASSWORDS: frozenset[str] = frozenset(
    {
        "password",
        "password1",
        "password123",
        "password1234",
        "passw0rd",
        "p@ssw0rd",
        "p@ssword",
        "qwerty",
        "qwerty12345",
        "qwerty123456",
        "qwertyuiop",
        "letmein",
        "letmein123",
        "welcome",
        "welcome123",
        "admin",
        "admin123",
        "administrator",
        "iloveyou",
        "abcdef",
        "abcdef123",
        "abc12345",
        "abcd1234",
        "12345678",
        "123456789",
        "1234567890",
        "monkey",
        "dragon",
        "master",
        "trustno1",
        "sunshine",
        "princess",
        "starwars",
        "football",
        "baseball",
        "helix",
        "helix123",
        "helixadmin",
        "changeme",
        "change_me",
        "default",
        "default1",
    }
)

_SYMBOLS = set(string.punctuation) | {" "}


def validate_password(value: str) -> str:
    """Return the password unchanged or raise ``ValueError`` with a user-safe
    message describing the first failing rule.

    Designed for use inside a Pydantic ``@field_validator("password")`` —
    Pydantic converts the ``ValueError`` into a 422 response with the message
    intact.
    """
    if value is None:
        raise ValueError("password is required")
    if not isinstance(value, str):  # pragma: no cover — Pydantic should coerce
        raise ValueError("password must be a string")

    if len(value) < MIN_LENGTH:
        raise ValueError(
            f"password must be at least {MIN_LENGTH} characters long"
        )
    if len(value) > MAX_LENGTH:
        raise ValueError(
            f"password must be at most {MAX_LENGTH} characters long"
        )

    has_upper = any(c.isascii() and c.isupper() for c in value)
    has_lower = any(c.isascii() and c.islower() for c in value)
    has_digit = any(c.isdigit() for c in value)
    has_symbol = any(c in _SYMBOLS for c in value)

    missing: list[str] = []
    if not has_upper:
        missing.append("upper-case letter")
    if not has_lower:
        missing.append("lower-case letter")
    if not has_digit:
        missing.append("digit")
    if not has_symbol:
        missing.append("symbol")
    if missing:
        raise ValueError(
            "password must contain at least one "
            + ", one ".join(missing)
        )

    # Case-insensitive denylist check — these are the obvious commons.
    if value.lower() in _COMMON_PASSWORDS:
        raise ValueError(
            "password is too common; pick something less guessable"
        )

    return value


__all__ = ["validate_password", "MIN_LENGTH", "MAX_LENGTH"]
