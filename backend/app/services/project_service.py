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
from app.services.migration_types import normalize_migration_type as _normalize_mt


# ── Projects ────────────────────────────────────────────────────────


def _owner_name_map(db: Session, owner_ids: set[str]) -> dict[str, str]:
    """Resolve a set of owner ids to display names in one query."""
    from app.models.identity import User
    if not owner_ids:
        return {}
    rows = db.query(User.id, User.name, User.email).filter(User.id.in_(owner_ids)).all()
    return {uid: (name or email or uid) for uid, name, email in rows}


def _project_to_response(project: Project, owner_names: dict[str, str] | None = None) -> ProjectResponse:
    """Serialise a Project, deriving source/target system from its first
    source/target connection row, and resolving the owner name when provided."""
    src = project.source_connections[0].connector_type if project.source_connections else None
    tgt = project.target_connections[0].connector_type if project.target_connections else None
    return ProjectResponse(
        id=project.id,
        organization_id=project.organization_id,
        name=project.name,
        description=project.description,
        status=project.status,
        risk_level=project.risk_level,
        migration_type=_normalize_mt(project.migration_type),
        owner_id=project.owner_id,
        owner_name=(owner_names or {}).get(project.owner_id),
        on_hold=bool(getattr(project, "on_hold", False)),
        require_run_approval=bool(getattr(project, "require_run_approval", True)),
        source_system=src,
        target_system=tgt,
        environment=getattr(project, "environment", None),
    )


def create_project(db: Session, org_id: str, owner_id: str, data: ProjectCreate) -> ProjectResponse:
    # Explicit owner from the form wins; otherwise the creator owns it.
    resolved_owner = data.owner_id or owner_id
    project = Project(
        organization_id=org_id, owner_id=resolved_owner, name=data.name,
        description=data.description, risk_level=data.risk_level,
        migration_type=_normalize_mt(data.migration_type), environment=data.environment,
        status=data.status or "draft",
    )
    db.add(project)
    db.flush()  # get project.id for the connection rows

    # Provision source/target connection rows from the chosen systems so the
    # project carries its source→target intent (the migration flow fills in
    # credentials later via the connection endpoints).
    if data.source_system:
        db.add(SourceConnection(
            organization_id=org_id, project_id=project.id,
            name=f"{data.source_system} source", connector_type=data.source_system, status="draft",
        ))
    if data.target_system:
        db.add(TargetConnection(
            organization_id=org_id, project_id=project.id,
            name=f"{data.target_system} target", connector_type=data.target_system, status="draft",
        ))
    db.commit()
    db.refresh(project)
    return _project_to_response(project, _owner_name_map(db, {project.owner_id}))


def force_delete_project(db: Session, project_id: str) -> None:
    """ADMIN hard delete: permanently remove a project and ALL child rows
    (FK-ordered). Irreversible. Callers must authorize (admin-only)."""
    from sqlalchemy import text
    # children of workflow_runs / recon_runs / validation_runs first
    db.execute(text("delete from workflow_steps where workflow_run_id in (select id from workflow_runs where project_id=:p)"), {"p": project_id})
    db.execute(text("delete from recon_results where run_id in (select id from recon_runs where project_id=:p)"), {"p": project_id})
    db.execute(text("delete from validation_results where run_id in (select id from validation_runs where project_id=:p)"), {"p": project_id})
    # column → table → schema metadata tree
    db.execute(text("delete from columns where table_id in (select t.id from tables t join schemas s on t.schema_id=s.id where s.project_id=:p)"), {"p": project_id})
    db.execute(text("delete from tables where schema_id in (select id from schemas where project_id=:p)"), {"p": project_id})
    for t in (
        "workflow_runs", "recon_runs", "validation_runs", "validation_rules",
        "schemas", "source_schema_snapshots", "source_connections",
        "target_connections", "migration_requirements", "subprojects",
    ):
        try:
            db.execute(text(f"delete from {t} where project_id=:p"), {"p": project_id})
        except Exception:
            db.rollback()  # table may not exist in this deployment; continue
            raise
    db.execute(text("delete from projects where id=:p"), {"p": project_id})
    db.commit()


def list_projects(db: Session, org_id: str, include_archived: bool = False) -> list[ProjectResponse]:
    q = db.query(Project).filter(Project.organization_id == org_id, Project.status != "deleted")
    if not include_archived:
        q = q.filter(Project.status != "archived")
    rows = q.all()
    names = _owner_name_map(db, {p.owner_id for p in rows})
    return [_project_to_response(p, names) for p in rows]


def get_project(db: Session, org_id: str, project_id: str) -> ProjectResponse:
    project = _get_project(db, org_id, project_id)
    return _project_to_response(project, _owner_name_map(db, {project.owner_id}))


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
    db.flush()
    req.root_id = req.id  # a brand-new requirement is the root of its own chain
    db.commit()
    db.refresh(req)
    return RequirementResponse.model_validate(req)


def edit_requirement(db: Session, org_id: str, project_id: str, requirement_id: str, source_text: str) -> RequirementResponse:
    """Edit a requirement by creating a NEW version in the same chain.

    History is preserved: the prior row is kept (marked 'superseded') and a new
    row is inserted with the next version number, sharing root_id. The latest
    version is what runs use.
    """
    _get_project(db, org_id, project_id)
    current = (
        db.query(MigrationRequirement)
        .filter(MigrationRequirement.id == requirement_id, MigrationRequirement.project_id == project_id)
        .first()
    )
    if not current:
        raise HTTPException(status_code=404, detail="Requirement not found")

    root = current.root_id or current.id
    siblings = db.query(MigrationRequirement).filter(
        (MigrationRequirement.root_id == root) | (MigrationRequirement.id == root),
        MigrationRequirement.project_id == project_id,
    ).all()
    next_version = max((int(s.version) if str(s.version).isdigit() else 1) for s in siblings) + 1
    # Retire every prior version in this chain — the new one becomes current.
    for s in siblings:
        if s.status != "superseded":
            s.status = "superseded"

    new_req = MigrationRequirement(
        project_id=project_id, source_text=source_text,
        version=str(next_version), root_id=root, status="draft",
    )
    db.add(new_req)
    db.commit()
    db.refresh(new_req)
    return RequirementResponse.model_validate(new_req)


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
