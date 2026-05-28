import asyncio
import hashlib
import secrets
import time
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.config import settings

security = HTTPBearer()

_REVOKED_PREFIX = "revoked_token:"
# SEC-003: per-bearer set of SSE ticket hashes minted from that bearer.
# When the bearer is revoked (logout / refresh), every ticket in the set
# is revoked too so a leaked ticket cannot outlive its parent session.
_SSE_TICKETS_PREFIX = "sse_tickets:"
# SC-013: per-ticket binding to the caller's forwarded IP + a UA hash,
# captured at mint time and verified on consume. A ticket leaked via a
# proxy/Referer log (CWE-598) is then unusable from a different client.
_SSE_BIND_PREFIX = "sse_bind:"
# SEC-030: helpful constants for iat/iss/aud.
_TOKEN_ISSUER = settings.APP_NAME
_TOKEN_AUDIENCE = settings.APP_NAME

# ── In-process negative cache for _is_revoked (C-2 from REVIEW_PERFORMANCE.md) ──
# Most JWTs are NOT revoked, so a tiny per-process TTL cache cuts Redis
# EXISTS round-trips to ~ 1/sec per unique token regardless of request
# rate. Negative-only — TRUE results are NEVER cached, so a revoked
# token starts being rejected on the next request after the cache entry
# expires (worst-case latency = `_REVOKE_NEGCACHE_TTL_S`).
#
# Security trade-off (acceptable): a user logged out via revoke_token()
# may still authenticate for up to 1 second per process. This matches
# typical Redis replication lag and is bounded by the cache TTL. The
# token's `exp` is still honoured exactly. To disable the cache, set
# JWT_REVOKE_NEGCACHE_TTL=0 in env.
_REVOKE_NEGCACHE_TTL_S = float(getattr(settings, "JWT_REVOKE_NEGCACHE_TTL", 1.0))
_REVOKE_NEGCACHE_MAX = 10_000
_revoke_negcache: dict[str, float] = {}


def _negcache_get(key: str) -> bool:
    """Return True iff `key` was recently confirmed not-revoked. Prunes expired."""
    seen_at = _revoke_negcache.get(key)
    if seen_at is None:
        return False
    if time.monotonic() - seen_at > _REVOKE_NEGCACHE_TTL_S:
        _revoke_negcache.pop(key, None)
        return False
    return True


def _negcache_put(key: str) -> None:
    """Record a not-revoked result. Caps the dict at `_REVOKE_NEGCACHE_MAX`."""
    if _REVOKE_NEGCACHE_TTL_S <= 0:
        return
    if len(_revoke_negcache) >= _REVOKE_NEGCACHE_MAX:
        # Cheap eviction: drop one arbitrary entry rather than tracking
        # LRU on the hot path. Missing the cache only means one extra
        # Redis EXISTS — never a correctness issue.
        _revoke_negcache.pop(next(iter(_revoke_negcache)), None)
    _revoke_negcache[key] = time.monotonic()


def _negcache_invalidate(key: str) -> None:
    """Drop a single entry from the cache (used when a token gets revoked)."""
    _revoke_negcache.pop(key, None)


def _token_key(token: str) -> str:
    return _REVOKED_PREFIX + hashlib.sha256(token.encode()).hexdigest()


def _token_hash(token: str) -> str:
    """Stable identifier for a token. Used as the SSE-ticket family key."""
    return hashlib.sha256(token.encode()).hexdigest()


def _sse_set_key(parent_token: str) -> str:
    return _SSE_TICKETS_PREFIX + _token_hash(parent_token)


def _sse_bind_key(sse_ticket: str) -> str:
    return _SSE_BIND_PREFIX + _token_hash(sse_ticket)


def _sse_bind_fingerprint(client_ip: str | None, user_agent: str | None) -> str:
    """Stable fingerprint of the consuming client. We hash the UA (it can be
    long / contain PII) and concatenate the forwarded IP. An empty IP is
    tolerated (mint and consume must simply agree)."""
    ua_hash = hashlib.sha256((user_agent or "").encode("utf-8")).hexdigest()
    return f"{client_ip or ''}|{ua_hash}"


def bind_sse_ticket(sse_ticket: str, client_ip: str | None, user_agent: str | None, ttl_seconds: int) -> None:
    """SC-013: store the mint-time client fingerprint for `sse_ticket`.

    No-op when Redis is unavailable — in that degraded mode the ticket falls
    back to its existing protections (60s TTL + session-revocation cascade).
    """
    from app.core.redis_client import get_redis
    r = get_redis()
    if not r:
        return
    try:
        r.setex(
            _sse_bind_key(sse_ticket),
            ttl_seconds,
            _sse_bind_fingerprint(client_ip, user_agent),
        )
    except Exception:
        pass


