"""Custom OpenAI-compatible provider.

Catch-all for vLLM, Text Generation WebUI, Groq, Fireworks, Together AI,
Cerebras, Anyscale, Replicate's OpenAI-compatible mode, etc. Caller supplies
the `base_url`; everything else is identical to OpenAI.
"""

from __future__ import annotations

from agents.runtime.providers.base import (
    BaseProvider,
    CallContext,
    parse_text_to_dict,
    safe_call,
)


class CustomProvider(BaseProvider):
    provider_type = "custom"
    default_base_url = None  # user-supplied

    def call(self, ctx: CallContext):
        return safe_call(lambda: self._call(ctx), "custom")

    def _call(self, ctx: CallContext):
        import httpx

        if not ctx.base_url:
            return None
        base = ctx.base_url.rstrip("/")
        resp = httpx.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {ctx.api_key}"} if ctx.api_key else {},
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
