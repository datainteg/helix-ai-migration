"""IR schema versioning.

The IR is persisted and exchanged between connector plugins and the engine, so
it carries a semantic version. Connectors declare the ``ir_version`` they emit;
the engine negotiates compatibility. Same-major versions are compatible
(additive/minor changes only); a major bump signals a breaking change.
"""

from __future__ import annotations

# Bump the MAJOR only for breaking IR changes; MINOR for additive fields.
IR_SCHEMA_VERSION = "0.1.0"


class IncompatibleIRVersionError(ValueError):
    """Raised when an IR document's schema version cannot be loaded."""

    def __init__(self, found: str, current: str = IR_SCHEMA_VERSION) -> None:
        self.found = found
        self.current = current
        super().__init__(
            f"IR schema version {found!r} is incompatible with engine version "
            f"{current!r} (major versions must match)."
        )


def parse_version(value: str) -> tuple[int, int, int]:
    """Parse ``"MAJOR.MINOR.PATCH"`` into a tuple. Raises ``ValueError``."""
    parts = value.split(".")
    if len(parts) != 3:
        raise ValueError(f"Malformed version string: {value!r}")
    try:
        major, minor, patch = (int(p) for p in parts)
    except ValueError as exc:  # non-integer component
        raise ValueError(f"Malformed version string: {value!r}") from exc
    return major, minor, patch


def is_compatible(version: str, current: str = IR_SCHEMA_VERSION) -> bool:
    """Return True if an IR of ``version`` can be loaded by ``current``.

    Compatibility rule: same MAJOR. A newer engine reads older same-major IR;
    an older engine reading a newer MINOR is tolerated (unknown fields ignored).
    """
    try:
        return parse_version(version)[0] == parse_version(current)[0]
    except ValueError:
        return False
