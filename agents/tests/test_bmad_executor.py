"""Tests for agents.runtime.bmad_executor — the agent+skill runner."""

from __future__ import annotations


def test_execute_agent_skill_mock_path_produces_artifact(isolated_artifact_root):
    from agents.bmad.schemas import AnalystOutput
    from agents.runtime.bmad_executor import execute_agent_skill

    result = execute_agent_skill(
        agent_code="bmad-agent-analyst",
        skill_name="bmad-product-brief",
        project_id="exec-test-1",
        requirement_text="Migrate CRM to Snowflake",
        output_model=AnalystOutput,
        upstream_agents=[],
        org_id=None,
    )
    assert result.success
    assert result.mode == "mock"
    assert result.artifact is not None
    assert result.artifact.path.is_file()
    assert isinstance(result.parsed, AnalystOutput)


def test_executor_passes_prior_context(isolated_artifact_root):
    """Downstream agent run should see upstream agent's artifact in its context list."""
    from agents.bmad.schemas import AnalystOutput, PMOutput
    from agents.runtime.artifact_store import collect_prior_context
    from agents.runtime.bmad_executor import execute_agent_skill

    # Mary first
    r1 = execute_agent_skill(
        agent_code="bmad-agent-analyst",
        skill_name="bmad-product-brief",
        project_id="chain-1",
        requirement_text="Test handoff",
        output_model=AnalystOutput,
    )
    assert r1.success

    # John runs second; verify his upstream context picks up Mary's artifact.
    ctx = collect_prior_context("chain-1", upstream_agents=["bmad-agent-analyst"])
    assert any(c["agent"] == "bmad-agent-analyst" for c in ctx)

    r2 = execute_agent_skill(
        agent_code="bmad-agent-pm",
        skill_name="bmad-create-prd",
        project_id="chain-1",
        requirement_text="Test handoff",
        output_model=PMOutput,
        upstream_agents=["bmad-agent-analyst"],
    )
    assert r2.success
    assert r2.artifact is not None
