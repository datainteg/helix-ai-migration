import json

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
    ConnectionCreate, ConnectionUpdate, ConnectionResponse,
    SchemaCreate, SchemaResponse,
    TableCreate, TableResponse,
    ColumnCreate,
)
from app.services.secret_service import encrypt_value, decrypt_value


# ── Projects ────────────────────────────────────────────────────────


def create_project(db: Session, org_id: str, owner_id: str, data: ProjectCreate) -> ProjectResponse:
    project = Project(organization_id=org_id, owner_id=owner_id, name=data.name, description=data.description, risk_level=data.risk_level, migration_type=data.migration_type)
    db.add(project)
    db.commit()
    db.refresh(project)
    return ProjectResponse.model_validate(project)


def list_projects(db: Session, org_id: str, include_archived: bool = False) -> list[ProjectResponse]:
    q = db.query(Project).filter(Project.organization_id == org_id, Project.status != "deleted")
    if not include_archived:
        q = q.filter(Project.status != "archived")
    return [ProjectResponse.model_validate(p) for p in q.all()]


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


# ── SubProjects ─────────────────────────────────────────────────────


def add_subproject(db: Session, org_id: str, project_id: str, data: SubProjectCreate) -> SubProjectResponse:
    _get_project(db, org_id, project_id)
    sp = SubProject(project_id=project_id, name=data.name, migration_domain=data.migration_domain)
    db.add(sp)
    db.commit()
    db.refresh(sp)
    return SubProjectResponse.model_validate(sp)


# ── Requirements ────────────────────────────────────────────────────


def add_requirement(db: Session, org_id: str, project_id: str, data: RequirementCreate) -> RequirementResponse:
    _get_project(db, org_id, project_id)
    req = MigrationRequirement(project_id=project_id, source_text=data.source_text)
    db.add(req)
    db.commit()
    db.refresh(req)
    return RequirementResponse.model_validate(req)


# ── Connection config encryption helpers ────────────────────────────

_SENSITIVE_KEYS = {
    "password", "secret", "token", "api_key", "access_key", "access_key_id",
    "secret_access_key", "client_secret", "private_key", "passphrase",
}


def _mask_value(key: str, value) -> str:
    """Return masked representation of a config value for safe display.

    SC-039: sensitive keys are masked to a fixed ``"***"`` regardless of
    length. The previous ``f"***{value[-4:]}"`` leaked the last 4 characters
    of every stored password / API key through the ``config_masked`` field,
    which is returned by ``GET /projects/{id}/sources`` to anyone with
    ``project:read`` (i.e. every role). Four trailing characters of a short
    or low-entropy secret materially shrink the brute-force space, so we no
    longer reveal them.
    """
    if not isinstance(value, str):
        return str(value)
    if key.lower() in _SENSITIVE_KEYS or any(s in key.lower() for s in _SENSITIVE_KEYS):
        return "***"
    return value


def _build_config_mask(config: dict) -> str:
    """Build a compact human-readable mask of the config dict.

    Example: 'host=db.example.com port=5432 user=admin password=***xyz1'
    """
    parts = []
    for k, v in config.items():
        if isinstance(v, (dict, list)):
            parts.append(f"{k}=<{type(v).__name__}>")
        else:
            parts.append(f"{k}={_mask_value(k, v)}")
    return " ".join(parts)[:500]


def _encrypt_config(config: dict) -> tuple[str, str]:
    """Encrypt a config dict. Returns (encrypted_json, masked_preview)."""
    if not config:
        return "", ""
    encrypted = encrypt_value(json.dumps(config, default=str, sort_keys=True))
    masked = _build_config_mask(config)
    return encrypted, masked


def _decrypt_config(encrypted: str | None) -> dict:
    """Decrypt a previously encrypted config blob. Empty if missing."""
    if not encrypted:
        return {}
    raw = decrypt_value(encrypted)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def get_source_config(db: Session, org_id: str, project_id: str, source_id: str) -> tuple[SourceConnection, dict]:
    """Internal helper: load + decrypt a source connection's config.

    Returns (model_row, decrypted_config). 404 if not found / cross-org.
    """
    _get_project(db, org_id, project_id)
    conn = (
        db.query(SourceConnection)
        .filter(
            SourceConnection.id == source_id,
            SourceConnection.project_id == project_id,
            SourceConnection.organization_id == org_id,
        )
        .first()
    )
    if not conn:
        raise HTTPException(status_code=404, detail="Source connection not found")
    return conn, _decrypt_config(conn.encrypted_config)


