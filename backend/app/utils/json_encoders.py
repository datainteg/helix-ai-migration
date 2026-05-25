"""Custom JSON encoders applied app-wide (API-C3).

The default FastAPI / Pydantic encoder already emits ISO-8601 for
`datetime`. The bug the contract audit flagged is in routers that
hand-build dicts using `str(some_datetime)` — Python's `__str__` is
NOT ISO-8601 (no `"T"` separator) and breaks Safari's `Date` parser.

Fixes are applied two ways:

1. The legacy hand-built dicts are being migrated to Pydantic response
   models that serialize via the standard encoder (per-router PRs).
2. For the remaining call sites that still pass `datetime` directly into
   `JSONResponse`, this module exposes `iso()` — a one-line helper that
   returns `value.isoformat()` or `None`. Cheaper to call than wrapping
   every router's `str(...)` rewrite individually.
"""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any


def iso(value: Any) -> str | None:
    """Return `value.isoformat()` if value is a date/time/datetime, else None.

    Use at every site that previously called `str(some_datetime)`.
    Designed to be drop-in: pass anything, get a string or None.
    """
    if value is None:
        return None
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    # Anything else: stringify but warn — the call site probably meant
    # `iso(some_datetime)` and accidentally passed a string already.
    return str(value)


# Mapping for `json.dumps(default=...)` and FastAPI's `json_encoders` model_config.
# Bind to ANY module that builds JSONResponse manually instead of returning
# a Pydantic model.
DEFAULT_JSON_ENCODERS: dict[type, Any] = {
    datetime: lambda v: v.isoformat(),
    date: lambda v: v.isoformat(),
    time: lambda v: v.isoformat(),
}
