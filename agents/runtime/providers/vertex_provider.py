"""Google Vertex AI provider — Gemini 3 Pro / Flash / Omni + Model Garden.

Uses `google-cloud-aiplatform` SDK; authentication is Application Default
Credentials (env var GOOGLE_APPLICATION_CREDENTIALS pointing at a service
account JSON, or workload-identity in GKE).

`extra_config` keys:
  gcp_project    (REQUIRED — no sensible default)
  gcp_location   (default: us-central1)

`api_key` is unused (Vertex uses ADC); included for interface symmetry.
"""

from __future__ import annotations

import logging

from agents.runtime.providers.base import (
    BaseProvider,
    CallContext,
    parse_text_to_dict,
    safe_call,
)

logger = logging.getLogger(__name__)


class VertexProvider(BaseProvider):
    provider_type = "vertex"
    default_base_url = None  # SDK-managed

    def call(self, ctx: CallContext):
        return safe_call(lambda: self._call(ctx), "vertex")

    def _call(self, ctx: CallContext):
        try:
            import vertexai
            from vertexai.generative_models import GenerativeModel
        except ImportError:
            logger.warning("google-cloud-aiplatform not installed — install to use Vertex AI")
            return None

        cfg = ctx.extra_config or {}
        project = cfg.get("gcp_project")
        if not project:
            logger.warning("Vertex AI requires extra_config.gcp_project")
            return None
        location = cfg.get("gcp_location", "us-central1")

        vertexai.init(project=project, location=location)
        model = GenerativeModel(ctx.model)

        # Vertex SDK doesn't have a top-level system prompt for vanilla Gemini;
        # prepend it inline. (For Claude-on-Vertex, use the Anthropic adapter
        # with the Vertex base URL instead.)
        full_prompt = f"{ctx.system_prompt}\n\n{ctx.user_prompt}"
        response = model.generate_content(
            full_prompt,
            generation_config={
                "temperature": ctx.temperature,
                "max_output_tokens": ctx.max_tokens,
            },
        )
        text = getattr(response, "text", "") or ""
        return parse_text_to_dict(text) if text else None
