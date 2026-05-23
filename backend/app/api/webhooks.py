from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, HttpUrl

from app.db.session import get_db
from app.auth.dependencies import require_permission
from app.services.auth_service import get_current_user
from app.models.webhook import WebhookEndpoint, WebhookDelivery

router = APIRouter(tags=["webhooks"])


class WebhookCreate(BaseModel):
    url: str
    secret: str | None = None
    events: str = "*"
    description: str | None = None


@router.get("/webhooks")
def list_webhooks(user_id: str = Depends(require_permission("admin:llm:read")), db: Session = Depends(get_db)):
    user = get_current_user(db, user_id)
    org_id = str(user.memberships[0].organization_id)
    hooks = db.query(WebhookEndpoint).filter(WebhookEndpoint.organization_id == org_id).all()
    return [{"id": h.id, "url": h.url, "events": h.events, "is_active": h.is_active, "description": h.description} for h in hooks]


@router.post("/webhooks", status_code=201)
def create_webhook(
    data: WebhookCreate,
    user_id: str = Depends(require_permission("admin:llm:write")),
    db: Session = Depends(get_db),
):
    user = get_current_user(db, user_id)
    org_id = str(user.memberships[0].organization_id)
    ep = WebhookEndpoint(
        organization_id=org_id,
        url=data.url,
        secret=data.secret,
        events=data.events,
        description=data.description,
    )
    db.add(ep)
    db.commit()
    db.refresh(ep)
    return {"id": ep.id, "url": ep.url, "events": ep.events, "is_active": ep.is_active}


@router.patch("/webhooks/{webhook_id}")
def update_webhook(
    webhook_id: str,
    data: WebhookCreate,
    user_id: str = Depends(require_permission("admin:llm:write")),
    db: Session = Depends(get_db),
):
    user = get_current_user(db, user_id)
    org_id = str(user.memberships[0].organization_id)
    ep = db.query(WebhookEndpoint).filter(WebhookEndpoint.id == webhook_id, WebhookEndpoint.organization_id == org_id).first()
    if not ep:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Webhook not found")
    if data.url:
        ep.url = data.url
    if data.events:
        ep.events = data.events
    if data.secret is not None:
        ep.secret = data.secret
    if data.description is not None:
        ep.description = data.description
    db.commit()
    db.refresh(ep)
    return {"id": ep.id, "url": ep.url, "events": ep.events, "is_active": ep.is_active}


@router.delete("/webhooks/{webhook_id}", status_code=204)
def delete_webhook(
    webhook_id: str,
    user_id: str = Depends(require_permission("admin:llm:write")),
    db: Session = Depends(get_db),
):
    user = get_current_user(db, user_id)
    org_id = str(user.memberships[0].organization_id)
    ep = db.query(WebhookEndpoint).filter(WebhookEndpoint.id == webhook_id, WebhookEndpoint.organization_id == org_id).first()
    if ep:
        db.delete(ep)
        db.commit()


@router.get("/webhooks/{webhook_id}/deliveries")
def list_deliveries(
    webhook_id: str,
    user_id: str = Depends(require_permission("admin:llm:read")),
    db: Session = Depends(get_db),
):
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
