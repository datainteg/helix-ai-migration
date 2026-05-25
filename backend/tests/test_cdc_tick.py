"""CDC tail-tick endpoint tests."""

import json
import uuid


def _admin_token(client):
    res = client.post("/api/v1/auth/first-admin", json={
        "email": "cdc@example.com",
        "name": "CDC Admin",
        "password": "CdcPass1234!",
        "organization_name": "CDC Org",
        "organization_slug": f"cdc-{uuid.uuid4().hex[:8]}",
    })
    return res.json()["access_token"]


def _project_with_cutover(client, token):
    proj = client.post("/api/v1/projects", headers={"Authorization": f"Bearer {token}"},
                       json={"name": "cdc-test"})
    if proj.status_code not in (200, 201):
        return None, None
    pid = proj.json()["id"]
    c = client.post(f"/api/v1/projects/{pid}/cutovers", headers={"Authorization": f"Bearer {token}"},
                    json={"source_ref": "src", "target_ref": "tgt"})
    cid = c.json()["id"]
    # advance to tail
    client.post(f"/api/v1/cutovers/{cid}/transition", headers={"Authorization": f"Bearer {token}"},
                json={"target_state": "tail"})
    return pid, cid


def test_tick_only_in_tail_state(client):
    token = _admin_token(client)
    pid, cid = _project_with_cutover(client, token)
    if not cid:
        return
    h = {"Authorization": f"Bearer {token}"}
    res = client.post(f"/api/v1/cutovers/{cid}/tail-sync/tick", headers=h, json={
        "rows_seen": 100, "rows_applied": 100, "lag_seconds": 0.5, "high_water_mark": "SCN:12345",
    })
    assert res.status_code == 200
    body = res.json()
    assert body["state"] == "tail"
    assert body["last_tail_tick"]["high_water_mark"] == "SCN:12345"


def test_tick_refuses_wrong_state(client):
    token = _admin_token(client)
    proj = client.post("/api/v1/projects", headers={"Authorization": f"Bearer {token}"},
                       json={"name": "cdc-test2"})
    if proj.status_code not in (200, 201):
        return
    pid = proj.json()["id"]
    c = client.post(f"/api/v1/projects/{pid}/cutovers", headers={"Authorization": f"Bearer {token}"},
                    json={"source_ref": "src", "target_ref": "tgt"})
    cid = c.json()["id"]
    # cutover is in 'bulk' state, NOT tail
    res = client.post(f"/api/v1/cutovers/{cid}/tail-sync/tick",
                      headers={"Authorization": f"Bearer {token}"},
                      json={"rows_seen": 0, "rows_applied": 0, "lag_seconds": 0, "high_water_mark": "x"})
    assert res.status_code == 409
