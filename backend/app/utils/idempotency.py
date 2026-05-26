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
* The decorator `@idempotent("create_workflow", status_code=201)` (route-name
  string + the route's declared HTTP status code) is applied to a FastAPI
  POST handler.
* On entry it hashes `(org_id, endpoint_name, body_sha256, key)` and
  looks up the hash in Redis under `idempotency:{hash}`.
* HIT → replays the stored JSON body with the ORIGINAL status_code (not
  hard-coded 200), plus an `Idempotency-Replayed` header so the caller
  can tell.  The body was stored via the same serialization path as MISS,
  so shape/field-ordering is symmetric.
* MISS → runs the handler. If the handler succeeds (2xx) the response
  is captured and stored for 24h. Non-2xx responses are NOT cached —
  the caller is expected to retry with a fresh key.

Cache envelope format
---------------------
Redis value is a JSON object: ``{"status_code": <int>, "body": <dict>}``.
Both MISS and HIT paths serialize Pydantic models via
``model.model_dump(mode="json")`` so the body shape is identical in both
cases (same field ordering, same ``exclude_none`` behaviour as FastAPI's
default pipeline, consistent datetime serialization).

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


def _serialize_result(result: Any) -> dict | list | Any:
    """Serialize a handler return value to a JSON-safe structure.

    Uses the same serialization path for both MISS (storing) and HIT
    (replaying) so the two code paths are symmetric:

    * Pydantic model  → ``model_dump(mode="json")`` — respects field
      aliases, validators, and exclude_none behaviour exactly as
      FastAPI's ``response_model`` pipeline would.
    * dict / list     → passed through ``jsonable_encoder`` for
      datetime/UUID coercion.
    * Anything else   → ``jsonable_encoder`` as fallback.
    """
    try:
        # BaseModel covers Pydantic v2; model_dump(mode="json") serializes
        # datetimes, UUIDs, enums to JSON-native types in the same way that
        # FastAPI's response_model serializer does.
        from pydantic import BaseModel
        if isinstance(result, BaseModel):
            return result.model_dump(mode="json")
    except ImportError:
        pass

    from fastapi.encoders import jsonable_encoder
    return jsonable_encoder(result)


def idempotent(
    endpoint_name: str,
    *,
    status_code: int = 200,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
):
    """Decorator: cache successful 2xx responses for 24h per ``(org, key, body)``.

    Parameters
    ----------
    endpoint_name:
        Logical name used in the cache key (e.g. ``"create_sprint"``).
        Must be unique across all decorated endpoints in the org
        namespace.
    status_code:
        The HTTP status code that the route handler *declares* (e.g.
        ``status_code=201`` for create endpoints).  This is stored in
        the cache envelope and replayed verbatim on HIT so that clients
        see ``201`` on the second call, not a hard-coded ``200``.
        **Must match the ``status_code=`` kwarg on the ``@router.post``
        decorator above this one.**  Defaults to ``200`` for
        backward-compatibility with endpoints that don't declare an
        explicit code.
    ttl_seconds:
        TTL for the Redis cache entry.  Defaults to 24 h.

    Applies to FastAPI route handlers that take a ``request: Request`` and an
    ``org_id: str`` argument (the common pattern across this codebase). If
    the handler doesn't have those, the helper falls back to MISS-always
    behaviour rather than crashing — non-invasive.

    Usage::

        @router.post("/projects/{pid}/sprints", status_code=201)
        @idempotent("create_sprint", status_code=201)
        async def api_create_sprint(...):
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
                    # BUG-FIX (API-C4-1): replay the status_code that was
                    # stored when the response was first created — NOT a
                    # hard-coded 200.  Routes declaring status_code=201 (e.g.
                    # POST /sprints, POST /cutovers) must replay 201 so
                    # clients can distinguish create-vs-replay-after-create.
                    cached_status = int(cached.get("status_code", status_code))
                    body = cached.get("body")
                except Exception:
                    # Malformed cache entry; fall through to fresh call.
                    cached = None
                else:
                    replay_headers = {REPLAY_HEADER: "true"}
                    # BUG-FIX (API-C4-2): body was stored via
                    # _serialize_result() which uses model_dump(mode="json")
                    # for Pydantic models — same path as below on MISS — so
                    # field ordering and validation are symmetric.
                    return JSONResponse(
                        content=body,
                        status_code=cached_status,
                        headers=replay_headers,
                    )

            # MISS — run the real handler.
            result = await func(*args, **kwargs)

            # Capture the response body for cache. The handler typically
            # returns a Pydantic model or dict — FastAPI converts it to
            # JSON later. We need the dict form here for storage.
            cached_body: Any
            cached_status_code: int
            if isinstance(result, Response):
                # Handler returned a raw Response; only cache 2xx.
                if 200 <= result.status_code < 300 and isinstance(result, JSONResponse):
                    cached_body = json.loads(result.body.decode())
                    cached_status_code = result.status_code
                else:
                    return result
            else:
                # BUG-FIX (API-C4-1): use the status_code declared by the
                # decorator (which must match @router.post(..., status_code=))
                # instead of the previous hard-coded 200.
                #
                # BUG-FIX (API-C4-2): serialize via _serialize_result() which
                # uses model_dump(mode="json") for Pydantic models — the same
                # serialization that FastAPI's response_model pipeline applies.
                # This ensures MISS and HIT produce structurally identical
                # bodies (same field ordering, same datetime format).
                cached_body = _serialize_result(result)
                cached_status_code = status_code

            try:
                redis_client.setex(
                    redis_full_key,
                    ttl_seconds,
                    json.dumps({"status_code": cached_status_code, "body": cached_body}),
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Redis SETEX failed in idempotency store: %s", exc)

            return result

        return _wrapper

    return _decorator
