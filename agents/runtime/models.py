"""2026 LLM model registry.

Single source of truth for what models are recommended per provider.
Frontend setup wizard + admin LLM Settings page should fetch this list
so a new model added here surfaces everywhere without code changes
elsewhere.

Schema per entry:
  id              — model id as the provider expects it
  name            — human-friendly label
  context_window  — max input tokens (best published value)
  max_output      — max output tokens
  reasoning       — bool; thinking/reasoning model
  multimodal      — bool; accepts images/audio/video
  supports_tools  — bool; function-calling
  recommended_for — short list of use-case tags
"""

from __future__ import annotations

from typing import Dict, List, TypedDict


class ModelEntry(TypedDict, total=False):
    id: str
    name: str
    context_window: int
    max_output: int
    reasoning: bool
    multimodal: bool
    supports_tools: bool
    recommended_for: List[str]


MODELS: Dict[str, List[ModelEntry]] = {
    "openai": [
        {"id": "gpt-5.5",          "name": "GPT-5.5",          "context_window": 400_000, "max_output": 100_000, "supports_tools": True, "multimodal": True, "recommended_for": ["general", "agents"]},
        {"id": "gpt-5.5-thinking", "name": "GPT-5.5 Thinking", "context_window": 400_000, "max_output": 200_000, "supports_tools": True, "reasoning": True,  "recommended_for": ["reasoning", "coding"]},
        {"id": "gpt-5-mini",       "name": "GPT-5 Mini",       "context_window": 200_000, "max_output": 32_000,  "supports_tools": True, "recommended_for": ["fast", "cheap"]},
        {"id": "gpt-realtime-2",   "name": "GPT Realtime 2",   "context_window": 128_000, "max_output": 8_000,   "supports_tools": True, "multimodal": True, "recommended_for": ["voice", "realtime"]},
    ],
    "anthropic": [
        {"id": "claude-opus-4-7",   "name": "Claude Opus 4.7",   "context_window": 1_000_000, "max_output": 64_000, "supports_tools": True, "multimodal": True, "reasoning": True, "recommended_for": ["coding", "agents", "reasoning"]},
        {"id": "claude-sonnet-4-6", "name": "Claude Sonnet 4.6", "context_window": 1_000_000, "max_output": 64_000, "supports_tools": True, "multimodal": True, "recommended_for": ["general", "balanced"]},
        {"id": "claude-haiku-4-5",  "name": "Claude Haiku 4.5",  "context_window": 200_000,   "max_output": 8_192,  "supports_tools": True, "multimodal": True, "recommended_for": ["fast", "cheap"]},
    ],
    "google": [
        {"id": "gemini-3-pro",          "name": "Gemini 3 Pro",          "context_window": 2_000_000, "max_output": 65_000, "supports_tools": True, "multimodal": True, "reasoning": True, "recommended_for": ["reasoning", "long-context"]},
        {"id": "gemini-3-flash",        "name": "Gemini 3 Flash",        "context_window": 1_000_000, "max_output": 65_000, "supports_tools": True, "multimodal": True, "recommended_for": ["fast", "general"]},
        {"id": "gemini-3.1-flash-lite", "name": "Gemini 3.1 Flash-Lite", "context_window": 1_000_000, "max_output": 32_000, "supports_tools": True, "recommended_for": ["cheap", "fast"]},
        {"id": "gemini-omni",           "name": "Gemini Omni",           "context_window": 1_000_000, "max_output": 65_000, "supports_tools": True, "multimodal": True, "recommended_for": ["multimodal", "voice", "video"]},
    ],
    "deepseek": [
        {"id": "deepseek-v4-pro",    "name": "DeepSeek V4 Pro",    "context_window": 1_000_000, "max_output": 384_000, "supports_tools": True, "reasoning": True, "recommended_for": ["coding", "reasoning", "agents"]},
        {"id": "deepseek-v4-flash",  "name": "DeepSeek V4 Flash",  "context_window": 1_000_000, "max_output": 384_000, "supports_tools": True, "recommended_for": ["fast", "chat", "cheap"]},
        # Legacy aliases — auto-mapped by DeepSeekProvider.
        {"id": "deepseek-chat",      "name": "DeepSeek Chat (legacy alias → V4 Flash)",      "context_window": 1_000_000, "max_output": 384_000, "recommended_for": ["legacy"]},
        {"id": "deepseek-reasoner",  "name": "DeepSeek Reasoner (legacy alias → V4 Pro)",   "context_window": 1_000_000, "max_output": 384_000, "reasoning": True, "recommended_for": ["legacy"]},
    ],
    "openrouter": [
        {"id": "openai/gpt-5.5",                  "name": "GPT-5.5 (via OpenRouter)"},
        {"id": "anthropic/claude-opus-4.7",       "name": "Claude Opus 4.7 (via OpenRouter)"},
        {"id": "anthropic/claude-sonnet-4.6",     "name": "Claude Sonnet 4.6 (via OpenRouter)"},
        {"id": "google/gemini-3-pro",             "name": "Gemini 3 Pro (via OpenRouter)"},
        {"id": "deepseek/deepseek-v4-pro",        "name": "DeepSeek V4 Pro (via OpenRouter)"},
        {"id": "meta-llama/llama-4-maverick",     "name": "Llama 4 Maverick (via OpenRouter)"},
    ],
    "bedrock": [
        {"id": "anthropic.claude-opus-4-7",       "name": "Claude Opus 4.7 (Bedrock)"},
        {"id": "anthropic.claude-sonnet-4-6",     "name": "Claude Sonnet 4.6 (Bedrock)"},
        {"id": "openai.gpt-5.5",                  "name": "GPT-5.5 (Bedrock)"},
        {"id": "openai.gpt-oss-120b",             "name": "GPT-OSS 120B (Bedrock)"},
        {"id": "meta.llama4-maverick",            "name": "Llama 4 Maverick (Bedrock)"},
        {"id": "mistral.mistral-large",           "name": "Mistral Large (Bedrock)"},
        {"id": "amazon.titan-text-premier-v1",    "name": "Titan Text Premier (Bedrock)"},
        {"id": "cohere.command-r-plus-v1",        "name": "Cohere Command R+ (Bedrock)"},
        {"id": "deepseek.deepseek-v4",            "name": "DeepSeek V4 (Bedrock)"},
    ],
    "vertex": [
        {"id": "gemini-3-pro",   "name": "Gemini 3 Pro (Vertex)"},
        {"id": "gemini-3-flash", "name": "Gemini 3 Flash (Vertex)"},
        {"id": "gemini-omni",    "name": "Gemini Omni (Vertex)"},
        {"id": "imagen-4",       "name": "Imagen 4 (Vertex — image gen)"},
        {"id": "veo-3",          "name": "Veo 3 (Vertex — video gen)"},
        {"id": "chirp-3",        "name": "Chirp 3 (Vertex — speech)"},
    ],
    "azure": [
        # Deployment names are tenant-specific; these are the underlying base models.
        {"id": "gpt-5.5",     "name": "GPT-5.5 (Azure)"},
        {"id": "gpt-5-mini",  "name": "GPT-5 Mini (Azure)"},
        {"id": "o1",          "name": "OpenAI o1 (Azure)"},
        {"id": "phi-4",       "name": "Phi-4 (Azure)"},
        {"id": "dall-e-4",    "name": "DALL-E 4 (Azure — image gen)"},
        {"id": "whisper-3",   "name": "Whisper 3 (Azure — speech)"},
    ],
    "custom": [
        # Custom is user-defined; no curated list.
    ],
    "local": [
        {"id": "llama4",         "name": "Llama 4"},
        {"id": "qwen3",          "name": "Qwen 3"},
        {"id": "gemma3",         "name": "Gemma 3"},
        {"id": "mistral-large",  "name": "Mistral Large"},
    ],
}


# Default recommended pick per provider — used by the setup wizard.
DEFAULT_MODELS: Dict[str, str] = {
    "openai":     "gpt-5.5",
    "anthropic":  "claude-sonnet-4-6",
    "google":     "gemini-3-flash",
    "deepseek":   "deepseek-v4-pro",
    "openrouter": "anthropic/claude-sonnet-4.6",
    "bedrock":    "anthropic.claude-sonnet-4-6",
    "vertex":     "gemini-3-flash",
    "azure":      "gpt-5.5",
    "custom":     "",
    "local":      "llama4",
}


def list_models(provider_type: str) -> List[ModelEntry]:
    return MODELS.get(provider_type, [])


def default_model(provider_type: str) -> str:
    return DEFAULT_MODELS.get(provider_type, "")
