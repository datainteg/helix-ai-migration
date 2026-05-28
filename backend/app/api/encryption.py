from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.auth.jwt import get_current_user_id
from app.auth.dependencies import require_permission, resolve_active_org_id
from app.services.auth_service import get_current_user
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


class SecretRewrapResponse(BaseModel):
    status: str
    rewrapped: int
    scanned: int
    by_table: dict[str, int]


def _require_super_admin(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    user = get_current_user(db, user_id)
    if not user.is_super_admin:
        raise HTTPException(status_code=403, detail="Super admin access required")
    return user


@router.post("/admin/secrets/rewrap-all", status_code=200, response_model=SecretRewrapResponse)
def rewrap_all_secrets(
    request: Request,
    admin=Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """SC-030: re-seal every KEK-level secret that is still sealed with the
    LEGACY sha256-derived Fernet key using the current direct ENCRYPTION_KEY.

    The secret_service uses a MultiFernet that ENCRYPTS with the direct key but
    DECRYPTS with either the direct or the legacy key, so legacy ciphertext keeps
    reading. Until every row is re-sealed, ENCRYPTION_KEY rotation is incomplete
    (the legacy slot must stay configured). This maintenance endpoint walks all
    secret-bearing columns, calls ``rewrap_if_legacy`` on each, and persists any
    upgraded ciphertext so the legacy key can finally be dropped.

    Super-admin only — it touches every org's secrets. Idempotent: rows already
    sealed with the direct key (or empty/IAM sentinels) are skipped.
    """
    from app.services.secret_service import rewrap_if_legacy
    from app.models.llm import LLMProviderSecret
    from app.models.project import SourceConnection, TargetConnection
    from app.models.webhook import WebhookEndpoint

    by_table: dict[str, int] = {}
    scanned = 0
    rewrapped = 0

    def _rewrap_column(rows, attr: str, table: str) -> None:
        nonlocal scanned, rewrapped
        count = 0
        for row in rows:
            scanned += 1
            current = getattr(row, attr, None)
            upgraded = rewrap_if_legacy(current)
            if upgraded is not None and upgraded != current:
                setattr(row, attr, upgraded)
                count += 1
                rewrapped += 1
        if count:
            by_table[table] = by_table.get(table, 0) + count

    _rewrap_column(db.query(LLMProviderSecret).all(), "encrypted_api_key", "llm_provider_secrets")
    _rewrap_column(db.query(SourceConnection).all(), "encrypted_config", "source_connections")
    _rewrap_column(db.query(TargetConnection).all(), "encrypted_config", "target_connections")
    _rewrap_column(db.query(WebhookEndpoint).all(), "secret", "webhook_endpoints")

    db.commit()

    write_audit(
        db,
        org_id="00000000-0000-0000-0000-000000000000",
        actor_id=admin.id,
        action="secrets_rewrapped_all",
        entity_type="platform",
        entity_id="",
        meta={"rewrapped": rewrapped, "scanned": scanned, "by_table": by_table},
        request=request,
    )

    return SecretRewrapResponse(
        status="ok", rewrapped=rewrapped, scanned=scanned, by_table=by_table,
    )
