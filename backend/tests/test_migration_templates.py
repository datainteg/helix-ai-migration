"""Migration template tests — catalog + clone."""

import uuid


def _admin_token(client):
    res = client.post("/api/v1/auth/first-admin", json={
        "email": "tpl@example.com",
        "name": "Template Admin",
        "password": "TplPass1234!",
        "organization_name": "Tpl Org",
        "organization_slug": f"tpl-{uuid.uuid4().hex[:8]}",
    })
    return res.json()["access_token"]


def test_list_templates_requires_auth(client):
    res = client.get("/api/v1/migration-templates")
    assert res.status_code in (401, 403)


def test_list_templates_returns_known(client):
    token = _admin_token(client)
    res = client.get("/api/v1/migration-templates", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    ids = {t["id"] for t in res.json()}
    assert "oracle-to-snowflake" in ids
    assert "sas-to-databricks" in ids
    assert "sqlserver-to-postgres" in ids


def test_get_template_404(client):
    token = _admin_token(client)
    res = client.get(
        "/api/v1/migration-templates/does-not-exist",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 404


def test_clone_creates_project_and_rules(client):
    token = _admin_token(client)
    res = client.post(
        "/api/v1/migration-templates/clone",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "template_id": "oracle-to-snowflake",
            "project_name": "ORA→SNOW pilot",
        },
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["project_id"]
    assert isinstance(body["validation_rule_ids"], list) and len(body["validation_rule_ids"]) >= 1
    # Agent prompt overrides come back so frontend can pass them into planning.
    assert "architect" in body["agent_prompts"]
