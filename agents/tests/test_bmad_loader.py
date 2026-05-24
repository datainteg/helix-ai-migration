"""Tests for agents.runtime.bmad_loader — config + agent + skill resolution."""

from __future__ import annotations

import pytest


def test_load_bmad_config_returns_project_name():
    from agents.runtime.bmad_loader import load_bmad_config, clear_cache

    clear_cache()
    cfg = load_bmad_config()
    assert cfg.project_name  # at minimum the installer-generated default
    assert cfg.planning_artifacts.endswith("planning-artifacts")
    assert cfg.implementation_artifacts.endswith("implementation-artifacts")


def test_load_bmad_agent_mary():
    from agents.runtime.bmad_loader import load_bmad_agent

    agent = load_bmad_agent("bmad-agent-analyst")
    assert agent.name == "Mary"
    assert agent.title == "Business Analyst"
    assert agent.phase == "Analysis"
    assert agent.skill_md  # SKILL.md content loaded
    assert agent.principles, "Mary should have at least one principle from customize.toml"
    assert agent.menu, "Mary should have menu items"


def test_load_bmad_agent_winston():
    from agents.runtime.bmad_loader import load_bmad_agent

    agent = load_bmad_agent("bmad-agent-architect")
    assert agent.name == "Winston"
    assert agent.title == "System Architect"
    assert agent.phase == "Solutioning"


def test_load_bmad_agent_missing_raises():
    from agents.runtime.bmad_loader import load_bmad_agent

    with pytest.raises(FileNotFoundError):
        load_bmad_agent("bmad-agent-doesnotexist")


def test_load_bmad_skill_product_brief():
    from agents.runtime.bmad_loader import load_bmad_skill

    skill = load_bmad_skill("bmad-product-brief")
    assert skill.phase == "1-analysis"
    assert skill.skill_md, "SKILL.md content should be non-empty"


def test_build_persona_prompt_contains_persona_layers():
    from agents.runtime.bmad_loader import build_persona_prompt, load_bmad_agent

    agent = load_bmad_agent("bmad-agent-analyst")
    prompt = build_persona_prompt(agent)
    assert "Mary" in prompt
    assert "Business Analyst" in prompt
    assert "Principles" in prompt or any(p in prompt for p in agent.principles)


def test_build_skill_instructions_strips_frontmatter():
    from agents.runtime.bmad_loader import build_skill_instructions, load_bmad_skill

    skill = load_bmad_skill("bmad-product-brief")
    body = build_skill_instructions(skill)
    assert not body.startswith("---"), "frontmatter should be stripped"


def test_all_six_official_agents_load():
    """Smoke test: every agent declared in _bmad/config.toml must load."""
    from agents.runtime.bmad_loader import load_bmad_agent

    codes = [
        "bmad-agent-analyst",
        "bmad-agent-tech-writer",
        "bmad-agent-pm",
        "bmad-agent-ux-designer",
        "bmad-agent-architect",
        "bmad-agent-dev",
    ]
    for code in codes:
        agent = load_bmad_agent(code)
        assert agent.name
        assert agent.title
        assert agent.skill_md
