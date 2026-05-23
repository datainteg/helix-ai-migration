"""Safe identifier validation for database connectors."""

import re

# Strict identifier pattern: alphanumeric + underscore, must start with letter or underscore
_SAFE_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_MAX_IDENTIFIER_LENGTH = 128


def validate_identifier(name: str, label: str = "identifier") -> str:
    """Validate a schema/table/column identifier against SQL injection.

    Returns the name unchanged if valid. Raises InvalidIdentifierError otherwise.
    """
    from connectors.base.exceptions import InvalidIdentifierError

    if not name or not isinstance(name, str):
        raise InvalidIdentifierError(f"{label} must be a non-empty string")
    if len(name) > _MAX_IDENTIFIER_LENGTH:
        raise InvalidIdentifierError(f"{label} exceeds {_MAX_IDENTIFIER_LENGTH} characters: {name[:50]}...")
    if not _SAFE_IDENTIFIER_RE.match(name):
        raise InvalidIdentifierError(
            f"{label} '{name}' contains invalid characters. "
            "Only alphanumeric characters and underscores are allowed."
        )
    return name
