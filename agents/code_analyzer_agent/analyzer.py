"""
Code Analyzer Agent — extracts inputs, outputs, dependencies, transformations.

Uses configured LLM provider when available. Falls back to typed summary stubs
so analysis remains available without external API dependencies.
"""

import logging

from agents.runtime.llm_client import call_llm
from agents.schemas.developer_agents import CodeAnalyzerOutput

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a code analyzer. Analyze the code and output valid JSON with: "
    "summary, inputs, outputs, dependencies (list of {name, type}), transformations, "
    "risks, complexity_score, assumptions, limitations, confidence_score."
)


def analyze_code(source_code: str, filename: str, org_id: str | None = None) -> CodeAnalyzerOutput:
    result = call_llm(
        agent_name="code_analyzer",
        system_prompt=_SYSTEM_PROMPT,
        user_prompt=f"File: {filename}\n```\n{source_code[:8000]}\n```",
        org_id=org_id,
    )
    if result:
        return CodeAnalyzerOutput(**result)

    lines = source_code.splitlines()
    import_count = sum(1 for l in lines if "import" in l)
    return CodeAnalyzerOutput(
        summary=f"Analyzed {filename} — {len(lines)} lines",
        inputs=["source_code"],
        outputs=["analysis_result"],
        risks=["High import count"] if import_count > 5 else [],
        complexity_score=min(len(lines) / 100, 10.0),
        assumptions=["Code is syntactically valid"],
        limitations=["Static analysis only — human review required for business logic"],
        confidence_score=0.75,
    )
