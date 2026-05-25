"""Azure OpenAI / Azure AI Foundry provider.

Uses the OpenAI SDK's `AzureOpenAI` client. Wire format is OpenAI
chat/completions, but routing requires `azure_endpoint`, `api_version`,
and a `deployment_name` instead of a global model id.

`extra_config` keys:
  azure_endpoint   (REQUIRED — e.g., https://my-resource.openai.azure.com)
  api_version      (default: 2026-01-01)
  deployment_name  (REQUIRED — the deployment name you chose in Azure)

`ctx.model` is informational; Azure routes by deployment_name.
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


class AzureProvider(BaseProvider):
    provider_type = "azure"
    default_base_url = None  # SDK-managed

    def call(self, ctx: CallContext):
        return safe_call(lambda: self._call(ctx), "azure")

    def _call(self, ctx: CallContext):
        try:
            from openai import AzureOpenAI
        except ImportError:
            logger.warning("openai package not installed — required for Azure")
            return None

        cfg = ctx.extra_config or {}
        endpoint = cfg.get("azure_endpoint")
        deployment = cfg.get("deployment_name")
        if not endpoint or not deployment:
            logger.warning("Azure requires extra_config.azure_endpoint + .deployment_name")
            return None
        api_version = cfg.get("api_version", "2026-01-01")

        client = AzureOpenAI(
            api_key=ctx.api_key,
            api_version=api_version,
            azure_endpoint=endpoint,
        )
        response = client.chat.completions.create(
            model=deployment,
            temperature=ctx.temperature,
            max_tokens=ctx.max_tokens,
            messages=[
                {"role": "system", "content": ctx.system_prompt},
                {"role": "user", "content": ctx.user_prompt},
            ],
            timeout=ctx.timeout,
        )
        content = response.choices[0].message.content if response.choices else ""
        return parse_text_to_dict(content) if content else None
