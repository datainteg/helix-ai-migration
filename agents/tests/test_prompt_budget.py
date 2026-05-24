"""Tests for the prompt-budget guard in bmad_executor."""

from __future__ import annotations

import os

import pytest


def test_truncate_smart_keeps_head_and_tail_under_limit():
    from agents.runtime.bmad_executor import _truncate_smart

    text = "HEAD_SECTION_" + ("X" * 5000) + "_TAIL_SECTION"
    truncated = _truncate_smart(text, max_chars=500, label="test body")

    assert len(truncated) <= 500 + 200  # truncation marker is ~80 chars
    assert "HEAD_SECTION" in truncated
    assert "TAIL_SECTION" in truncated
    assert "truncated" in truncated
    assert "test body" in truncated  # label included


def test_truncate_smart_passthrough_when_under_limit():
    from agents.runtime.bmad_executor import _truncate_smart

    text = "short content"
    assert _truncate_smart(text, max_chars=1000) == text


def test_truncate_smart_handles_zero_max():
    from agents.runtime.bmad_executor import _truncate_smart

    assert _truncate_smart("anything", max_chars=0) == ""


def test_estimate_tokens_uses_char_heuristic():
    from agents.runtime.bmad_executor import _estimate_tokens

    assert _estimate_tokens("") == 1            # min floor
    assert _estimate_tokens("abcd") == 1
    assert _estimate_tokens("a" * 400) == 100   # 400 / 4


def test_token_budget_respects_env(monkeypatch):
    from agents.runtime.bmad_executor import _token_budget

    monkeypatch.setenv("HELIX_PROMPT_TOKEN_BUDGET", "20000")
    assert _token_budget() == 20000

    monkeypatch.setenv("HELIX_PROMPT_TOKEN_BUDGET", "garbage")
    # Bad value falls back to default.
    assert _token_budget() == 6000

    monkeypatch.delenv("HELIX_PROMPT_TOKEN_BUDGET", raising=False)
    assert _token_budget() == 6000


def test_allocate_prompt_budget_no_upstream():
    from agents.runtime.bmad_executor import _allocate_prompt_budget

    skill, artifact = _allocate_prompt_budget(
        output_schema_chars=500,
        persona_chars=1000,
        skill_body_chars=20000,
        requirement_chars=300,
        upstream_count=0,
    )
    assert artifact == 0          # no upstream → no artifact budget
    assert skill > 0              # remaining budget goes to skill body


def test_allocate_prompt_budget_with_upstream():
    from agents.runtime.bmad_executor import _allocate_prompt_budget

    skill, artifact = _allocate_prompt_budget(
        output_schema_chars=500,
        persona_chars=1000,
        skill_body_chars=20000,
        requirement_chars=300,
        upstream_count=4,
    )
    assert skill > 0
    assert artifact > 0
    # Skill share and artifact bundle should roughly halve the slack.
    assert artifact >= 500        # min floor enforced


def test_allocate_prompt_budget_under_low_budget(monkeypatch):
    from agents.runtime.bmad_executor import _allocate_prompt_budget

    monkeypatch.setenv("HELIX_PROMPT_TOKEN_BUDGET", "2000")  # very tight
    skill, artifact = _allocate_prompt_budget(
        output_schema_chars=500,
        persona_chars=1000,
        skill_body_chars=20000,
        requirement_chars=300,
        upstream_count=4,
    )
    # Even under a tight budget the function shouldn't return zero.
    assert skill >= 500
    assert artifact >= 500


def test_executor_persists_token_metrics_in_frontmatter(isolated_artifact_root):
    """End-to-end: run an agent and verify the artifact frontmatter records
    prompt_tokens_estimate + prompt_token_budget."""
    from agents.bmad.schemas import AnalystOutput
    from agents.runtime.bmad_executor import execute_agent_skill

    result = execute_agent_skill(
        agent_code="bmad-agent-analyst",
        skill_name="bmad-product-brief",
        project_id="budget-test",
        requirement_text="Migrate CRM to Snowflake",
        output_model=AnalystOutput,
    )
    assert result.success
    assert result.artifact is not None
    front = result.artifact.frontmatter
    assert "prompt_tokens_estimate" in front
    assert "prompt_token_budget" in front
    assert isinstance(front["prompt_tokens_estimate"], int)
    assert front["prompt_tokens_estimate"] > 0


def test_executor_truncates_skill_when_budget_tight(isolated_artifact_root, monkeypatch):
    """Verify truncation kicks in when budget is artificially tight."""
    from agents.bmad.schemas import DevOutput
    from agents.runtime.bmad_executor import execute_agent_skill

    monkeypatch.setenv("HELIX_PROMPT_TOKEN_BUDGET", "2000")  # tight
    # bmad-dev-story SKILL.md is ~25K chars — under 2K-token budget it MUST truncate.
    result = execute_agent_skill(
        agent_code="bmad-agent-dev",
        skill_name="bmad-dev-story",
        project_id="budget-tight",
        requirement_text="Implement migration loader",
        output_model=DevOutput,
    )
    assert result.success
    # Token estimate should be under our budget × char ratio × 0.75 (prompt budget).
    budget_chars = 2000 * 4 * 0.75
    front = result.artifact.frontmatter
    assert front["prompt_tokens_estimate"] * 4 <= budget_chars + 5000  # +slack for fixed reservations
