"""Unit tests for every LLM provider adapter.

One test per adapter covers:
  - URL/endpoint shape
  - API-key placement (header vs body)
  - Request body shape
  - Successful JSON parse round-trip
  - Failure modes return None (never raise) so the caller can fall back

httpx-based adapters are tested by monkey-patching `httpx.post`.
SDK-based adapters (Bedrock, Vertex, Azure) inject a fake client/module so
the test exercises adapter glue without needing boto3 / google-cloud /
openai installed.

Regression coverage for 2026-05-25 review:
  - Gemini: API key MUST live in `x-goog-api-key` header, NOT URL.
  - PydanticAI client: no env-var mutation (separate test in
    test_pydantic_ai_client.py).
"""

from __future__ import annotations

import json
import sys
import types
from typing import Any

import httpx
import pytest

from agents.runtime.providers.base import CallContext


# ── httpx response stub ────────────────────────────────────────────────


class _FakeResponse:
    def __init__(self, status: int, body: dict):
        self.status_code = status
        self._body = body
        self.text = json.dumps(body)

    def json(self) -> dict:  # mimic httpx Response
        return self._body


def _ok(body: dict) -> _FakeResponse:
    return _FakeResponse(200, body)


def _err(status: int = 500) -> _FakeResponse:
    return _FakeResponse(status, {"error": "boom"})


@pytest.fixture
def _ctx() -> CallContext:
    return CallContext(
        model="test-model",
        system_prompt="be terse",
        user_prompt="hi",
        api_key="sk-test-abc",
        temperature=0.5,
        max_tokens=128,
        timeout=5.0,
    )


# ── OpenAI ─────────────────────────────────────────────────────────────


def test_openai_uses_bearer_header_and_chat_endpoint(monkeypatch, _ctx):
    from agents.runtime.providers import openai_provider as mod

    captured: dict[str, Any] = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return _ok({"choices": [{"message": {"content": '{"out": "ok"}'}}]})

    monkeypatch.setattr(httpx, "post", fake_post)
    out = mod.OpenAIProvider().call(_ctx)
    assert out == {"out": "ok"}
    assert captured["url"].endswith("/chat/completions")
    assert captured["headers"]["Authorization"] == "Bearer sk-test-abc"
    assert captured["json"]["messages"][0]["role"] == "system"


def test_openai_returns_none_on_5xx(monkeypatch, _ctx):
    from agents.runtime.providers import openai_provider as mod

    monkeypatch.setattr(httpx, "post", lambda *a, **kw: _err(503))
    assert mod.OpenAIProvider().call(_ctx) is None


# ── Anthropic ──────────────────────────────────────────────────────────


def test_anthropic_uses_x_api_key_header_and_system_top_level(monkeypatch, _ctx):
    from agents.runtime.providers import anthropic_provider as mod

    captured: dict[str, Any] = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return _ok({"content": [{"text": '{"out": "claude"}'}]})

    monkeypatch.setattr(httpx, "post", fake_post)
    out = mod.AnthropicProvider().call(_ctx)
    assert out == {"out": "claude"}
    assert captured["headers"]["x-api-key"] == "sk-test-abc"
    assert captured["headers"]["anthropic-version"] == "2023-06-01"
    assert captured["json"]["system"] == "be terse"
    # Anthropic body uses top-level `system`, not a system message.
    roles = [m["role"] for m in captured["json"]["messages"]]
    assert "system" not in roles


# ── Gemini ─────────────────────────────────────────────────────────────


def test_gemini_uses_header_not_url(monkeypatch, _ctx):
    """Regression: API key MUST live in x-goog-api-key, never in URL."""
    from agents.runtime.providers import gemini_provider as mod

    captured: dict[str, Any] = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        return _ok({"candidates": [{"content": {"parts": [{"text": '{"out": "gem"}'}]}}]})

    monkeypatch.setattr(httpx, "post", fake_post)
    out = mod.GeminiProvider().call(_ctx)
    assert out == {"out": "gem"}
    assert "?key=" not in captured["url"]
    assert "key=" not in captured["url"]
    assert captured["headers"]["x-goog-api-key"] == "sk-test-abc"


# ── DeepSeek ───────────────────────────────────────────────────────────