def sse_ticket_binding_ok(sse_ticket: str, client_ip: str | None, user_agent: str | None) -> bool:
    """SC-013: True iff the consuming client matches the mint-time binding.

    Fail-OPEN when there is no stored binding (Redis offline at mint, or a
    legacy ticket minted before this change) so we never break the SSE flow in
    a degraded deployment. Fail-CLOSED only when a binding EXISTS and differs —
    that is the leaked-ticket-replayed-elsewhere case.
    """
    from app.core.redis_client import get_redis
    r = get_redis()
    if not r:
        return True
    try:
        stored = r.get(_sse_bind_key(sse_ticket))
    except Exception:
        return True
    if stored is None:
        return True
    if isinstance(stored, bytes):
        stored = stored.decode("utf-8", errors="replace")
    return hmac_compare(stored, _sse_bind_fingerprint(client_ip, user_agent))


def hmac_compare(a: str, b: str) -> bool:
    """Constant-time string compare (thin wrapper so callers don't import
    the stdlib symbol directly)."""
    import hmac as _hmac
    return _hmac.compare_digest(a, b)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(
    user_id: str,
    expires_delta: timedelta | None = None,
    extra_claims: dict | None = None,
) -> str:
    """Mint a JWT.

    SEC-030: every token now carries `iat` / `iss` / `aud` / `jti` claims
    so deployments that share a JWT secret across blue/green / staging
    cannot cross-accept tokens. `iat` also enables the per-user
    `token_epoch` invalidation pattern documented in SEC-034.
    """
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode = {
        "sub": user_id,
        "exp": expire,
        "iat": now,
        "nbf": now,
        "iss": _TOKEN_ISSUER,
        "aud": _TOKEN_AUDIENCE,
        "jti": secrets.token_urlsafe(16),
        # SC-036: every token carries an explicit scope. Normal bearers are
        # "default"; the SSE ticket mint overrides this with "sse" via
        # extra_claims. `get_current_user_id` rejects any token whose scope is
        # set and not "default", so an SSE ticket can never act as a full
        # bearer on a non-SSE endpoint (the two SSE handlers check for "sse").
        "scope": "default",
    }
    if extra_claims:
        to_encode.update(extra_claims)
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm="HS256")


def register_sse_ticket(parent_bearer: str, sse_ticket: str, ttl_seconds: int) -> None:
    """SEC-003: associate an SSE ticket with the bearer that minted it.

    On `revoke_token(parent_bearer)` (logout / refresh) we iterate the
    set and revoke every member, ensuring the SSE ticket cannot outlive
    the originating session. No-op when Redis is unavailable — in that
    case the ticket simply expires by its own 60-second TTL.
    """
    from app.core.redis_client import get_redis
    r = get_redis()
    if not r:
        return
    try:
        key = _sse_set_key(parent_bearer)
        # The set value is the *sha256 of the ticket*, so we never store
        # raw tokens — matches the existing revocation-list shape.
        r.sadd(key, _token_hash(sse_ticket))
        # Set the TTL on the set to at least the bearer's lifetime so it
        # cleans itself up. Use the bearer's max TTL as the upper bound.
        r.expire(key, max(ttl_seconds, settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60))
    except Exception:
        pass


def _revoke_sse_family(parent_token: str, expires_in_seconds: int) -> None:
    """SEC-003: revoke every SSE ticket minted from a bearer."""
    from app.core.redis_client import get_redis
    r = get_redis()
    if not r:
        return
    try:
        key = _sse_set_key(parent_token)
        members = r.smembers(key) or set()
        for ticket_hash in members:
            r.setex(_REVOKED_PREFIX + ticket_hash, expires_in_seconds, "1")
        r.delete(key)
    except Exception:
        pass


def revoke_token(token: str, expires_in_seconds: int = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60) -> None:
    """Add token to Redis revocation list. No-op if Redis is unavailable.

    SEC-003: also cascades to every SSE ticket minted from this bearer
    so a stolen short-lived ticket cannot survive the logout / refresh
    that revoked its parent.
    """
    from app.core.redis_client import get_redis
    r = get_redis()
    if r:
        try:
            r.setex(_token_key(token), expires_in_seconds, "1")
        except Exception:
            pass
    # Drop any stale not-revoked entry so the next check sees the
    # revocation immediately rather than waiting for the TTL.
    _negcache_invalidate(_token_key(token))
    _revoke_sse_family(token, expires_in_seconds)


