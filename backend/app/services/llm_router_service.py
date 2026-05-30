from enum import Enum


class LLMProviderType(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    DEEPSEEK = "deepseek"
    OPENROUTER = "openrouter"
    BEDROCK = "bedrock"        # AWS Bedrock — Claude, Llama, Mistral, Titan, ...
    VERTEX = "vertex"          # Google Vertex AI — Gemini + Model Garden
    AZURE = "azure"            # Azure OpenAI Service
    CUSTOM = "custom"
    LOCAL = "local"


SUPPORTED_PROVIDERS = [p.value for p in LLMProviderType]

# Agent codes — single source of truth. The 6 BMAD personas match
# `_bmad/config.toml`; `assistant` is the in-app Help agent (Ask Helix).
# LLMAgentMapping rows use these codes as `agent_type`. An admin can map any of
# these to a specific provider+model; unmapped agents fall back to the org's
# default provider/model (see resolve_routing).
AGENT_TYPES = [
    "bmad-agent-analyst",        # Mary    — Business Analyst
    "bmad-agent-tech-writer",    # Paige   — Technical Writer
    "bmad-agent-pm",             # John    — Product Manager
    "bmad-agent-ux-designer",    # Sally   — UX Designer
    "bmad-agent-architect",      # Winston — System Architect
    "bmad-agent-dev",            # Amelia  — Senior Software Engineer
    "assistant",                 # Helix Help agent (the "Ask Helix" popup)
]


def resolve_routing(agent_type: str, default_provider_id: str, default_model: str, mappings: list) -> tuple[str, str, float, int]:
    """Resolve which provider/model to use for an agent. Falls back to defaults."""
    for m in mappings:
        if m.agent_type == agent_type:
            return m.provider_id, m.model, m.temperature, m.max_tokens
    return default_provider_id, default_model, 0.7, 4096
