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


def _decrypt_extra_config_safe(extra: dict | None) -> dict | None:
    """SEC-010 helper — best-effort decrypt of sealed extra_config envelopes.

    Imported lazily so this worker-side module doesn't hard-depend on the
    backend package at import time (Temporal activity boot order).
    """
    if not extra:
        return extra
    try:
        from app.services.llm_provider_service import decrypt_extra_config
        return decrypt_extra_config(extra)
    except Exception:  # noqa: BLE001
        return extra


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

        # Resolve provider/routing/secret, building the CallContext, then RELEASE
        # the DB connection BEFORE the (slow, ~10-30s) provider call — holding a
        # pooled connection for the whole LLM call starves the pool under
        # concurrency.
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
            provider_type = provider_obj.provider_type
            ctx = CallContext(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                api_key=api_key,
                base_url=provider_obj.base_url,
                temperature=float(temp),
                max_tokens=int(max_tokens),
                timeout=float(provider_obj.timeout),
                # SEC-010: decrypt sealed sensitive keys before handing the dict to the provider
                extra_config=_decrypt_extra_config_safe(provider_obj.extra_config) or {},
            )
        finally:
            db.close()  # connection released before the LLM call below

        adapter = get_provider(provider_type)
        if adapter is None:
            logger.warning("no adapter for provider_type=%s", provider_type)
            return None

        result = adapter.call(ctx)

        # Usage/cost sync on a fresh, short-lived session (adapters don't surface
        # token counts → estimate ~4 chars/token). Without this, call_llm-based
        # agents (migration type_mapper/script_generator, assistants) never
        # appeared in llm_usage_records — only the BMAD executor did.
        if result is not None and org_id:
            try:
                import json as _json
                from app.services.cost_service import record_usage
                udb = SessionLocal()
                try:
                    record_usage(
                        udb, organization_id=org_id, provider_type=provider_type, model=model,
                        input_tokens=max(1, (len(system_prompt) + len(user_prompt)) // 4),
                        output_tokens=max(1, len(_json.dumps(result)) // 4), agent_name=agent_name,
                    )
                finally:
                    udb.close()
            except Exception:  # noqa: BLE001 — usage accounting must never fail the call
                logger.debug("call_llm usage record failed", exc_info=True)
        return result
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM call failed for agent %s: %s", agent_name, exc)
    return None
