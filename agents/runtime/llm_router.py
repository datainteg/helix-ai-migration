"""LLM Router — selects provider/model per agent with mock-mode fallback.

Never exposes API keys. Logs provider/model used but not secrets.
"""

from __future__ import annotations

import logging
from typing import Any

from agents.runtime.types import LLMRouterResult

logger = logging.getLogger(__name__)

# ── Agent-to-model defaults (mock mode) ──────────────────────────────
_AGENT_DEFAULT_MODELS: dict[str, str] = {
    "business_analyst": "mock-gpt-4.1",
    "architect": "mock-claude-3-opus",
    "data_engineer": "mock-gpt-4.1",
    "qa_validation": "mock-gpt-4.1",
    "recon": "mock-claude-3-opus",
    "devops": "mock-gpt-4.1",
    "pm": "mock-claude-3-opus",
}


def _resolve_agent_routing(
    agent_name: str,
    agent_provider_id: str | None = None,
    agent_model: str | None = None,
) -> dict[str, Any]:
    """Resolve provider/model for an agent from mappings or defaults."""
    model = agent_model or _AGENT_DEFAULT_MODELS.get(agent_name, "mock-gpt-4.1")
    return {
        "provider_id": agent_provider_id,
        "model": model,
    }


def route_llm_call(
    *,
    agent_name: str,
    prompt: str,
    provider_id: str | None = None,
    model: str | None = None,
    mock_response: str | None = None,
) -> LLMRouterResult:
    """Route an LLM call for the given agent.

    In mock mode (no provider configured), returns the mock_response.
    When providers are wired, this will call the real LLM API.

    Args:
        agent_name: BMAD agent key (e.g. "business_analyst")
        prompt: The input prompt text
        provider_id: Optional provider ID from agent mapping
        model: Optional model override
        mock_response: Text to return in mock mode

    Returns:
        LLMRouterResult with raw_text, provider_name, model_name, agent_name, mode
    """
    routing = _resolve_agent_routing(agent_name, provider_id, model)
    resolved_model = routing["model"]

    if mock_response is not None:
        logger.info(
            "LLM router [mock] agent=%s model=%s prompt_len=%d",
            agent_name,
            resolved_model,
            len(prompt),
        )
        return LLMRouterResult(
            raw_text=mock_response,
            provider_name="mock",
            model_name=resolved_model,
            agent_name=agent_name,
            mode="mock",
            metadata={"prompt_len": len(prompt)},
        )

    # TODO: Wire real LLM provider calls here when providers are configured.
    # The routing dict will have provider_id pointing to a configured LLMProvider
    # with encrypted API key. Call build_llm_provider_adapter + test_connection
    # pattern once the backend service layer is importable from agents.

    logger.warning(
        "LLM router [mock-fallback] agent=%s model=%s — no mock_response provided, returning empty",
        agent_name,
        resolved_model,
    )
    return LLMRouterResult(
        raw_text="",
        provider_name="mock",
        model_name=resolved_model,
        agent_name=agent_name,
        mode="mock",
        metadata={"prompt_len": len(prompt)},
    )


def build_mock_agent_prompt(agent_name: str, requirement_text: str) -> str:
    """Build a mock prompt for an agent based on BMAD agent metadata."""
    from agents.bmad.official_agents import get_official_agent_metadata

    agent = get_official_agent_metadata(agent_name)
    return (
        f"You are {agent['name']}, the {agent['title']}.\n"
        f"Phase: {agent['phase']}\n"
        f"Description: {agent['description']}\n\n"
        f"Requirement:\n{requirement_text}\n\n"
        f"Generate a structured migration planning output for your role."
    )
