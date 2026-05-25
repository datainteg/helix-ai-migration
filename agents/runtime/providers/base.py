"""BaseProvider — interface every LLM adapter implements.

Each provider lives in its own file under `agents/runtime/providers/`
and registers itself via `register_provider()` so the dispatcher can
look it up by `provider_type` string. Adapters return raw text; the
caller is responsible for JSON extraction + Pydantic validation
(see `agents.runtime.structured_output`).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class CallContext:
    """Everything an adapter needs to make one LLM call."""

    model: str
    system_prompt: str
    user_prompt: str
    api_key: str
    base_url: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: float = 60.0
    # Provider-specific dict: aws_region, gcp_project, azure_endpoint, etc.
    extra_config: Optional[Dict[str, Any]] = None


class BaseProvider:
    """All providers implement this single method."""

    #: Stable identifier; matches `LLMProviderType` value in the DB.
    provider_type: str = ""

    #: Default base URL (informational only — caller may override).
    default_base_url: Optional[str] = None

    def call(self, ctx: CallContext) -> Optional[dict]:
        """Make one LLM call and return parsed dict (best-effort JSON).

        Returns None on transport/auth failure so the caller can fall back
        to a mock or another provider. Should NOT raise; log and return None.
        """
        raise NotImplementedError


# ── Registry ───────────────────────────────────────────────────────

_REGISTRY: Dict[str, BaseProvider] = {}


def register_provider(provider: BaseProvider) -> None:
    """Register a provider instance. Idempotent — last one wins."""
    if not provider.provider_type:
        raise ValueError(f"{provider.__class__.__name__} must set provider_type")
    _REGISTRY[provider.provider_type] = provider


def get_provider(provider_type: str) -> Optional[BaseProvider]:
    """Lookup a registered provider by type string."""
    return _REGISTRY.get(provider_type)


def list_providers() -> list[str]:
    """All registered provider_type strings."""
    return sorted(_REGISTRY.keys())


# ── Shared helpers used by multiple adapters ───────────────────────


def parse_text_to_dict(content: str) -> dict:
    """Best-effort JSON-from-text. Falls back to `{"summary": content}`."""
    from agents.runtime.structured_output import safe_extract_json

    json_str = safe_extract_json(content)
    if json_str:
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass
    return {"summary": content}


def safe_call(fn: Callable[[], Optional[dict]], adapter_name: str) -> Optional[dict]:
    """Wrap an adapter call so transport errors return None, not raise."""
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001
        logger.warning("%s call failed: %s", adapter_name, exc)
        return None
