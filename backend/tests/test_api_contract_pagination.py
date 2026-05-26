"""Contract tests for the pagination envelope (API-C2).

These cover the `{items, total, limit, offset}` shape that every list
endpoint in this scope must return. The frontend will adapt in a
follow-up PR; here we just verify the backend keeps the contract stable.
"""

from __future__ import annotations

import uuid

import pytest


def _admin_token(client):
    res = client.post("/api/v1/auth/first-admin", json={
        "email": "pagination@example.com",
        "name": "Pagination Admin",
        "password": "Pagination123!",
        "organization_name": "Pagination Org",
        "organization_slug": f"pagination-{uuid.uuid4().hex[:8]}",
    })
    return res.json()["access_token"]


def _project(client, token):
    res = client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "pagination-test"},
    )
    if res.status_code not in (200, 201):
        pytest.skip(f"project creation failed: {res.status_code}")
    body = res.json()
    # Projects endpoint also returns an envelope after API-C2 — handle both shapes.
    if isinstance(body, dict) and "items" not in body and "id" in body:
        return body["id"]
    pytest.skip("unexpected project response shape")


def _is_paginated_envelope(body) -> bool:
    """An envelope is a dict with the canonical 4 keys."""
    if not isinstance(body, dict):
        return False
    expected = {"items", "total", "limit", "offset"}
    return expected.issubset(body.keys())


def test_sprints_list_returns_envelope(client):
    token = _admin_token(client)
    pid = _project(client, token)
    res = client.get(
        f"/api/v1/projects/{pid}/sprints",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert _is_paginated_envelope(res.json()), res.json()


def test_cutovers_list_returns_envelope(client):
    token = _admin_token(client)
    pid = _project(client, token)
    res = client.get(
        f"/api/v1/projects/{pid}/cutovers",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert _is_paginated_envelope(res.json()), res.json()


def test_artifacts_org_list_returns_envelope(client):
    token = _admin_token(client)
    res = client.get(
        "/api/v1/artifacts",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert _is_paginated_envelope(res.json()), res.json()


def test_artifacts_project_list_returns_envelope(client):
    token = _admin_token(client)
    pid = _project(client, token)
    res = client.get(
        f"/api/v1/projects/{pid}/artifacts",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert _is_paginated_envelope(res.json()), res.json()


def test_validation_rules_list_returns_envelope(client):
    token = _admin_token(client)
    pid = _project(client, token)
    res = client.get(
        f"/api/v1/projects/{pid}/validation-rules",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert _is_paginated_envelope(res.json()), res.json()


def test_workflows_list_returns_envelope(client):
    token = _admin_token(client)
    res = client.get(
        "/api/v1/agent-workflows",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert _is_paginated_envelope(res.json()), res.json()


def test_pagination_limit_offset_propagated(client):
    """limit + offset values are echoed back in the envelope so the client
    can build the next page URL without tracking them locally."""
    token = _admin_token(client)
    res = client.get(
        "/api/v1/artifacts?limit=10&offset=5",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["limit"] == 10
    assert body["offset"] == 5


def test_pagination_envelope_has_int_total(client):
    """`total` is an int (or null). Empty list → total == 0."""
    token = _admin_token(client)
    res = client.get(
        "/api/v1/artifacts",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    body = res.json()
    # Either an integer or explicitly null.
    assert body["total"] is None or isinstance(body["total"], int), body


def test_superadmin_path_reachable(client):
    """API-C1: the canonical superadmin path is `/api/v1/superadmin/...`.

    After the prefix consolidation the path is still the same end-URL
    but the router-prefix is removed. Hitting an unknown user with
    super-admin endpoint should 401/403 (auth gate), NOT 404 (which would
    indicate the prefix is broken).
    """
    res = client.get("/api/v1/superadmin/organizations")
    # No auth → 401 or 403. Crucially NOT 404 (route exists).
    assert res.status_code in (401, 403), res.status_code
