from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx

from app.schemas.llm import TestConnectionResponse


OPENAI_COMPATIBLE_PROVIDER_TYPES = {"openai", "deepseek", "openrouter", "custom"}
DEFAULT_OPENAI_COMPATIBLE_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}


@dataclass(frozen=True)
class ProviderConnectionConfig:
    provider_type: str
    name: str
    base_url: str | None
    timeout: int


class BaseLLMProviderAdapter(ABC):
    def __init__(self, config: ProviderConnectionConfig):
        self.config = config

    @abstractmethod
    async def test_connection(self, api_key: str) -> TestConnectionResponse:
        raise NotImplementedError


class OpenAICompatibleAdapter(BaseLLMProviderAdapter):
    async def test_connection(self, api_key: str) -> TestConnectionResponse:
        base_url = self.config.base_url or DEFAULT_OPENAI_COMPATIBLE_BASE_URLS.get(self.config.provider_type)
        if not base_url:
            return TestConnectionResponse(
                success=False,
                message=f"No base URL configured for {self.config.provider_type}",
            )

        try:
            async with httpx.AsyncClient(timeout=float(self.config.timeout)) as client:
                response = await client.get(
                    f"{base_url.rstrip('/')}/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
        except httpx.TimeoutException:
            return TestConnectionResponse(
                success=False,
                message=f"Connection to {base_url} timed out after {self.config.timeout}s",
            )
        except httpx.ConnectError:
            return TestConnectionResponse(
                success=False,
                message=f"Cannot reach {base_url}: connection failed",
            )
        except httpx.RequestError:
            return TestConnectionResponse(
                success=False,
                message=f"Connection to {base_url} failed",
            )

        if 200 <= response.status_code < 300:
            return TestConnectionResponse(success=True, message=f"Connected to {self.config.name}")
        if response.status_code in {401, 403}:
            return TestConnectionResponse(success=False, message="Authentication failed")
        return TestConnectionResponse(
            success=False,
            message=f"Provider returned HTTP {response.status_code}",
        )


class AnthropicAdapter(BaseLLMProviderAdapter):
    async def test_connection(self, api_key: str) -> TestConnectionResponse:
        return TestConnectionResponse(
            success=False,
            message="Anthropic connection testing is not implemented yet",
        )


class GeminiAdapter(BaseLLMProviderAdapter):
    async def test_connection(self, api_key: str) -> TestConnectionResponse:
        return TestConnectionResponse(
            success=False,
            message="Gemini connection testing is not implemented yet",
        )


class LocalModelAdapter(BaseLLMProviderAdapter):
    async def test_connection(self, api_key: str) -> TestConnectionResponse:
        return TestConnectionResponse(
            success=False,
            message="Local model connection testing is not implemented yet",
        )


def build_llm_provider_adapter(config: ProviderConnectionConfig) -> BaseLLMProviderAdapter:
    provider_type = config.provider_type.lower()
    normalized_config = ProviderConnectionConfig(
        provider_type=provider_type,
        name=config.name,
        base_url=config.base_url,
        timeout=config.timeout,
    )

    if provider_type in OPENAI_COMPATIBLE_PROVIDER_TYPES:
        return OpenAICompatibleAdapter(normalized_config)
    if provider_type == "anthropic":
        return AnthropicAdapter(normalized_config)
    if provider_type in {"google", "gemini"}:
        return GeminiAdapter(normalized_config)
    if provider_type in {"local", "ollama"}:
        return LocalModelAdapter(normalized_config)
    return LocalModelAdapter(normalized_config)