def get_target_config(db: Session, org_id: str, project_id: str, target_id: str) -> tuple[TargetConnection, dict]:
    _get_project(db, org_id, project_id)
    conn = (
        db.query(TargetConnection)
        .filter(
            TargetConnection.id == target_id,
            TargetConnection.project_id == project_id,
            TargetConnection.organization_id == org_id,
        )
        .first()
    )
    if not conn:
        raise HTTPException(status_code=404, detail="Target connection not found")
    return conn, _decrypt_config(conn.encrypted_config)


# ── Source / Target Connections ─────────────────────────────────────


def add_source(db: Session, org_id: str, project_id: str, data: ConnectionCreate) -> ConnectionResponse:
    _get_project(db, org_id, project_id)
    encrypted, masked = _encrypt_config(data.config)
    conn = SourceConnection(
        organization_id=org_id,
        project_id=project_id,
        name=data.name,
        connector_type=data.connector_type,
        encrypted_config=encrypted or None,
        config_masked=masked or None,
    )
    db.add(conn)
    db.commit()
    db.refresh(conn)
    return ConnectionResponse.model_validate(conn)


def list_sources(db: Session, org_id: str, project_id: str) -> list[ConnectionResponse]:
    _get_project(db, org_id, project_id)
    conns = db.query(SourceConnection).filter(SourceConnection.project_id == project_id, SourceConnection.organization_id == org_id).all()
    return [ConnectionResponse.model_validate(c) for c in conns]


def update_source(db: Session, org_id: str, project_id: str, source_id: str, data: ConnectionUpdate) -> ConnectionResponse:
    conn, _ = get_source_config(db, org_id, project_id, source_id)
    if data.name is not None:
        conn.name = data.name
    if data.status is not None:
        conn.status = data.status
    if data.config is not None:
        encrypted, masked = _encrypt_config(data.config)
        conn.encrypted_config = encrypted or None
        conn.config_masked = masked or None
    db.commit()
    db.refresh(conn)
    return ConnectionResponse.model_validate(conn)


def delete_source(db: Session, org_id: str, project_id: str, source_id: str) -> None:
    conn, _ = get_source_config(db, org_id, project_id, source_id)
    db.delete(conn)
    db.commit()


def add_target(db: Session, org_id: str, project_id: str, data: ConnectionCreate) -> ConnectionResponse:
    _get_project(db, org_id, project_id)
    encrypted, masked = _encrypt_config(data.config)
    conn = TargetConnection(
        organization_id=org_id,
        project_id=project_id,
        name=data.name,
        connector_type=data.connector_type,
        encrypted_config=encrypted or None,
        config_masked=masked or None,
    )
    db.add(conn)
    db.commit()
    db.refresh(conn)
    return ConnectionResponse.model_validate(conn)


def list_targets(db: Session, org_id: str, project_id: str) -> list[ConnectionResponse]:
    _get_project(db, org_id, project_id)
    conns = db.query(TargetConnection).filter(TargetConnection.project_id == project_id, TargetConnection.organization_id == org_id).all()
    return [ConnectionResponse.model_validate(c) for c in conns]


def update_target(db: Session, org_id: str, project_id: str, target_id: str, data: ConnectionUpdate) -> ConnectionResponse:
    conn, _ = get_target_config(db, org_id, project_id, target_id)
    if data.name is not None:
        conn.name = data.name
    if data.status is not None:
        conn.status = data.status
    if data.config is not None:
        encrypted, masked = _encrypt_config(data.config)
        conn.encrypted_config = encrypted or None
        conn.config_masked = masked or None
    db.commit()
    db.refresh(conn)
    return ConnectionResponse.model_validate(conn)


def delete_target(db: Session, org_id: str, project_id: str, target_id: str) -> None:
    conn, _ = get_target_config(db, org_id, project_id, target_id)
    db.delete(conn)
    db.commit()


# ── Schema / Table / Column Metadata ────────────────────────────────


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
