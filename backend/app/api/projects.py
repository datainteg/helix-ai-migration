from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.auth.jwt import get_current_user_id
from app.auth.dependencies import resolve_active_org_id
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
def api_create_project(request: Request, data: ProjectCreate, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
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


@router.get("/projects/{project_id}", response_model=ProjectResponse)
def api_get_project(project_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return get_project(db, _org_id(user_id, db), project_id)


@router.patch("/projects/{project_id}/archive", response_model=ProjectResponse)
def api_archive_project(project_id: str, request: Request, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
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
def api_restore_project(project_id: str, request: Request, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
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


@router.delete("/projects/{project_id}", status_code=204)
def api_delete_project(project_id: str, request: Request, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """Soft-delete: sets status to 'deleted'. Data retained for audit trail."""
    from app.services.project_service import ensure_project_access
    from app.models.project import Project
    org_id = _org_id(user_id, db)
    ensure_project_access(db, org_id, project_id)
    p = db.query(Project).filter(Project.id == project_id).first()
    p.status = "deleted"
    db.commit()
    write_audit(db, org_id=org_id, actor_id=user_id, action="project_deleted", entity_type="project", entity_id=project_id, request=request)


# ── SubProjects ──

@router.post("/projects/{project_id}/subprojects", response_model=SubProjectResponse, status_code=201)
def api_add_subproject(project_id: str, data: SubProjectCreate, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return add_subproject(db, _org_id(user_id, db), project_id, data)


# ── Requirements ──

@router.post("/projects/{project_id}/requirements", response_model=RequirementResponse, status_code=201)
def api_add_requirement(project_id: str, data: RequirementCreate, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return add_requirement(db, _org_id(user_id, db), project_id, data)


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