def _is_revoked(token: str) -> bool:
    """Sync revocation check. Safe to call from sync `def` handlers
    (FastAPI runs them in a thread-pool worker, so the Redis round-trip
    does NOT block the event loop). Async handlers should prefer
    `_is_revoked_async` so the Redis I/O is non-blocking.

    C-2 mitigation: in-process negative cache short-circuits the Redis
    EXISTS for tokens seen as not-revoked within the last
    `_REVOKE_NEGCACHE_TTL_S` seconds. A TRUE result is never cached —
    a revoked token will be rejected on the next request after the
    cache entry expires (worst-case ≤ 1 s default).
    """
    key = _token_key(token)
    if _negcache_get(key):
        return False
    from app.core.redis_client import get_redis
    r = get_redis()
    if not r:
        # Cannot positively confirm; do not cache the absence of an
        # answer. Defaulting to "not revoked" matches the prior
        # behaviour when Redis is offline.
        return False
    try:
        # Revocation lookups use sha256 in BOTH the parent and child
        # paths, so we just check the prefix+hash key directly.
        revoked = bool(r.exists(key))
    except Exception:
        return False
    if not revoked:
        _negcache_put(key)
    return revoked


async def _is_revoked_async(token: str) -> bool:
    """Non-blocking revocation check for async handlers.

    The negative cache shortcut is checked synchronously (no I/O); a
    cache miss offloads the Redis EXISTS to a worker thread via
    `asyncio.to_thread` so the event loop never blocks on Redis I/O.

    Used by the SSE handlers (sprints.py / agent_workflows.py) which
    decode the SSE ticket inside an `async def` and would otherwise
    burn the entire Redis RTT on the event loop.
    """
    key = _token_key(token)
    if _negcache_get(key):
        return False
    from app.core.redis_client import get_redis
    r = get_redis()
    if not r:
        return False
    try:
        revoked = await asyncio.to_thread(lambda: bool(r.exists(key)))
    except Exception:
        return False
    if not revoked:
        _negcache_put(key)
    return revoked


def _decode_jwt(token: str) -> dict:
    """Pure JWT decode + signature/iat/iss/aud verification. No I/O."""
    try:
        # SEC-030: pin algorithm, audience, issuer. `options` lets us
        # opt-in to `iat`/`nbf`/`aud`/`iss` validation explicitly.
        return jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=["HS256"],
            audience=_TOKEN_AUDIENCE,
            issuer=_TOKEN_ISSUER,
            options={
                "verify_aud": True,
                "verify_iss": True,
                "verify_iat": True,
                "verify_exp": True,
            },
        )
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def decode_access_token(token: str) -> dict:
    payload = _decode_jwt(token)
    if _is_revoked(token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked")
    return payload


async def decode_access_token_async(token: str) -> dict:
    """Async variant that runs the Redis revocation check via
    `asyncio.to_thread` so the FastAPI event loop is never blocked on
    Redis I/O. Preferred for async-def handlers (SSE streams, etc.).

    Semantics are identical to `decode_access_token`; only the I/O
    path differs.
    """
    payload = _decode_jwt(token)
    if await _is_revoked_async(token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked")
    return payload


async def get_current_user_id(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    payload = decode_access_token(credentials.credentials)
    user_id: str | None = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    # SC-036: reject scoped tokens on the normal bearer path. Only "default"
    # (or a token minted before this change, which carries no scope) is a
    # full bearer. An SSE ticket (scope="sse") must NOT authenticate any
    # non-SSE endpoint even within its 60s TTL — the two SSE handlers verify
    # scope=="sse" themselves and bypass this dependency entirely.
    scope = payload.get("scope")
    if scope is not None and scope != "default":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token scope is not valid for this endpoint",
        )
    # SC-012: propagate impersonation attribution onto request.state so
    # the audit writer can record the originating super-admin alongside
    # the impersonated user. Missing/None when the JWT was not minted by
    # /superadmin/impersonate. Wrapped in a try/except because some test
    # paths construct ASGI scopes without a `state` attribute.
    try:
        request.state.impersonator_id = payload.get("imp_by")
        request.state.impersonation_reason = payload.get("imp_reason")
    except Exception:  # noqa: BLE001 — best-effort, never block auth
        pass
    return user_id
