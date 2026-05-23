from pathlib import Path

from agents.bmad.graph import build_bmad_graph, run_bmad_graph
from agents.bmad.official_agents import get_official_agent_metadata, load_official_bmad_agent


def test_bmad_agent_metadata_uses_official_named_agents():
    analyst = get_official_agent_metadata("business_analyst")
    architect = get_official_agent_metadata("architect")

    assert analyst["name"] == "Mary"
    assert analyst["title"] == "Business Analyst"
    assert analyst["command"] == "bmad-analyst"
    assert analyst["skill_id"] == "bmad-agent-analyst"
    assert analyst["skill_path"] == "src/bmm-skills/1-analysis/bmad-agent-analyst/SKILL.md"
    assert analyst["source"] == "official_bmad_skill"
    assert Path(analyst["resolved_skill_path"]).is_file()
    assert Path(analyst["resolved_customize_path"]).is_file()
    assert Path(analyst["bmad_root"]).name == "BMAD-METHOD"

    assert architect["name"] == "Winston"
    assert architect["title"] == "System Architect"
    assert architect["command"] == "bmad-architect"
    assert architect["skill_id"] == "bmad-agent-architect"
    assert architect["skill_path"] == "src/bmm-skills/3-solutioning/bmad-agent-architect/SKILL.md"
    assert architect["source"] == "official_bmad_skill"
    assert Path(architect["resolved_skill_path"]).is_file()
    assert Path(architect["resolved_customize_path"]).is_file()
    assert Path(architect["bmad_root"]).name == "BMAD-METHOD"


def test_bmad_agent_metadata_can_load_official_skill_files(tmp_path: Path):
    skill_dir = tmp_path / "src" / "bmm-skills" / "1-analysis" / "bmad-agent-analyst"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\ndescription: Strategic business analyst and requirements expert.\n---\n# Mary - Business Analyst\n",
        encoding="utf-8",
    )
    (skill_dir / "customize.toml").write_text(
        '[agent]\nname = "Mary"\ntitle = "Business Analyst"\n',
        encoding="utf-8",
    )

    metadata = load_official_bmad_agent("business_analyst", tmp_path)

    assert metadata.source == "official_bmad_skill"
    assert metadata.name == "Mary"
    assert metadata.title == "Business Analyst"
    assert metadata.description == "Strategic business analyst and requirements expert."


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
    data = resp.json()
    assert data["mode"] == "local_fallback"
    assert data["status"] == "completed"
    wf = data["result"]
    assert wf["status"] == "completed"
    assert wf["approval_required"] is True
    assert set(wf["outputs"]) == {"business_analyst", "architect", "validation_planner", "approval_gate"}

    resp = client.post(
        "/api/v1/agent-workflows/test-wf-id/approve",
        json={"decision": "approved", "notes": "Looks good"},
        headers=h,
    )
    assert resp.status_code == 200
