"""Local provider — Ollama / LM Studio / oobabooga / vLLM-local.

OpenAI-compatible wire format; default base URL points at Ollama's
out-of-the-box bind (`http://localhost:11434/v1`). API key is accepted
but ignored by most local runtimes — Ollama in particular treats anything
as valid.
"""

from __future__ import annotations

from agents.runtime.providers.base import (
    BaseProvider,
    CallContext,
    parse_text_to_dict,
    safe_call,
)


class LocalProvider(BaseProvider):
    provider_type = "local"
    default_base_url = "http://localhost:11434/v1"

    def call(self, ctx: CallContext):
        return safe_call(lambda: self._call(ctx), "local")

    def _call(self, ctx: CallContext):
        import httpx

        base = (ctx.base_url or self.default_base_url).rstrip("/")
        resp = httpx.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {ctx.api_key or 'local'}"},
            json={
                "model": ctx.model,
                "temperature": ctx.temperature,
                "max_tokens": ctx.max_tokens,
                "messages": [
                    {"role": "system", "content": ctx.system_prompt},
                    {"role": "user", "content": ctx.user_prompt},
                ],
            },
            timeout=ctx.timeout,
        )
        if 200 <= resp.status_code < 300:
            content = resp.json()["choices"][0]["message"]["content"]
            return parse_text_to_dict(content)
        return None
