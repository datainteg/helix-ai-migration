"""Performance tests — JWT revocation negative cache (C-2).

Verifies:
  - _is_revoked short-circuits via the in-process cache on hot tokens
    so we hit Redis at most once per token per TTL window.
  - revoke_token invalidates the cache entry so a freshly-revoked
    token is rejected immediately on the next call.
  - _is_revoked_async behaves identically and never blocks the loop
    (we assert that the underlying redis.exists is called via
    asyncio.to_thread, i.e., in a worker thread — not the event loop).

These are pure unit tests over the jwt module; they do not need a
database or a running app, so they reuse the redis-mock pattern from
conftest.py rather than spinning up the full test app.
"""

from __future__ import annotations

import asyncio
import threading
from unittest.mock import MagicMock, patch

import pytest

from app.auth import jwt as jwt_module


def _fresh_negcache():
    """Helper: clear the per-process negative cache between tests."""
    jwt_module._revoke_negcache.clear()


def test_is_revoked_caches_negative_results(monkeypatch):
    """After the first not-revoked answer, subsequent calls must not
    hit Redis at all until the TTL expires."""
    _fresh_negcache()
    mock_redis = MagicMock()
    mock_redis.exists.return_value = 0  # not revoked

    with patch("app.core.redis_client.get_redis", return_value=mock_redis):
        assert jwt_module._is_revoked("hot-token") is False
        assert jwt_module._is_revoked("hot-token") is False
        assert jwt_module._is_revoked("hot-token") is False

    # Exactly one Redis round-trip across three calls.
    assert mock_redis.exists.call_count == 1


def test_is_revoked_does_not_cache_positive_results(monkeypatch):
    """A revoked token must hit Redis on every call so revocation
    propagates without delay even if the cache somehow had an entry."""
    _fresh_negcache()
    mock_redis = MagicMock()
    mock_redis.exists.return_value = 1  # revoked

    with patch("app.core.redis_client.get_redis", return_value=mock_redis):
        assert jwt_module._is_revoked("bad-token") is True
        assert jwt_module._is_revoked("bad-token") is True
        assert jwt_module._is_revoked("bad-token") is True

    # No caching of TRUE results — every call hits Redis.
    assert mock_redis.exists.call_count == 3


def test_revoke_token_invalidates_negcache(monkeypatch):
    """If a token was negative-cached, revoke_token must drop the
    entry so the next _is_revoked sees Redis and returns True."""
    _fresh_negcache()
    mock_redis = MagicMock()
    # First two calls: exists=0 (cached false). After revoke: exists=1.
    mock_redis.exists.side_effect = [0, 1]
    mock_redis.setex.return_value = True
    mock_redis.smembers.return_value = set()  # no SSE family
    mock_redis.delete.return_value = 0

    with patch("app.core.redis_client.get_redis", return_value=mock_redis):
        assert jwt_module._is_revoked("tok") is False  # caches negative
        # Cache hit — no Redis call.
        assert jwt_module._is_revoked("tok") is False
        # Now revoke. Must invalidate negcache.
        jwt_module.revoke_token("tok", expires_in_seconds=60)
        assert jwt_module._is_revoked("tok") is True  # cache invalidated

    assert mock_redis.exists.call_count == 2


def test_negcache_respects_ttl_expiry(monkeypatch):
    """When the cache entry ages past the TTL, the next call must
    re-check Redis (so a revocation taking effect mid-TTL is picked
    up on the very next request after expiry)."""
    _fresh_negcache()
    mock_redis = MagicMock()
    mock_redis.exists.return_value = 0

    # Force the TTL to a long value and then drive monotonic forward
    # past it via monkeypatch.
    monkeypatch.setattr(jwt_module, "_REVOKE_NEGCACHE_TTL_S", 0.5)

    base_time = 1_000_000.0
    current = [base_time]
    monkeypatch.setattr(jwt_module.time, "monotonic", lambda: current[0])

    with patch("app.core.redis_client.get_redis", return_value=mock_redis):
        # First call: Redis hit + cache populate.
        assert jwt_module._is_revoked("ttl-token") is False
        assert mock_redis.exists.call_count == 1

        # Same instant: cache hit, no Redis.
        assert jwt_module._is_revoked("ttl-token") is False
        assert mock_redis.exists.call_count == 1

        # Jump past TTL: cache miss, Redis hit again.
        current[0] = base_time + 1.0
        assert jwt_module._is_revoked("ttl-token") is False
        assert mock_redis.exists.call_count == 2


