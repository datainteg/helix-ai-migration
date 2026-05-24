"""End-to-end tests for the BMAD LangGraph pipeline."""

from __future__ import annotations


def test_pending_when_no_approval(isolated_artifact_root):
    from agents.bmad.graph import run_bmad_graph

    result = run_bmad_graph(
        project_id="graph-pending",
        requirement_id="r1",
        requirement_text="Migrate CRM to Snowflake",
        approval_decision=None,
    )
    assert result["status"] == "pending"
    # Planning chain: project_context + analyst + pm + ux + arch + stories + readiness + approval_gate.
    assert set(result["outputs"]).issuperset(
        {
            "project_context",
            "analyst",
            "pm",
            "ux_designer",
            "architect",
            "architect_stories",
            "architect_readiness",
            "approval_gate",
        }
    )
    # Implementation nodes should not have run.
    assert "dev" not in result["outputs"]
    assert "dev_story" not in result["outputs"]


def test_completed_when_approved(isolated_artifact_root):
    from agents.bmad.graph import run_bmad_graph

    result = run_bmad_graph(
        project_id="graph-approved",
        requirement_id="r2",
        requirement_text="Migrate Oracle to Databricks",
        approval_decision="approved",
    )
    assert result["status"] == "completed"
    assert {"dev_story", "dev", "qa", "code_review", "tech_writer"}.issubset(result["outputs"])
    # Project context bootstrap should always run first.
    assert "project_context" in result["outputs"]


def test_rejected_path(isolated_artifact_root):
    from agents.bmad.graph import run_bmad_graph

    result = run_bmad_graph(
        project_id="graph-rejected",
        requirement_id="r3",
        requirement_text="Migrate SAS to Spark",
        approval_decision="rejected",
    )
    assert result["status"] == "rejected"
    # Approval gate output should reflect rejection routing.
    gate = result["outputs"]["approval_gate"]
    assert gate["next_step"] == "revise_planning"
    assert "dev" not in result["outputs"]


def test_artifacts_persisted_for_every_planning_agent(isolated_artifact_root):
    from agents.bmad.graph import run_bmad_graph

    result = run_bmad_graph(
        project_id="graph-artifacts",
        requirement_id="r4",
        requirement_text="Migrate MySQL ecom store to Postgres",
        approval_decision="approved",
    )
    paths = result["artifact_paths"]
    # 6 distinct producing agents (analyst, pm, ux, architect, dev, tech-writer)
    assert "bmad-agent-analyst" in paths
    assert "bmad-agent-pm" in paths
    assert "bmad-agent-architect" in paths
    assert "bmad-agent-dev" in paths
    assert "bmad-agent-tech-writer" in paths

    for agent_code, files in paths.items():
        for f in files:
            from pathlib import Path

            assert Path(f).is_file(), f"missing artifact: {f}"
