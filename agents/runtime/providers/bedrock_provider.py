"""AWS Bedrock provider — Claude, Llama 4, Mistral, Titan, Cohere, DeepSeek, GPT-OSS.

Routes by model ID prefix:
  anthropic.*  → Anthropic Messages API body
  meta.*       → Llama prompt body
  mistral.*    → Mistral prompt body
  cohere.*     → Cohere generate body
  amazon.*     → Titan Text body
  deepseek.*   → DeepSeek chat body (OpenAI-shaped)
  openai.*     → OpenAI chat body (new in 2026 via Bedrock)

`extra_config` keys (all optional — boto3 falls back to env/IAM):
  aws_region              (default: us-east-1)
  aws_access_key_id
  aws_secret_access_key
  aws_session_token

`api_key` is unused (Bedrock auths via SigV4); included for interface
symmetry. To skip storing AWS keys server-side, leave the api_key blank
and rely on the container/instance role.
"""

from __future__ import annotations

import json
import logging

from agents.runtime.providers.base import (
    BaseProvider,
    CallContext,
    parse_text_to_dict,
    safe_call,
)

logger = logging.getLogger(__name__)


class BedrockProvider(BaseProvider):
    provider_type = "bedrock"
    default_base_url = None  # SDK-managed

    def call(self, ctx: CallContext):
        return safe_call(lambda: self._call(ctx), "bedrock")

    def _call(self, ctx: CallContext):
        try:
            import boto3
        except ImportError:
            logger.warning("boto3 not installed — install boto3 to use Bedrock")
            return None

        cfg = ctx.extra_config or {}
        region = cfg.get("aws_region", "us-east-1")
        client_kwargs = {"region_name": region}

        # Optional explicit keys; otherwise boto3 picks up env / instance role.
        if cfg.get("aws_access_key_id"):
            client_kwargs["aws_access_key_id"] = cfg["aws_access_key_id"]
            client_kwargs["aws_secret_access_key"] = cfg.get("aws_secret_access_key", "")
            if cfg.get("aws_session_token"):
                client_kwargs["aws_session_token"] = cfg["aws_session_token"]

        client = boto3.client("bedrock-runtime", **client_kwargs)

        body = _build_body(ctx)
        response = client.invoke_model(
            modelId=ctx.model,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json",
        )
        raw = json.loads(response["body"].read())
        text = _extract_text(ctx.model, raw)
        return parse_text_to_dict(text) if text else None


def _build_body(ctx: CallContext) -> dict:
    """Build the Bedrock invoke body for the model family."""
    mid = ctx.model.lower()

    if mid.startswith("anthropic."):
        return {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": ctx.max_tokens,
            "system": ctx.system_prompt,
            "messages": [{"role": "user", "content": ctx.user_prompt}],
        }

    if mid.startswith("meta."):
        # H-006: Llama 3+ (meta.llama3-*, meta.llama4-*) use the chat
        # template tokens, NOT the Llama 2 [INST] format. Wrapping a Llama 3
        # prompt in <s>[INST]...[/INST]</s> causes the tokens to be parsed
        # as literal text and the model emits garbage.
        # Legacy meta.llama2-* still expects [INST]...[/INST].
        if mid.startswith("meta.llama3-") or mid.startswith("meta.llama4-"):
            combined = (
                f"{ctx.system_prompt}\n\n{ctx.user_prompt}"
                if ctx.system_prompt
                else ctx.user_prompt
            )
            prompt = (
                "<|begin_of_text|>"
                "<|start_header_id|>user<|end_header_id|>\n\n"
                f"{combined}<|eot_id|>"
                "<|start_header_id|>assistant<|end_header_id|>\n\n"
            )
        else:
            prompt = f"<s>[INST]{ctx.system_prompt}\n\n{ctx.user_prompt}[/INST]"
        return {
            "prompt": prompt,
            "temperature": ctx.temperature,
            "max_gen_len": ctx.max_tokens,
        }

    if mid.startswith("mistral."):
        # Mistral on Bedrock expects [INST]...[/INST] but NOT a surrounding
        # <s> token — the Bedrock wrapper adds the BOS itself.
        return {
            "prompt": f"[INST]{ctx.system_prompt}\n\n{ctx.user_prompt}[/INST]",
            "temperature": ctx.temperature,
            "max_tokens": ctx.max_tokens,
        }

    if mid.startswith("cohere."):
        return {
            "prompt": f"{ctx.system_prompt}\n\n{ctx.user_prompt}",
            "temperature": ctx.temperature,
            "max_tokens": ctx.max_tokens,
        }

    if mid.startswith("amazon."):
        return {
            "inputText": f"{ctx.system_prompt}\n\n{ctx.user_prompt}",
            "textGenerationConfig": {
                "temperature": ctx.temperature,
                "maxTokenCount": ctx.max_tokens,
            },
        }

    if mid.startswith("deepseek.") or mid.startswith("openai."):
        # OpenAI-shaped chat body, Bedrock 2026 addition.
        return {
            "messages": [
                {"role": "system", "content": ctx.system_prompt},
                {"role": "user", "content": ctx.user_prompt},
            ],
            "temperature": ctx.temperature,
            "max_tokens": ctx.max_tokens,
        }

    # Unknown family — pass through as OpenAI-shaped.
    return {
        "messages": [
            {"role": "system", "content": ctx.system_prompt},
            {"role": "user", "content": ctx.user_prompt},
        ],
        "temperature": ctx.temperature,
        "max_tokens": ctx.max_tokens,
    }


def _extract_text(model_id: str, raw: dict) -> str:
    """Pull the assistant text out of whatever shape the family returned."""
    mid = model_id.lower()

    if mid.startswith("anthropic."):
        return raw.get("content", [{}])[0].get("text", "")
    if mid.startswith("meta."):
        return raw.get("generation", "")
    if mid.startswith("mistral."):
        outs = raw.get("outputs", [])
        return outs[0].get("text", "") if outs else ""
    if mid.startswith("cohere."):
        gens = raw.get("generations", [])
        return gens[0].get("text", "") if gens else ""
    if mid.startswith("amazon."):
        results = raw.get("results", [])
        return results[0].get("outputText", "") if results else ""
    if mid.startswith("deepseek.") or mid.startswith("openai."):
        choices = raw.get("choices", [])
        return choices[0].get("message", {}).get("content", "") if choices else ""
    # Best-effort fallback
    return raw.get("output", "") or raw.get("text", "") or ""
