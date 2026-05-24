"""Tests for agents.runtime.artifact_store — file-based agent handoff."""

from __future__ import annotations


def test_write_and_read_artifact(isolated_artifact_root):
    from agents.runtime.artifact_store import read_artifact, write_artifact

    artifact = write_artifact(
        project_id="proj-x",
        agent_code="bmad-agent-analyst",
        skill="bmad-product-brief",
        filename="product-brief",
        body="# Hello\nMary's brief.",
        frontmatter={"summary": "test"},
    )
    assert artifact.path.is_file()
    rt = read_artifact(artifact.path)
    assert rt.frontmatter["summary"] == "test"
    assert rt.frontmatter["agent"] == "bmad-agent-analyst"
    assert "Mary's brief." in rt.body


def test_latest_index_resolves_most_recent(isolated_artifact_root):
    import time

    from agents.runtime.artifact_store import read_latest, write_artifact

    write_artifact(
        project_id="proj-y",
        agent_code="bmad-agent-pm",
        skill="bmad-create-prd",
        filename="prd",
        body="v1",
    )
    time.sleep(1)  # ensure different timestamp slug
    write_artifact(
        project_id="proj-y",
        agent_code="bmad-agent-pm",
        skill="bmad-create-prd",
        filename="prd",
        body="v2 latest",
    )
    latest = read_latest("proj-y", "bmad-agent-pm", "prd")
    assert latest is not None
    assert "v2 latest" in latest.body


def test_list_artifacts_filters_by_agent(isolated_artifact_root):
    from agents.runtime.artifact_store import list_artifacts, write_artifact

    write_artifact(
        project_id="proj-z",
        agent_code="bmad-agent-analyst",
        skill="bmad-product-brief",
        filename="brief",
        body="A",
    )
    write_artifact(
        project_id="proj-z",
        agent_code="bmad-agent-pm",
        skill="bmad-create-prd",
        filename="prd",
        body="B",
    )
    pm_only = list_artifacts("proj-z", agent_code="bmad-agent-pm")
    assert len(pm_only) == 1
    assert pm_only[0].agent_code == "bmad-agent-pm"

    all_artifacts = list_artifacts("proj-z")
    assert len(all_artifacts) == 2


def test_collect_prior_context_returns_summary_dicts(isolated_artifact_root):
    from agents.runtime.artifact_store import collect_prior_context, write_artifact

    write_artifact(
        project_id="proj-c",
        agent_code="bmad-agent-analyst",
        skill="bmad-product-brief",
        filename="brief",
        body="Mary's brief body",
    )
    ctx = collect_prior_context("proj-c", upstream_agents=["bmad-agent-analyst"])
    assert len(ctx) == 1
    assert ctx[0]["agent"] == "bmad-agent-analyst"
    assert "Mary's brief body" in ctx[0]["body"]
