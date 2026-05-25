"""Anthropic provider — Claude Opus 4.7 / Sonnet 4.6 / Haiku 4.5.

Hits the Messages API directly via httpx (no SDK dependency so we stay
runtime-light). System prompt goes in its own top-level field per
Anthropic spec — not as a "system" role inside `messages`.
"""

from __future__ import annotations

from agents.runtime.providers.base import (
    BaseProvider,
    CallContext,
    parse_text_to_dict,
    safe_call,
)


class AnthropicProvider(BaseProvider):
    provider_type = "anthropic"
    default_base_url = "https://api.anthropic.com"

    def call(self, ctx: CallContext):
        return safe_call(lambda: self._call(ctx), "anthropic")

    def _call(self, ctx: CallContext):
        import httpx

        base = (ctx.base_url or self.default_base_url).rstrip("/")
        resp = httpx.post(
            f"{base}/v1/messages",
            headers={
                "x-api-key": ctx.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": ctx.model,
                "max_tokens": ctx.max_tokens,
                "system": ctx.system_prompt,
                "messages": [{"role": "user", "content": ctx.user_prompt}],
            },
            timeout=ctx.timeout,
        )
        if 200 <= resp.status_code < 300:
            content = resp.json()["content"][0]["text"]
            return parse_text_to_dict(content)
        return None
