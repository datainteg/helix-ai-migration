"""OpenRouter provider — multi-vendor router (openai/*, anthropic/*, etc.).

Same wire format as OpenAI; separate adapter so we can hard-code the
base URL and add the `HTTP-Referer` + `X-Title` headers OpenRouter
recommends so traffic is attributable to Helix.
"""

from __future__ import annotations

from agents.runtime.providers.base import (
    BaseProvider,
    CallContext,
    parse_text_to_dict,
    safe_call,
)


class OpenRouterProvider(BaseProvider):
    provider_type = "openrouter"
    default_base_url = "https://openrouter.ai/api/v1"

    def call(self, ctx: CallContext):
        return safe_call(lambda: self._call(ctx), "openrouter")

    def _call(self, ctx: CallContext):
        import httpx

        base = (ctx.base_url or self.default_base_url).rstrip("/")
        resp = httpx.post(
            f"{base}/chat/completions",
            headers={
                "Authorization": f"Bearer {ctx.api_key}",
                "HTTP-Referer": "https://github.com/datainteg/helix-ai-migration",
                "X-Title": "Helix Migration",
            },
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
