"""Shared rate limiter instances — disabled in test/dev, active in production.

Two limiters:
  - limiter          per-IP, default for unauthenticated + auth endpoints
  - org_limiter      per-org, used on costly authenticated paths so a single
                     noisy tenant cannot starve other tenants in a shared
                     deployment

Decorate write endpoints that touch LLM or workflow surface with
`@org_limiter.limit(...)` instead of (or in addition to) the per-IP limiter.
"""

import logging
import os

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

logger = logging.getLogger(__name__)


# SC-001: rate limiting is now ON by default. The only off-switch is the
# explicit HELIX_DISABLE_RATE_LIMIT=1 envvar, intended for test runners.
# Tying the kill-switch to an envvar (rather than APP_ENV) means a forgotten
# APP_ENV does not silently disable login throttling in staging/dev.
_RL_DISABLED = bool(os.environ.get("HELIX_DISABLE_RATE_LIMIT"))
_RL_ENABLED = not _RL_DISABLED

if _RL_DISABLED:
    # CRITICAL: log loudly so the absence of throttling is never silent.
    logger.critical(
        "Rate limiting is DISABLED via HELIX_DISABLE_RATE_LIMIT — auth and "
        "LLM endpoints have no brute-force / cost-amplification brake. This "
        "must only be set inside test runners."
    )


def _remote_address(request: Request) -> str:
    """SC-051: per-IP limiter key that honours the trusted-proxy
    X-Forwarded-For chain. Behind Caddy, `get_remote_address` returns the
    proxy's loopback for EVERY request, so all callers shared one bucket and
    the auth brute-force throttle was effectively global. `get_client_ip`
    returns the proxy loopback verbatim when no proxy is trusted, so this is
    a safe drop-in.
    """
    try:
        from app.utils.client_ip import get_client_ip
        ip = get_client_ip(request)
        if ip:
            return ip
    except Exception:  # noqa: BLE001
        pass
    return get_remote_address(request)


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
    return _remote_address(request)


limiter = Limiter(
    key_func=_remote_address,
    enabled=_RL_ENABLED,
)


org_limiter = Limiter(
    key_func=_org_key,
    enabled=_RL_ENABLED,
)
