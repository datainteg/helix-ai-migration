from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.project import (
    Project, SubProject, MigrationRequirement,
    SourceConnection, TargetConnection,
    SchemaMetadata, TableMetadata, ColumnMetadata,
)
from app.schemas.project import (
    ProjectCreate, ProjectResponse,
    SubProjectCreate, SubProjectResponse,
    RequirementCreate, RequirementResponse,
    ConnectionCreate, ConnectionResponse,
    SchemaCreate, SchemaResponse,
    TableCreate, TableResponse,
    ColumnCreate,
)


# ── Projects ──

def create_project(db: Session, org_id: str, owner_id: str, data: ProjectCreate) -> ProjectResponse:
    project = Project(organization_id=org_id, owner_id=owner_id, name=data.name, description=data.description, risk_level=data.risk_level)
    db.add(project)
    db.commit()
    db.refresh(project)
    return ProjectResponse.model_validate(project)


def list_projects(db: Session, org_id: str) -> list[ProjectResponse]:
    projects = db.query(Project).filter(Project.organization_id == org_id).all()
    return [ProjectResponse.model_validate(p) for p in projects]


def get_project(db: Session, org_id: str, project_id: str) -> ProjectResponse:
    project = _get_project(db, org_id, project_id)
    return ProjectResponse.model_validate(project)


def _get_project(db: Session, org_id: str, project_id: str) -> Project:
    project = db.query(Project).filter(Project.id == project_id, Project.organization_id == org_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def ensure_project_access(db: Session, org_id: str, project_id: str) -> Project:
    return _get_project(db, org_id, project_id)


# ── SubProjects ──

def add_subproject(db: Session, org_id: str, project_id: str, data: SubProjectCreate) -> SubProjectResponse:
    _get_project(db, org_id, project_id)
    sp = SubProject(project_id=project_id, name=data.name, migration_domain=data.migration_domain)
    db.add(sp)
    db.commit()
    db.refresh(sp)
    return SubProjectResponse.model_validate(sp)


# ── Requirements ──

def add_requirement(db: Session, org_id: str, project_id: str, data: RequirementCreate) -> RequirementResponse:
    _get_project(db, org_id, project_id)
    req = MigrationRequirement(project_id=project_id, source_text=data.source_text)
    db.add(req)
    db.commit()
    db.refresh(req)
    return RequirementResponse.model_validate(req)


# ── Source / Target Connections ──

def add_source(db: Session, org_id: str, project_id: str, data: ConnectionCreate) -> ConnectionResponse:
    _get_project(db, org_id, project_id)
    conn = SourceConnection(organization_id=org_id, project_id=project_id, name=data.name, connector_type=data.connector_type)
    db.add(conn)
    db.commit()
    db.refresh(conn)
    return ConnectionResponse.model_validate(conn)


def list_sources(db: Session, org_id: str, project_id: str) -> list[ConnectionResponse]:
    _get_project(db, org_id, project_id)
    conns = db.query(SourceConnection).filter(SourceConnection.project_id == project_id, SourceConnection.organization_id == org_id).all()
    return [ConnectionResponse.model_validate(c) for c in conns]


def add_target(db: Session, org_id: str, project_id: str, data: ConnectionCreate) -> ConnectionResponse:
    _get_project(db, org_id, project_id)
    conn = TargetConnection(organization_id=org_id, project_id=project_id, name=data.name, connector_type=data.connector_type)
    db.add(conn)
    db.commit()
    db.refresh(conn)
    return ConnectionResponse.model_validate(conn)


def list_targets(db: Session, org_id: str, project_id: str) -> list[ConnectionResponse]:
    _get_project(db, org_id, project_id)
    conns = db.query(TargetConnection).filter(TargetConnection.project_id == project_id, TargetConnection.organization_id == org_id).all()
    return [ConnectionResponse.model_validate(c) for c in conns]


# ── Schema / Table / Column Metadata ──

def add_schema(db: Session, org_id: str, project_id: str, data: SchemaCreate) -> SchemaResponse:
    _get_project(db, org_id, project_id)
    schema = SchemaMetadata(project_id=project_id, name=data.name, schema_type=data.schema_type)
    db.add(schema)
    db.commit()
    db.refresh(schema)
    return SchemaResponse.model_validate(schema)


def add_table(db: Session, org_id: str, schema_id: str, data: TableCreate) -> TableResponse:
    schema = (
        db.query(SchemaMetadata)
        .join(Project, SchemaMetadata.project_id == Project.id)
        .filter(SchemaMetadata.id == schema_id, Project.organization_id == org_id)
        .first()
    )
    if not schema:
        raise HTTPException(status_code=404, detail="Schema not found")
    table = TableMetadata(schema_id=schema_id, name=data.name, row_count=data.row_count)
    db.add(table)
    db.commit()
    db.refresh(table)
    return TableResponse.model_validate(table)


def add_column(db: Session, org_id: str, table_id: str, data: ColumnCreate):
    table = (
        db.query(TableMetadata)
        .join(SchemaMetadata, TableMetadata.schema_id == SchemaMetadata.id)
        .join(Project, SchemaMetadata.project_id == Project.id)
        .filter(TableMetadata.id == table_id, Project.organization_id == org_id)
        .first()
    )
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    col = ColumnMetadata(table_id=table_id, name=data.name, data_type=data.data_type, nullable=data.nullable, ordinal_position=data.ordinal_position)
    db.add(col)
    db.commit()
