"""Unit tests for idempotency decorator correctness (API-C4).

Covers the two bugs fixed in 2026-05:

BUG-1  Cache HIT was replayed with hard-coded ``status_code=200`` even
       when the route declared ``status_code=201``.  Fix: ``@idempotent``
       now accepts a ``status_code`` kwarg that is stored in the cache
       envelope and replayed verbatim.

BUG-2  Cache MISS serialized the response via ``jsonable_encoder``;
       cache HIT returned the stored dict as-is via ``JSONResponse``,
       bypassing FastAPI's ``response_model`` pipeline.  Fix: both paths
       now use ``_serialize_result()`` which calls
       ``model.model_dump(mode="json")`` for Pydantic models, giving
       identical field ordering and datetime formatting.

The tests mock Redis so they run without any infrastructure.
"""
from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_request(*, org_id: str = "org-test", key: str | None = "idem-key-1") -> Request:
    """Return a minimal Starlette Request with the idempotency state set."""
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/test",
        "query_string": b"",
        "headers": [],
        "server": ("testserver", 80),
        "scheme": "http",
    }
    req = Request(scope)
    req.state.idempotency_key = key
    req._body = b'{"name": "test"}'  # type: ignore[attr-defined]
    return req


class _SprintOut(BaseModel):
    id: str
    name: str
    status: str


def _make_redis(*, stored: dict | None = None) -> MagicMock:
    """Return a mock Redis client.

    If *stored* is not None the ``get`` call returns a JSON-encoded version
    of it (simulating a pre-existing cache entry / HIT scenario).
    """
    r = MagicMock()
    if stored is not None:
        r.get.return_value = json.dumps(stored).encode()
    else:
        r.get.return_value = None
    r.setex.return_value = True
    return r


# ---------------------------------------------------------------------------
# Test 1 — POST returning 201: second call returns 201, not 200
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cache_hit_replays_201_not_200():
    """HIT must replay the stored status_code (201), not a hard-coded 200.

    Scenario: create_sprint was called once and cached with status 201.
    The second call (same Idempotency-Key) must receive 201.
    """
    from app.utils.idempotency import idempotent

    call_count = 0

    @idempotent("create_sprint_test", status_code=201)
    async def _handler(request: Request, org_id: str) -> _SprintOut:
        nonlocal call_count
        call_count += 1
        return _SprintOut(id="sp-1", name="Sprint 1", status="planning")

    req = _make_request()

    # ── MISS (first call) ──────────────────────────────────────────────────
    miss_redis = _make_redis(stored=None)
    with patch("app.utils.idempotency._redis", return_value=miss_redis):
        first = await _handler(request=req, org_id="org-test")

    assert call_count == 1, "handler should have been called once on MISS"
    # The decorator returns the Pydantic model on MISS so FastAPI can run
    # response_model serialization; the status code is stored in Redis.
    assert isinstance(first, _SprintOut)
    stored_envelope = json.loads(miss_redis.setex.call_args[0][2])
    assert stored_envelope["status_code"] == 201, (
        "BUG-1: MISS must store status_code=201, not 200"
    )

    # ── HIT (second call with same key) ────────────────────────────────────
    hit_redis = _make_redis(stored=stored_envelope)
    with patch("app.utils.idempotency._redis", return_value=hit_redis):
        second = await _handler(request=req, org_id="org-test")

    assert call_count == 1, "handler must NOT be called again on HIT"
    assert isinstance(second, JSONResponse), "HIT must return a JSONResponse"
    assert second.status_code == 201, (
        f"BUG-1: HIT must replay status_code=201, got {second.status_code}"
    )
    assert second.headers.get("idempotency-replayed") == "true"


