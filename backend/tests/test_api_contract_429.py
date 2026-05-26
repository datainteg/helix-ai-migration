"""Contract tests for the standardized 429 response (Cross-cutting in
REVIEW_API_CONTRACT.md — rate-limit responses).

The replacement handler returns:
  status: 429
  body:   {"detail": "Rate limit exceeded", "retry_after_seconds": N}
  header: Retry-After: N
"""

from __future__ import annotations


def test_retry_after_extractor_defaults_to_60s():
    """When slowapi's RateLimitExceeded lacks parseable metadata the
    helper falls back to 60s (matches the typical `30/minute` quota)."""
    from app.utils.rate_limit_handler import _extract_retry_after

    class _FakeExc:
        # Intentionally no `.limit` attribute → exception path → fallback.
        detail = "Rate limit exceeded: x per y unknown"

    assert _extract_retry_after(_FakeExc()) == 60  # type: ignore[arg-type]


def test_retry_after_extractor_parses_text_form():
    """Textual `"per N minute"` patterns are pulled out as seconds."""
    from app.utils.rate_limit_handler import _extract_retry_after

    class _FakeExc:
        detail = "5 per 2 minute"

    assert _extract_retry_after(_FakeExc()) == 120  # type: ignore[arg-type]


def test_handler_returns_standard_envelope_and_header():
    """The handler returns a JSONResponse with the expected shape."""
    from fastapi import Request
    from app.utils.rate_limit_handler import rate_limit_exceeded_handler

    class _FakeExc:
        detail = "1 per 1 second"

    # Minimal Starlette scope so the Request object can be built.
    scope = {
        "type": "http",
        "headers": [],
        "client": ("203.0.113.1", 1234),
        "method": "GET",
        "path": "/x",
        "query_string": b"",
        "server": ("test", 80),
        "scheme": "http",
    }
    req = Request(scope)
    resp = rate_limit_exceeded_handler(req, _FakeExc())  # type: ignore[arg-type]
    assert resp.status_code == 429
    assert resp.headers["Retry-After"] == "1"
    import json
    body = json.loads(resp.body)
    assert body["detail"] == "Rate limit exceeded"
    assert body["retry_after_seconds"] == 1
