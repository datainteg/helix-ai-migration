"""Shared type definitions for the agent runtime."""

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel


@dataclass
class LLMRouterResult:
    """Result from an LLM router call."""

    raw_text: str
    provider_name: str
    model_name: str
    agent_name: str
    mode: str  # "mock" | "llm"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StructuredOutputResult:
    """Result from structured output parsing."""

    success: bool
    parsed: BaseModel | None = None
    raw_text: str = ""
    model_name: str = ""
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
