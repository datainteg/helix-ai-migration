from agents.bmad.graph import build_bmad_graph, run_bmad_graph


def test_bmad_langgraph_returns_structured_outputs():
    graph = build_bmad_graph()
    assert graph is not None

    result = run_bmad_graph(
        project_id="project-1",
        requirement_id="requirement-1",
        organization_id="org-1",
        requirement_text="Migrate CRM data from Oracle to Snowflake",
    )

    assert result["status"] == "completed"
    assert result["current_agent"] == "approval_gate"
    assert result["approval_required"] is True
    assert result["errors"] == []
    assert set(result["outputs"]) == {"business_analyst", "architect", "validation_planner", "approval_gate"}
    assert "Mary (Business Analyst)" in result["outputs"]["business_analyst"]["summary"]
    assert "Winston (System Architect)" in result["outputs"]["architect"]["architecture_summary"]
    assert result["final_output"]["status"] == "completed"


def test_workflow_flow(client):
    """BMAD workflow test with LangGraph-backed wrapper."""

    client.post("/api/v1/auth/first-admin", json={
        "email": "w@t.com", "name": "W", "password": "Test123!",
        "organization_name": "O", "organization_slug": "o",
    })
    login = client.post("/api/v1/auth/login", json={"email": "w@t.com", "password": "Test123!"})
    token = login.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}

    resp = client.post("/api/v1/projects", json={"name": "WF Project"}, headers=h)
    pid = resp.json()["id"]
    resp = client.post(f"/api/v1/projects/{pid}/requirements", json={"source_text": "Migrate X to Y"}, headers=h)
    rid = resp.json()["id"]

    resp = client.post(f"/api/v1/projects/{pid}/agent-workflows", json={"requirement_id": rid}, headers=h)
    assert resp.status_code == 200
    wf = resp.json()["workflow"]
    assert wf["status"] == "completed"
    assert wf["approval_required"] is True
    assert set(wf["outputs"]) == {"business_analyst", "architect", "validation_planner", "approval_gate"}

    resp = client.post(
        "/api/v1/agent-workflows/test-wf-id/approve",
        json={"decision": "approved", "notes": "Looks good"},
        headers=h,
    )
    assert resp.status_code == 200
