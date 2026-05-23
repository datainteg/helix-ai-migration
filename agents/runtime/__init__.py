"""Agent runtime — LLM router and structured output utilities."""

from agents.runtime.llm_router import (
    build_mock_agent_prompt,
    route_llm_call,
)
from agents.runtime.structured_output import (
    build_mock_agent_response,
    parse_router_result,
    parse_structured_output,
    safe_extract_json,
)
from agents.runtime.types import LLMRouterResult, StructuredOutputResult

__all__ = [
    "LLMRouterResult",
    "StructuredOutputResult",
    "build_mock_agent_prompt",
    "build_mock_agent_response",
    "parse_router_result",
    "parse_structured_output",
    "route_llm_call",
    "safe_extract_json",
]
