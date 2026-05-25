"""Provider registry — one file per LLM backend.

Each provider lives in its own module; importing this package registers
all built-ins so `get_provider("openai")` works without explicit wiring
at every call site.
"""

from agents.runtime.providers.base import (
    BaseProvider,
    CallContext,
    get_provider,
    list_providers,
    register_provider,
)
from agents.runtime.providers.anthropic_provider import AnthropicProvider
from agents.runtime.providers.azure_provider import AzureProvider
from agents.runtime.providers.bedrock_provider import BedrockProvider
from agents.runtime.providers.custom_provider import CustomProvider
from agents.runtime.providers.deepseek_provider import DeepSeekProvider
from agents.runtime.providers.gemini_provider import GeminiProvider
from agents.runtime.providers.local_provider import LocalProvider
from agents.runtime.providers.openai_provider import OpenAIProvider
from agents.runtime.providers.openrouter_provider import OpenRouterProvider
from agents.runtime.providers.vertex_provider import VertexProvider


# Self-registration at import time. Order doesn't matter — registry is keyed
# by provider_type. Last writer wins, which is fine because each class has a
# unique provider_type.
for _cls in (
    OpenAIProvider,
    AnthropicProvider,
    GeminiProvider,
    DeepSeekProvider,
    OpenRouterProvider,
    BedrockProvider,
    VertexProvider,
    AzureProvider,
    CustomProvider,
    LocalProvider,
):
    register_provider(_cls())


__all__ = [
    "BaseProvider",
    "CallContext",
    "get_provider",
    "list_providers",
    "register_provider",
    "OpenAIProvider",
    "AnthropicProvider",
    "GeminiProvider",
    "DeepSeekProvider",
    "OpenRouterProvider",
    "BedrockProvider",
    "VertexProvider",
    "AzureProvider",
    "CustomProvider",
    "LocalProvider",
]
