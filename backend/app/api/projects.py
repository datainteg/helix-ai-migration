from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.auth.jwt import get_current_user_id
from app.auth.dependencies import resolve_active_org_id, require_permission, user_has_role
from app.schemas.project import (
    ProjectCreate, ProjectResponse,
    SubProjectCreate, SubProjectResponse,
    RequirementCreate, RequirementResponse,
    ConnectionCreate, ConnectionUpdate, ConnectionResponse, ConnectionTestResponse,
    SchemaCreate, SchemaResponse,
    TableCreate, TableResponse,
    ColumnCreate,
)
from app.services.project_service import (
    create_project, list_projects, get_project,
    add_subproject, add_requirement,
    add_source, list_sources, update_source, delete_source, get_source_config,
    add_target, list_targets, update_target, delete_target, get_target_config,
    add_schema, add_table, add_column,
)
from app.services.connector_service import test_connection as svc_test_connection
from app.services.connector_service import (
    discover_schemas as svc_discover_schemas,
    discover_tables as svc_discover_tables,
    discover_columns as svc_discover_columns,
)
from app.schemas.pagination import PaginatedResponse, paginate
from app.rate_limiting import limiter
from app.api.audit import write_audit
# SEC-015: stored configs must hit the same host allowlist as freshly
# submitted configs — re-import the connectors-router enforcer here.
from app.api.connectors import _enforce_host_allowlist

router = APIRouter(tags=["projects"])


def _org_id(user_id: str, db: Session) -> str:
    """Resolve caller's *active* org. SEC-002: previously returned
    `memberships[0].organization_id` with no status filter, so a suspended
    member could still mutate projects / connections. Now defers to the
    canonical helper which raises 403 when no active membership exists.
    """
    return resolve_active_org_id(db, user_id)


# ── Projects ──

@router.post("/projects", response_model=ProjectResponse, status_code=201)
def api_create_project(request: Request, data: ProjectCreate, user_id: str = Depends(require_permission("project:write")), db: Session = Depends(get_db)):
    org_id = _org_id(user_id, db)
    result = create_project(db, org_id, user_id, data)
    write_audit(db, org_id=org_id, actor_id=user_id, action="project_created", entity_type="project", entity_id=result.id, request=request)
    return result


