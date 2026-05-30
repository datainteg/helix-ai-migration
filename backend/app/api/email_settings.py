"""Email / SMTP settings API.

Admin surface to configure + test the org's mail transport. Secrets are write-
only (masked on read). The test endpoint sends a real message using the typed
config (saved or not) so an admin can verify before saving.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.auth.dependencies import require_permission, resolve_active_org_id
from app.api.audit import write_audit
from app.services import email_settings_service as ess

logger = logging.getLogger(__name__)
router = APIRouter(tags=["email-settings"])


class EmailSettingsUpdate(BaseModel):
    enabled: bool = False
    provider: str = Field(default="smtp", pattern="^(smtp|sendgrid)$")
    from_email: str | None = None
    from_name: str | None = None
    smtp_host: str | None = None
    smtp_port: int | None = Field(default=None, ge=1, le=65535)
    smtp_user: str | None = None
    smtp_password: str | None = None         # write-only; blank keeps stored
    smtp_tls: bool | None = None
    sendgrid_api_key: str | None = None      # write-only; blank keeps stored


class EmailTestRequest(EmailSettingsUpdate):
    to: EmailStr


@router.get("/email-settings")
def get_email_settings(
    user_id: str = Depends(require_permission("admin:llm:read")),
    db: Session = Depends(get_db),
):
    org_id = resolve_active_org_id(db, user_id)
    return ess.to_public_dict(ess.get_settings_row(db, org_id))


@router.put("/email-settings")
def put_email_settings(
    data: EmailSettingsUpdate,
    request: Request,
    user_id: str = Depends(require_permission("admin:llm:write")),
    db: Session = Depends(get_db),
):
    org_id = resolve_active_org_id(db, user_id)
    row = ess.upsert_settings(db, org_id, data.model_dump(exclude_unset=True))
    # Audit without secrets.
    safe = {k: v for k, v in data.model_dump().items() if k not in ("smtp_password", "sendgrid_api_key")}
    write_audit(db, org_id=org_id, actor_id=user_id, action="email_settings_updated",
                entity_type="email_settings", entity_id=row.id, meta=safe, request=request)
    return ess.to_public_dict(row)


@router.post("/email-settings/test")
async def test_email_settings(
    data: EmailTestRequest,
    user_id: str = Depends(require_permission("admin:llm:write")),
    db: Session = Depends(get_db),
):
    """Send a test email using the supplied config (merged over the saved one)."""
    org_id = resolve_active_org_id(db, user_id)
    overrides = data.model_dump(exclude={"to"}, exclude_unset=True)
    cfg = ess.build_test_config(db, org_id, overrides)
    try:
        await ess.send_with_config(
            cfg,
            to=str(data.to),
            subject="Helix — test email",
            html_body="<p>This is a test email from Helix. Your mail configuration is working. ✅</p>",
            text_body="This is a test email from Helix. Your mail configuration is working.",
        )
        return {"ok": True, "message": f"Test email sent to {data.to} via {cfg.provider}."}
    except Exception as e:  # surface the exact transport error to the admin
        logger.warning("email test failed: %s", e)
        raise HTTPException(status_code=400, detail=f"Test failed: {e}")
