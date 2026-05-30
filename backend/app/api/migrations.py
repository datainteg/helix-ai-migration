"""DB-migration agent-chain trigger (A2 / Phase B).

Starts the MigrationPerNodeWorkflow (SchemaAnalyst→TypeMapper→ScriptGenerator→
Reconciler) for a project, alongside the BMAD pipeline. Resolves the project's
source/target connections to their DECRYPTED configs (host-allowlist enforced)
and passes them to the worker so SchemaAnalyst/Reconciler can introspect the
real databases. Status/steps/artifacts read through the existing
agent-workflows endpoints; approval uses /agent-workflows/{id}/signal-approve.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.connectors import _enforce_host_allowlist
from app.auth.dependencies import get_current_organization_id
from app.auth.jwt import get_current_user_id
from app.db.session import get_db
from app.models.project import MigrationRequirement
from app.services.project_service import (
    ensure_project_access,
    get_source_config,
    get_target_config,
)
from app.services.workflow_service import start_migration_workflow
from app.utils.idempotency import idempotent

router = APIRouter(tags=["migrations"])

_DEFAULT_REQUIREMENT_TEXT = (
    "Full database schema + data migration from the configured source connection "
    "to the configured target connection."
)


class StartMigrationRequest(BaseModel):
    source_connection_id: str
    target_connection_id: str | None = None
    requirement_id: str | None = None


class StartMigrationResponse(BaseModel):
    workflow_id: str
    run_id: str
    status: str
    mode: str
    kind: str = "migration"


def _resolve_requirement(db: Session, project_id: str, requirement_id: str | None) -> str:
    """Return a valid requirement_id, creating a default one if none is given."""
    if requirement_id:
        req = (
            db.query(MigrationRequirement)
            .filter(
                MigrationRequirement.id == requirement_id,
                MigrationRequirement.project_id == project_id,
            )
            .first()
        )
        if not req:
            raise HTTPException(status_code=404, detail="Requirement not found")
        return req.id
    # Auto: reuse the project's first requirement, else create a default one so
    # the golden-path "Generate migration" button works without a separate step.
    existing = (
        db.query(MigrationRequirement)
        .filter(MigrationRequirement.project_id == project_id)
        .order_by(MigrationRequirement.created_at.asc())
        .first()
    )
    if existing:
        return existing.id
    req = MigrationRequirement(project_id=project_id, source_text=_DEFAULT_REQUIREMENT_TEXT, status="draft")
    db.add(req)
    db.commit()
    db.refresh(req)
    return req.id


@router.post("/projects/{project_id}/migrations", response_model=StartMigrationResponse)
@idempotent("start_migration")
async def start_migration(
    request: Request,
    project_id: str,
    data: StartMigrationRequest,
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Start the DB-migration agent chain for a project.

    Resolves source (required) + target (optional) connections to decrypted,
    host-allowlist-enforced configs and hands them to the worker. The workflow
    id is namespaced `mig-{project}-{requirement}` so it never collides with a
    BMAD `bmad-...` run. Idempotent on the `Idempotency-Key` header.
    """
    ensure_project_access(db, org_id, project_id)

    # Source connection (required) → decrypted config.
    src_conn, src_config = get_source_config(db, org_id, project_id, data.source_connection_id)
    if not src_config:
        raise HTTPException(status_code=400, detail="Source connection has no stored credentials")
    src_config = _enforce_host_allowlist(src_config)

    # Target connection (optional) → decrypted config.
    tgt_type: str | None = None
    tgt_config: dict | None = None
    if data.target_connection_id:
        tgt_conn, tgt_cfg = get_target_config(db, org_id, project_id, data.target_connection_id)
        if tgt_cfg:
            tgt_config = _enforce_host_allowlist(tgt_cfg)
            tgt_type = tgt_conn.connector_type

    requirement_id = _resolve_requirement(db, project_id, data.requirement_id)

    correlation_id = getattr(request.state, "request_id", None) if request else None
    result = await start_migration_workflow(
        project_id=project_id,
        requirement_id=requirement_id,
        organization_id=org_id,
        source_connection_id=data.source_connection_id,
        target_connection_id=data.target_connection_id,
        source_connector_type=src_conn.connector_type,
        target_connector_type=tgt_type,
        source_config=src_config,
        target_config=tgt_config,
        db=db,
        correlation_id=correlation_id,
    )
    return StartMigrationResponse(
        workflow_id=result["workflow_id"],
        run_id=result["run_id"],
        status=result["status"],
        mode=result["mode"],
    )
