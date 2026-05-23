"""
Code Review Agent — quality, security, performance, maintainability review.

Uses configured LLM provider when available. Falls back to static checks.
"""

import logging

from agents.runtime.llm_client import call_llm
from agents.schemas.developer_agents import CodeReviewOutput, SecurityFinding

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a code reviewer. Review the code and output valid JSON with: "
    "summary, quality_findings, anti_patterns, formatting_issues, "
    "security_findings (list of {severity, description, location}), "
    "performance_issues, maintainability_risks, hardcoded_secrets_detected (bool), "
    "assumptions, limitations, confidence_score."
)


def review_code(source_code: str, filename: str, org_id: str | None = None) -> CodeReviewOutput:
    result = call_llm(
        agent_name="code_review",
        system_prompt=_SYSTEM_PROMPT,
        user_prompt=f"File: {filename}\n```\n{source_code[:8000]}\n```",
        org_id=org_id,
    )
    if result:
        return CodeReviewOutput(**result)

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
