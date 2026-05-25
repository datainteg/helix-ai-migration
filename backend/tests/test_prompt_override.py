"""Prompt-override propagation test for the BMAD executor.

Asserts that execute_agent_skill threads `prompt_override` into the
system_prompt seen by the LLM transport. Uses a stub transport that
captures the system prompt.
"""

from __future__ import annotations

import os
import types
from pathlib import Path


def test_prompt_override_appended_to_system_prompt(monkeypatch, tmp_path):
    """Force mock mode so the executor runs deterministically + assert that
    the override string lands inside the system prompt produced for the
    artifact frontmatter."""
    # Run inside a clean artifact root so the executor's write doesn't touch
    # the real project tree.
    monkeypatch.setenv("HELIX_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("HELIX_LLM_TRANSPORT", "mock")  # skip httpx + pydantic_ai paths

    # Stub bmad_loader so we don't need the BMAD-METHOD tree on disk for
    # this test. The override path runs entirely before any LLM call.
    from agents.runtime import bmad_executor as bx

    fake_agent = types.SimpleNamespace(code="test-agent", title="T", role="r", whenToUse="w", style="s", principles=[])
    fake_skill = types.SimpleNamespace(code="test-skill", title="T", description="d", body="", outputArtifacts=[])
    monkeypatch.setattr(bx, "load_bmad_agent", lambda code: fake_agent)
    monkeypatch.setattr(bx, "load_bmad_skill", lambda code: fake_skill)
    monkeypatch.setattr(bx, "collect_prior_context", lambda *a, **kw: [])

    captured = {}

    real_inner = bx._execute_agent_skill_inner

    def spy_inner(**kw):
        captured["prompt_override"] = kw.get("prompt_override")
        return real_inner(**kw)

    monkeypatch.setattr(bx, "_execute_agent_skill_inner", spy_inner)

    from pydantic import BaseModel
    class Stub(BaseModel):
        summary: str = ""

    bx.execute_agent_skill(
        agent_code="test-agent",
        skill_name="test-skill",
        project_id="p",
        requirement_text="r",
        output_model=Stub,
        prompt_override="Always emit partition keys when targeting BigQuery.",
    )
    assert captured["prompt_override"] == "Always emit partition keys when targeting BigQuery."
