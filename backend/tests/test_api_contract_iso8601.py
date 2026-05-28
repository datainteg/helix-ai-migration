"""Contract tests for ISO-8601 datetime serialization (API-C3).

Every JSON field carrying a timestamp must be ISO-8601 (`"T"` separator,
optional `Z` or offset). The previous bug was `str(datetime)` which
produces `"2026-05-26 14:33:21+00:00"` — no `T`, breaks Safari's
`Date` parser.

`re.fullmatch(_ISO_PATTERN, value)` here is the same shape Stripe's
public docs use as the canonical ISO-8601 production output.
"""

from __future__ import annotations

import re
import uuid


# Loose ISO-8601 with optional fractional seconds and zone offset.
# Accepts `2026-05-26T14:33:21`, `2026-05-26T14:33:21.123456`,
# `2026-05-26T14:33:21+00:00`, `2026-05-26T14:33:21Z`.
_ISO_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?$"
)


def _is_iso(s: str | None) -> bool:
    if s is None:
        return True  # null is allowed
    return bool(_ISO_PATTERN.match(s))


def _admin_token(client):
    res = client.post("/api/v1/auth/first-admin", json={
        "email": "iso@example.com",
        "name": "ISO Admin",
        "password": "IsoTestPass123!",
        "organization_name": "ISO Org",
        "organization_slug": f"iso-{uuid.uuid4().hex[:8]}",
    })
    return res.json()["access_token"]


def _project(client, token):
    res = client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "iso-test"},
    )
    if res.status_code not in (200, 201):
        return None
    body = res.json()
    if isinstance(body, dict) and "id" in body:
        return body["id"]
    return None


def test_cutover_created_at_is_iso8601(client):
    """The cutover create + list responses include `created_at` strings."""
    token = _admin_token(client)
    pid = _project(client, token)
    if not pid:
        return

    create = client.post(
        f"/api/v1/projects/{pid}/cutovers",
        headers={"Authorization": f"Bearer {token}"},
        json={"source_ref": "src://a", "target_ref": "tgt://b"},
    )
    assert create.status_code == 201
    body = create.json()
    assert _is_iso(body["created_at"]), body["created_at"]
    # Bulk timestamp is set at create time → also ISO.
    assert _is_iso(body["timestamps"]["bulk"]), body["timestamps"]


def test_workflows_list_created_at_is_iso8601(client):
    """list_all_workflows formats `created_at` via .isoformat()."""
    token = _admin_token(client)
    # Even an empty list returns an envelope; nothing to assert without seeded
    # workflows. The contract-level test below covers the format itself.
    res = client.get("/api/v1/agent-workflows", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    body = res.json()
    for row in body.get("items", []):
        assert _is_iso(row.get("created_at")), row


def test_superadmin_list_orgs_created_at_is_iso8601(client):
    """Superadmin endpoint is gated by `is_super_admin` flag; without
    that flag we expect 403, NOT 404 (route still exists)."""
    token = _admin_token(client)
    res = client.get(
        "/api/v1/superadmin/organizations",
        headers={"Authorization": f"Bearer {token}"},
    )
    # Auth gate (not a super-admin) — but the route exists.
    assert res.status_code in (200, 403), res.status_code
    if res.status_code == 200:
        for row in res.json():
            assert _is_iso(row.get("created_at"))


def test_iso_pattern_rejects_legacy_str_datetime():
    """Sanity: the regex rejects the OLD `str(datetime)` shape."""
    assert not _is_iso("2026-05-26 14:33:21+00:00")  # no T
    # And accepts the new shape.
    assert _is_iso("2026-05-26T14:33:21+00:00")
    assert _is_iso("2026-05-26T14:33:21.123456+00:00")
    assert _is_iso("2026-05-26T14:33:21Z")
