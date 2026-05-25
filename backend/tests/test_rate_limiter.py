"""Per-org rate limiter unit tests.

The Limiter is enabled only when APP_ENV == production, so we test the
key_func in isolation rather than triggering an enforced 429.
"""

from fastapi import Request


class _FakeScope:
    def __init__(self, headers: list[tuple[bytes, bytes]], client: tuple[str, int] | None = ("203.0.113.1", 51234)) -> None:
        self.scope = {
            "type": "http",
            "headers": headers,
            "client": client,
            "method": "GET",
            "path": "/x",
        }


def _make_request(*, org_id: str | None = None, auth: str | None = None, client_ip: str | None = "203.0.113.1") -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if org_id is not None:
        headers.append((b"x-active-org-id", org_id.encode()))
    if auth is not None:
        headers.append((b"authorization", auth.encode()))
    scope = {
        "type": "http",
        "headers": headers,
        "client": (client_ip, 51234) if client_ip else None,
        "method": "GET",
        "path": "/x",
        "query_string": b"",
        "server": ("testserver", 80),
        "scheme": "http",
    }
    return Request(scope)


def test_key_uses_org_header_when_present():
    from app.rate_limiting import _org_key
    req = _make_request(org_id="org-123")
    assert _org_key(req) == "org:org-123"


def test_key_falls_back_to_jwt_tail():
    from app.rate_limiting import _org_key
    req = _make_request(auth="Bearer abcdef1234567890ABCDEF")
    key = _org_key(req)
    assert key.startswith("user:")


def test_key_falls_back_to_ip():
    from app.rate_limiting import _org_key
    req = _make_request(client_ip="203.0.113.99")
    assert _org_key(req) == "203.0.113.99"
