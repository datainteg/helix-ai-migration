"""Shared LLM HTTP client. Supports OpenAI, Anthropic, Gemini, and OpenAI-compatible APIs."""

from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)


def _call_openai_compatible(base: str, api_key: str, model: str, temp: float, max_tokens: int,
                             system_prompt: str, user_prompt: str, timeout: float) -> dict | None:
    import httpx
    from agents.runtime.structured_output import safe_extract_json
    resp = httpx.post(
        f"{base.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model, "temperature": temp, "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        },
        timeout=timeout,
    )
    if 200 <= resp.status_code < 300:
        content = resp.json()["choices"][0]["message"]["content"]
        json_str = safe_extract_json(content)
        return json.loads(json_str) if json_str else {"summary": content}
    return None


def _call_anthropic(base: str, api_key: str, model: str, max_tokens: int,
                    system_prompt: str, user_prompt: str, timeout: float) -> dict | None:
    import httpx
    from agents.runtime.structured_output import safe_extract_json
    resp = httpx.post(
        f"{base.rstrip('/')}/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": max_tokens,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        },
        timeout=timeout,
    )
    if 200 <= resp.status_code < 300:
        content = resp.json()["content"][0]["text"]
        json_str = safe_extract_json(content)
        return json.loads(json_str) if json_str else {"summary": content}
    return None


def _call_gemini(base: str, api_key: str, model: str,
                 system_prompt: str, user_prompt: str, timeout: float) -> dict | None:
    import httpx
    from agents.runtime.structured_output import safe_extract_json
    endpoint = f"{base.rstrip('/')}/v1beta/models/{model}:generateContent?key={api_key}"
    resp = httpx.post(
        endpoint,
        json={
            "contents": [{"parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}]}],
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 4096},
        },
        timeout=timeout,
    )
    if 200 <= resp.status_code < 300:
        content = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        json_str = safe_extract_json(content)
        return json.loads(json_str) if json_str else {"summary": content}
    return None


def call_llm(
    agent_name: str,
    system_prompt: str,
    user_prompt: str,
    org_id: str | None = None,
) -> dict | None:
    """Call configured LLM provider for an agent. Returns parsed JSON dict or None on failure."""
    try:
        from app.services.llm_router_service import resolve_routing, LLMProviderType
        from app.models.llm import LLMProvider, LLMAgentMapping
        from app.db.session import SessionLocal
        from app.services.secret_service import decrypt_value

        db = SessionLocal()
        try:
            q = db.query(LLMProvider).filter(LLMProvider.status == "active")
            if org_id:
                q = q.filter(LLMProvider.organization_id == org_id)
            provider = q.first()
            if not provider:
                return None

            mappings = db.query(LLMAgentMapping).all()
            pid, model, temp, max_tokens = resolve_routing(agent_name, provider.id, provider.default_model, mappings)
            provider_obj = db.query(LLMProvider).filter(LLMProvider.id == pid).first()
            if not provider_obj or not provider_obj.secrets:
                return None

            secret = max(provider_obj.secrets, key=lambda s: s.key_version)
            api_key = decrypt_value(secret.encrypted_api_key)
            base = provider_obj.base_url or "https://api.openai.com/v1"
            timeout = float(provider_obj.timeout)
            ptype = provider_obj.provider_type or LLMProviderType.OPENAI

            if ptype == LLMProviderType.ANTHROPIC:
                return _call_anthropic(base or "https://api.anthropic.com", api_key, model, max_tokens, system_prompt, user_prompt, timeout)
            elif ptype == LLMProviderType.GOOGLE:
                return _call_gemini(base or "https://generativelanguage.googleapis.com", api_key, model, system_prompt, user_prompt, timeout)
            else:
                return _call_openai_compatible(base, api_key, model, temp, max_tokens, system_prompt, user_prompt, timeout)
        finally:
            db.close()
    except Exception as exc:
        logger.warning("LLM call failed for agent %s: %s", agent_name, exc)
    return None
