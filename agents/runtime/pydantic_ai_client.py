"""PydanticAI client wrapper.

Wraps `pydantic_ai.Agent` so the rest of the runtime can request a typed,
schema-validated LLM call without importing PydanticAI directly. Falls back
gracefully when PydanticAI is unavailable or the provider type is not yet
supported by this wrapper — callers must handle a `None` return.

This layer exists so the BMAD nodes get structured outputs end-to-end without
hand-rolling JSON extraction + Pydantic validation for every provider.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)


_PROVIDER_PREFIXES = {
    "openai": "openai:",
    "anthropic": "anthropic:",
    "google": "google-gla:",
    "deepseek": "openai:",      # DeepSeek is OpenAI-compatible; pass base_url separately
    "openrouter": "openai:",
    "custom": "openai:",
    "local": "openai:",
}


def _build_model_id(provider_type: str, model: str) -> str:
    prefix = _PROVIDER_PREFIXES.get(provider_type.lower(), "openai:")
    return f"{prefix}{model}"


def call_pydantic_ai(
    *,
    agent_name: str,
    provider_type: str,
    model: str,
    api_key: str,
    base_url: str | None,
    system_prompt: str,
    user_prompt: str,
    output_model: type[BaseModel],
    temperature: float = 0.7,
    timeout: float = 60.0,
) -> BaseModel | None:
    """Run a typed LLM call via PydanticAI; return a validated model or None.

    Returns None (not raises) on any failure so callers can fall back to
    the legacy httpx client or to deterministic mock data.
    """
    try:
        from pydantic_ai import Agent
    except ImportError:
        logger.info("pydantic_ai not installed — skipping typed call for agent=%s", agent_name)
        return None

    try:
        model_id = _build_model_id(provider_type, model)
        # PydanticAI reads API keys from env by default; set the relevant one.
        import os

        env_var = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "google": "GEMINI_API_KEY",
            "deepseek": "OPENAI_API_KEY",
            "openrouter": "OPENAI_API_KEY",
            "custom": "OPENAI_API_KEY",
            "local": "OPENAI_API_KEY",
        }.get(provider_type.lower(), "OPENAI_API_KEY")

        previous = os.environ.get(env_var)
        os.environ[env_var] = api_key
        try:
            agent = Agent(model_id, result_type=output_model, system_prompt=system_prompt)
            run = agent.run_sync(user_prompt)
            result = getattr(run, "data", None) or getattr(run, "output", None)
            if isinstance(result, output_model):
                logger.info(
                    "PydanticAI [ok] agent=%s provider=%s model=%s",
                    agent_name,
                    provider_type,
                    model,
                )
                return result
            logger.warning(
                "PydanticAI returned non-typed result agent=%s type=%s",
                agent_name,
                type(result).__name__,
            )
            return None
        finally:
            if previous is None:
                os.environ.pop(env_var, None)
            else:
                os.environ[env_var] = previous

    except Exception as exc:  # noqa: BLE001 — caller falls back on None
        logger.warning(
            "PydanticAI call failed agent=%s provider=%s model=%s: %s",
            agent_name,
            provider_type,
            model,
            exc,
        )
        return None


def is_available() -> bool:
    """Return True if pydantic_ai is importable."""
    try:
        import pydantic_ai  # noqa: F401
        return True
    except ImportError:
        return False
