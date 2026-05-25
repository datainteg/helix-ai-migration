"""Server-side request forgery (SSRF) protection.

Used by webhook registration + delivery to reject URLs that point at internal
infrastructure (loopback, RFC1918, link-local, cloud metadata services).

Apply at BOTH boundaries:
  - admit-time (create/update): rejects obvious attacks early
  - send-time (delivery): re-checks because stored DB rows may be poisoned later
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from app.core.config import settings


class SSRFViolation(ValueError):
    """Raised when a URL targets a forbidden network range."""


# Cloud-provider instance metadata endpoints. These are link-local already and
# would be caught by the RFC range check, but listed explicitly for clarity in
# error messages and because some providers expose them on routable hosts.
_FORBIDDEN_HOSTS = {
    "metadata.google.internal",
    "metadata",
    "169.254.169.254",
    "fd00:ec2::254",
}

_ALLOWED_SCHEMES = ("https",)
# Allow http only in non-prod to support local webhook testing.
_DEV_ALLOWED_SCHEMES = ("http", "https")


def _is_forbidden_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        ip.is_loopback
        or ip.is_link_local
        or ip.is_private
        or ip.is_multicast
        or ip.is_unspecified
        or ip.is_reserved
    )


def validate_external_url(url: str) -> None:
    """Raise SSRFViolation if `url` is unsafe to fetch.

    Checks: scheme allowlist, host present, DNS resolves to only public IPs,
    explicit metadata-host denylist.
    """
    if not url or not isinstance(url, str):
        raise SSRFViolation("URL must be a non-empty string")

    parsed = urlparse(url)
    allowed = _DEV_ALLOWED_SCHEMES if settings.APP_ENV != "production" else _ALLOWED_SCHEMES
    if parsed.scheme.lower() not in allowed:
        raise SSRFViolation(f"Scheme must be one of {allowed}, got {parsed.scheme!r}")

    host = (parsed.hostname or "").lower()
    if not host:
        raise SSRFViolation("URL must include a host")
    if host in _FORBIDDEN_HOSTS:
        raise SSRFViolation(f"Host {host!r} is on the SSRF denylist")

    # Resolve every A/AAAA record. Reject if any address is private/loopback.
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise SSRFViolation(f"Host {host!r} did not resolve: {exc}") from exc

    seen: set[str] = set()
    for info in infos:
        addr = info[4][0]
        if addr in seen:
            continue
        seen.add(addr)
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if _is_forbidden_ip(ip):
            raise SSRFViolation(f"Host {host!r} resolves to forbidden address {addr}")