def test_deepseek_aliases_legacy_model(monkeypatch, _ctx):
    from agents.runtime.providers import deepseek_provider as mod

    captured: dict[str, Any] = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["json"] = json
        return _ok({"choices": [{"message": {"content": '{"out": "ds"}'}}]})

    monkeypatch.setattr(httpx, "post", fake_post)
    ctx = CallContext(
        model="deepseek-chat",
        system_prompt="x",
        user_prompt="y",
        api_key="k",
    )
    mod.DeepSeekProvider().call(ctx)
    # `deepseek-chat` is a legacy alias for `deepseek-v4-flash` per 2026 mapping.
    assert captured["json"]["model"] == "deepseek-v4-flash"


# ── OpenRouter ─────────────────────────────────────────────────────────


def test_openrouter_sends_attribution_headers(monkeypatch, _ctx):
    from agents.runtime.providers import openrouter_provider as mod

    captured: dict[str, Any] = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["headers"] = headers
        return _ok({"choices": [{"message": {"content": '{"out": "or"}'}}]})

    monkeypatch.setattr(httpx, "post", fake_post)
    mod.OpenRouterProvider().call(_ctx)
    assert captured["headers"]["Authorization"] == "Bearer sk-test-abc"
    assert "HTTP-Referer" in captured["headers"]
    assert "X-Title" in captured["headers"]


# ── Custom (OpenAI-compatible) ─────────────────────────────────────────


def test_custom_requires_base_url(monkeypatch, _ctx):
    from agents.runtime.providers import custom_provider as mod

    # Without base_url the call must short-circuit to None — never POST.
    called = {"n": 0}

    def fake_post(*a, **kw):
        called["n"] += 1
        return _ok({})

    monkeypatch.setattr(httpx, "post", fake_post)
    assert mod.CustomProvider().call(_ctx) is None
    assert called["n"] == 0


def test_custom_sends_to_user_base_url(monkeypatch, _ctx):
    from agents.runtime.providers import custom_provider as mod

    captured: dict[str, Any] = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        return _ok({"choices": [{"message": {"content": '{"out": "c"}'}}]})

    monkeypatch.setattr(httpx, "post", fake_post)
    _ctx.base_url = "https://internal.example.com/v1"
    out = mod.CustomProvider().call(_ctx)
    assert out == {"out": "c"}
    assert captured["url"] == "https://internal.example.com/v1/chat/completions"


# ── Local (Ollama / LM Studio) ────────────────────────────────────────


def test_local_tolerates_blank_api_key(monkeypatch, _ctx):
    from agents.runtime.providers import local_provider as mod

    captured: dict[str, Any] = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["headers"] = headers
        captured["url"] = url
        return _ok({"choices": [{"message": {"content": '{"out": "l"}'}}]})

    monkeypatch.setattr(httpx, "post", fake_post)
    _ctx.api_key = ""
    out = mod.LocalProvider().call(_ctx)
    assert out == {"out": "l"}
    # Ollama accepts anything as Bearer; adapter substitutes a placeholder.
    assert captured["headers"]["Authorization"].startswith("Bearer ")
    assert "localhost:11434" in captured["url"]


# ── Bedrock (SDK-backed) ──────────────────────────────────────────────


def test_bedrock_requires_boto3_and_is_idempotent_to_empty_api_key(monkeypatch):
    """Empty api_key is fine — Bedrock auths via SigV4 / IAM, not the key."""
    from agents.runtime.providers import bedrock_provider as mod

    # Fake `boto3` module so we don't need the dep installed in CI.
    fake_boto3 = types.ModuleType("boto3")
    invoked: dict[str, Any] = {}

    class FakeBody:
        def read(self) -> bytes:
            return b'{"content":[{"text":"{\\"out\\": \\"br\\"}"}]}'

    class FakeClient:
        def invoke_model(self, modelId, body, contentType, accept):
            invoked["modelId"] = modelId
            invoked["body"] = body
            return {"body": FakeBody()}

    fake_boto3.client = lambda *a, **kw: FakeClient()
    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)

    ctx = CallContext(
        model="anthropic.claude-3-7-sonnet",
        system_prompt="s", user_prompt="u",
        api_key="",  # blank — IAM auth
        extra_config={"aws_region": "us-east-1"},
    )
    out = mod.BedrockProvider().call(ctx)
    assert out == {"out": "br"}
    assert invoked["modelId"] == "anthropic.claude-3-7-sonnet"


