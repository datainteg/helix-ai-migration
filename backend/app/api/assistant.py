"""Ask Helix — in-app assistant chat.

A lightweight chat endpoint backing the "Ask Helix" popup. Uses the org's
configured LLM provider via the shared call_llm transport. Non-mutating (it
reads nothing it shouldn't and writes no domain data), so it's allowlisted for
read-only demo sessions in main.py.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_organization_id
from app.auth.jwt import get_current_user_id
from app.db.session import get_db

router = APIRouter(tags=["assistant"])

_SYSTEM = (
    "You are the Helix Help agent — a friendly in-app guide whose only job is to teach users "
    "how Helix works and walk them through using it. You answer inside a small chat popup, so "
    "keep replies short, scannable, and warm.\n\n"
    "WHAT HELIX IS: an open-source, self-hosted, AI-powered platform that plans, generates, "
    "validates, and reconciles enterprise database migrations (e.g. Oracle → Snowflake, "
    "Postgres → BigQuery).\n\n"
    "THE GOLDEN PATH (guide users along this):\n"
    "1. Create a Project (**Projects → New**).\n"
    "2. Connect a source and a target database (**Connectors**, or the project's **Source & "
    "Target** tab) — enter credentials, click **Test**, then **Save**.\n"
    "3. Open the project's **Migration** tab and click **Generate Migration**. The AI agent "
    "chain runs: **SchemaAnalyst** (introspects the source schema) → **TypeMapper** (maps source "
    "types to the target dialect, flagging lossy/ambiguous cases) → a human **Approval** gate → "
    "**ScriptGenerator** (writes target DDL + data-migration + rollback SQL) → **Reconciler** "
    "(row-count/checksum reconciliation).\n"
    "4. Review the live steps, the generated artifacts, and the reconciliation report (a "
    "**verified %**).\n\n"
    "KEY CONCEPTS:\n"
    "- Migrations are **dry-run by default** (SAFE_EXECUTION_MODE=analysis_only) — Helix "
    "generates scripts; it does not execute against your target unless execution is explicitly "
    "enabled.\n"
    "- LLM providers are configured per-organization in **Admin → LLM settings**.\n"
    "- A read-only **Demo user** (the **Login with Demo User** button) loads a fully-seeded "
    "sample migration so people can explore without an account.\n"
    "- Reconciliation/validation are how Helix proves the migration moved data correctly.\n"
    "- Sign out from the **sidebar footer**.\n\n"
    "HOW TO ANSWER:\n"
    "- Format every reply in clean, concise markdown so it renders well in the chat popup: use "
    "**bold** for exact UI labels (page names, tabs, buttons), numbered steps for any procedure, "
    "single-sentence bullets for lists, and short paragraphs. Never produce a wall of text.\n"
    "- Default to brief: 1–3 sentences or a short numbered list. Expand only when the user asks "
    "for detail.\n"
    "- Ground every answer in the facts above. Do NOT invent features, settings, pages, buttons, "
    "integrations, or behavior that aren't described here. If you don't know or Helix doesn't "
    "appear to support it, say so plainly and suggest the closest thing that does exist.\n"
    "- If the request is ambiguous, prefer to answer with a reasonable default and note the "
    "assumption; only ask ONE short clarifying question when you genuinely cannot proceed.\n"
    "- End any actionable/procedural answer with a concrete next step — the exact page, tab, or "
    "button to go to next (e.g. \"Next: open the **Migration** tab and click **Generate "
    "Migration**.\").\n"
    "- Stay on Helix. If asked something unrelated, briefly redirect back to what you can help "
    "with."
)


class ChatTurn(BaseModel):
    role: str = Field(default="user")
    content: str = Field(default="", max_length=4000)


class AskRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    history: list[ChatTurn] = Field(default_factory=list)


class AskResponse(BaseModel):
    answer: str


@router.post("/assistant/ask", response_model=AskResponse)
def ask_helix(
    data: AskRequest,
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    from agents.runtime.llm_client import call_llm

    convo = ""
    for turn in (data.history or [])[-6:]:
        if turn.content.strip():
            convo += f"\n{turn.role.upper()}: {turn.content.strip()}"
    user_prompt = (convo + f"\nUSER: {data.message.strip()}").strip()

    result = call_llm("assistant", _SYSTEM, user_prompt, org_id=org_id)
    if not result:
        return AskResponse(
            answer=(
                "The assistant is unavailable — no LLM provider is configured for this "
                "organization. An admin can add one under Admin → LLM settings."
            )
        )
    if isinstance(result, dict):
        answer = result.get("answer") or result.get("summary") or result.get("text") or ""
        if not answer:
            answer = next((v for v in result.values() if isinstance(v, str) and v.strip()), "")
    else:
        answer = str(result)
    return AskResponse(answer=answer.strip() or "I didn't get a response from the model — please try again.")


class AskProjectRequest(BaseModel):
    project_id: str = Field(..., min_length=1, max_length=36)
    message: str = Field(..., min_length=1, max_length=4000)
    history: list[ChatTurn] = Field(default_factory=list)


@router.post("/assistant/ask-project", response_model=AskResponse)
def ask_helix_project(
    data: AskProjectRequest,
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Project-aware orchestrator agent — answers questions about ONE project,
    grounded in its real status, workflow/agent runs, artifacts, and recon/
    validation. Read-only. Backed by a LangGraph graph (project_orchestrator)."""
    from app.services.project_service import ensure_project_access
    ensure_project_access(db, org_id, data.project_id)  # 403/404 if not in org

    from agents.runtime.project_orchestrator import ask_project
    history = [{"role": t.role, "content": t.content} for t in (data.history or [])]
    answer = ask_project(data.project_id, org_id, data.message.strip(), history)
    return AskResponse(answer=answer)
