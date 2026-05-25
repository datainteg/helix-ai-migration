"""Standardized 429 (Too Many Requests) response shape.

REVIEW_API_CONTRACT.md `Cross-cutting: Rate-limit responses` flagged
that slowapi's default 429 returns `{"error": "..."}` — different from
the FastAPI default `{"detail": "..."}`. Two error envelopes on the
wire confuses SDK consumers.

This module replaces slowapi's default handler with one that:

* Returns `{"detail": "Rate limit exceeded", "retry_after_seconds": N}`
* Sets a `Retry-After: N` header (RFC 6585)
* Uses HTTP status 429

`N` is parsed from slowapi's `RateLimitExceeded` exception when
possible; defaults to 60 seconds otherwise.
"""

from __future__ import annotations

import re
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded


# slowapi formats the limit-window text like "1 per 5 second" / "10/minute".
# Parse a numeric retry-after out of the limit description; fall back to 60s.
_WINDOW_TO_SECONDS = {
    "second": 1,
    "minute": 60,
    "hour": 3600,
    "day": 86400,
}


def _extract_retry_after(exc: RateLimitExceeded) -> int:
    """Best-effort guess at how long the caller should wait, in seconds.

    Reads `exc.limit.limit` (slowapi's `RateLimitItem`). When unavailable
    falls back to 60s — generous default that matches the typical
    `30/minute` quota used across this codebase.
    """
    try:
        limit = exc.limit.limit  # type: ignore[union-attr]
        amount = getattr(limit, "amount", None)
        multiples = getattr(limit, "multiples", 1) or 1
        window = getattr(limit, "GRANULARITY", None) or limit.namespace  # type: ignore[union-attr]
        window_name = getattr(window, "name", None) or str(window)
        seconds = _WINDOW_TO_SECONDS.get(window_name.lower(), None)
        if seconds and amount:
            # Worst-case wait = full window, conservative for the client.
            return int(seconds * multiples)
    except Exception:
        pass

    # Fallback: parse the textual representation, e.g. "10 per 1 minute".
    try:
        text = str(exc.detail) if hasattr(exc, "detail") else str(exc)
        m = re.search(r"per\s+(\d+)?\s*(second|minute|hour|day)", text)
        if m:
            count = int(m.group(1) or 1)
            window_name = m.group(2)
            return int(_WINDOW_TO_SECONDS.get(window_name, 60) * count)
    except Exception:
        pass

    return 60


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Replacement for `slowapi._rate_limit_exceeded_handler`.

    Returns the FastAPI-standard `{detail, ...}` envelope plus a
    `retry_after_seconds` field that consumers can read without parsing
    the human-readable string.
    """
    retry_after = _extract_retry_after(exc)
    body: dict[str, Any] = {
        "detail": "Rate limit exceeded",
        "retry_after_seconds": retry_after,
    }
    headers = {"Retry-After": str(retry_after)}
    return JSONResponse(status_code=429, content=body, headers=headers)
