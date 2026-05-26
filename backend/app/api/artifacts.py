from fastapi import APIRouter, Depends, Query, Request, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.auth.jwt import get_current_user_id
from app.auth.dependencies import resolve_active_org_id, get_current_organization_id
from app.models.artifacts import CodeArtifact
from app.services.artifact_version_service import create_artifact_metadata, list_artifacts, get_artifact, list_versions
from app.services.project_service import ensure_project_access
from app.storage.local import sanitize_filename, save_artifact_file, validate_upload
from app.api.audit import write_audit
from app.schemas.pagination import PaginatedResponse, paginate
from app.utils.idempotency import idempotent
from app.services.llm_provider_service import decrypt_extra_config as _dec

router = APIRouter(tags=["artifacts"])


class ArtifactSummary(BaseModel):
    """Lightweight artifact row used by list endpoints.

    Replaces the previous hand-built dict in `api_list_org_artifacts` so the
    OpenAPI schema enumerates real fields. `created_at` is an ISO-8601 string
    (e.g. `"2026-05-26T14:33:21+00:00"`) — the legacy `str(datetime)` repr
    that broke Safari's `Date` parser is gone.
    """

    id: str
    project_id: str
    filename: str
    file_type: str | None = None
    status: str | None = None
    created_at: str | None = None


