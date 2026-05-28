"""SC-051: trustworthy client-IP resolution behind a reverse proxy.

Behind Caddy/nginx, `request.client.host` is always the proxy's loopback /
bridge IP, so the audit trail and slowapi's per-IP rate limiter both lose the
real caller. Naively trusting `X-Forwarded-For` is worse — any client can
forge it. The correct behaviour is to trust the header ONLY when the immediate
peer (`request.client.host`) is a configured trusted proxy, and then take the
*rightmost* entry that is not itself a trusted proxy (the address the trusted
proxy actually observed).

Configuration is via `settings.TRUSTED_PROXIES` (comma-separated):
  * empty               → never trust XFF; use request.client.host verbatim.
  * "*"                 → trust a single proxy hop (use when only the proxy
                          can reach the backend, e.g. a closed bridge net).
  * "10.0.0.5,10.0.0.6" → trust XFF only when the peer is one of these.
"""

from __future__ import annotations

from functools import lru_cache

from app.core.config import settings


@lru_cache(maxsize=1)
def _trusted_set() -> tuple[frozenset[str], bool]:
    raw = (settings.TRUSTED_PROXIES or "").strip()
    if not raw:
        return frozenset(), False
    if raw == "*":
        return frozenset(), True
    entries = {p.strip() for p in raw.split(",") if p.strip()}
    return frozenset(entries), False


def _is_trusted(ip: str | None) -> bool:
    if not ip:
        return False
    trusted, wildcard = _trusted_set()
    if wildcard:
        return True
    return ip in trusted


def get_client_ip(request) -> str | None:
    """Resolve the real client IP for `request`.

    When the immediate peer is a trusted proxy, walk `X-Forwarded-For` from
    the right and return the first address that is NOT itself trusted — that
    is the address the trusted proxy observed. Falls back to
    `request.client.host` when there is no trustworthy header.
    """
    if request is None:
        return None
    peer = request.client.host if request.client else None
    if not _is_trusted(peer):
        # The immediate connection is not a trusted proxy; never trust XFF.
        return peer
    try:
        xff = request.headers.get("X-Forwarded-For", "")
    except Exception:  # noqa: BLE001 — defensive on exotic ASGI scopes
        xff = ""
    if not xff:
        return peer
    # Rightmost-trusted parse: the chain is "client, proxy1, proxy2"; the
    # rightmost entry was added by the proxy nearest us. Skip trusted hops.
    parts = [p.strip() for p in xff.split(",") if p.strip()]
    for candidate in reversed(parts):
        if not _is_trusted(candidate):
            return candidate
    # Every entry was a trusted proxy → fall back to the leftmost.
    return parts[0] if parts else peer
