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


def _build_model(provider_type: str, model: str, api_key: str, base_url: str | None):
    """Construct a PydanticAI model using explicit Provider constructors.

    Avoids mutating os.environ — that approach was a race hazard across
    concurrent agent calls. Each call instead owns its own Provider+Model
    pair with the api_key passed directly.
    """
    ptype = provider_type.lower()

    if ptype == "anthropic":
        from pydantic_ai.models.anthropic import AnthropicModel
        from pydantic_ai.providers.anthropic import AnthropicProvider
        return AnthropicModel(model, provider=AnthropicProvider(api_key=api_key))

    if ptype == "google":
        from pydantic_ai.models.gemini import GeminiModel
        from pydantic_ai.providers.google_gla import GoogleGLAProvider
        return GeminiModel(model, provider=GoogleGLAProvider(api_key=api_key))

    # openai-compatible family: openai, deepseek, openrouter, custom, local.
    from pydantic_ai.models.openai import OpenAIModel
    from pydantic_ai.providers.openai import OpenAIProvider
    provider = OpenAIProvider(api_key=api_key, base_url=base_url) if base_url else OpenAIProvider(api_key=api_key)
    return OpenAIModel(model, provider=provider)


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
        # Build the model with an explicit provider. No env-var mutation: this
        # avoids the global-state race seen when multiple agents fire concurrently
        # with different keys.
        try:
            llm_model = _build_model(provider_type, model, api_key, base_url)
        except ImportError as exc:
            # PydanticAI sub-package for this provider isn't installed. Caller
            # falls back to the legacy httpx client.
            logger.info("pydantic_ai provider unavailable for %s: %s", provider_type, exc)
            return None

        agent = Agent(llm_model, result_type=output_model, system_prompt=system_prompt)
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
