"""Shared rate limiter instances — disabled in test/dev, active in production.

Two limiters:
  - limiter          per-IP, default for unauthenticated + auth endpoints
  - org_limiter      per-org, used on costly authenticated paths so a single
                     noisy tenant cannot starve other tenants in a shared
                     deployment

Decorate write endpoints that touch LLM or workflow surface with
`@org_limiter.limit(...)` instead of (or in addition to) the per-IP limiter.
"""

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings


def _org_key(request: Request) -> str:
    """Resolve a key for per-org limits.

    Falls back to remote IP when no JWT is present so the limiter can still
    function on unauthenticated endpoints. The Bearer JWT's `sub` claim is
    the user id; we promote it to an org id by reading the X-Active-Org-Id
    header when the frontend sets it (cheap, no DB lookup).
    """
    org = request.headers.get("X-Active-Org-Id")
    if org:
        return f"org:{org}"
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        # Hash the trailing token-tail so multiple users in one org are not
        # bucketed together when the header is absent — still per-user, but
        # uniform with the org key namespace.
        return f"user:{auth[-16:]}"
    return get_remote_address(request)


limiter = Limiter(
    key_func=get_remote_address,
    enabled=settings.APP_ENV == "production",
)


org_limiter = Limiter(
    key_func=_org_key,
    enabled=settings.APP_ENV == "production",
)
