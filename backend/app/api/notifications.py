"""In-app notifications API.

REST list / unread-count / mark-read for the notification bell, an admin rules
surface, and an SSE stream for live delivery (the bell polls unread-count by
default; the stream is available for live push).
"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.auth.dependencies import require_permission, resolve_active_org_id
from app.auth.jwt import get_current_user_id
from app.api.audit import write_audit
from app.services import notification_service as ns

router = APIRouter(tags=["notifications"])


def _notif_dict(n) -> dict:
    return {
        "id": n.id,
        "type": n.type,
        "severity": n.severity,
        "title": n.title,
        "body": n.body,
        "link": n.link,
        "read": n.read_at is not None,
        "created_at": n.created_at.isoformat() if n.created_at else None,
    }


@router.get("/notifications")
def get_notifications(
    unread: bool = False,
    limit: int = 50,
    offset: int = 0,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    org_id = resolve_active_org_id(db, user_id)
    rows = ns.list_notifications(db, org_id, user_id, unread_only=unread, limit=limit, offset=offset)
    return [_notif_dict(n) for n in rows]


@router.get("/notifications/unread-count")
def get_unread_count(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    org_id = resolve_active_org_id(db, user_id)
    return {"count": ns.unread_count(db, org_id, user_id)}


@router.post("/notifications/{notification_id}/read")
def post_mark_read(
    notification_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    org_id = resolve_active_org_id(db, user_id)
    if not ns.mark_read(db, org_id, user_id, notification_id):
        raise HTTPException(status_code=404, detail="notification not found")
    return {"ok": True}


@router.post("/notifications/read-all")
def post_mark_all_read(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    org_id = resolve_active_org_id(db, user_id)
    n = ns.mark_all_read(db, org_id, user_id)
    return {"marked": n}


# ----------------------------------- rules -----------------------------------

class RuleUpdate(BaseModel):
    enabled: bool = True
    threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    channels: str = Field(default="in_app")  # csv: in_app[,email]


@router.get("/notifications/rules")
def get_rules(
    user_id: str = Depends(require_permission("admin:llm:read")),
    db: Session = Depends(get_db),
):
    org_id = resolve_active_org_id(db, user_id)
    return ns.list_rules(db, org_id)


@router.put("/notifications/rules/{event_type}")
def put_rule(
    event_type: str,
    data: RuleUpdate,
    request: Request,
    user_id: str = Depends(require_permission("admin:llm:write")),
    db: Session = Depends(get_db),
):
    org_id = resolve_active_org_id(db, user_id)
    # Sanitise channels to the allowed set.
    chans = ",".join(c for c in (data.channels or "").split(",") if c.strip() in ("in_app", "email")) or "in_app"
    row = ns.upsert_rule(db, org_id, event_type, enabled=data.enabled, threshold=data.threshold, channels=chans)
    write_audit(db, org_id=org_id, actor_id=user_id, action="notification_rule_updated",
                entity_type="notification_rule", entity_id=event_type,
                meta=row, request=request)
    return row


# ----------------------------------- stream ----------------------------------

@router.get("/notifications/stream")
async def stream_notifications(request: Request, token: str):
    """SSE stream of unread-count updates. Auth via a scope=sse ticket minted
    by POST /auth/sse-ticket (same pattern as the sprint execution stream)."""
    from app.auth.jwt import decode_access_token_async, sse_ticket_binding_ok
    from app.utils.client_ip import get_client_ip
    from app.db.session import SessionLocal

    auth_db = SessionLocal()
    try:
        try:
            payload = await decode_access_token_async(token)
            user_id = payload.get("sub")
            if not user_id:
                raise ValueError("missing sub")
            if payload.get("scope") != "sse":
                raise ValueError("token is not an sse ticket")
            if not sse_ticket_binding_ok(token, get_client_ip(request), request.headers.get("user-agent")):
                raise ValueError("sse ticket client mismatch")
            org_id = resolve_active_org_id(auth_db, user_id)
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid stream token")
    finally:
        auth_db.close()

    token_exp = payload.get("exp")

    async def gen():
        import time
        last = -1
        while True:
            if await request.is_disconnected():
                break
            if token_exp and time.time() >= token_exp:
                break
            tick_db = SessionLocal()
            try:
                count = ns.unread_count(tick_db, org_id, user_id)
            finally:
                tick_db.close()
            if count != last:
                last = count
                yield f"data: {json.dumps({'unread': count})}\n\n"
            await asyncio.sleep(10)

    return StreamingResponse(gen(), media_type="text/event-stream")
