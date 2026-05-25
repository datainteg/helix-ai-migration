"""DeepSeek provider — V4 Pro (reasoning) + V4 Flash (chat).

Wire format is OpenAI-compatible chat/completions; the dedicated adapter
exists so we can hard-code the right base URL + handle legacy aliases
(`deepseek-chat` → `deepseek-v4-flash`, `deepseek-reasoner` → `deepseek-v4-pro`).
"""

from __future__ import annotations

from agents.runtime.providers.base import (
    BaseProvider,
    CallContext,
    parse_text_to_dict,
    safe_call,
)


# Legacy → current alias mapping per DeepSeek's 2026 migration notice.
_LEGACY_ALIASES = {
    "deepseek-chat": "deepseek-v4-flash",
    "deepseek-reasoner": "deepseek-v4-pro",
}


class DeepSeekProvider(BaseProvider):
    provider_type = "deepseek"
    default_base_url = "https://api.deepseek.com/v1"

    def call(self, ctx: CallContext):
        return safe_call(lambda: self._call(ctx), "deepseek")

    def _call(self, ctx: CallContext):
        import httpx

        model = _LEGACY_ALIASES.get(ctx.model, ctx.model)
        base = (ctx.base_url or self.default_base_url).rstrip("/")
        resp = httpx.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {ctx.api_key}"},
            json={
                "model": model,
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
