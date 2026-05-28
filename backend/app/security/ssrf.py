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
    # SC-017: IPv4-mapped IPv6 (e.g. ::ffff:169.254.169.254) must be checked
    # against the embedded v4 address — the v6 wrapper itself is "global".
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return (
        ip.is_loopback
        or ip.is_link_local
        or ip.is_private
        or ip.is_multicast
        or ip.is_unspecified
        or ip.is_reserved
    )


def _parse_literal_ip(host: str):
    """SC-017: return an ip_address if `host` is a literal IP in any form.

    Handles:
      * dotted-quad / standard IPv6  (ipaddress.ip_address handles directly)
      * decimal-encoded IPv4         (e.g. "2852039166" → 169.254.169.254)
      * IPv6 with surrounding brackets — urlparse already strips them, but be
        defensive in case a raw value is passed through.

    Returns None when `host` is a DNS name (to be resolved by the caller).
    """
    if not host:
        return None
    candidate = host
    if candidate.startswith("[") and candidate.endswith("]"):
        candidate = candidate[1:-1]
    # Try the standard textual form first (covers dotted-quad + IPv6).
    try:
        return ipaddress.ip_address(candidate)
    except ValueError:
        pass
    # Purely-numeric host → treat as a 32-bit (or larger) integer IP.
    if candidate.isdigit():
        try:
            return ipaddress.ip_address(int(candidate))
        except (ValueError, ipaddress.AddressValueError):
            return None
    return None


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

    # SC-017: handle literal IPs BEFORE the DNS path. urlparse(...).hostname
    # returns the raw literal for `http://2852039166/` (decimal IMDS) and for
    # `http://[::1]/` (IPv6 brackets stripped to `::1`). getaddrinfo may or
    # may not normalise these, so we check them directly with no DNS step.
    literal_ip = _parse_literal_ip(host)
    if literal_ip is not None:
        if _is_forbidden_ip(literal_ip):
            raise SSRFViolation(
                f"Host {host!r} is a literal address in a forbidden range ({literal_ip})"
            )
        # Public literal IP — no hostname to resolve, admission passes.
        return

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
