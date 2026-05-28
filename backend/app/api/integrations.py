"""Inbound integrations — currently Slack slash-command receiver.

Slack flow:
  /helix approve <workflow_id> [notes]   →  POST signal-approve
  /helix reject  <workflow_id> [notes]   →  POST signal-reject
  /helix status  <workflow_id>           →  Return workflow status (ephemeral)

Setup:
  1. Create a Slack app, enable Slash Commands, point /helix at
     POST https://<your-host>/api/v1/integrations/slack/command
  2. Copy the Signing Secret into SLACK_SIGNING_SECRET in .env.
  3. Map each Slack user_id to a Helix user_id in slack_user_map.json
     OR set HELIX_SLACK_DEFAULT_USER=<helix_user_id> for a single
     service-account fallback.

Security:
  - Slack-signed (HMAC-SHA256 of `v0:{timestamp}:{body}` with the signing
    secret) — request rejected if signature fails or timestamp is stale.
  - The mapped Helix user must have admin:llm:write permission for the
    target workflow's org. The endpoint does NOT impersonate; it acts as
    the mapped user.

This module degrades gracefully when SLACK_SIGNING_SECRET is unset — the
endpoint replies 503 so an accidental routing config does not look like a
silent success.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.workflow import WorkflowRun
from app.services.workflow_service import update_workflow_run_status
from app.api.audit import write_audit
from app.auth.dependencies import user_has_permission, resolve_active_membership

router = APIRouter(tags=["integrations"])
logger = logging.getLogger(__name__)


_MAX_TIMESTAMP_SKEW_SEC = 60 * 5  # Slack docs: reject anything older than 5 min.


def _verify_slack_signature(secret: str, body: bytes, timestamp: str, signature: str) -> bool:
    """HMAC verify the inbound request. Constant-time compare."""
    try:
        ts = int(timestamp)
    except (TypeError, ValueError):
        return False
    if abs(time.time() - ts) > _MAX_TIMESTAMP_SKEW_SEC:
        return False
    # SC-033: HMAC the RAW request bytes, not a `decode(errors="replace")`
    # round-trip. Slack signs the exact bytes it sent; decoding with the
    # replacement char and re-encoding would diverge from Slack's basestring
    # for any non-UTF-8 byte (silently rejecting legit traffic) and is a
    # subtle protocol mismatch. Build the basestring as bytes directly.
    basestring = b"v0:" + timestamp.encode("ascii", "ignore") + b":" + body
    digest = hmac.new(secret.encode(), basestring, hashlib.sha256).hexdigest()
    expected = f"v0={digest}"
    return hmac.compare_digest(expected, signature or "")


def _load_user_map() -> dict[str, str]:
    """Lazy load slack_user_id → helix_user_id map (JSON file or env)."""
    path = os.getenv("HELIX_SLACK_USER_MAP", "")
    if path and os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to read slack user map at %s: %s", path, exc)
    return {}


def _resolve_user(slack_user_id: str) -> Optional[str]:
    mapping = _load_user_map()
    return mapping.get(slack_user_id) or os.getenv("HELIX_SLACK_DEFAULT_USER") or None


@router.post("/integrations/slack/command")
async def slack_command(request: Request):
    from app.db.session import SessionLocal

    secret = os.getenv("SLACK_SIGNING_SECRET", "")
    if not secret:
        raise HTTPException(status_code=503, detail="Slack integration not configured (SLACK_SIGNING_SECRET unset)")

    body = await request.body()
    if not _verify_slack_signature(
        secret,
        body,
        request.headers.get("X-Slack-Request-Timestamp", ""),
        request.headers.get("X-Slack-Signature", ""),
    ):
        raise HTTPException(status_code=401, detail="Invalid Slack signature")

    # Slash command bodies are application/x-www-form-urlencoded. Use
    # Starlette's built-in form parser (handles `+` → space, repeated keys,
    # multipart boundaries) rather than splitting `&` by hand — the manual
    # form parser dropped values with `=` or `&` inside notes.
    raw_form = await request.form()
    form = {k: str(v) for k, v in raw_form.items()}

    slack_user_id = form.get("user_id", "")
    text = form.get("text", "").strip()
    if not text:
        return {"response_type": "ephemeral", "text": "Usage: `/helix approve|reject|status <workflow_id> [notes]`"}

    parts = text.split(None, 2)
    action = parts[0].lower()
    workflow_id = parts[1] if len(parts) > 1 else ""
    notes = parts[2] if len(parts) > 2 else ""

    if action not in {"approve", "reject", "status"}:
        return {"response_type": "ephemeral", "text": f"Unknown action {action!r}. Use approve / reject / status."}
    if not workflow_id:
        return {"response_type": "ephemeral", "text": "Missing workflow_id."}

    helix_user = _resolve_user(slack_user_id)
    if not helix_user:
        return {
            "response_type": "ephemeral",
            "text": f"Slack user {slack_user_id} is not mapped to a Helix user. Add to HELIX_SLACK_USER_MAP.",
        }

    db: Session = SessionLocal()
    try:
        run = db.query(WorkflowRun).filter(WorkflowRun.workflow_id == workflow_id).first()
        if not run:
            return {"response_type": "ephemeral", "text": f"Workflow {workflow_id} not found."}

        if action == "status":
            return {
                "response_type": "ephemeral",
                "text": f"`{workflow_id}` status: *{run.status}* (mode: {run.mode})",
            }

        # SEC-012: verify the mapped Helix user has `agent:approve` permission
        # AND belongs to the workflow's own organisation.  Both checks must pass
        # before we forward the signal — an attacker with a valid Slack identity
        # but wrong/missing Helix role must not be able to approve any workflow.
        try:
            membership = resolve_active_membership(db, helix_user)
        except Exception:
            return {"response_type": "ephemeral", "text": "Your Helix account has no active organization membership."}

        if membership.organization_id != run.organization_id:
            logger.warning(
                "Slack permission denied: user %s org %s != workflow org %s",
                helix_user, membership.organization_id, run.organization_id,
            )
            raise HTTPException(
                status_code=403,
                detail={
                    "response_type": "ephemeral",
                    "text": "You don't have approval permission in the workflow's organization.",
                },
            )

        if not user_has_permission(db, helix_user, "agent:approve"):
            logger.warning("Slack permission denied: user %s lacks agent:approve", helix_user)
            raise HTTPException(
                status_code=403,
                detail={
                    "response_type": "ephemeral",
                    "text": "You don't have approval permission in the workflow's organization.",
                },
            )

        # Forward the signal via the Temporal client. The endpoint is
        # `async def` so we MUST `await` the inner coroutine — the previous
        # `asyncio.run()` call raised `RuntimeError: asyncio.run() cannot be
        # called from a running event loop` and broke the entire Slack flow.
        from temporalio.client import Client

        async def _signal():
            client = await Client.connect(os.getenv("TEMPORAL_ADDRESS", "localhost:7233"))
            handle = client.get_workflow_handle(workflow_id)
            await handle.signal("approve" if action == "approve" else "reject", notes)

        try:
            await _signal()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Slack signal forward failed for %s: %s", workflow_id, exc)
            return {"response_type": "ephemeral", "text": f"Could not signal workflow: {exc}"}

        update_workflow_run_status(
            db, workflow_id, "approved" if action == "approve" else "rejected",
            organization_id=run.organization_id,
        )
        write_audit(db, org_id=run.organization_id, actor_id=helix_user,
                    action=f"slack_{action}_workflow",
                    entity_type="workflow_run", entity_id=workflow_id,
                    meta={"notes": notes, "slack_user": slack_user_id})

        return {
            "response_type": "in_channel",
            "text": f"<@{slack_user_id}> {action}d workflow `{workflow_id}`" + (f" — {notes}" if notes else ""),
        }
    finally:
        db.close()
