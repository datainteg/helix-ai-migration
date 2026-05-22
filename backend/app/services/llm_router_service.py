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

AGENT_TYPES = [
    "business_analyst", "architect", "data_engineer",
    "qa_validation", "recon", "devops", "pm",
    "code_analyzer", "code_review", "code_migration",
    "notebook_generator", "dag_review", "version_control",
]


def resolve_routing(agent_type: str, default_provider_id: str, default_model: str, mappings: list) -> tuple[str, str, float, int]:
    """Resolve which provider/model to use for an agent. Falls back to defaults."""
    for m in mappings:
        if m.agent_type == agent_type:
            return m.provider_id, m.model, m.temperature, m.max_tokens
    return default_provider_id, default_model, 0.7, 4096
