"""Shared LLM dispatcher.

Thin shim over the provider registry in `agents.runtime.providers`. Loads
the org's active provider row from the DB, resolves the per-agent routing
override, builds a `CallContext`, and forwards to the matching adapter.
Each adapter is one file under `agents/runtime/providers/`.
"""

from __future__ import annotations

import logging

from agents.runtime.providers import CallContext, get_provider

logger = logging.getLogger(__name__)


def call_llm(
    agent_name: str,
    system_prompt: str,
    user_prompt: str,
    org_id: str | None = None,
) -> dict | None:
    """Run one LLM call for `agent_name`. Returns parsed dict, or None on failure."""
    try:
        from app.services.llm_router_service import resolve_routing
        from app.models.llm import LLMProvider, LLMAgentMapping
        from app.services.secret_service import decrypt_value
        # Prefer worker-local SessionLocal when running inside a Temporal
        # activity to keep the worker decoupled from FastAPI request scope.
        try:
            from worker.db.session import SessionLocal  # type: ignore
        except Exception:
            from app.db.session import SessionLocal  # type: ignore

        db = SessionLocal()
        try:
            q = db.query(LLMProvider).filter(LLMProvider.status == "active")
            if org_id:
                q = q.filter(LLMProvider.organization_id == org_id)
            provider = q.first()
            if not provider:
                return None

            mappings_q = db.query(LLMAgentMapping)
            if org_id:
                mappings_q = mappings_q.filter(LLMAgentMapping.organization_id == org_id)
            mappings = mappings_q.all()
            pid, model, temp, max_tokens = resolve_routing(
                agent_name, provider.id, provider.default_model, mappings
            )
            provider_obj = db.query(LLMProvider).filter(LLMProvider.id == pid).first()
            if not provider_obj or not provider_obj.secrets:
                return None

            secret = max(provider_obj.secrets, key=lambda s: s.key_version)
            api_key = decrypt_value(secret.encrypted_api_key)

            adapter = get_provider(provider_obj.provider_type)
            if adapter is None:
                logger.warning("no adapter for provider_type=%s", provider_obj.provider_type)
                return None

            ctx = CallContext(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                api_key=api_key,
                base_url=provider_obj.base_url,
                temperature=float(temp),
                max_tokens=int(max_tokens),
                timeout=float(provider_obj.timeout),
                extra_config=provider_obj.extra_config or {},
            )
            return adapter.call(ctx)
        finally:
            db.close()
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM call failed for agent %s: %s", agent_name, exc)
    return None
