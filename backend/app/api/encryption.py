from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.auth.dependencies import require_permission, resolve_active_org_id
from app.services.envelope_encryption_service import rotate_dek
from app.api.audit import write_audit

router = APIRouter(tags=["encryption"])


class DEKRotateResponse(BaseModel):
    status: str
    organization_id: str


@router.post("/admin/org/rotate-dek", status_code=200, response_model=DEKRotateResponse)
def rotate_org_dek(
    request: Request,
    user_id: str = Depends(require_permission("admin:llm:write")),
    db: Session = Depends(get_db),
):
    """Rotate the org's Data Encryption Key. Re-encrypt secrets separately after rotation."""
    org_id = resolve_active_org_id(db, user_id)
    rotate_dek(db, org_id)
    # Audit emission was missing (REVIEW_API_CONTRACT lists encryption
    # under the no-audit set). DEK rotation is compliance-critical —
    # this row is the auditor's only trace.
    write_audit(
        db, org_id=org_id, actor_id=user_id,
        action="dek_rotated",
        entity_type="organization", entity_id=org_id,
        request=request,
    )
    return DEKRotateResponse(status="rotated", organization_id=org_id)
