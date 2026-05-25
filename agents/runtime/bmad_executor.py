"""BMAD agent executor — runs one agent+skill, produces a markdown artifact.

This is the glue between BMAD definitions (persona + skill SKILL.md), the LLM
transport stack, and the artifact store. A LangGraph node typically calls
`execute_agent_skill()` once per BMAD step and lets that single call:

  1. Load the BMAD agent persona via `bmad_loader.load_bmad_agent`
  2. Load the task skill via `bmad_loader.load_bmad_skill`
  3. Read prior artifacts (the "memory" handoff) from `artifact_store`
  4. Build a system prompt (persona) + user prompt (skill instructions + context)
  5. Call the LLM:
        - PydanticAI (typed, validated output) when an LLM provider + PydanticAI are configured
        - httpx-backed `call_llm` as fallback for providers without PydanticAI coverage
        - Deterministic mock as last-resort fallback so the graph completes end-to-end
  6. Persist the produced markdown to the artifact store
  7. Return both the markdown artifact and a parsed metadata model

Output contract: the LLM is asked to return a markdown document with a YAML
frontmatter block whose fields match the supplied Pydantic `output_model`.
We parse the frontmatter, validate with Pydantic, and stash the full document
in the artifact store so downstream agents can read the whole thing.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any

import yaml
from pydantic import BaseModel, ValidationError

from agents.runtime.artifact_store import Artifact, collect_prior_context, write_artifact
from agents.runtime.bmad_loader import (
    BMADAgent,
    BMADSkill,
    build_persona_prompt,
    build_skill_instructions,
    load_bmad_agent,
    load_bmad_skill,
)
from agents.runtime.llm_client import call_llm
from agents.runtime.metrics import timed_run
from agents.runtime.pydantic_ai_client import call_pydantic_ai, is_available as pydantic_ai_available

logger = logging.getLogger(__name__)


_FRONT_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)

# Order of transports tried. Override with HELIX_LLM_TRANSPORT="pydantic_ai", "httpx", "mock".
_DEFAULT_TRANSPORT_ORDER = ("pydantic_ai", "httpx", "mock")

# Prompt budget — total tokens (system + user) allowed per LLM call.
# Default is conservative to fit 8K-context models with response headroom.
# Override via HELIX_PROMPT_TOKEN_BUDGET env var.
_DEFAULT_TOKEN_BUDGET = 6000

# Rough char→token ratio. English ≈ 4 chars/token; mono-spaced markdown
# averages closer to 3.5. Pick 4 to under-estimate (truncate aggressively).
_CHARS_PER_TOKEN = 4


def _token_budget() -> int:
    raw = os.getenv("HELIX_PROMPT_TOKEN_BUDGET", "")
    if not raw:
        return _DEFAULT_TOKEN_BUDGET
    try:
        return max(int(raw), 1000)
    except ValueError:
        return _DEFAULT_TOKEN_BUDGET


def _estimate_tokens(text: str) -> int:
    """Char-based token estimate. Fast, deterministic, no tokenizer dep."""
    return max(1, len(text) // _CHARS_PER_TOKEN)


def _truncate_smart(text: str, max_chars: int, *, label: str = "section") -> str:
    """Keep head + tail; drop the middle. Marks the cut with a clear breadcrumb.

    Targets agents that put the most important content at the top (intent,
    role) and the bottom (output contract, final instructions) of SKILL.md.
    """
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    # Reserve ~80 chars for the truncation marker.
    body_chars = max(max_chars - 80, 100)
    head = int(body_chars * 0.7)
    tail = body_chars - head
    return (
        f"{text[:head].rstrip()}\n\n"
        f"[... {label} truncated: {len(text) - body_chars} chars dropped ...]\n\n"
        f"{text[-tail:].lstrip()}"
    )


@dataclass
class AgentRunResult:
    """Outcome of running one BMAD agent+skill."""

    success: bool
    artifact: Artifact | None
    parsed: BaseModel | None
    raw_text: str
    mode: str          # "pydantic_ai" | "httpx" | "mock"
    errors: list[str]


# ── Prompt builders ─────────────────────────────────────────────────


def _build_system_prompt(
    agent: BMADAgent,
    skill: BMADSkill,
    output_model: type[BaseModel],
    *,
    skill_body_chars: int | None = None,
) -> str:
    """Compose persona + skill body + output contract.

    `skill_body_chars` caps the SKILL.md body when provided — SKILL.md files
    in BMAD-METHOD can be 25K+ chars and blow context budgets without this.
    """
    persona = build_persona_prompt(agent)
    skill_body = build_skill_instructions(skill)
    if skill_body_chars is not None and len(skill_body) > skill_body_chars:
        skill_body = _truncate_smart(
            skill_body,
            skill_body_chars,
            label=f"BMAD skill body for {skill.name}",
        )

    fields_block = json.dumps(
        {name: str(field.annotation) for name, field in output_model.model_fields.items()},
        indent=2,
    )

    return (
        f"{persona}\n\n"
        f"## Task: {skill.name}\n"
        f"{skill_body}\n\n"
        f"## Output Contract\n"
        f"Respond with a single markdown document. The document MUST start with a YAML\n"
        f"frontmatter block (fenced by `---`) whose top-level keys match the\n"
        f"{output_model.__name__} schema below. Use sensible defaults when a field\n"
        f"is not derivable from the input. After the frontmatter, write the full\n"
        f"deliverable as ordinary markdown (this is what downstream agents read).\n"
        f"Do not wrap the document in additional code fences.\n\n"
        f"### {output_model.__name__} fields\n"
        f"```json\n{fields_block}\n```"
    )


def _build_user_prompt(
    *,
    project_id: str,
    requirement_text: str,
    prior_context: list[dict[str, Any]],
    artifact_chars_per_item: int = 6000,
) -> str:
    parts = [
        f"Project: {project_id}",
        "",
        "## Migration requirement",
        requirement_text or "(no requirement text provided)",
    ]
    if prior_context:
        parts.append("")
        parts.append("## Upstream artifacts (prior agent outputs)")
        for idx, item in enumerate(prior_context, start=1):
            parts.append(
                f"\n### {idx}. {item.get('agent', 'unknown')} / {item.get('skill', 'unknown')}"
                f" → {item.get('filename', '')}"
            )
            body = (item.get("body") or "").strip()
            if body:
                truncated = _truncate_smart(
                    body,
                    artifact_chars_per_item,
                    label=f"artifact {item.get('agent', '?')}/{item.get('filename', '?')}",
                )
                parts.append(truncated)
    parts.append("")
    parts.append("Produce the artifact now per the output contract above.")
    return "\n".join(parts)


def _allocate_prompt_budget(
    *,
    output_schema_chars: int,
    persona_chars: int,
    skill_body_chars: int,
    requirement_chars: int,
    upstream_count: int,
) -> tuple[int, int]:
    """Return (skill_body_max_chars, artifact_max_chars_each) within the token budget.

    Strategy:
      1. Reserve ~25% of the budget for the LLM's response (markdown body).
      2. Reserve a hard floor for persona + output schema (they're the
         contract — never truncate).
      3. Split the remainder 50/50 between SKILL.md body and upstream
         artifacts (split evenly among upstream items).
      4. Always keep requirement_text intact — it's the user's intent.
    """
    budget_tokens = _token_budget()
    # Reserve 25% for the LLM response, leaving 75% for the prompt.
    prompt_budget_chars = int(budget_tokens * _CHARS_PER_TOKEN * 0.75)

    # Hard reservations — never truncate these.
    fixed = persona_chars + output_schema_chars + requirement_chars + 1000  # 1k for boilerplate
    remaining = max(prompt_budget_chars - fixed, 1500)

    if upstream_count == 0:
        # All remaining budget goes to SKILL.md body.
        return remaining, 0

    # Split 50/50 between SKILL.md body and the upstream context bundle.
    skill_share = remaining // 2
    artifact_share = remaining - skill_share
    per_artifact = max(artifact_share // upstream_count, 500)

    # Don't expand SKILL.md beyond its actual size — saves chars for artifacts.
    if skill_body_chars > 0 and skill_share > skill_body_chars:
        slack = skill_share - skill_body_chars
        per_artifact += slack // max(upstream_count, 1)
        skill_share = skill_body_chars

    return skill_share, per_artifact


# ── Parsing ─────────────────────────────────────────────────────────


def _split_markdown(text: str) -> tuple[dict[str, Any], str]:
    """Return (frontmatter_dict, body) for a markdown doc with YAML frontmatter."""
    match = _FRONT_RE.match(text.strip())
    if not match:
        return {}, text.strip()
    try:
        front = yaml.safe_load(match.group(1)) or {}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Frontmatter YAML parse failed: %s", exc)
        front = {}
    if not isinstance(front, dict):
        front = {}
    return front, match.group(2).strip()


def _parse_metadata(text: str, output_model: type[BaseModel]) -> tuple[BaseModel | None, list[str]]:
    front, _ = _split_markdown(text)
    if not front:
        return None, ["No YAML frontmatter found in artifact"]
    try:
        return output_model.model_validate(front), []
    except ValidationError as exc:
        return None, [f"{err['msg']} (field: {'.'.join(str(p) for p in err['loc'])})" for err in exc.errors()]


# ── Mock fallback ───────────────────────────────────────────────────


def _build_mock_markdown(
    *,
    agent: BMADAgent,
    skill: BMADSkill,
    output_model: type[BaseModel],
    requirement_text: str,
    project_id: str,
) -> str:
    """Generate a deterministic markdown artifact (frontmatter + body) for mock mode."""
    mock_fields: dict[str, Any] = {}
    for field_name, field_info in output_model.model_fields.items():
        annotation = str(field_info.annotation)
        if field_name == "summary":
            mock_fields[field_name] = (
                f"{agent.name} ({agent.title}) ran {skill.name} for {project_id} in mock mode."
            )
        elif field_name == "approval_required":
            mock_fields[field_name] = True
        elif field_name == "approval_reason":
            mock_fields[field_name] = "Human approval required before implementation."
        elif field_name == "next_step":
            mock_fields[field_name] = "await_human_approval"
        elif field_name == "sign_off":
            mock_fields[field_name] = "needs_revision"
        elif "list" in annotation:
            mock_fields[field_name] = []
        elif "bool" in annotation:
            mock_fields[field_name] = False
        elif "float" in annotation:
            mock_fields[field_name] = 0.0
        elif "int" in annotation:
            mock_fields[field_name] = 0
        elif "str" in annotation:
            mock_fields[field_name] = ""
        else:
            mock_fields[field_name] = None

    front_yaml = yaml.safe_dump(mock_fields, sort_keys=False, allow_unicode=True).strip()
    body = (
        f"# {agent.name} — {skill.name}\n\n"
        f"_This document was generated in mock mode (no LLM provider configured)._\n\n"
        f"## Requirement\n{requirement_text or '(no requirement text)'}\n\n"
        f"## Notes\n"
        f"Mock fallback for downstream agents to chain off. Configure an LLM provider\n"
        f"and rerun the workflow to replace this with real analysis.\n"
    )
    return f"---\n{front_yaml}\n---\n\n{body}"


def _wrap_as_markdown(data: dict[str, Any], *, agent: BMADAgent, skill: BMADSkill) -> str:
    """Wrap bare JSON dict from an LLM into the markdown+frontmatter contract."""
    summary = data.get("summary") or f"{agent.name} ran {skill.name}"
    front_yaml = yaml.safe_dump(data, sort_keys=False, allow_unicode=True).strip()
    body = (
        f"# {agent.name} — {skill.name}\n\n"
        f"{summary}\n\n"
        f"_Structured output above is the source of truth for downstream agents._\n"
    )
    return f"---\n{front_yaml}\n---\n\n{body}"


def _model_to_markdown(model: BaseModel, *, agent: BMADAgent, skill: BMADSkill) -> str:
    """Convert a typed PydanticAI result back into the markdown+frontmatter contract."""
    data = model.model_dump()
    return _wrap_as_markdown(data, agent=agent, skill=skill)


# ── LLM transport selection ─────────────────────────────────────────


def _transport_order() -> tuple[str, ...]:
    override = os.getenv("HELIX_LLM_TRANSPORT")
    if not override:
        return _DEFAULT_TRANSPORT_ORDER
    return tuple(x.strip() for x in override.split(",") if x.strip())


def _resolve_provider_for_org(org_id: str | None) -> dict[str, Any] | None:
    """Return decrypted provider details for an org, or None if unavailable.

    Used by the PydanticAI transport. Reads the same LLMProvider table the
    httpx transport uses, so behaviour is consistent across paths.
    """
    if not org_id:
        return None
    # Prefer the worker-local SessionLocal when running inside a Temporal
    # activity. Falls back to backend's SessionLocal for in-process planning
    # runs. This is what keeps the worker decoupled from FastAPI request scope.
    SessionLocal = None
    try:
        from worker.db.session import SessionLocal as _WorkerSession  # type: ignore
        SessionLocal = _WorkerSession
    except Exception:
        try:
            from app.db.session import SessionLocal as _AppSession  # type: ignore
            SessionLocal = _AppSession
        except Exception as exc:  # noqa: BLE001
            logger.info("PydanticAI provider lookup skipped — no DB session available: %s", exc)
            return None
    try:
        from app.models.llm import LLMAgentMapping, LLMProvider
        from app.services.llm_router_service import resolve_routing
        from app.services.secret_service import decrypt_value
    except Exception as exc:  # noqa: BLE001
        logger.info("PydanticAI provider lookup skipped — backend not importable here: %s", exc)
        return None

    db = SessionLocal()
    try:
        provider = (
            db.query(LLMProvider)
            .filter(LLMProvider.status == "active", LLMProvider.organization_id == org_id)
            .first()
        )
        if not provider:
            return None
        mappings = (
            db.query(LLMAgentMapping)
            .filter(LLMAgentMapping.organization_id == org_id)
            .all()
        )
        pid, model, temp, max_tokens = resolve_routing(
            "bmad-agent",
            provider.id,
            provider.default_model,
            mappings,
        )
        provider_obj = db.query(LLMProvider).filter(LLMProvider.id == pid).first()
        if not provider_obj or not provider_obj.secrets:
            return None
        secret = max(provider_obj.secrets, key=lambda s: s.key_version)
        return {
            "provider_type": provider_obj.provider_type,
            "model": model,
            "api_key": decrypt_value(secret.encrypted_api_key),
            "base_url": provider_obj.base_url,
            "temperature": float(temp or provider_obj.temperature or 0.7),
            "timeout": float(provider_obj.timeout or 60),
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("Provider lookup raised for org=%s: %s", org_id, exc)
        return None
    finally:
        db.close()


def _try_pydantic_ai(
    *,
    agent: BMADAgent,
    skill: BMADSkill,
    system_prompt: str,
    user_prompt: str,
    output_model: type[BaseModel],
    org_id: str | None,
) -> tuple[BaseModel | None, str | None]:
    """Try PydanticAI transport. Returns (parsed_model, raw_markdown) or (None, None)."""
    if not pydantic_ai_available():
        return None, None

    provider_info = _resolve_provider_for_org(org_id)
    if not provider_info:
        return None, None

    parsed = call_pydantic_ai(
        agent_name=agent.code,
        provider_type=provider_info["provider_type"],
        model=provider_info["model"],
        api_key=provider_info["api_key"],
        base_url=provider_info.get("base_url"),
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        output_model=output_model,
        temperature=provider_info.get("temperature", 0.7),
        timeout=provider_info.get("timeout", 60.0),
    )
    if parsed is None:
        return None, None
    return parsed, _model_to_markdown(parsed, agent=agent, skill=skill)


def _try_httpx(
    *,
    agent: BMADAgent,
    skill: BMADSkill,
    system_prompt: str,
    user_prompt: str,
    org_id: str | None,
) -> str | None:
    """Try the httpx-backed call_llm transport. Returns raw markdown or None."""
    try:
        llm_dict = call_llm(agent.code, system_prompt, user_prompt, org_id=org_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("httpx transport raised for %s/%s: %s", agent.code, skill.name, exc)
        return None
    if llm_dict is None:
        return None
    return _wrap_as_markdown(llm_dict, agent=agent, skill=skill)


# ── Public API ──────────────────────────────────────────────────────


def execute_agent_skill(
    *,
    agent_code: str,
    skill_name: str,
    project_id: str,
    requirement_text: str,
    output_model: type[BaseModel],
    upstream_agents: list[str] | None = None,
    org_id: str | None = None,
    artifact_filename: str | None = None,
    correlation_id: str | None = None,
) -> AgentRunResult:
    """Run one BMAD agent+skill end-to-end and return the artifact + parsed metadata.

    Transport order is controlled by `HELIX_LLM_TRANSPORT` (comma-separated:
    `pydantic_ai`, `httpx`, `mock`; default `pydantic_ai,httpx,mock`).

    `correlation_id` propagates the request-id from the HTTP layer through
    Temporal into the artifact frontmatter + Prometheus metric labels for
    end-to-end traceability. Pass the same value across all 13 nodes in one
    workflow run.
    """
    upstream_agents = upstream_agents or []

    with timed_run(agent_code=agent_code, skill=skill_name) as metric_ctx:
        result = _execute_agent_skill_inner(
            agent_code=agent_code,
            skill_name=skill_name,
            project_id=project_id,
            requirement_text=requirement_text,
            output_model=output_model,
            upstream_agents=upstream_agents,
            org_id=org_id,
            artifact_filename=artifact_filename,
            correlation_id=correlation_id,
            metric_ctx=metric_ctx,
        )
    return result


def _execute_agent_skill_inner(
    *,
    agent_code: str,
    skill_name: str,
    project_id: str,
    requirement_text: str,
    output_model: type[BaseModel],
    upstream_agents: list[str],
    org_id: str | None,
    artifact_filename: str | None,
    correlation_id: str | None,
    metric_ctx,
) -> AgentRunResult:
    try:
        agent = load_bmad_agent(agent_code)
        skill = load_bmad_skill(skill_name)
    except FileNotFoundError as exc:
        logger.error("BMAD load failed (corr_id=%s): %s", correlation_id, exc)
        metric_ctx.set_outcome(success=False, mode="error")
        return AgentRunResult(success=False, artifact=None, parsed=None, raw_text="", mode="error", errors=[str(exc)])

    prior_context = collect_prior_context(project_id, upstream_agents=upstream_agents) if upstream_agents else []

    # Budget allocation — keep prompt within HELIX_PROMPT_TOKEN_BUDGET tokens.
    persona_chars = len(build_persona_prompt(agent))
    raw_skill_body = build_skill_instructions(skill)
    output_schema_chars = sum(len(str(f.annotation)) for f in output_model.model_fields.values()) + 200
    skill_max, artifact_max = _allocate_prompt_budget(
        output_schema_chars=output_schema_chars,
        persona_chars=persona_chars,
        skill_body_chars=len(raw_skill_body),
        requirement_chars=len(requirement_text or ""),
        upstream_count=len(prior_context),
    )

    system_prompt = _build_system_prompt(agent, skill, output_model, skill_body_chars=skill_max)
    user_prompt = _build_user_prompt(
        project_id=project_id,
        requirement_text=requirement_text,
        prior_context=prior_context,
        artifact_chars_per_item=artifact_max,
    )

    prompt_tokens_estimate = _estimate_tokens(system_prompt) + _estimate_tokens(user_prompt)
    logger.info(
        "BMAD prompt budget corr_id=%s agent=%s skill=%s tokens~%d (budget=%d) skill_body=%d artifacts=%d×%d",
        correlation_id,
        agent_code,
        skill_name,
        prompt_tokens_estimate,
        _token_budget(),
        skill_max,
        len(prior_context),
        artifact_max,
    )

    raw_text = ""
    mode = "mock"
    parsed_from_typed_call: BaseModel | None = None

    for transport in _transport_order():
        if transport == "pydantic_ai":
            typed_parsed, typed_raw = _try_pydantic_ai(
                agent=agent,
                skill=skill,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                output_model=output_model,
                org_id=org_id,
            )
            if typed_raw:
                parsed_from_typed_call = typed_parsed
                raw_text = typed_raw
                mode = "pydantic_ai"
                break
        elif transport == "httpx":
            httpx_raw = _try_httpx(
                agent=agent,
                skill=skill,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                org_id=org_id,
            )
            if httpx_raw:
                raw_text = httpx_raw
                mode = "httpx"
                break
        elif transport == "mock":
            raw_text = _build_mock_markdown(
                agent=agent,
                skill=skill,
                output_model=output_model,
                requirement_text=requirement_text,
                project_id=project_id,
            )
            mode = "mock"
            break

    if not raw_text:
        # Last-resort: force mock so the workflow doesn't stall.
        raw_text = _build_mock_markdown(
            agent=agent,
            skill=skill,
            output_model=output_model,
            requirement_text=requirement_text,
            project_id=project_id,
        )
        mode = "mock"

    if parsed_from_typed_call is not None:
        parsed: BaseModel | None = parsed_from_typed_call
        errors: list[str] = []
    else:
        parsed, errors = _parse_metadata(raw_text, output_model)

    if parsed is None and mode != "mock":
        logger.warning("Real LLM output failed parse for %s — falling back to mock. errors=%s", agent_code, errors)
        raw_text = _build_mock_markdown(
            agent=agent,
            skill=skill,
            output_model=output_model,
            requirement_text=requirement_text,
            project_id=project_id,
        )
        mode = "mock"
        parsed, errors = _parse_metadata(raw_text, output_model)

    if parsed is None:
        metric_ctx.set_outcome(success=False, mode=mode, prompt_tokens=prompt_tokens_estimate)
        return AgentRunResult(success=False, artifact=None, parsed=None, raw_text=raw_text, mode=mode, errors=errors)

    front, body = _split_markdown(raw_text)
    artifact = write_artifact(
        project_id=project_id,
        agent_code=agent_code,
        skill=skill_name,
        filename=artifact_filename or skill_name.replace("bmad-", ""),
        body=body,
        frontmatter={
            **front,
            "llm_mode": mode,
            "pydantic_ai_available": pydantic_ai_available(),
            "prompt_tokens_estimate": prompt_tokens_estimate,
            "prompt_token_budget": _token_budget(),
            "correlation_id": correlation_id,
        },
    )

    metric_ctx.set_outcome(success=True, mode=mode, prompt_tokens=prompt_tokens_estimate)

    # Cost recording — best-effort estimate from prompt + response length.
    # Vendor `usage` blocks would be more accurate; pluggable via provider
    # adapters later. Skipped for `mock` mode (no real LLM call happened).
    if mode != "mock" and org_id:
        _record_agent_cost(
            org_id=org_id,
            project_id=project_id,
            agent_code=agent_code,
            mode=mode,
            input_tokens=prompt_tokens_estimate,
            output_tokens=max(1, _estimate_tokens(raw_text)),
        )

    return AgentRunResult(
        success=True,
        artifact=artifact,
        parsed=parsed,
        raw_text=raw_text,
        mode=mode,
        errors=[],
    )


def _record_agent_cost(
    *,
    org_id: str,
    project_id: str,
    agent_code: str,
    mode: str,
    input_tokens: int,
    output_tokens: int,
) -> None:
    """Persist one LLMUsageRecord row for this agent call.

    Best-effort: resolves the org's active provider + this agent's model
    mapping, then calls cost_service.record_usage. Opens its own DB session
    (worker-local preferred) so it works from both backend and worker
    Temporal activities. Silent on failure — cost recording must never
    block the workflow.
    """
    SessionLocal = None
    try:
        from worker.db.session import SessionLocal as _W  # type: ignore
        SessionLocal = _W
    except Exception:
        try:
            from app.db.session import SessionLocal as _A  # type: ignore
            SessionLocal = _A
        except Exception:
            return
    try:
        from app.models.llm import LLMProvider, LLMAgentMapping
        from app.services.llm_router_service import resolve_routing
        from app.services.cost_service import record_usage
    except Exception:
        return

    db = SessionLocal()
    try:
        provider = (
            db.query(LLMProvider)
            .filter(LLMProvider.organization_id == org_id, LLMProvider.status == "active")
            .first()
        )
        if not provider:
            return
        mappings = db.query(LLMAgentMapping).filter(LLMAgentMapping.organization_id == org_id).all()
        pid, model, _t, _m = resolve_routing(agent_code, provider.id, provider.default_model, mappings)
        target = db.query(LLMProvider).filter(LLMProvider.id == pid).first() or provider
        record_usage(
            db,
            organization_id=org_id,
            provider_type=target.provider_type,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            project_id=project_id,
            agent_name=agent_code,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Cost recording failed for agent=%s: %s", agent_code, exc)
    finally:
        db.close()