# ── Vertex (SDK-backed) ───────────────────────────────────────────────


def test_vertex_requires_gcp_project(monkeypatch):
    """Missing gcp_project must short-circuit, not crash."""
    from agents.runtime.providers import vertex_provider as mod

    ctx = CallContext(model="gemini-pro", system_prompt="s", user_prompt="u", api_key="", extra_config={})
    assert mod.VertexProvider().call(ctx) is None


def test_vertex_inits_once_per_project_location(monkeypatch):
    """Regression: vertexai.init must be wrapped in a lock + memoized."""
    from agents.runtime.providers import vertex_provider as mod

    init_calls: list[tuple[str, str]] = []

    # Fake `vertexai` package + a generative_models submodule.
    fake_vertexai = types.ModuleType("vertexai")
    fake_vertexai.init = lambda project, location: init_calls.append((project, location))
    fake_gm = types.ModuleType("vertexai.generative_models")

    class FakeModel:
        def __init__(self, model: str) -> None:
            self.model = model
        def generate_content(self, prompt, generation_config=None):
            return types.SimpleNamespace(text='{"out": "v"}')

    fake_gm.GenerativeModel = FakeModel
    monkeypatch.setitem(sys.modules, "vertexai", fake_vertexai)
    monkeypatch.setitem(sys.modules, "vertexai.generative_models", fake_gm)

    # Reset the memo so this test is order-independent.
    mod._active_init = None  # type: ignore[attr-defined]

    ctx = CallContext(
        model="gemini-pro",
        system_prompt="s", user_prompt="u",
        api_key="",
        extra_config={"gcp_project": "demo", "gcp_location": "us-central1"},
    )
    mod.VertexProvider().call(ctx)
    mod.VertexProvider().call(ctx)  # second call must NOT re-init
    assert init_calls == [("demo", "us-central1")]


# ── Azure (SDK-backed) ────────────────────────────────────────────────


def test_azure_requires_endpoint_and_deployment(monkeypatch):
    from agents.runtime.providers import azure_provider as mod

    # Inject a fake `openai` module so the adapter's lazy import succeeds.
    fake_openai = types.ModuleType("openai")
    fake_openai.AzureOpenAI = object  # never actually constructed in this path
    monkeypatch.setitem(sys.modules, "openai", fake_openai)

    ctx = CallContext(model="gpt-5", system_prompt="s", user_prompt="u", api_key="k", extra_config={})
    assert mod.AzureProvider().call(ctx) is None


def test_azure_uses_deployment_for_routing(monkeypatch):
    from agents.runtime.providers import azure_provider as mod

    captured: dict[str, Any] = {}

    class FakeChatCompletions:
        def create(self, model, temperature, max_tokens, messages, timeout):
            captured["model"] = model
            captured["messages"] = messages
            return types.SimpleNamespace(choices=[types.SimpleNamespace(message=types.SimpleNamespace(content='{"out": "az"}'))])

    class FakeChat:
        completions = FakeChatCompletions()

    class FakeAzureOpenAI:
        def __init__(self, api_key, api_version, azure_endpoint):
            captured["init"] = (api_key, api_version, azure_endpoint)
        chat = FakeChat()

    fake_openai = types.ModuleType("openai")
    fake_openai.AzureOpenAI = FakeAzureOpenAI
    monkeypatch.setitem(sys.modules, "openai", fake_openai)

    ctx = CallContext(
        model="gpt-5", system_prompt="s", user_prompt="u", api_key="azkey",
        extra_config={
            "azure_endpoint": "https://my-resource.openai.azure.com",
            "deployment_name": "prod-gpt5",
            "api_version": "2026-01-01",
        },
    )
    out = mod.AzureProvider().call(ctx)
    assert out == {"out": "az"}
    # Azure routes by deployment_name, NOT the model field.
    assert captured["model"] == "prod-gpt5"
    assert captured["init"] == ("azkey", "2026-01-01", "https://my-resource.openai.azure.com")
