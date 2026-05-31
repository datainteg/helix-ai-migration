"""Project-aware orchestrator agent ("Ask Helix about this project").

A small in-process LangGraph that answers questions about ONE project, grounded
in that project's real data:

    gather_context → select_artifacts → read_artifacts → answer

- gather_context : project summary + live workflow step status + artifact index
                   + recent comments (pure DB reads; no artifact bodies yet).
- select_artifacts: pick the 1–3 artifacts most relevant to the question
                   (LLM router with a heuristic "latest-N" fallback).
- read_artifacts : read the chosen artifact files (allowlist-guarded) and
                   truncate to fit the prompt token budget.
- answer         : call_llm("assistant-project", …) grounded on everything above.

Strictly grounded: the system prompt forbids inventing project facts. No RAG —
context is fetched + stuffed directly. Every node degrades gracefully.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Hard caps so a chatty project can't blow the prompt budget.
_MAX_ARTIFACTS = 3
_PER_ARTIFACT_CHARS = 6000
_INDEX_LIMIT = 25


# --------------------------------------------------------------------------- #
# Helpers (sync DB reads — the graph runs synchronously in the API process).
# --------------------------------------------------------------------------- #

def _safe_truncate(text: str, max_chars: int, label: str = "section") -> str:
    try:
        from agents.runtime.bmad_executor import _truncate_smart
        return _truncate_smart(text, max_chars, label=label)
    except Exception:
        return text[:max_chars]


def _session():
    try:
        from worker.db.session import SessionLocal  # worker context
    except Exception:
        from app.db.session import SessionLocal      # FastAPI context
    return SessionLocal()


def _gather_context(project_id: str, org_id: str) -> dict:
    """Compact, grounded snapshot of the project. Never raises — returns
    whatever it could read."""
    from app.models.project import Project, ProjectComment, SchemaMetadata, TableMetadata
    from app.models.workflow import WorkflowRun, WorkflowStep
    from app.models.validation import ValidationResult, ValidationRun, ReconResult, ReconRun
    from sqlalchemy import func

    ctx: dict[str, Any] = {"artifact_index": []}
    db = _session()
    try:
        p = db.query(Project).filter(Project.id == project_id, Project.organization_id == org_id).first()
        if not p:
            ctx["error"] = "project_not_found"
            return ctx
        src = p.source_connections[0].connector_type if p.source_connections else None
        tgt = p.target_connections[0].connector_type if p.target_connections else None
        ctx["project"] = {
            "name": p.name, "description": p.description, "status": p.status,
            "on_hold": bool(getattr(p, "on_hold", False)),
            "risk_level": p.risk_level, "environment": getattr(p, "environment", None),
            "source": src, "target": tgt,
        }

        # table / schema counts
        schema_ids = [s.id for s in db.query(SchemaMetadata.id).filter(SchemaMetadata.project_id == project_id).all()]
        ctx["schema_count"] = len(schema_ids)
        ctx["table_count"] = (
            db.query(func.count(TableMetadata.id)).filter(TableMetadata.schema_id.in_(schema_ids)).scalar()
            if schema_ids else 0
        )

        # validation / recon %
        def _pct(model, run_model, run_fk, ok_filter):
            total = db.query(func.count(model.id)).join(run_model, run_fk).filter(run_model.project_id == project_id).scalar() or 0
            ok = db.query(func.count(model.id)).join(run_model, run_fk).filter(run_model.project_id == project_id, ok_filter).scalar() or 0
            return round(ok / total * 100, 1) if total else None, total
        ctx["validation_pct"], ctx["validation_total"] = _pct(
            ValidationResult, ValidationRun, ValidationResult.run_id == ValidationRun.id, ValidationResult.status == "passed")
        ctx["recon_pct"], ctx["recon_total"] = _pct(
            ReconResult, ReconRun, ReconResult.run_id == ReconRun.id, ReconResult.mismatch_count == 0)

        # latest workflow run + live step status
        run = (
            db.query(WorkflowRun)
            .filter(WorkflowRun.project_id == project_id)
            .order_by(WorkflowRun.created_at.desc())
            .first()
        )
        if run:
            steps = (
                db.query(WorkflowStep)
                .filter(WorkflowStep.workflow_run_id == run.id)
                .order_by(WorkflowStep.step_order)
                .all()
            )
            ctx["latest_run"] = {
                "workflow_id": run.workflow_id, "status": run.status, "kind": run.kind or "bmad",
                "created_at": str(run.created_at) if run.created_at else None,
                "steps": [{"agent": s.agent_name, "order": s.step_order, "status": s.status,
                           "error": s.error_message} for s in steps],
            }
            # artifact index from step rows
            idx = []
            for s in steps:
                ap = None
                payload = s.parsed_output_json if isinstance(s.parsed_output_json, dict) else None
                if payload:
                    paths = payload.get("artifact_paths") or payload.get("artifact_path")
                    ap = paths[-1] if isinstance(paths, list) and paths else (paths if isinstance(paths, str) else None)
                if ap:
                    idx.append({"agent": s.agent_name, "order": s.step_order,
                                "path": ap, "title": os.path.basename(ap)})
            ctx["artifact_index"] = idx[:_INDEX_LIMIT]
        else:
            ctx["latest_run"] = None

        # recent comments
        comments = (
            db.query(ProjectComment)
            .filter(ProjectComment.project_id == project_id)
            .order_by(ProjectComment.created_at.desc())
            .limit(5).all()
        )
        ctx["comments"] = [{"kind": c.kind, "author": c.author_name, "body": c.body,
                            "at": str(c.created_at) if c.created_at else None} for c in comments]
    except Exception as exc:  # noqa: BLE001
        logger.warning("project orchestrator gather_context failed: %s", exc)
    finally:
        db.close()
    return ctx


def _artifact_allowed(path: str) -> bool:
    try:
        from app.api.agent_workflows import _artifact_path_is_allowed
        return _artifact_path_is_allowed(path)
    except Exception:
        return False


def _select_artifacts(message: str, index: list[dict], org_id: str) -> list[str]:
    """Pick 1–3 artifact paths most relevant to the question. LLM router with a
    'latest by step order' heuristic fallback."""
    if not index:
        return []
    latest = [a["path"] for a in sorted(index, key=lambda a: a.get("order", 0), reverse=True)][:_MAX_ARTIFACTS]
    try:
        from agents.runtime.llm_client import call_llm
        listing = "\n".join(f"{i}. {a['agent']} — {a['title']}" for i, a in enumerate(index))
        sys = ("You pick which migration artifacts to read to answer a question. "
               "Reply with ONLY a comma-separated list of the item numbers (max 3), most relevant first.")
        usr = f"QUESTION: {message}\n\nARTIFACTS:\n{listing}\n\nNumbers:"
        res = call_llm("assistant-project-router", sys, usr, org_id=org_id)
        raw = ""
        if isinstance(res, dict):
            raw = res.get("answer") or res.get("summary") or res.get("text") or next((v for v in res.values() if isinstance(v, str)), "")
        nums = [int(x) for x in __import__("re").findall(r"\d+", str(raw))][:_MAX_ARTIFACTS]
        picked = [index[n]["path"] for n in nums if 0 <= n < len(index)]
        return picked or latest
    except Exception as exc:  # noqa: BLE001
        logger.debug("artifact selection fell back to latest-N: %s", exc)
        return latest


def _read_artifacts(paths: list[str]) -> list[dict]:
    out = []
    for path in paths[:_MAX_ARTIFACTS]:
        if not _artifact_allowed(path) or not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            out.append({"title": os.path.basename(path),
                        "content": _safe_truncate(content, _PER_ARTIFACT_CHARS, label="artifact")})
        except Exception:  # noqa: BLE001
            continue
    return out


# --------------------------------------------------------------------------- #
# Prompt assembly + answer
# --------------------------------------------------------------------------- #

_SYSTEM = (
    "You are the Helix project orchestrator — an expert assistant for ONE specific data-migration "
    "project. You have visibility into the project's status, its AI agent pipeline runs (with live "
    "per-step status), the artifacts those agents produced, reconciliation/validation outcomes, and "
    "the activity timeline. Answer questions about THIS project clearly and concretely, in markdown.\n\n"
    "STRICT GROUNDING: Use ONLY the PROJECT CONTEXT and ARTIFACTS provided below. Never invent runs, "
    "statuses, tables, or results. If the data needed to answer isn't present (e.g. no workflow has run "
    "yet), say so plainly and suggest the next step (e.g. start a workflow from the project). Be concise; "
    "use bold for key facts, short bullets/steps, and reference the relevant agent/artifact by name."
)


def _render_context(ctx: dict) -> str:
    if ctx.get("error") == "project_not_found":
        return "PROJECT CONTEXT: (project not found / no access)"
    p = ctx.get("project", {})
    lines = ["PROJECT CONTEXT", f"- Name: {p.get('name')}", f"- Status: {p.get('status')}"
             + (" (ON HOLD)" if p.get("on_hold") else ""),
             f"- Source → Target: {p.get('source') or '?'} → {p.get('target') or '?'}",
             f"- Environment: {p.get('environment') or '—'} · Risk: {p.get('risk_level') or '—'}",
             f"- Schemas: {ctx.get('schema_count', 0)} · Tables: {ctx.get('table_count', 0)}"]
    vp, vt = ctx.get("validation_pct"), ctx.get("validation_total", 0)
    rp, rt = ctx.get("recon_pct"), ctx.get("recon_total", 0)
    lines.append(f"- Validation: {vp}% pass ({vt} results)" if vt else "- Validation: no runs yet")
    lines.append(f"- Reconciliation: {rp}% clean ({rt} results)" if rt else "- Reconciliation: no runs yet")
    if p.get("description"):
        lines.append(f"- Description: {p['description']}")

    run = ctx.get("latest_run")
    if run:
        lines.append(f"\nLATEST WORKFLOW RUN: {run['workflow_id']} — status={run['status']} (kind={run['kind']})")
        for s in run.get("steps", []):
            err = f" — ERROR: {s['error']}" if s.get("error") else ""
            lines.append(f"  • {s['agent']} (step {s['order']}): {s['status']}{err}")
    else:
        lines.append("\nLATEST WORKFLOW RUN: none — no agent pipeline has run for this project yet.")

    idx = ctx.get("artifact_index", [])
    if idx:
        lines.append("\nARTIFACTS PRODUCED:")
        for a in idx:
            lines.append(f"  • {a['agent']}: {a['title']}")
    if ctx.get("comments"):
        lines.append("\nRECENT ACTIVITY:")
        for c in ctx["comments"]:
            tag = "" if c["kind"] == "comment" else f"[{c['kind']}] "
            lines.append(f"  • {tag}{c.get('author') or 'system'}: {c['body']}")
    return "\n".join(lines)


def _build_user_prompt(message: str, ctx: dict, artifacts: list[dict], history: list[dict]) -> str:
    parts = [_render_context(ctx)]
    if artifacts:
        parts.append("\nARTIFACT CONTENTS:")
        for a in artifacts:
            parts.append(f"\n--- {a['title']} ---\n{a['content']}")
    convo = ""
    for turn in (history or [])[-6:]:
        role = turn.get("role"); content = turn.get("content")
        if role and content:
            convo += f"\n{role.upper()}: {content}"
    parts.append(f"\nCONVERSATION:{convo}\nUSER: {message}")
    return "\n".join(parts)


# --------------------------------------------------------------------------- #
# LangGraph wiring
# --------------------------------------------------------------------------- #

_compiled = None


def _build_graph():
    from langgraph.graph import StateGraph, END

    def gather(state: dict) -> dict:
        state["ctx"] = _gather_context(state["project_id"], state["org_id"])
        return state

    def select(state: dict) -> dict:
        state["picked_paths"] = _select_artifacts(
            state["message"], state["ctx"].get("artifact_index", []), state["org_id"])
        return state

    def read(state: dict) -> dict:
        state["artifacts"] = _read_artifacts(state.get("picked_paths", []))
        return state

    def answer(state: dict) -> dict:
        from agents.runtime.llm_client import call_llm
        user_prompt = _build_user_prompt(state["message"], state["ctx"], state.get("artifacts", []), state.get("history", []))
        res = call_llm("assistant-project", _SYSTEM, user_prompt, org_id=state["org_id"])
        if not res:
            state["answer"] = ("The project assistant is unavailable — no LLM provider is configured for "
                               "this organization. An admin can add one under Admin → LLM settings.")
            return state
        if isinstance(res, dict):
            ans = res.get("answer") or res.get("summary") or res.get("text") or ""
            if not ans:
                ans = next((v for v in res.values() if isinstance(v, str) and v.strip()), "")
        else:
            ans = str(res)
        state["answer"] = ans.strip() or "I couldn't generate an answer — please try rephrasing."
        return state

    g = StateGraph(dict)
    g.add_node("gather", gather)
    g.add_node("select", select)
    g.add_node("read", read)
    g.add_node("answer", answer)
    g.set_entry_point("gather")
    g.add_edge("gather", "select")
    g.add_edge("select", "read")
    g.add_edge("read", "answer")
    g.add_edge("answer", END)
    return g.compile()


def ask_project(project_id: str, org_id: str, message: str, history: Optional[list[dict]] = None) -> str:
    """Run the orchestrator graph and return a grounded markdown answer."""
    global _compiled
    if _compiled is None:
        _compiled = _build_graph()
    try:
        final = _compiled.invoke({
            "project_id": project_id, "org_id": org_id,
            "message": message, "history": history or [],
        })
        return final.get("answer") or "No answer."
    except Exception as exc:  # noqa: BLE001
        logger.exception("project orchestrator failed")
        return f"Sorry — I hit an error answering that ({type(exc).__name__}). Please try again."
