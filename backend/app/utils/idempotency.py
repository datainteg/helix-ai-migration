"""Idempotency-Key support for expensive POST endpoints (API-C4).

Why this exists
---------------
`POST /agent-workflows` starts a BMAD planning run that costs real LLM
money. A flaky network retrying the same POST 2× = 2 workflows started,
2× spend, possibly conflicting artifacts. The fix recommended in
REVIEW_API_CONTRACT.md §1 row 3 is:

    accept `Idempotency-Key` header, persist
    `(org_id, endpoint, body, key) → response_body`
    for 24h in Redis, return the existing response on collision.

Shape
-----
* The decorator `@idempotent("create_workflow")` (route-name string) is
  applied to a FastAPI POST handler.
* On entry it hashes `(org_id, endpoint_name, body_sha256, key)` and
  looks up the hash in Redis under `idempotency:{hash}`.
* HIT → replays the cached JSON body verbatim (returns 200 with the
  same shape the original response had, plus an `Idempotency-Replayed`
  header so the caller can tell).
* MISS → runs the handler. If the handler succeeds (2xx) the response
  is captured and stored for 24h. Non-2xx responses are NOT cached —
  the caller is expected to retry with a fresh key.

Failure modes
-------------
* Redis unavailable → log a warning, treat every request as a MISS.
  This is a per-request key/value lookup; failing open is safer than
  rejecting the call.
* No `Idempotency-Key` header → behave as before (no caching). The
  decorator is non-invasive.

Middleware companion
--------------------
`IdempotencyMiddleware` sets `request.state.idempotency_key` so the
helper can read it without rummaging through headers itself.
"""

from __future__ import annotations

import functools
import hashlib
import json
import logging
from typing import Any, Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


logger = logging.getLogger(__name__)


# 24 h, per the review spec. Keep as a module constant so a test or
# operator override can monkey-patch it without rewriting Redis calls.
DEFAULT_TTL_SECONDS = 24 * 60 * 60


# Header name lifted into a constant so middleware + decorator agree.
IDEMPOTENCY_HEADER = "Idempotency-Key"
REPLAY_HEADER = "Idempotency-Replayed"


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """Stash the Idempotency-Key header on `request.state`.

    The header itself is not authoritative — the decorator still hashes
    `(org_id, endpoint, body)` together with the key, so two callers
    using the same key but different bodies get distinct cache entries.
    This middleware is the cheap parse step; the decorator does the work.
    """

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        # Header lookup is case-insensitive on Starlette's MutableHeaders.
        key = request.headers.get(IDEMPOTENCY_HEADER)
        # Always set, even if None, so the helper can read it without
        # `hasattr` gymnastics.
        request.state.idempotency_key = key
        return await call_next(request)


def _compute_cache_key(*, endpoint_name: str, org_id: str, body_bytes: bytes, key: str) -> str:
    """Hash the inputs into a single cache key.

    Including the request body in the hash means a malicious caller who
    re-uses an Idempotency-Key with different body data does NOT get the
    cached response — they get a fresh handler invocation. This matches
    Stripe's idempotency semantics: same key + same body → cached;
    same key + different body → 422 (we treat it as a MISS instead,
    which is more permissive but safer for our SDK consumers).
    """
    body_digest = hashlib.sha256(body_bytes or b"").hexdigest()
    combined = f"{endpoint_name}|{org_id}|{body_digest}|{key}"
    return hashlib.sha256(combined.encode()).hexdigest()


def _redis():
    """Return shared Redis client or None — failures are non-fatal."""
    try:
        from app.core.redis_client import get_redis
        return get_redis()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Redis client import failed; idempotency disabled: %s", exc)
        return None


async def _read_body(request: Request) -> bytes:
    """Read and stash the request body so downstream handlers can re-read it.

    FastAPI's JSON parser consumes the body stream once; subsequent reads
    return empty. We stash the bytes on `_body` (Starlette's convention)
    so the regular path keeps working after the cache lookup is done.
    """
    if not hasattr(request, "_body") or request._body is None:  # type: ignore[attr-defined]
        body = await request.body()
        request._body = body  # type: ignore[attr-defined]
        return body
    return request._body  # type: ignore[attr-defined]


def idempotent(endpoint_name: str, *, ttl_seconds: int = DEFAULT_TTL_SECONDS):
    """Decorator: cache successful 2xx responses for 24h per `(org, key, body)`.

    Applies to FastAPI route handlers that take a `request: Request` and an
    `org_id: str` argument (the common pattern across this codebase). If
    the handler doesn't have those, the helper falls back to MISS-always
    behaviour rather than crashing — non-invasive.

    Usage:
        @router.post("/projects/{pid}/agent-workflows")
        @idempotent("start_workflow")
        async def start_workflow(...):
            ...
    """

    def _decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        @functools.wraps(func)
        async def _wrapper(*args, **kwargs):
            # FastAPI passes dependencies as kwargs (when names match) so
            # request + org_id are pulled from there. If absent (some test
            # harness calling the function directly), skip caching.
            request: Request | None = kwargs.get("request")
            org_id: str | None = kwargs.get("org_id")

            if request is None or org_id is None:
                return await func(*args, **kwargs)

            key = getattr(request.state, "idempotency_key", None)
            if not key:
                # No header → no caching. Just run the handler.
                return await func(*args, **kwargs)

            redis_client = _redis()
            if redis_client is None:
                # Redis down → fail open. Log once at warn level.
                return await func(*args, **kwargs)

            body_bytes = await _read_body(request)
            cache_key = _compute_cache_key(
                endpoint_name=endpoint_name,
                org_id=org_id,
                body_bytes=body_bytes,
                key=key,
            )
            redis_full_key = f"idempotency:{cache_key}"

            try:
                cached_raw = redis_client.get(redis_full_key)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Redis GET failed in idempotency lookup: %s", exc)
                cached_raw = None

            if cached_raw:
                try:
                    cached = json.loads(cached_raw)
                    status_code = int(cached.get("status_code", 200))
                    body = cached.get("body")
                except Exception:
                    # Malformed cache entry; fall through to fresh call.
                    cached = None
                else:
                    headers = {REPLAY_HEADER: "true"}
                    return JSONResponse(
                        content=body,
                        status_code=status_code,
                        headers=headers,
                    )

            # MISS — run the real handler.
            result = await func(*args, **kwargs)

            # Capture the response body for cache. The handler typically
            # returns a Pydantic model or dict — fastapi converts it to
            # JSON later. We need the dict form here, so:
            cached_body: Any
            status_code = 200
            if isinstance(result, Response):
                # Handler returned a raw Response; only cache 2xx.
                if 200 <= result.status_code < 300 and isinstance(result, JSONResponse):
                    cached_body = json.loads(result.body.decode())
                    status_code = result.status_code
                else:
                    return result
            else:
                # Pydantic / dict / list — serialize via FastAPI's encoder
                # so datetimes etc. are ISO-8601 in the cached body too.
                from fastapi.encoders import jsonable_encoder
                cached_body = jsonable_encoder(result)

            try:
                redis_client.setex(
                    redis_full_key,
                    ttl_seconds,
                    json.dumps({"status_code": status_code, "body": cached_body}),
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Redis SETEX failed in idempotency store: %s", exc)

            return result

        return _wrapper

    return _decorator
