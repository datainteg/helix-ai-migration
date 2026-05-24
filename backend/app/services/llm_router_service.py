from enum import Enum


class LLMProviderType(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    DEEPSEEK = "deepseek"
    OPENROUTER = "openrouter"
    CUSTOM = "custom"
    LOCAL = "local"


SUPPORTED_PROVIDERS = [p.value for p in LLMProviderType]

# BMAD agent codes — single source of truth, matches the 6 personas declared in
# `_bmad/config.toml`. LLMAgentMapping rows use these codes as `agent_type`.
AGENT_TYPES = [
    "bmad-agent-analyst",        # Mary    — Business Analyst
    "bmad-agent-tech-writer",    # Paige   — Technical Writer
    "bmad-agent-pm",             # John    — Product Manager
    "bmad-agent-ux-designer",    # Sally   — UX Designer
    "bmad-agent-architect",      # Winston — System Architect
    "bmad-agent-dev",            # Amelia  — Senior Software Engineer
]


def resolve_routing(agent_type: str, default_provider_id: str, default_model: str, mappings: list) -> tuple[str, str, float, int]:
    """Resolve which provider/model to use for an agent. Falls back to defaults."""
    for m in mappings:
        if m.agent_type == agent_type:
            return m.provider_id, m.model, m.temperature, m.max_tokens
    return default_provider_id, default_model, 0.7, 4096