@router.get("/projects", response_model=PaginatedResponse[ProjectResponse])
def api_list_projects(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    include_archived: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List projects for the caller's org (paginated envelope).

    Breaking change vs v0.x: response is now ``{items, total, limit, offset}``
    instead of a bare array.  See REVIEW_API_CONTRACT.md §API-C2.
    """
    rows = list_projects(db, _org_id(user_id, db), include_archived=include_archived)
    return paginate(rows, limit=limit, offset=offset)


@router.get("/projects/summary")
def api_projects_summary(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Per-project rollup for the Projects table: validation %, recon %, table
    count, and latest workflow status/kind. One pass over the org's projects.
    Returns a dict keyed by project_id so the list page can merge it in."""
    from sqlalchemy import func
    from app.models.project import Project, TableMetadata, SchemaMetadata
    from app.models.workflow import WorkflowRun
    from app.models.validation import ValidationResult, ValidationRun, ReconResult, ReconRun

    org_id = _org_id(user_id, db)
    project_ids = [p.id for p in db.query(Project.id).filter(Project.organization_id == org_id).all()]
    if not project_ids:
        return {}

    out: dict[str, dict] = {pid: {} for pid in project_ids}

    # Validation: passed / total per project.
    v_rows = (
        db.query(ValidationRun.project_id, ValidationResult.status, func.count(ValidationResult.id))
        .join(ValidationResult, ValidationResult.run_id == ValidationRun.id)
        .filter(ValidationRun.project_id.in_(project_ids))
        .group_by(ValidationRun.project_id, ValidationResult.status)
        .all()
    )
    v_agg: dict[str, dict[str, int]] = {}
    for pid, status, n in v_rows:
        d = v_agg.setdefault(pid, {"total": 0, "passed": 0})
        d["total"] += int(n)
        if status == "passed":
            d["passed"] += int(n)

    # Recon: clean / total per project.
    r_rows = (
        db.query(ReconRun.project_id, ReconResult.mismatch_count, func.count(ReconResult.id))
        .join(ReconResult, ReconResult.run_id == ReconRun.id)
        .filter(ReconRun.project_id.in_(project_ids))
        .group_by(ReconRun.project_id, ReconResult.mismatch_count)
        .all()
    )
    r_agg: dict[str, dict[str, int]] = {}
    for pid, mismatch, n in r_rows:
        d = r_agg.setdefault(pid, {"total": 0, "clean": 0})
        d["total"] += int(n)
        if (mismatch or 0) == 0:
            d["clean"] += int(n)

    # Table count per project (via schema metadata).
    t_rows = (
        db.query(SchemaMetadata.project_id, func.count(TableMetadata.id))
        .join(TableMetadata, TableMetadata.schema_id == SchemaMetadata.id)
        .filter(SchemaMetadata.project_id.in_(project_ids))
        .group_by(SchemaMetadata.project_id)
        .all()
    )
    tbl_counts = {pid: int(n) for pid, n in t_rows}

    # Latest workflow run per project (status + kind = "phase").
    wf_rows = (
        db.query(WorkflowRun.project_id, WorkflowRun.status, WorkflowRun.kind, WorkflowRun.created_at)
        .filter(WorkflowRun.project_id.in_(project_ids))
        .order_by(WorkflowRun.created_at.desc())
        .all()
    )
    latest_wf: dict[str, dict] = {}
    for pid, status, kind, _created in wf_rows:
        if pid not in latest_wf:
            latest_wf[pid] = {"status": status, "kind": kind or "bmad"}

    for pid in project_ids:
        v = v_agg.get(pid)
        r = r_agg.get(pid)
        out[pid] = {
            "validation_pct": round(v["passed"] / v["total"] * 100, 1) if v and v["total"] else None,
            "recon_pct": round(r["clean"] / r["total"] * 100, 1) if r and r["total"] else None,
            "table_count": tbl_counts.get(pid, 0),
            "latest_status": latest_wf.get(pid, {}).get("status"),
            "phase": latest_wf.get(pid, {}).get("kind"),
        }
    return out


@router.get("/projects/members")
def api_project_members(user_id: str = Depends(require_permission("project:write")), db: Session = Depends(get_db)):
    """Active org members for the project owner picker (project:write — so PMs
    can assign owners, not just admins)."""
    from app.models.identity import OrganizationMember, User
    org_id = _org_id(user_id, db)
    rows = (
        db.query(User.id, User.name, User.email)
        .join(OrganizationMember, OrganizationMember.user_id == User.id)
        .filter(OrganizationMember.organization_id == org_id, OrganizationMember.status == "active")
        .all()
    )
    return [{"user_id": uid, "name": name, "email": email} for uid, name, email in rows]


@router.get("/projects/{project_id}/overview")
def api_project_overview(project_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """Rich, REAL detail for the project page: counts, per-schema progress (from
    introspected metadata), latest workflow run + live step status, and
    validation/recon rollups. Everything is grounded in actual rows — sections
    with no data return empty, never fabricated."""
    from sqlalchemy import func
    from app.models.project import Project, SchemaMetadata, TableMetadata
    from app.models.workflow import WorkflowRun, WorkflowStep
    from app.models.validation import ValidationResult, ValidationRun, ReconResult, ReconRun
    from app.services.project_service import ensure_project_access

    org_id = _org_id(user_id, db)
    ensure_project_access(db, org_id, project_id)
    p = db.query(Project).filter(Project.id == project_id, Project.organization_id == org_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")

    # ── per-schema progress from introspected metadata ──
    schemas = db.query(SchemaMetadata).filter(SchemaMetadata.project_id == project_id).all()
    schema_rows = []
    total_tables = 0
    for s in schemas:
        tbls = db.query(TableMetadata).filter(TableMetadata.schema_id == s.id).all()
        rows = sum((t.row_count or 0) for t in tbls)
        total_tables += len(tbls)
        schema_rows.append({
            "schema": s.name,
            "schema_type": getattr(s, "schema_type", "source"),
            "tables": len(tbls),
            "rows": rows,
        })

    # ── latest workflow run + live steps ──
    run = (
        db.query(WorkflowRun).filter(WorkflowRun.project_id == project_id)
        .order_by(WorkflowRun.created_at.desc()).first()
    )
    latest_run = None
    if run:
        steps = (
            db.query(WorkflowStep).filter(WorkflowStep.workflow_run_id == run.id)
            .order_by(WorkflowStep.step_order).all()
        )
        done = sum(1 for s in steps if (s.status or "").lower() in ("completed", "approved", "done", "succeeded"))
        latest_run = {
            "workflow_id": run.workflow_id, "status": run.status, "kind": run.kind or "bmad",
            "mode": run.mode, "created_at": str(run.created_at) if run.created_at else None,
            "steps_done": done, "steps_total": len(steps),
            "steps": [{"agent": s.agent_name, "order": s.step_order, "status": s.status,
                       "error": s.error_message, "artifact_path": _step_artifact(s)} for s in steps],
        }

    # ── validation / recon rollups ──
    def _pct(model, run_model, on, ok):
        total = db.query(func.count(model.id)).join(run_model, on).filter(run_model.project_id == project_id).scalar() or 0
        good = db.query(func.count(model.id)).join(run_model, on).filter(run_model.project_id == project_id, ok).scalar() or 0
        return (round(good / total * 100, 1) if total else None), total
    val_pct, val_total = _pct(ValidationResult, ValidationRun, ValidationResult.run_id == ValidationRun.id, ValidationResult.status == "passed")
    recon_pct, recon_total = _pct(ReconResult, ReconRun, ReconResult.run_id == ReconRun.id, ReconResult.mismatch_count == 0)

    return {
        "schema_count": len(schemas),
        "table_count": total_tables,
        "schemas": schema_rows,
        "latest_run": latest_run,
        "validation": {"pct": val_pct, "total": val_total},
        "recon": {"pct": recon_pct, "total": recon_total},
    }


def _step_artifact(step) -> str | None:
    payload = step.parsed_output_json if isinstance(step.parsed_output_json, dict) else None
    if not payload:
        return None
    paths = payload.get("artifact_paths") or payload.get("artifact_path")
    if isinstance(paths, list) and paths:
        return paths[-1]
    return paths if isinstance(paths, str) else None


@router.get("/projects/{project_id}", response_model=ProjectResponse)
def api_get_project(project_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return get_project(db, _org_id(user_id, db), project_id)


@router.patch("/projects/{project_id}/archive", response_model=ProjectResponse)
def api_archive_project(project_id: str, request: Request, user_id: str = Depends(require_permission("project:write")), db: Session = Depends(get_db)):
    from app.services.project_service import ensure_project_access
    from app.models.project import Project
    org_id = _org_id(user_id, db)
    ensure_project_access(db, org_id, project_id)
    p = db.query(Project).filter(Project.id == project_id).first()
    p.status = "archived"
    db.commit()
    db.refresh(p)
    write_audit(db, org_id=org_id, actor_id=user_id, action="project_archived", entity_type="project", entity_id=project_id, request=request)
    return p


@router.patch("/projects/{project_id}/restore", response_model=ProjectResponse)
def api_restore_project(project_id: str, request: Request, user_id: str = Depends(require_permission("project:write")), db: Session = Depends(get_db)):
    from app.services.project_service import ensure_project_access
    from app.models.project import Project
    org_id = _org_id(user_id, db)
    ensure_project_access(db, org_id, project_id)
    p = db.query(Project).filter(Project.id == project_id).first()
    p.status = "draft"
    db.commit()
    db.refresh(p)
    write_audit(db, org_id=org_id, actor_id=user_id, action="project_restored", entity_type="project", entity_id=project_id, request=request)
    return p


class ProjectUpdate(BaseModel):
    owner_id: str | None = None
    status: str | None = None


@router.patch("/projects/{project_id}", response_model=ProjectResponse)
def api_update_project(project_id: str, data: ProjectUpdate, request: Request, user_id: str = Depends(require_permission("project:write")), db: Session = Depends(get_db)):
    """Update a project's owner and/or status (project:write)."""
    from app.services.project_service import ensure_project_access, _project_to_response, _owner_name_map
    from app.models.project import Project
    from app.models.identity import OrganizationMember
    org_id = _org_id(user_id, db)
    ensure_project_access(db, org_id, project_id)
    p = db.query(Project).filter(Project.id == project_id).first()
    if data.owner_id is not None:
        # Owner must be an active member of this org.
        m = (
            db.query(OrganizationMember)
            .filter(OrganizationMember.organization_id == org_id, OrganizationMember.user_id == data.owner_id, OrganizationMember.status == "active")
            .first()
        )
        if not m:
            raise HTTPException(status_code=400, detail="Owner must be an active member of this organization")
        p.owner_id = data.owner_id
    if data.status is not None:
        if data.status not in ("draft", "running", "awaiting", "completed", "failed", "archived"):
            raise HTTPException(status_code=400, detail="Invalid status")
        p.status = data.status
    db.commit()
    db.refresh(p)
    write_audit(db, org_id=org_id, actor_id=user_id, action="project_updated", entity_type="project", entity_id=project_id, meta=data.model_dump(exclude_none=True), request=request)
    return _project_to_response(p, _owner_name_map(db, {p.owner_id}))


class HoldRequest(BaseModel):
    on_hold: bool
    comment: str = Field(min_length=1, max_length=2000)


@router.post("/projects/{project_id}/hold", response_model=ProjectResponse)
def api_hold_project(project_id: str, data: HoldRequest, request: Request, user_id: str = Depends(require_permission("project:write")), db: Session = Depends(get_db)):
    """Put a project on hold or set it live. A comment (reason) is required and
    recorded on the project's activity timeline. On hold blocks new workflows."""
    from app.services.project_service import ensure_project_access, _project_to_response, _owner_name_map
    from app.models.project import Project, ProjectComment
    from app.services.auth_service import get_current_user
    org_id = _org_id(user_id, db)
    ensure_project_access(db, org_id, project_id)
    p = db.query(Project).filter(Project.id == project_id).first()
    p.on_hold = data.on_hold
    actor = get_current_user(db, user_id)
    db.add(ProjectComment(
        project_id=project_id, author_id=user_id,
        author_name=getattr(actor, "name", None) or getattr(actor, "email", None),
        kind="hold" if data.on_hold else "live", body=data.comment.strip(),
    ))
    db.commit()
    db.refresh(p)
    write_audit(db, org_id=org_id, actor_id=user_id,
                action="project_held" if data.on_hold else "project_resumed",
                entity_type="project", entity_id=project_id, request=request)
    return _project_to_response(p, _owner_name_map(db, {p.owner_id}))


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


def _comment_dict(c) -> dict:
    return {
        "id": c.id,
        "author_id": c.author_id,
        "author_name": c.author_name,
        "kind": c.kind,
        "body": c.body,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


@router.get("/projects/{project_id}/comments")
def api_list_comments(project_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """Project activity timeline — comments + hold/live events, newest first."""
    from app.services.project_service import ensure_project_access
    from app.models.project import ProjectComment
    org_id = _org_id(user_id, db)
    ensure_project_access(db, org_id, project_id)
    rows = (
        db.query(ProjectComment)
        .filter(ProjectComment.project_id == project_id)
        .order_by(ProjectComment.created_at.desc())
        .all()
    )
    return [_comment_dict(c) for c in rows]


@router.post("/projects/{project_id}/comments", status_code=201)
def api_add_comment(project_id: str, data: CommentCreate, user_id: str = Depends(require_permission("project:write")), db: Session = Depends(get_db)):
    from app.services.project_service import ensure_project_access
    from app.models.project import ProjectComment
    from app.services.auth_service import get_current_user
    org_id = _org_id(user_id, db)
    ensure_project_access(db, org_id, project_id)
    actor = get_current_user(db, user_id)
    c = ProjectComment(
        project_id=project_id, author_id=user_id,
        author_name=getattr(actor, "name", None) or getattr(actor, "email", None),
        kind="comment", body=data.body.strip(),
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return _comment_dict(c)


@router.delete("/projects/{project_id}", status_code=204)
def api_delete_project(project_id: str, request: Request, user_id: str = Depends(require_permission("project:write")), db: Session = Depends(get_db)):
    """Soft-delete: sets status to 'deleted'. Data retained for audit trail."""
    from app.services.project_service import ensure_project_access
    from app.models.project import Project
    org_id = _org_id(user_id, db)
    ensure_project_access(db, org_id, project_id)
    p = db.query(Project).filter(Project.id == project_id).first()
    p.status = "deleted"
    db.commit()
    write_audit(db, org_id=org_id, actor_id=user_id, action="project_deleted", entity_type="project", entity_id=project_id, request=request)


@router.delete("/projects/{project_id}/force", status_code=204)
def api_force_delete_project(project_id: str, request: Request, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """ADMIN-ONLY hard delete: permanently removes the project and all of its
    child data (runs, steps, recon, validation, connections, schema, etc.).
    Irreversible — distinct from the soft-delete above."""
    if not user_has_role(db, user_id, {"super_admin", "admin"}):
        raise HTTPException(status_code=403, detail="Only admins can force-delete a project")
    from app.services.project_service import ensure_project_access, force_delete_project
    org_id = _org_id(user_id, db)
    ensure_project_access(db, org_id, project_id)
    force_delete_project(db, project_id)
    write_audit(db, org_id=org_id, actor_id=user_id, action="project_force_deleted", entity_type="project", entity_id=project_id, request=request)


# ── SubProjects ──

@router.post("/projects/{project_id}/subprojects", response_model=SubProjectResponse, status_code=201)
def api_add_subproject(project_id: str, data: SubProjectCreate, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return add_subproject(db, _org_id(user_id, db), project_id, data)


# ── Requirements ──

@router.post("/projects/{project_id}/requirements", response_model=RequirementResponse, status_code=201)
def api_add_requirement(project_id: str, data: RequirementCreate, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return add_requirement(db, _org_id(user_id, db), project_id, data)


@router.get("/projects/{project_id}/requirements")
def api_list_requirements(project_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """List a project's migration requirements — used to start a workflow (the
    requirement is what the BMAD/migration pipeline plans from)."""
    from app.services.project_service import ensure_project_access
    from app.models.project import MigrationRequirement
    org_id = _org_id(user_id, db)
    ensure_project_access(db, org_id, project_id)
    rows = (
        db.query(MigrationRequirement)
        .filter(MigrationRequirement.project_id == project_id)
        .order_by(MigrationRequirement.created_at.desc())
        .all()
    )
    return [{"id": r.id, "source_text": r.source_text, "status": r.status,
             "version": r.version, "created_at": str(r.created_at) if r.created_at else None}
            for r in rows]


# ── Sources ──

@router.post("/projects/{project_id}/sources", response_model=ConnectionResponse, status_code=201)
def api_add_source(request: Request, project_id: str, data: ConnectionCreate, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    # SEC-015: every store-of-config path runs through the allowlist —
    # otherwise an operator can poison the row at admit-time and the
    # downstream `/test` / discovery endpoints will dial IMDS / RFC1918.
    if data.config:
        _enforce_host_allowlist(data.config)
    org_id = _org_id(user_id, db)
    result = add_source(db, org_id, project_id, data)
    from app.api.audit import write_audit
    write_audit(db, org_id=org_id, actor_id=user_id, action="source_connection_created",
                entity_type="source_connection", entity_id=result.id,
                meta={"connector_type": data.connector_type, "name": data.name}, request=request)
    return result


@router.get("/projects/{project_id}/sources", response_model=list[ConnectionResponse])
def api_list_sources(project_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return list_sources(db, _org_id(user_id, db), project_id)


@router.patch("/projects/{project_id}/sources/{source_id}", response_model=ConnectionResponse)
def api_update_source(project_id: str, source_id: str, data: ConnectionUpdate, request: Request, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    # SEC-015: PATCH was previously the loophole — allowed setting host to
    # 169.254.169.254 with no check, then the unguarded /test path dialed it.
    if data.config:
        _enforce_host_allowlist(data.config)
    org_id = _org_id(user_id, db)
    result = update_source(db, org_id, project_id, source_id, data)
    from app.api.audit import write_audit
    write_audit(db, org_id=org_id, actor_id=user_id, action="source_connection_updated",
                entity_type="source_connection", entity_id=source_id, request=request)
    return result


@router.delete("/projects/{project_id}/sources/{source_id}", status_code=204)
def api_delete_source(project_id: str, source_id: str, request: Request, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    org_id = _org_id(user_id, db)
    delete_source(db, org_id, project_id, source_id)
    from app.api.audit import write_audit
    write_audit(db, org_id=org_id, actor_id=user_id, action="source_connection_deleted",
                entity_type="source_connection", entity_id=source_id, request=request)


@router.post("/projects/{project_id}/sources/{source_id}/test", response_model=ConnectionTestResponse)
@limiter.limit("20/minute")
async def api_test_source(request: Request, project_id: str, source_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """Test a stored source connection using its decrypted credentials."""
    org_id = _org_id(user_id, db)
    conn, config = get_source_config(db, org_id, project_id, source_id)
    if not config:
        raise HTTPException(status_code=400, detail="Connection has no stored credentials")
    # SEC-015 / SC-015: revalidate the stored config at delivery time — a row
    # may have been poisoned before the host allowlist was raised, or DNS may
    # have rebinded since the row was stored. The returned config has its
    # host pinned to the validated IP so connect-time can't re-resolve to an
    # internal address.
    safe_config = _enforce_host_allowlist(config)
    result = await svc_test_connection(conn.connector_type, safe_config)
    conn.status = "active" if result.success else "error"
    db.commit()
    return ConnectionTestResponse(success=result.success, message=result.message)


@router.post("/projects/{project_id}/sources/{source_id}/discover/schemas")
@limiter.limit("30/minute")
async def api_discover_source_schemas(request: Request, project_id: str, source_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    org_id = _org_id(user_id, db)
    conn, config = get_source_config(db, org_id, project_id, source_id)
    if not config:
        raise HTTPException(status_code=400, detail="Connection has no stored credentials")
    safe_config = _enforce_host_allowlist(config)  # SEC-015 / SC-015 (pins IP)
    result = await svc_discover_schemas(conn.connector_type, safe_config)
    return [{"schema_name": s.schema_name} for s in result]


# ── Targets ──

@router.post("/projects/{project_id}/targets", response_model=ConnectionResponse, status_code=201)
def api_add_target(request: Request, project_id: str, data: ConnectionCreate, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    if data.config:
        _enforce_host_allowlist(data.config)  # SEC-015
    org_id = _org_id(user_id, db)
    result = add_target(db, org_id, project_id, data)
    from app.api.audit import write_audit
    write_audit(db, org_id=org_id, actor_id=user_id, action="target_connection_created",
                entity_type="target_connection", entity_id=result.id,
                meta={"connector_type": data.connector_type, "name": data.name}, request=request)
    return result


@router.get("/projects/{project_id}/targets", response_model=list[ConnectionResponse])
def api_list_targets(project_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return list_targets(db, _org_id(user_id, db), project_id)


@router.patch("/projects/{project_id}/targets/{target_id}", response_model=ConnectionResponse)
def api_update_target(project_id: str, target_id: str, data: ConnectionUpdate, request: Request, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    if data.config:
        _enforce_host_allowlist(data.config)  # SEC-015
    org_id = _org_id(user_id, db)
    result = update_target(db, org_id, project_id, target_id, data)
    from app.api.audit import write_audit
    write_audit(db, org_id=org_id, actor_id=user_id, action="target_connection_updated",
                entity_type="target_connection", entity_id=target_id, request=request)
    return result


@router.delete("/projects/{project_id}/targets/{target_id}", status_code=204)
def api_delete_target(project_id: str, target_id: str, request: Request, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    org_id = _org_id(user_id, db)
    delete_target(db, org_id, project_id, target_id)
    from app.api.audit import write_audit
    write_audit(db, org_id=org_id, actor_id=user_id, action="target_connection_deleted",
                entity_type="target_connection", entity_id=target_id, request=request)


@router.post("/projects/{project_id}/targets/{target_id}/test", response_model=ConnectionTestResponse)
@limiter.limit("20/minute")
async def api_test_target(request: Request, project_id: str, target_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    org_id = _org_id(user_id, db)
    conn, config = get_target_config(db, org_id, project_id, target_id)
    if not config:
        raise HTTPException(status_code=400, detail="Connection has no stored credentials")
    safe_config = _enforce_host_allowlist(config)  # SEC-015 / SC-015 (pins IP)
    result = await svc_test_connection(conn.connector_type, safe_config)
    conn.status = "active" if result.success else "error"
    db.commit()
    return ConnectionTestResponse(success=result.success, message=result.message)


@router.post("/projects/{project_id}/targets/{target_id}/discover/schemas")
@limiter.limit("30/minute")
async def api_discover_target_schemas(request: Request, project_id: str, target_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    org_id = _org_id(user_id, db)
    conn, config = get_target_config(db, org_id, project_id, target_id)
    if not config:
        raise HTTPException(status_code=400, detail="Connection has no stored credentials")
    safe_config = _enforce_host_allowlist(config)  # SEC-015 / SC-015 (pins IP)
    result = await svc_discover_schemas(conn.connector_type, safe_config)
    return [{"schema_name": s.schema_name} for s in result]


# ── Schema Metadata ──

@router.post("/projects/{project_id}/schemas", response_model=SchemaResponse, status_code=201)
def api_add_schema(project_id: str, data: SchemaCreate, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return add_schema(db, _org_id(user_id, db), project_id, data)


@router.post("/schemas/{schema_id}/tables", response_model=TableResponse, status_code=201)
def api_add_table(schema_id: str, data: TableCreate, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return add_table(db, _org_id(user_id, db), schema_id, data)


@router.post("/tables/{table_id}/columns", status_code=201)
def api_add_column(table_id: str, data: ColumnCreate, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    add_column(db, _org_id(user_id, db), table_id, data)
    return {"status": "created"}
