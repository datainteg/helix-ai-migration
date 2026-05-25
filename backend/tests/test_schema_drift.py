"""Schema drift snapshot + diff tests."""

import uuid


def _admin_token(client):
    res = client.post("/api/v1/auth/first-admin", json={
        "email": "drift@example.com",
        "name": "Drift Admin",
        "password": "DriftPass123!",
        "organization_name": "Drift Org",
        "organization_slug": f"drift-{uuid.uuid4().hex[:8]}",
    })
    return res.json()["access_token"]


def _project(client, token):
    res = client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "drift-test"},
    )
    if res.status_code not in (200, 201):
        return None
    return res.json()["id"]


def _snapshot(client, token, project_id, source_ref, tables):
    return client.post(
        f"/api/v1/projects/{project_id}/sources/{source_ref}/schema-snapshots",
        headers={"Authorization": f"Bearer {token}"},
        json={"schemas": ["public"], "tables": tables},
    )


def test_drift_needs_two_snapshots(client):
    token = _admin_token(client)
    pid = _project(client, token)
    if not pid:
        return
    res = _snapshot(client, token, pid, "src", [
        {"schema_name": "public", "table_name": "users", "columns": [{"name": "id", "data_type": "int"}]}
    ])
    assert res.status_code == 201

    drift = client.get(
        f"/api/v1/projects/{pid}/sources/src/drift",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert drift.status_code == 200
    assert drift.json()["drift_detected"] is False


def test_drift_detects_added_table_and_type_change(client):
    token = _admin_token(client)
    pid = _project(client, token)
    if not pid:
        return

    # Baseline
    _snapshot(client, token, pid, "src", [
        {"schema_name": "public", "table_name": "users", "columns": [
            {"name": "id", "data_type": "int"},
            {"name": "email", "data_type": "varchar"},
        ]},
    ])
    # Latest: user.email type changed + new table 'orders'
    _snapshot(client, token, pid, "src", [
        {"schema_name": "public", "table_name": "users", "columns": [
            {"name": "id", "data_type": "int"},
            {"name": "email", "data_type": "text"},
        ]},
        {"schema_name": "public", "table_name": "orders", "columns": [
            {"name": "id", "data_type": "int"},
        ]},
    ])

    drift = client.get(
        f"/api/v1/projects/{pid}/sources/src/drift",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    assert drift["drift_detected"] is True
    assert "public.orders" in drift["added_tables"]
    type_changes = drift["column_changes"]
    found = any(
        chg.get("table") == "users" and any(t.get("column") == "email" for t in chg.get("type_changes", []))
        for chg in type_changes
    )
    assert found
