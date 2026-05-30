"""DB-migration agent-chain trigger (A2).

Starts the MigrationPerNodeWorkflow (SchemaAnalyst→TypeMapper→ScriptGenerator→
Reconciler) for a project, alongside the BMAD pipeline. Status/steps/artifacts
are read through the existing agent-workflows endpoints (shared
workflow_runs/workflow_steps tables); approval uses the same signal mechanism.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_organization_id
from app.auth.jwt import get_current_user_id
from app.db.session import get_db
from app.models.project import MigrationRequirement
from app.services.project_service import ensure_project_access
from app.services.workflow_service import start_migration_workflow
from app.utils.idempotency import idempotent

router = APIRouter(tags=["migrations"])


class StartMigrationRequest(BaseModel):
    requirement_id: str
    source_connection_id: str | None = None
    target_connection_id: str | None = None
    source_connector_type: str | None = None
    target_connector_type: str | None = None


class StartMigrationResponse(BaseModel):
    workflow_id: str
    run_id: str
    status: str
    mode: str
    kind: str = "migration"


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
    """Start the DB-migration agent chain for a project requirement.

    Idempotent on the `Idempotency-Key` header (shared with BMAD start). The
    workflow id is namespaced `mig-{project}-{requirement}` so it never
    collides with a BMAD `bmad-...` run.
    """
    ensure_project_access(db, org_id, project_id)

    requirement = (
        db.query(MigrationRequirement)
        .filter(
            MigrationRequirement.id == data.requirement_id,
            MigrationRequirement.project_id == project_id,
        )
        .first()
    )
    if not requirement:
        raise HTTPException(status_code=404, detail="Requirement not found")

    correlation_id = getattr(request.state, "request_id", None) if request else None
    result = await start_migration_workflow(
        project_id=project_id,
        requirement_id=data.requirement_id,
        organization_id=org_id,
        source_connection_id=data.source_connection_id,
        target_connection_id=data.target_connection_id,
        source_connector_type=data.source_connector_type,
        target_connector_type=data.target_connector_type,
        requirement_text=getattr(requirement, "source_text", "") or "",
        db=db,
        correlation_id=correlation_id,
    )
    return StartMigrationResponse(
        workflow_id=result["workflow_id"],
        run_id=result["run_id"],
        status=result["status"],
        mode=result["mode"],
    )
