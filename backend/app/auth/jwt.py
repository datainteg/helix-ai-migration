import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.config import settings

security = HTTPBearer()

_REVOKED_PREFIX = "revoked_token:"
# SEC-003: per-bearer set of SSE ticket hashes minted from that bearer.
# When the bearer is revoked (logout / refresh), every ticket in the set
# is revoked too so a leaked ticket cannot outlive its parent session.
_SSE_TICKETS_PREFIX = "sse_tickets:"
# SEC-030: helpful constants for iat/iss/aud.
_TOKEN_ISSUER = settings.APP_NAME
_TOKEN_AUDIENCE = settings.APP_NAME


def _token_key(token: str) -> str:
    return _REVOKED_PREFIX + hashlib.sha256(token.encode()).hexdigest()


def _token_hash(token: str) -> str:
    """Stable identifier for a token. Used as the SSE-ticket family key."""
    return hashlib.sha256(token.encode()).hexdigest()


def _sse_set_key(parent_token: str) -> str:
    return _SSE_TICKETS_PREFIX + _token_hash(parent_token)


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
    _revoke_sse_family(token, expires_in_seconds)


def _is_revoked(token: str) -> bool:
    from app.core.redis_client import get_redis
    r = get_redis()
    if not r:
        return False
    try:
        # Revocation lookups use sha256 in BOTH the parent and child
        # paths, so we just check the prefix+hash key directly.
        return bool(r.exists(_token_key(token)))
    except Exception:
        return False


def decode_access_token(token: str) -> dict:
    try:
        # SEC-030: pin algorithm, audience, issuer. `options` lets us
        # opt-in to `iat`/`nbf`/`aud`/`iss` validation explicitly.
        payload = jwt.decode(
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
    if _is_revoked(token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked")
    return payload


async def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    payload = decode_access_token(credentials.credentials)
    user_id: str | None = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return user_id
