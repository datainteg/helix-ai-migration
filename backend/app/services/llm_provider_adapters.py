"""LLM provider connection-test adapters.

Each provider gets a tiny `test_connection(api_key)` that returns a
TestConnectionResponse. Where possible the test is free / metadata-only
(GET /models, list_foundation_models, etc.). For SDK-backed providers we
just try to initialize the client — a failed init signals a config
problem to the operator without spending tokens.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import httpx

from app.schemas.llm import TestConnectionResponse

logger = logging.getLogger(__name__)


OPENAI_COMPATIBLE_PROVIDER_TYPES = {"openai", "deepseek", "openrouter", "custom"}
DEFAULT_OPENAI_COMPATIBLE_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}
DEFAULT_LOCAL_BASE_URL = "http://localhost:11434/v1"


@dataclass(frozen=True)
class ProviderConnectionConfig:
    provider_type: str
    name: str
    base_url: Optional[str]
    timeout: int
    extra_config: Dict[str, Any] = field(default_factory=dict)


class BaseLLMProviderAdapter(ABC):
    def __init__(self, config: ProviderConnectionConfig):
        self.config = config

    @abstractmethod
    async def test_connection(self, api_key: str) -> TestConnectionResponse:
        raise NotImplementedError


# ── OpenAI-compatible (OpenAI / DeepSeek / OpenRouter / Custom) ──────


class OpenAICompatibleAdapter(BaseLLMProviderAdapter):
    async def test_connection(self, api_key: str) -> TestConnectionResponse:
        base_url = self.config.base_url or DEFAULT_OPENAI_COMPATIBLE_BASE_URLS.get(self.config.provider_type)
        if not base_url:
            return TestConnectionResponse(success=False, message=f"No base URL configured for {self.config.provider_type}")
        return await _http_get_models(base_url, api_key, float(self.config.timeout), self.config.name)


# ── Anthropic ─────────────────────────────────────────────────────────


class AnthropicAdapter(BaseLLMProviderAdapter):
    async def test_connection(self, api_key: str) -> TestConnectionResponse:
        base = (self.config.base_url or "https://api.anthropic.com").rstrip("/")
        # GET /v1/models is free and returns 200 with a valid key.
        try:
            async with httpx.AsyncClient(timeout=float(self.config.timeout)) as client:
                resp = await client.get(
                    f"{base}/v1/models",
                    headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
                )
        except httpx.RequestError as exc:
            return TestConnectionResponse(success=False, message=f"Cannot reach {base}: {exc}")

        if 200 <= resp.status_code < 300:
            return TestConnectionResponse(success=True, message=f"Connected to {self.config.name}")
        if resp.status_code in {401, 403}:
            return TestConnectionResponse(success=False, message="Authentication failed")
        return TestConnectionResponse(success=False, message=f"Anthropic returned HTTP {resp.status_code}")


# ── Google Gemini API ────────────────────────────────────────────────


class GeminiAdapter(BaseLLMProviderAdapter):
    async def test_connection(self, api_key: str) -> TestConnectionResponse:
        base = (self.config.base_url or "https://generativelanguage.googleapis.com").rstrip("/")
        try:
            async with httpx.AsyncClient(timeout=float(self.config.timeout)) as client:
                resp = await client.get(f"{base}/v1beta/models?key={api_key}")
        except httpx.RequestError as exc:
            return TestConnectionResponse(success=False, message=f"Cannot reach {base}: {exc}")

        if 200 <= resp.status_code < 300:
            return TestConnectionResponse(success=True, message=f"Connected to {self.config.name}")
        if resp.status_code in {400, 401, 403}:
            return TestConnectionResponse(success=False, message="Invalid API key")
        return TestConnectionResponse(success=False, message=f"Gemini returned HTTP {resp.status_code}")


# ── Local (Ollama / LM Studio) ────────────────────────────────────────


class LocalModelAdapter(BaseLLMProviderAdapter):
    async def test_connection(self, api_key: str) -> TestConnectionResponse:
        base = (self.config.base_url or DEFAULT_LOCAL_BASE_URL).rstrip("/")
        try:
            async with httpx.AsyncClient(timeout=float(self.config.timeout)) as client:
                # Ollama's /api/tags lists installed models; the OpenAI-compatible
                # mirror exposes /v1/models. Try /v1/models first (matches the
                # adapter wire format), then fall back to /api/tags.
                resp = await client.get(
                    f"{base}/models",
                    headers={"Authorization": f"Bearer {api_key or 'local'}"},
                )
                if resp.status_code == 404:
                    resp = await client.get(f"{base.rsplit('/v1', 1)[0]}/api/tags")
        except httpx.RequestError as exc:
            return TestConnectionResponse(success=False, message=f"Cannot reach {base}: {exc}")

        if 200 <= resp.status_code < 300:
            return TestConnectionResponse(success=True, message=f"Connected to {self.config.name}")
        return TestConnectionResponse(success=False, message=f"Local runtime returned HTTP {resp.status_code}")


# ── AWS Bedrock ──────────────────────────────────────────────────────


class BedrockAdapter(BaseLLMProviderAdapter):
    async def test_connection(self, api_key: str) -> TestConnectionResponse:
        try:
            import boto3
        except ImportError:
            return TestConnectionResponse(success=False, message="boto3 not installed in this image")

        cfg = self.config.extra_config or {}
        region = cfg.get("aws_region", "us-east-1")
        client_kwargs = {"region_name": region}
        if cfg.get("aws_access_key_id"):
            client_kwargs["aws_access_key_id"] = cfg["aws_access_key_id"]
            client_kwargs["aws_secret_access_key"] = cfg.get("aws_secret_access_key", "")
            if cfg.get("aws_session_token"):
                client_kwargs["aws_session_token"] = cfg["aws_session_token"]

        try:
            client = boto3.client("bedrock", **client_kwargs)
            client.list_foundation_models()  # free; returns 403 if creds invalid
            return TestConnectionResponse(success=True, message=f"Connected to AWS Bedrock ({region})")
        except Exception as exc:  # noqa: BLE001
            return TestConnectionResponse(success=False, message=f"Bedrock auth failed: {exc}")


# ── Google Vertex AI ─────────────────────────────────────────────────


class VertexAdapter(BaseLLMProviderAdapter):
    async def test_connection(self, api_key: str) -> TestConnectionResponse:
        cfg = self.config.extra_config or {}
        project = cfg.get("gcp_project")
        if not project:
            return TestConnectionResponse(success=False, message="Missing extra_config.gcp_project")
        location = cfg.get("gcp_location", "us-central1")

        try:
            import vertexai
        except ImportError:
            return TestConnectionResponse(success=False, message="google-cloud-aiplatform not installed")

        try:
            vertexai.init(project=project, location=location)
            return TestConnectionResponse(success=True, message=f"Vertex initialized for {project}/{location}")
        except Exception as exc:  # noqa: BLE001
            return TestConnectionResponse(success=False, message=f"Vertex init failed: {exc}")


# ── Azure OpenAI / Azure AI Foundry ──────────────────────────────────


class AzureAdapter(BaseLLMProviderAdapter):
    async def test_connection(self, api_key: str) -> TestConnectionResponse:
        cfg = self.config.extra_config or {}
        endpoint = cfg.get("azure_endpoint")
        if not endpoint:
            return TestConnectionResponse(success=False, message="Missing extra_config.azure_endpoint")
        api_version = cfg.get("api_version", "2026-01-01")
        base = endpoint.rstrip("/")
        url = f"{base}/openai/deployments?api-version={api_version}"

        try:
            async with httpx.AsyncClient(timeout=float(self.config.timeout)) as client:
                resp = await client.get(url, headers={"api-key": api_key})
        except httpx.RequestError as exc:
            return TestConnectionResponse(success=False, message=f"Cannot reach {endpoint}: {exc}")

        if 200 <= resp.status_code < 300:
            return TestConnectionResponse(success=True, message=f"Connected to Azure OpenAI ({endpoint})")
        if resp.status_code in {401, 403}:
            return TestConnectionResponse(success=False, message="Azure auth failed (check api-key)")
        return TestConnectionResponse(success=False, message=f"Azure returned HTTP {resp.status_code}")


# ── Factory ──────────────────────────────────────────────────────────


def build_llm_provider_adapter(config: ProviderConnectionConfig) -> BaseLLMProviderAdapter:
    provider_type = config.provider_type.lower()
    normalized_config = ProviderConnectionConfig(
        provider_type=provider_type,
        name=config.name,
        base_url=config.base_url,
        timeout=config.timeout,
        extra_config=config.extra_config or {},
    )

    if provider_type in OPENAI_COMPATIBLE_PROVIDER_TYPES:
        return OpenAICompatibleAdapter(normalized_config)
    if provider_type == "anthropic":
        return AnthropicAdapter(normalized_config)
    if provider_type in {"google", "gemini"}:
        return GeminiAdapter(normalized_config)
    if provider_type in {"local", "ollama"}:
        return LocalModelAdapter(normalized_config)
    if provider_type == "bedrock":
        return BedrockAdapter(normalized_config)
    if provider_type == "vertex":
        return VertexAdapter(normalized_config)
    if provider_type == "azure":
        return AzureAdapter(normalized_config)
    # Unknown — be conservative and use the OpenAI-compatible path so the
    # operator still gets a real HTTP status back.
    return OpenAICompatibleAdapter(normalized_config)


# ── Shared HTTP helper ───────────────────────────────────────────────


async def _http_get_models(base_url: str, api_key: str, timeout: float, name: str) -> TestConnectionResponse:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(
                f"{base_url.rstrip('/')}/models",
                headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
            )
    except httpx.TimeoutException:
        return TestConnectionResponse(success=False, message=f"Connection to {base_url} timed out after {timeout}s")
    except httpx.ConnectError:
        return TestConnectionResponse(success=False, message=f"Cannot reach {base_url}: connection failed")
    except httpx.RequestError:
        return TestConnectionResponse(success=False, message=f"Connection to {base_url} failed")

    if 200 <= response.status_code < 300:
        return TestConnectionResponse(success=True, message=f"Connected to {name}")
    if response.status_code in {401, 403}:
        return TestConnectionResponse(success=False, message="Authentication failed")
    return TestConnectionResponse(success=False, message=f"Provider returned HTTP {response.status_code}")
