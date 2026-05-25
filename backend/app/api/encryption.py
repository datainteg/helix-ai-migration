from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.auth.dependencies import require_permission, resolve_active_org_id
from app.services.envelope_encryption_service import rotate_dek

router = APIRouter(tags=["encryption"])


@router.post("/admin/org/rotate-dek", status_code=200)
def rotate_org_dek(
    user_id: str = Depends(require_permission("admin:llm:write")),
    db: Session = Depends(get_db),
):
    """Rotate the org's Data Encryption Key. Re-encrypt secrets separately after rotation."""
    org_id = resolve_active_org_id(db, user_id)
    rotate_dek(db, org_id)
    return {"status": "rotated", "organization_id": org_id}