# ---------------------------------------------------------------------------
# Test 2 — HIT body shape matches MISS body shape (field ordering parity)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_hit_body_matches_miss_body():
    """MISS and HIT must produce structurally identical body dicts.

    Specifically: field ordering and serialization (e.g. datetimes) must be
    the same whether the response comes from a fresh handler call or from the
    Redis cache.  Both paths now use model_dump(mode='json').
    """
    from app.utils.idempotency import idempotent, _serialize_result

    @idempotent("sprint_body_test", status_code=201)
    async def _handler(request: Request, org_id: str) -> _SprintOut:
        return _SprintOut(id="sp-2", name="My Sprint", status="active")

    req = _make_request(key="body-key-1")

    # Capture what would be stored on MISS.
    miss_redis = _make_redis(stored=None)
    with patch("app.utils.idempotency._redis", return_value=miss_redis):
        miss_result = await _handler(request=req, org_id="org-test")

    stored_envelope = json.loads(miss_redis.setex.call_args[0][2])
    miss_body = stored_envelope["body"]

    # Simulate HIT with the stored envelope.
    hit_redis = _make_redis(stored=stored_envelope)
    with patch("app.utils.idempotency._redis", return_value=hit_redis):
        hit_result = await _handler(request=req, org_id="org-test")

    assert isinstance(hit_result, JSONResponse)
    hit_body = json.loads(hit_result.body.decode())

    # Also check against what _serialize_result produces directly.
    direct_serialized = _serialize_result(miss_result)

    assert hit_body == miss_body, (
        "BUG-2: HIT body must equal MISS body exactly\n"
        f"  HIT:  {hit_body}\n"
        f"  MISS: {miss_body}"
    )
    assert hit_body == direct_serialized, (
        "BUG-2: HIT body must match model_dump(mode='json') output\n"
        f"  HIT:         {hit_body}\n"
        f"  Serialized:  {direct_serialized}"
    )
    # Verify the expected field values are present.
    assert hit_body == {"id": "sp-2", "name": "My Sprint", "status": "active"}


# ---------------------------------------------------------------------------
# Test 3 — Redis fail (mock raises on GET) → fail-open, both calls execute
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_redis_get_raises_fail_open():
    """If Redis raises on GET, the decorator must fail-open (run handler).

    Both calls must reach the handler (no cached result served).
    """
    from app.utils.idempotency import idempotent

    call_count = 0

    @idempotent("failopen_test", status_code=200)
    async def _handler(request: Request, org_id: str) -> dict:
        nonlocal call_count
        call_count += 1
        return {"result": "ok", "call": call_count}

    req = _make_request(key="fail-open-key")

    broken_redis = MagicMock()
    broken_redis.get.side_effect = ConnectionError("Redis connection refused")
    broken_redis.setex.side_effect = ConnectionError("Redis connection refused")

    with patch("app.utils.idempotency._redis", return_value=broken_redis):
        first = await _handler(request=req, org_id="org-test")

    assert call_count == 1, "first call must reach handler even when Redis raises"

    # Reset body so second call computes same cache key.
    req._body = b'{"name": "test"}'  # type: ignore[attr-defined]
    with patch("app.utils.idempotency._redis", return_value=broken_redis):
        second = await _handler(request=req, org_id="org-test")

    assert call_count == 2, (
        "second call must also reach handler when Redis raises (fail-open)"
    )


# ---------------------------------------------------------------------------
# Test 4 — Redis client returns None (unavailable) → fail-open
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_redis_unavailable_fail_open():
    """If _redis() returns None (client unavailable), treat every call as MISS."""
    from app.utils.idempotency import idempotent

    call_count = 0

    @idempotent("unavailable_test", status_code=200)
    async def _handler(request: Request, org_id: str) -> dict:
        nonlocal call_count
        call_count += 1
        return {"ok": True}

    req = _make_request(key="unavail-key")

    with patch("app.utils.idempotency._redis", return_value=None):
        await _handler(request=req, org_id="org-test")
        req._body = b'{"name": "test"}'  # type: ignore[attr-defined]
        await _handler(request=req, org_id="org-test")

    assert call_count == 2, "both calls must execute when Redis is None (fail-open)"


# ---------------------------------------------------------------------------
# Test 5 — No Idempotency-Key header → pass-through (no caching attempted)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_idempotency_key_skips_cache():
    """Without an Idempotency-Key header the decorator must be a no-op."""
    from app.utils.idempotency import idempotent

    call_count = 0

    @idempotent("nokey_test", status_code=201)
    async def _handler(request: Request, org_id: str) -> dict:
        nonlocal call_count
        call_count += 1
        return {"id": "x"}

    req_no_key = _make_request(key=None)
    mock_redis = _make_redis()

    with patch("app.utils.idempotency._redis", return_value=mock_redis):
        await _handler(request=req_no_key, org_id="org-test")
        await _handler(request=req_no_key, org_id="org-test")

    assert call_count == 2, "both calls must execute when no Idempotency-Key"
    mock_redis.get.assert_not_called()
    mock_redis.setex.assert_not_called()
