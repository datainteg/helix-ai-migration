from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.auth.jwt import get_current_user_id
from app.schemas.project import (
    ProjectCreate, ProjectResponse,
    SubProjectCreate, SubProjectResponse,
    RequirementCreate, RequirementResponse,
    ConnectionCreate, ConnectionResponse,
    SchemaCreate, SchemaResponse,
    TableCreate, TableResponse,
    ColumnCreate,
)
from app.services.project_service import (
    create_project, list_projects, get_project,
    add_subproject, add_requirement,
    add_source, list_sources, add_target, list_targets,
    add_schema, add_table, add_column,
)
from app.services.auth_service import get_current_user

router = APIRouter(tags=["projects"])


def _org_id(user_id: str, db: Session) -> str:
    return get_current_user(db, user_id).memberships[0].organization_id


# ── Projects ──

@router.post("/projects", response_model=ProjectResponse, status_code=201)
def api_create_project(data: ProjectCreate, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return create_project(db, _org_id(user_id, db), user_id, data)


@router.get("/projects", response_model=list[ProjectResponse])
def api_list_projects(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return list_projects(db, _org_id(user_id, db))


@router.get("/projects/{project_id}", response_model=ProjectResponse)
def api_get_project(project_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return get_project(db, _org_id(user_id, db), project_id)


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
def api_add_source(project_id: str, data: ConnectionCreate, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return add_source(db, _org_id(user_id, db), project_id, data)


@router.get("/projects/{project_id}/sources", response_model=list[ConnectionResponse])
def api_list_sources(project_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return list_sources(db, _org_id(user_id, db), project_id)


# ── Targets ──

@router.post("/projects/{project_id}/targets", response_model=ConnectionResponse, status_code=201)
def api_add_target(project_id: str, data: ConnectionCreate, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return add_target(db, _org_id(user_id, db), project_id, data)


@router.get("/projects/{project_id}/targets", response_model=list[ConnectionResponse])
def api_list_targets(project_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return list_targets(db, _org_id(user_id, db), project_id)


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
