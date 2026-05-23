"""Structured output parser for agent responses.

Extracts JSON from plain text or fenced ```json blocks, validates with
Pydantic models, and preserves raw output separately.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from pydantic import BaseModel, ValidationError

from agents.runtime.types import LLMRouterResult, StructuredOutputResult

logger = logging.getLogger(__name__)

# ── JSON extraction ──────────────────────────────────────────────────

_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*\n?(.*?)\n?```", re.DOTALL)
_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)
_JSON_ARRAY_RE = re.compile(r"\[.*\]", re.DOTALL)


def safe_extract_json(raw_text: str) -> str | None:
    """Extract JSON string from raw text.

    Tries in order:
    1. Fenced ```json ... ``` block
    2. Fenced ``` ... ``` block (any language)
    3. Raw { ... } JSON object
    4. Raw [ ... ] JSON array

    Returns the extracted JSON string or None.
    """
    if not raw_text or not raw_text.strip():
        return None

    # 1. Try fenced JSON block
    match = _FENCED_JSON_RE.search(raw_text)
    if match:
        return match.group(1).strip()

    # 2. Try raw JSON object
    match = _JSON_OBJECT_RE.search(raw_text)
    if match:
        return match.group(0).strip()

    # 3. Try raw JSON array
    match = _JSON_ARRAY_RE.search(raw_text)
    if match:
        return match.group(0).strip()

    return None


def parse_structured_output(
    raw_text: str,
    output_model: type[BaseModel],
    *,
    agent_name: str = "unknown",
) -> StructuredOutputResult:
    """Parse raw LLM output into a validated Pydantic model.

    Args:
        raw_text: Raw text from the LLM response
        output_model: Pydantic model class to validate against
        agent_name: Agent name for logging context

    Returns:
        StructuredOutputResult with parsed model or errors
    """
    if not raw_text or not raw_text.strip():
        return StructuredOutputResult(
            success=False,
            raw_text=raw_text,
            model_name=output_model.__name__,
            errors=["Empty or whitespace-only input"],
        )

    json_str = safe_extract_json(raw_text)
    if json_str is None:
        return StructuredOutputResult(
            success=False,
            raw_text=raw_text,
            model_name=output_model.__name__,
            errors=["No JSON found in the raw output"],
        )

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as exc:
        logger.warning(
            "JSON decode failed for agent=%s model=%s: %s",
            agent_name,
            output_model.__name__,
            exc,
        )
        return StructuredOutputResult(
            success=False,
            raw_text=raw_text,
            model_name=output_model.__name__,
            errors=[f"JSON decode error: {exc}"],
            metadata={"extracted_json": json_str[:500]},
        )

    try:
        parsed = output_model.model_validate(data)
    except ValidationError as exc:
        logger.warning(
            "Pydantic validation failed for agent=%s model=%s: %s",
            agent_name,
            output_model.__name__,
            exc.errors(),
        )
        return StructuredOutputResult(
            success=False,
            raw_text=raw_text,
            model_name=output_model.__name__,
            errors=[f"Validation error: {err['msg']} (field: {'.'.join(map(str, err['loc']))})" for err in exc.errors()],
            metadata={"extracted_json": json_str[:500]},
        )

    logger.info(
        "Structured output parsed successfully: agent=%s model=%s",
        agent_name,
        output_model.__name__,
    )
    return StructuredOutputResult(
        success=True,
        parsed=parsed,
        raw_text=raw_text,
        model_name=output_model.__name__,
        metadata={"extracted_json": json_str[:500]},
    )


def parse_router_result(
    result: LLMRouterResult,
    output_model: type[BaseModel],
) -> StructuredOutputResult:
    """Convenience: parse an LLMRouterResult through structured output.

    Preserves the router metadata and adds parse results.
    """
    parsed = parse_structured_output(
        result.raw_text,
        output_model,
        agent_name=result.agent_name,
    )
    parsed.metadata.update(result.metadata)
    parsed.metadata["router_mode"] = result.mode
    parsed.metadata["router_provider"] = result.provider_name
    parsed.metadata["router_model"] = result.model_name
    return parsed


def build_mock_agent_response(
    agent_name: str,
    output_model: type[BaseModel],
    *,
    requirement_text: str = "",
) -> StructuredOutputResult:
    """Build a deterministic mock agent response with structured output.

    Uses the BMAD agent metadata to create a realistic mock JSON response
    that validates against the given Pydantic model.

    Args:
        agent_name: BMAD agent key
        output_model: Pydantic model to validate against
        requirement_text: Optional requirement context

    Returns:
        StructuredOutputResult with parsed mock data
    """
    from agents.bmad.official_agents import get_official_agent_metadata

    agent = get_official_agent_metadata(agent_name)

    # Build mock data based on model fields
    mock_data: dict[str, Any] = {}
    for field_name, field_info in output_model.model_fields.items():
        field_type = field_info.annotation

        if field_name == "summary":
            mock_data[field_name] = (
                f"{agent['name']} ({agent['title']}) generated a mock {output_model.__name__} "
                f"for the migration requirement."
            )
        elif field_name == "architecture_summary":
            mock_data[field_name] = (
                f"{agent['name']} ({agent['title']}) prepared the draft migration architecture."
            )
        elif field_name == "validation_strategy":
            mock_data[field_name] = (
                "Metadata-driven validation and reconciliation checks before migration execution."
            )
        elif field_name == "reconciliation_approach":
            mock_data[field_name] = (
                "Compare source and target metadata summaries first; defer row-level to later phases."
            )
        elif field_name == "approval_required":
            mock_data[field_name] = True
        elif field_name == "approval_reason":
            mock_data[field_name] = "Human approval is required before execution-oriented agents continue."
        elif field_name == "next_step":
            mock_data[field_name] = "await_human_approval"
        elif field_name == "status":
            mock_data[field_name] = "completed"
        elif field_name == "quality_score":
            mock_data[field_name] = 0.85
        elif field_name == "business_goals":
            mock_data[field_name] = [
                "Clarify migration objective and business success criteria.",
            ]
        elif field_name == "assumptions":
            mock_data[field_name] = [
                "The current requirement text is the authoritative planning input.",
            ]
        elif field_name == "open_questions":
            mock_data[field_name] = [
                "What is the required cutover window?",
            ]
        elif field_name == "risks":
            mock_data[field_name] = [
                {
                    "title": "Incomplete migration scope",
                    "severity": "medium",
                    "impact": "Planning may miss critical systems.",
                    "mitigation": "Review with business owners before approval.",
                }
            ]
        elif field_name == "source_systems":
            mock_data[field_name] = ["source system metadata pending"]
        elif field_name == "target_systems":
            mock_data[field_name] = ["target platform metadata pending"]
        elif field_name == "integration_points":
            mock_data[field_name] = ["Metadata capture API", "Agent planning workflow"]
        elif field_name == "dependencies":
            mock_data[field_name] = ["Approved business requirement"]
        elif field_name == "checks":
            mock_data[field_name] = [
                "Schema compatibility check",
                "Row count comparison",
                "Null and duplicate summary",
            ]
        elif field_name == "acceptance_criteria":
            mock_data[field_name] = [
                "Business goals are reviewed.",
                "Architecture plan is approved.",
            ]
        else:
            # Generic fallback for unknown fields
            mock_data[field_name] = f"[mock {field_name}]"

    mock_json = json.dumps(mock_data, indent=2)
    return parse_structured_output(mock_json, output_model, agent_name=agent_name)
