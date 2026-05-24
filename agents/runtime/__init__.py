"""Agent runtime — BMAD loader, artifact store, executor, LLM transports."""

from agents.runtime.artifact_store import (
    Artifact,
    collect_prior_context,
    list_artifacts,
    planning_root_for_project,
    read_artifact,
    read_latest,
    write_artifact,
)
from agents.runtime.bmad_executor import AgentRunResult, execute_agent_skill
from agents.runtime.bmad_loader import (
    BMADAgent,
    BMADConfig,
    BMADSkill,
    bmad_install_dir,
    bmad_method_root,
    build_persona_prompt,
    build_skill_instructions,
    load_bmad_agent,
    load_bmad_config,
    load_bmad_skill,
    project_root,
)
from agents.runtime.llm_client import call_llm
from agents.runtime.pydantic_ai_client import call_pydantic_ai, is_available as pydantic_ai_available
from agents.runtime.structured_output import safe_extract_json

__all__ = [
    # BMAD core
    "Artifact",
    "BMADAgent",
    "BMADConfig",
    "BMADSkill",
    "AgentRunResult",
    "bmad_install_dir",
    "bmad_method_root",
    "build_persona_prompt",
    "build_skill_instructions",
    "collect_prior_context",
    "execute_agent_skill",
    "list_artifacts",
    "load_bmad_agent",
    "load_bmad_config",
    "load_bmad_skill",
    "planning_root_for_project",
    "project_root",
    "read_artifact",
    "read_latest",
    "write_artifact",
    # LLM transports
    "call_llm",
    "call_pydantic_ai",
    "pydantic_ai_available",
    # JSON utilities
    "safe_extract_json",
]
