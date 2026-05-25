from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.session import get_db
from app.auth.dependencies import require_permission, resolve_active_org_id
from app.services.secret_service import encrypt_value
from app.security.ssrf import SSRFViolation, validate_external_url
from app.models.webhook import WebhookEndpoint, WebhookDelivery
from app.api.audit import write_audit

router = APIRouter(tags=["webhooks"])


def _resolve_org_id(db: Session, user_id: str) -> str:
    # Delegates to the canonical active-membership resolver so suspended
    # members are correctly rejected (was a stale-membership leak before).
    return resolve_active_org_id(db, user_id)


class WebhookCreate(BaseModel):
    url: str
    secret: str | None = None
    events: str = "*"
    description: str | None = None


@router.get("/webhooks")
def list_webhooks(user_id: str = Depends(require_permission("admin:llm:read")), db: Session = Depends(get_db)):
    org_id = _resolve_org_id(db, user_id)
    hooks = db.query(WebhookEndpoint).filter(WebhookEndpoint.organization_id == org_id).all()
    return [{"id": h.id, "url": h.url, "events": h.events, "is_active": h.is_active, "description": h.description} for h in hooks]


@router.post("/webhooks", status_code=201)
def create_webhook(
    request: Request,
    data: WebhookCreate,
    user_id: str = Depends(require_permission("admin:llm:write")),
    db: Session = Depends(get_db),
):
    org_id = _resolve_org_id(db, user_id)
    try:
        validate_external_url(data.url)
    except SSRFViolation as exc:
        raise HTTPException(status_code=400, detail=f"Invalid webhook URL: {exc}")
    # HMAC signing secret is stored encrypted; the signer decrypts on send.
    encrypted_secret = encrypt_value(data.secret) if data.secret else None
    ep = WebhookEndpoint(
        organization_id=org_id,
        url=data.url,
        secret=encrypted_secret,
        events=data.events,
        description=data.description,
    )
    db.add(ep)
    db.commit()
    db.refresh(ep)
    write_audit(db, org_id=org_id, actor_id=user_id, action="webhook_created",
                entity_type="webhook", entity_id=ep.id,
                meta={"url": data.url, "events": data.events}, request=request)
    return {"id": ep.id, "url": ep.url, "events": ep.events, "is_active": ep.is_active}


@router.patch("/webhooks/{webhook_id}")
def update_webhook(
    request: Request,
    webhook_id: str,
    data: WebhookCreate,
    user_id: str = Depends(require_permission("admin:llm:write")),
    db: Session = Depends(get_db),
):
    org_id = _resolve_org_id(db, user_id)
    ep = db.query(WebhookEndpoint).filter(WebhookEndpoint.id == webhook_id, WebhookEndpoint.organization_id == org_id).first()
    if not ep:
        raise HTTPException(status_code=404, detail="Webhook not found")
    if data.url:
        try:
            validate_external_url(data.url)
        except SSRFViolation as exc:
            raise HTTPException(status_code=400, detail=f"Invalid webhook URL: {exc}")
        ep.url = data.url
    if data.events:
        ep.events = data.events
    if data.secret is not None:
        ep.secret = encrypt_value(data.secret) if data.secret else None
    if data.description is not None:
        ep.description = data.description
    db.commit()
    db.refresh(ep)
    write_audit(db, org_id=org_id, actor_id=user_id, action="webhook_updated",
                entity_type="webhook", entity_id=ep.id, request=request)
    return {"id": ep.id, "url": ep.url, "events": ep.events, "is_active": ep.is_active}


@router.delete("/webhooks/{webhook_id}", status_code=204)
def delete_webhook(
    request: Request,
    webhook_id: str,
    user_id: str = Depends(require_permission("admin:llm:write")),
    db: Session = Depends(get_db),
):
    org_id = _resolve_org_id(db, user_id)
    ep = db.query(WebhookEndpoint).filter(WebhookEndpoint.id == webhook_id, WebhookEndpoint.organization_id == org_id).first()
    if ep:
        db.delete(ep)
        db.commit()
        write_audit(db, org_id=org_id, actor_id=user_id, action="webhook_deleted",
                    entity_type="webhook", entity_id=webhook_id, request=request)


@router.get("/webhooks/{webhook_id}/deliveries")
def list_deliveries(
    webhook_id: str,
    user_id: str = Depends(require_permission("admin:llm:read")),
    db: Session = Depends(get_db),
):
    org_id = _resolve_org_id(db, user_id)
    # Verify the webhook endpoint actually belongs to the caller's org before
    # exposing its delivery history (payload + response_body may contain secrets).
    endpoint = (
        db.query(WebhookEndpoint)
        .filter(
            WebhookEndpoint.id == webhook_id,
            WebhookEndpoint.organization_id == org_id,
        )
        .first()
    )
    if not endpoint:
        raise HTTPException(status_code=404, detail="Webhook not found")

    deliveries = (
        db.query(WebhookDelivery)
        .filter(WebhookDelivery.endpoint_id == webhook_id)
        .order_by(WebhookDelivery.created_at.desc())
        .limit(50)
        .all()
    )
    return [
        {"id": d.id, "event": d.event, "success": d.success, "status_code": d.status_code, "created_at": str(d.created_at)}
        for d in deliveries
    ]