@router.get("/artifacts", response_model=PaginatedResponse[ArtifactSummary])
def api_list_org_artifacts(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Org-wide artifact list — every artifact across all projects.

    Returns a `{items,total,limit,offset}` envelope (breaking change vs v0.x
    bare array — see REVIEW_API_CONTRACT.md §API-C2).

    Used by /developer-workspace (top-level IDE view) so operators can scan
    artifacts without first picking a project. Per-project list lives at
    /projects/{project_id}/artifacts.
    """
    from sqlalchemy import func
    org_id = resolve_active_org_id(db, user_id)
    # Cheap COUNT(*) for the envelope — same WHERE clause as the SELECT.
    total = (
        db.query(func.count(CodeArtifact.id))
        .filter(CodeArtifact.organization_id == org_id)
        .scalar()
        or 0
    )
    rows = (
        db.query(CodeArtifact)
        .filter(CodeArtifact.organization_id == org_id)
        .order_by(CodeArtifact.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    items = [
        ArtifactSummary(
            id=a.id,
            project_id=a.project_id,
            filename=a.filename,
            file_type=a.file_type,
            status=a.status,
            created_at=a.created_at.isoformat() if a.created_at else None,
        )
        for a in rows
    ]
    # Already paginated at the DB level — pass full COUNT(*) as total and
    # the raw page as items; do NOT re-slice.
    return PaginatedResponse[ArtifactSummary](
        items=items, total=int(total), limit=limit, offset=offset,
    )


@router.post("/projects/{project_id}/artifacts/upload")
async def upload_artifact(request: Request, project_id: str, file: UploadFile = File(...), user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    org_id = resolve_active_org_id(db, user_id)
    ensure_project_access(db, org_id, project_id)

    original_filename = file.filename or "unknown"
    content = await file.read()
    validate_upload(original_filename, content)

    from app.storage.s3 import save_artifact as save_artifact_dispatch
    path = save_artifact_dispatch(project_id, original_filename, content)

    ext = sanitize_filename(original_filename).rsplit(".", 1)[-1].lower()
    result = create_artifact_metadata(db, org_id, project_id, original_filename, ext, str(path), content)
    write_audit(db, org_id=org_id, actor_id=user_id, action="artifact_uploaded", entity_type="artifact", entity_id=result.id, meta={"filename": original_filename}, request=request)
    return result


@router.get(
    "/projects/{project_id}/artifacts",
    response_model=PaginatedResponse[dict],
)
def api_list_artifacts(
    project_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List artifacts for a project (paginated envelope).

    Breaking change vs v0.x: response is now `{items,total,limit,offset}`.
    `items` keeps the existing row shape returned by `list_artifacts`
    until that service is migrated to a typed schema.
    """
    org_id = resolve_active_org_id(db, user_id)
    ensure_project_access(db, org_id, project_id)
    rows = list_artifacts(db, org_id, project_id)
    return paginate(rows, limit=limit, offset=offset)


@router.get("/artifacts/{artifact_id}")
def api_get_artifact(artifact_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return get_artifact(db, resolve_active_org_id(db, user_id), artifact_id)


@router.get("/artifacts/{artifact_id}/versions")
def api_list_versions(artifact_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return list_versions(db, resolve_active_org_id(db, user_id), artifact_id)


class RollbackLink(BaseModel):
    rollback_artifact_id: str


@router.post("/artifacts/{artifact_id}/rollback")
def api_link_rollback(
    artifact_id: str,
    data: "RollbackLink",
    request: Request,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Attach a rollback artifact to a forward-migration artifact.

    Both artifacts must belong to the caller's org. Returns the updated
    parent artifact. Idempotent — re-linking overwrites the previous pointer.
    """
    from fastapi import HTTPException
    org_id = resolve_active_org_id(db, user_id)
    forward = db.query(CodeArtifact).filter(
        CodeArtifact.id == artifact_id, CodeArtifact.organization_id == org_id
    ).first()
    if not forward:
        raise HTTPException(status_code=404, detail="Artifact not found")
    reverse = db.query(CodeArtifact).filter(
        CodeArtifact.id == data.rollback_artifact_id, CodeArtifact.organization_id == org_id
    ).first()
    if not reverse:
        raise HTTPException(status_code=404, detail="Rollback artifact not found")
    if reverse.id == forward.id:
        raise HTTPException(status_code=400, detail="Artifact cannot roll back itself")
    forward.rollback_artifact_id = reverse.id
    db.commit()
    db.refresh(forward)
    # Audit emission was missing — REVIEW_API_CONTRACT lists this endpoint
    # among the no-audit set.
    write_audit(
        db, org_id=org_id, actor_id=user_id,
        action="artifact_rollback_linked",
        entity_type="artifact", entity_id=forward.id,
        meta={"rollback_artifact_id": reverse.id},
        request=request,
    )
    return {
        "id": forward.id,
        "filename": forward.filename,
        "rollback_artifact_id": forward.rollback_artifact_id,
    }


@router.post("/artifacts/{artifact_id}/generate-rollback")
@idempotent("generate_rollback")
async def api_generate_rollback(
    artifact_id: str,
    request: Request,
    user_id: str = Depends(get_current_user_id),
    org_id: str = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
):
    """LLM-generate an inverse migration script and link it as the rollback.

    Reads the forward artifact, feeds it to the org's active LLM provider with
    a fixed system prompt, saves the output as a paired *.rollback.<ext>
    artifact, sets rollback_artifact_id, and records the LLM usage row.

    Idempotent on `Idempotency-Key` header (API-C4) — retries don't burn
    a second LLM call + duplicate the rollback artifact. The link itself
    was already idempotent at the data-model level (re-running overwrote
    the previous pointer); the API-level cache also avoids the LLM cost.
    """
    from pathlib import Path
    from fastapi import HTTPException
    from app.storage.local import save_artifact_file, sanitize_filename
    from app.services.artifact_version_service import create_artifact_metadata
    from app.services.secret_service import decrypt_value
    from app.services.cost_service import record_usage
    from app.services.llm_router_service import resolve_routing
    from app.models.llm import LLMProvider, LLMAgentMapping
    from agents.runtime.providers import CallContext, get_provider as get_llm_provider

    # `org_id` is now resolved by the dependency injector — needed by the
    # @idempotent decorator to scope the cache key per-org.
    forward = db.query(CodeArtifact).filter(
        CodeArtifact.id == artifact_id, CodeArtifact.organization_id == org_id
    ).first()
    if not forward:
        raise HTTPException(status_code=404, detail="Artifact not found")

    try:
        from app.storage.s3 import read_artifact_bytes
        content = read_artifact_bytes(forward.storage_path).decode("utf-8")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to read forward artifact: {exc}")

    provider = (
        db.query(LLMProvider)
        .filter(LLMProvider.organization_id == org_id, LLMProvider.status == "active")
        .first()
    )
    if not provider or not provider.secrets:
        raise HTTPException(status_code=409, detail="No active LLM provider configured")

    mappings = db.query(LLMAgentMapping).filter(LLMAgentMapping.organization_id == org_id).all()
    pid, model, _temp, max_tokens = resolve_routing(
        "bmad-agent-rollback", provider.id, provider.default_model, mappings
    )
    target_provider = db.query(LLMProvider).filter(LLMProvider.id == pid).first() or provider
    secret = max(target_provider.secrets, key=lambda s: s.key_version)
    api_key = decrypt_value(secret.encrypted_api_key)

    adapter = get_llm_provider(target_provider.provider_type)
    if adapter is None:
        raise HTTPException(status_code=501, detail=f"No adapter for {target_provider.provider_type}")

    system_prompt = (
        "You are a senior database engineer producing reverse-migration scripts. "
        "Given a forward migration (DDL, DML, or migration code), output ONLY the "
        "exact statements that revert every change. Include DROP for newly created "
        "objects, ALTER ... DROP COLUMN for added columns, restore previous "
        "constraints, and reverse data operations where deterministic. Do not "
        "include explanations, prose, or markdown fences. Output one statement "
        "per logical revert, in the correct order to leave the schema as it was."
    )
    user_prompt = f"Forward migration ({forward.file_type or 'sql'}):\n\n{content}\n\nProduce the rollback now."

    ctx = CallContext(
        model=model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        api_key=api_key,
        base_url=target_provider.base_url,
        temperature=0.0,
        max_tokens=int(max_tokens or target_provider.max_tokens or 4096),
        timeout=float(target_provider.timeout or 60),
        # SEC-010: decrypt sealed sensitive keys before handing the dict to the LLM transport
        extra_config=(_dec(target_provider.extra_config) or {}),
    )
    parsed = adapter.call(ctx)
    if parsed is None:
        raise HTTPException(status_code=502, detail="Rollback generation failed (LLM transport error)")

    rollback_text = parsed.get("summary") or parsed.get("rollback") or parsed.get("content") or ""
    if not rollback_text.strip():
        rollback_text = str(parsed)

    from app.storage.s3 import save_artifact as save_artifact_dispatch
    base = sanitize_filename(forward.filename)
    rollback_name = f"{base}.rollback.{forward.file_type or 'sql'}"
    rollback_path = save_artifact_dispatch(forward.project_id, rollback_name, rollback_text.encode("utf-8"))
    reverse = create_artifact_metadata(
        db, org_id, forward.project_id, rollback_name, forward.file_type or "sql",
        str(rollback_path), rollback_text.encode("utf-8"),
    )

    forward_row = db.query(CodeArtifact).filter(CodeArtifact.id == forward.id).first()
    if forward_row:
        forward_row.rollback_artifact_id = reverse.id
        db.commit()

    try:
        record_usage(
            db,
            organization_id=org_id,
            provider_type=target_provider.provider_type,
            model=model,
            input_tokens=int(len(user_prompt.split()) * 1.3),
            output_tokens=max(1, len(rollback_text) // 4),
            project_id=forward.project_id,
            agent_name="rollback_generator",
        )
    except Exception:  # noqa: BLE001
        pass

    write_audit(db, org_id=org_id, actor_id=user_id, action="rollback_generated",
                entity_type="artifact", entity_id=forward.id,
                meta={"rollback_artifact_id": reverse.id}, request=request)

    return {
        "forward_artifact_id": forward.id,
        "rollback_artifact_id": reverse.id,
        "rollback_filename": rollback_name,
        "bytes": len(rollback_text),
    }


@router.get("/artifacts/{artifact_id}/rollback")
def api_get_rollback(
    artifact_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Return the paired rollback artifact metadata, or 404 if none linked."""
    from fastapi import HTTPException
    org_id = resolve_active_org_id(db, user_id)
    forward = db.query(CodeArtifact).filter(
        CodeArtifact.id == artifact_id, CodeArtifact.organization_id == org_id
    ).first()
    if not forward:
        raise HTTPException(status_code=404, detail="Artifact not found")
    if not forward.rollback_artifact_id:
        raise HTTPException(status_code=404, detail="No rollback linked")
    reverse = db.query(CodeArtifact).filter(CodeArtifact.id == forward.rollback_artifact_id).first()
    if not reverse:
        raise HTTPException(status_code=404, detail="Linked rollback artifact missing")
    return {
        "id": reverse.id,
        "filename": reverse.filename,
        "file_type": reverse.file_type,
        "storage_path": reverse.storage_path,
        "content_hash": reverse.content_hash,
        "status": reverse.status,
        # ISO-8601 (API-C3)
        "created_at": reverse.created_at.isoformat() if reverse.created_at else None,
    }
