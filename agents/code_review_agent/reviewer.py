"""
Code Review Agent — quality, security, performance, maintainability review.

Uses configured LLM provider when available. Falls back to static checks.
"""

import json
import logging
import os
import sys

from agents.runtime.structured_output import safe_extract_json
from agents.schemas.developer_agents import CodeReviewOutput, SecurityFinding

logger = logging.getLogger(__name__)

# Ensure backend is importable
_backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
if _backend_root not in sys.path:
    sys.path.insert(0, _backend_root)


def _try_llm_call(source_code: str, filename: str, org_id: str | None = None) -> dict | None:
    """Try LLM review via configured provider. Falls back to None on any error."""
    try:
        from app.services.llm_router_service import resolve_routing
        from app.models.llm import LLMProvider, LLMAgentMapping
        from app.db.session import SessionLocal
        from app.services.secret_service import decrypt_value
        import httpx

        db = SessionLocal()
        try:
            q = db.query(LLMProvider).filter(LLMProvider.status == "active")
            if org_id:
                q = q.filter(LLMProvider.organization_id == org_id)
            provider = q.first()

            if not provider:
                return None
            mappings = db.query(LLMAgentMapping).all()
            pid, model, temp, max_tokens = resolve_routing("code_review", provider.id, provider.default_model, mappings)
            provider_obj = db.query(LLMProvider).filter(LLMProvider.id == pid).first()
            if not provider_obj or not provider_obj.secrets:
                return None
            secret = max(provider_obj.secrets, key=lambda s: s.key_version)
            api_key = decrypt_value(secret.encrypted_api_key)
            base = provider_obj.base_url or "https://api.openai.com/v1"

            resp = httpx.post(
                f"{base.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model, "temperature": temp, "max_tokens": max_tokens,
                    "messages": [
                        {"role": "system", "content": "You are a code reviewer. Review the code and output valid JSON with: summary, quality_findings, anti_patterns, formatting_issues, security_findings (list of {severity, description, location}), performance_issues, maintainability_risks, hardcoded_secrets_detected (bool), assumptions, limitations, confidence_score."},
                        {"role": "user", "content": f"File: {filename}\n```\n{source_code[:8000]}\n```"},
                    ],
                },
                timeout=float(provider_obj.timeout),
            )
            if 200 <= resp.status_code < 300:
                content = resp.json()["choices"][0]["message"]["content"]
                json_str = safe_extract_json(content)
                return json.loads(json_str) if json_str else {"summary": content}
        finally:
            db.close()
    except Exception as exc:
        logger.warning("LLM code review failed for %s: %s", filename, exc)
    return None


def review_code(source_code: str, filename: str) -> CodeReviewOutput:
    result = _try_llm_call(source_code, filename)
    if result:
        return CodeReviewOutput(**result)

    # Fallback: static pattern checks
    has_secrets = any(kw in source_code.lower() for kw in ["password", "secret", "api_key", "token"])
    security_findings = []
    if has_secrets:
        security_findings.append(SecurityFinding(severity="high", description="Potential hardcoded secret detected"))

    return CodeReviewOutput(
        summary=f"Reviewed {filename} — {len(source_code.splitlines())} lines",
        quality_findings=[],
        anti_patterns=[],
        hardcoded_secrets_detected=has_secrets,
        security_findings=security_findings,
        assumptions=["Code review is AI-assisted — human verification required"],
        limitations=["Static analysis only — no execution or full dependency resolution"],
        confidence_score=0.80,
    )
