"""Google Gemini provider — Gemini 3 Pro / 3 Flash / 3.1 Flash-Lite / Omni.

Uses the public generateContent endpoint. For Workspace/Vertex use the
`VertexProvider` instead (different auth + endpoint structure).
"""

from __future__ import annotations

from agents.runtime.providers.base import (
    BaseProvider,
    CallContext,
    parse_text_to_dict,
    safe_call,
)


class GeminiProvider(BaseProvider):
    provider_type = "google"
    default_base_url = "https://generativelanguage.googleapis.com"

    def call(self, ctx: CallContext):
        return safe_call(lambda: self._call(ctx), "gemini")

    def _call(self, ctx: CallContext):
        import httpx

        base = (ctx.base_url or self.default_base_url).rstrip("/")
        # Send the API key in the x-goog-api-key header instead of the URL
        # query string so it does not leak into web-server access logs or
        # browser history. Google's API supports both, header is preferred.
        url = f"{base}/v1beta/models/{ctx.model}:generateContent"
        resp = httpx.post(
            url,
            headers={"x-goog-api-key": ctx.api_key} if ctx.api_key else {},
            json={
                "contents": [
                    {"parts": [{"text": f"{ctx.system_prompt}\n\n{ctx.user_prompt}"}]}
                ],
                "generationConfig": {
                    "temperature": ctx.temperature,
                    "maxOutputTokens": ctx.max_tokens,
                },
            },
            timeout=ctx.timeout,
        )
        if 200 <= resp.status_code < 300:
            content = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            return parse_text_to_dict(content)
        return None