def test_negcache_caps_at_max_entries(monkeypatch):
    """Flooding the cache with unique tokens must NOT exceed the
    configured cap — this protects against OOM under a token-spam
    attack."""
    _fresh_negcache()
    monkeypatch.setattr(jwt_module, "_REVOKE_NEGCACHE_MAX", 5)
    mock_redis = MagicMock()
    mock_redis.exists.return_value = 0

    with patch("app.core.redis_client.get_redis", return_value=mock_redis):
        for i in range(20):
            jwt_module._is_revoked(f"flood-{i}")

    # Cap of 5 — never exceeded regardless of how many distinct
    # tokens we threw in.
    assert len(jwt_module._revoke_negcache) <= 5


def test_negcache_disabled_when_ttl_zero(monkeypatch):
    """If JWT_REVOKE_NEGCACHE_TTL is 0, results are never cached and
    every _is_revoked hits Redis. Lets paranoid operators opt out."""
    _fresh_negcache()
    monkeypatch.setattr(jwt_module, "_REVOKE_NEGCACHE_TTL_S", 0.0)
    mock_redis = MagicMock()
    mock_redis.exists.return_value = 0

    with patch("app.core.redis_client.get_redis", return_value=mock_redis):
        for _ in range(5):
            jwt_module._is_revoked("no-cache-token")

    assert mock_redis.exists.call_count == 5
    assert len(jwt_module._revoke_negcache) == 0


def test_is_revoked_when_redis_down_returns_false(monkeypatch):
    """Defensive: if Redis is unreachable, fall back to the
    not-revoked outcome (matches prior behaviour)."""
    _fresh_negcache()
    with patch("app.core.redis_client.get_redis", return_value=None):
        assert jwt_module._is_revoked("nope") is False
        # Don't cache absence-of-answer.
        assert len(jwt_module._revoke_negcache) == 0


def test_is_revoked_swallows_redis_exception(monkeypatch):
    """If redis.exists raises, return False — never bubble up a 500
    from the revocation check."""
    _fresh_negcache()
    mock_redis = MagicMock()
    mock_redis.exists.side_effect = ConnectionError("redis flapped")

    with patch("app.core.redis_client.get_redis", return_value=mock_redis):
        assert jwt_module._is_revoked("crash-token") is False
        assert len(jwt_module._revoke_negcache) == 0


# ── Async variant tests ────────────────────────────────────────────


def test_is_revoked_async_offloads_to_thread(monkeypatch):
    """The async variant must run the (blocking) redis.exists in a
    worker thread, not on the event loop. We assert the thread id is
    different from the loop's thread id during the call."""
    _fresh_negcache()

    main_thread = threading.get_ident()
    captured_thread: dict[str, int] = {}

    def slow_exists(_key):
        captured_thread["tid"] = threading.get_ident()
        return 0  # not revoked

    mock_redis = MagicMock()
    mock_redis.exists.side_effect = slow_exists

    async def go():
        with patch("app.core.redis_client.get_redis", return_value=mock_redis):
            result = await jwt_module._is_revoked_async("loop-token")
            assert result is False

    asyncio.run(go())
    # Must have run in a worker thread, NOT the event-loop thread.
    assert captured_thread["tid"] != main_thread


def test_is_revoked_async_uses_negcache(monkeypatch):
    """Async variant honours the same negative cache: only the first
    call per token in the TTL window touches Redis."""
    _fresh_negcache()
    mock_redis = MagicMock()
    mock_redis.exists.return_value = 0

    async def go():
        with patch("app.core.redis_client.get_redis", return_value=mock_redis):
            await jwt_module._is_revoked_async("a-token")
            await jwt_module._is_revoked_async("a-token")
            await jwt_module._is_revoked_async("a-token")

    asyncio.run(go())
    assert mock_redis.exists.call_count == 1


def test_decode_access_token_async_rejects_revoked(monkeypatch):
    """End-to-end: a revoked token must raise 401 from
    decode_access_token_async, same as the sync version."""
    _fresh_negcache()
    mock_redis = MagicMock()
    mock_redis.exists.return_value = 1  # revoked

    # Mint a real token so jwt.decode succeeds.
    token = jwt_module.create_access_token("u-1")

    async def go():
        with patch("app.core.redis_client.get_redis", return_value=mock_redis):
            with pytest.raises(Exception) as exc_info:
                await jwt_module.decode_access_token_async(token)
            # FastAPI HTTPException; check status_code via attribute.
            assert getattr(exc_info.value, "status_code", None) == 401

    asyncio.run(go())
