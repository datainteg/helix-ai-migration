"""OpenAI provider — gpt-5.5, gpt-5-mini, gpt-realtime-2.

Uses the chat/completions endpoint (kept here rather than the newer
`responses` API for parity with every OpenAI-compatible mirror in the
fleet — DeepSeek, OpenRouter, Together, Fireworks, Groq, vLLM, etc.).
"""

from __future__ import annotations

from agents.runtime.providers.base import (
    BaseProvider,
    CallContext,
    parse_text_to_dict,
    safe_call,
)


class OpenAIProvider(BaseProvider):
    provider_type = "openai"
    default_base_url = "https://api.openai.com/v1"

    def call(self, ctx: CallContext):
        return safe_call(lambda: self._call(ctx), "openai")

    def _call(self, ctx: CallContext):
        import httpx

        base = (ctx.base_url or self.default_base_url).rstrip("/")
        resp = httpx.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {ctx.api_key}"},
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
