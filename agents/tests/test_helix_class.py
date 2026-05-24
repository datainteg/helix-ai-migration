"""Tests for the HelixBMAD class facade."""

from __future__ import annotations

import pytest


def test_helix_class_imports_at_top_level():
    """`from agents import HelixBMAD` must work — single canonical import."""
    from agents import HelixBMAD, HelixBMADResult  # noqa: F401


def test_helix_requires_project_id():
    from agents import HelixBMAD

    with pytest.raises(ValueError):
        HelixBMAD(project_id="", requirement_id="r1", requirement_text="x")


def test_helix_requires_requirement_id():
    from agents import HelixBMAD

    with pytest.raises(ValueError):
        HelixBMAD(project_id="p1", requirement_id="", requirement_text="x")


def test_helix_workflow_id_format():
    from agents import HelixBMAD

    helix = HelixBMAD(project_id="proj-1", requirement_id="req-1", requirement_text="test")
    assert helix.workflow_id == "bmad-proj-1-req-1"


def test_helix_run_pending_when_no_approval(isolated_artifact_root):
    from agents import HelixBMAD

    result = HelixBMAD(
        project_id="helix-pending",
        requirement_id="r1",
        requirement_text="Migrate CRM to Snowflake",
    ).run()

    assert result.status == "pending"
    assert result.mode == "local"
    assert result.workflow_id == "bmad-helix-pending-r1"
    assert "approval_gate" in result.outputs
    assert "dev" not in result.outputs


def test_helix_run_completed_when_approved(isolated_artifact_root):
    from agents import HelixBMAD

    result = HelixBMAD(
        project_id="helix-approved",
        requirement_id="r2",
        requirement_text="Migrate Oracle to Databricks",
        approval_decision="approved",
    ).run()

    assert result.status == "completed"
    assert {"project_context", "analyst", "dev", "tech_writer"}.issubset(result.outputs)


def test_helix_list_artifacts_returns_summaries(isolated_artifact_root):
    from agents import HelixBMAD

    helix = HelixBMAD(
        project_id="helix-arts",
        requirement_id="r3",
        requirement_text="Migrate",
        approval_decision="approved",
    )
    helix.run()
    arts = helix.list_artifacts()
    assert len(arts) > 0
    assert all("agent" in a and "skill" in a and "body" in a for a in arts)


def test_helix_get_artifact_returns_latest_for_agent(isolated_artifact_root):
    from agents import HelixBMAD

    helix = HelixBMAD(
        project_id="helix-latest",
        requirement_id="r4",
        requirement_text="Migrate",
        approval_decision="approved",
    )
    helix.run()
    mary_art = helix.get_artifact("bmad-agent-analyst")
    assert mary_art is not None
    assert mary_art["agent"] == "bmad-agent-analyst"


def test_helix_to_dict_round_trip(isolated_artifact_root):
    from agents import HelixBMAD

    result = HelixBMAD(
        project_id="helix-dict",
        requirement_id="r5",
        requirement_text="Migrate",
    ).run()
    d = result.to_dict()
    assert d["workflow_id"] == result.workflow_id
    assert d["status"] == result.status
    assert isinstance(d["outputs"], dict)
    assert isinstance(d["artifact_paths"], dict)


def test_project_context_file_written_to_stable_path(isolated_artifact_root):
    """Phase 0 must mirror project-context.md to a glob-discoverable stable path."""
    from pathlib import Path

    from agents import HelixBMAD
    from agents.runtime.artifact_store import planning_root_for_project

    helix = HelixBMAD(
        project_id="helix-context",
        requirement_id="r6",
        requirement_text="Migrate",
        approval_decision="approved",
    )
    helix.run()

    root = planning_root_for_project("helix-context")
    stable = root / "project-context.md"
    assert stable.is_file(), f"missing stable project-context.md at {stable}"
    # Confirm it has BMAD frontmatter.
    text = stable.read_text(encoding="utf-8")
    assert text.startswith("---")
    assert "bmad-generate-project-context" in text
