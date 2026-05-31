from sqlalchemy import Column, String, ForeignKey, Text, Integer, Boolean
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class Project(BaseModel):
    __tablename__ = "projects"

    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    # URL-friendly identifier (unique per org). Readable project URLs use this
    # instead of the UUID. Nullable for legacy rows (backfilled by migration);
    # the project-fetch resolves either slug or id.
    slug = Column(String(140), nullable=True, index=True)
    description = Column(Text, nullable=True)
    status = Column(String(50), default="draft", nullable=False)
    risk_level = Column(String(20), default="unknown")
    migration_type = Column(String(50), nullable=True)
    # Target deployment environment label (dev/staging/prod/…). Collected at
    # project creation; nullable for rows created before this column.
    environment = Column(String(50), nullable=True)
    # Operational hold — when True, starting new BMAD/agent workflows is refused.
    # Orthogonal to `status` (a live project can be put on hold and resumed).
    on_hold = Column(Boolean, default=False, nullable=False, server_default="false")
    # Pre-start governance: when True (default), a workflow run must be approved
    # by a project manager before the agents run. Toggleable per project.
    require_run_approval = Column(Boolean, default=True, nullable=False, server_default="true")
    owner_id = Column(String(36), nullable=False)

    organization = relationship("Organization", back_populates="projects")
    subprojects = relationship("SubProject", back_populates="project", cascade="all, delete-orphan")
    requirements = relationship("MigrationRequirement", back_populates="project", cascade="all, delete-orphan")
    source_connections = relationship("SourceConnection", back_populates="project", cascade="all, delete-orphan")
    target_connections = relationship("TargetConnection", back_populates="project", cascade="all, delete-orphan")


class SubProject(BaseModel):
    __tablename__ = "subprojects"

    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)
    name = Column(String(255), nullable=False)
    migration_domain = Column(String(100), nullable=True)
    status = Column(String(50), default="draft", nullable=False)

    project = relationship("Project", back_populates="subprojects")


class ProjectComment(BaseModel):
    """A note on a project's activity timeline. `kind` distinguishes free-text
    user comments from system-recorded hold/live events (which carry the
    toggle reason in `body`)."""

    __tablename__ = "project_comments"

    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    author_id = Column(String(36), nullable=True)         # null = system
    author_name = Column(String(255), nullable=True)      # denormalised for display
    kind = Column(String(20), default="comment", nullable=False)  # comment | hold | live
    body = Column(Text, nullable=False)


class MigrationRequirement(BaseModel):
    __tablename__ = "migration_requirements"

    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)
    source_text = Column(Text, nullable=False)
    status = Column(String(50), default="draft")
    version = Column(String(20), default="1")
    # Version-chain grouping: all versions of one logical requirement share a
    # root_id (the id of v1). NULL for legacy rows = treated as their own root.
    # Editing a requirement creates a NEW row (next version) with the same
    # root_id, preserving history.
    root_id = Column(String(36), nullable=True, index=True)

    project = relationship("Project", back_populates="requirements")


class WorkflowRunRequest(BaseModel):
    """A request to run a workflow that needs project-manager approval BEFORE the
    agents start (pre-start gate). Separate from WorkflowRun (which only exists
    once a run actually starts in Temporal). On approval, the normal start path
    runs and its workflow_id is linked back here.
    """
    __tablename__ = "workflow_run_requests"

    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    requirement_id = Column(String(36), nullable=False)
    requested_by = Column(String(36), nullable=False)        # actor user_id
    status = Column(String(20), default="pending", nullable=False)  # pending|approved|rejected
    approver_id = Column(String(36), nullable=True)
    notes = Column(Text, nullable=True)
    workflow_id = Column(String(100), nullable=True)         # set once started after approval


class SourceConnection(BaseModel):
    __tablename__ = "source_connections"

    organization_id = Column(String(36), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)
    name = Column(String(255), nullable=False)
    connector_type = Column(String(50), nullable=False)
    status = Column(String(50), default="draft")
    # Encrypted JSON blob of the connector config (host, port, username, password, etc.).
    # Fernet-encrypted using app.services.secret_service. NEVER returned via API.
    encrypted_config = Column(Text, nullable=True)
    # Safe-to-display redacted preview of the config (passwords masked).
    config_masked = Column(String(500), nullable=True)

    project = relationship("Project", back_populates="source_connections")
    schemas = relationship("SchemaMetadata", back_populates="source_connection", foreign_keys="SchemaMetadata.source_connection_id")


class TargetConnection(BaseModel):
    __tablename__ = "target_connections"

    organization_id = Column(String(36), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)
    name = Column(String(255), nullable=False)
    connector_type = Column(String(50), nullable=False)
    status = Column(String(50), default="draft")
    encrypted_config = Column(Text, nullable=True)
    config_masked = Column(String(500), nullable=True)

    project = relationship("Project", back_populates="target_connections")
    schemas = relationship("SchemaMetadata", back_populates="target_connection", foreign_keys="SchemaMetadata.target_connection_id")


class SchemaMetadata(BaseModel):
    __tablename__ = "schemas"

    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)
    source_connection_id = Column(String(36), ForeignKey("source_connections.id"), nullable=True)
    target_connection_id = Column(String(36), ForeignKey("target_connections.id"), nullable=True)
    name = Column(String(255), nullable=False)
    schema_type = Column(String(20), default="source")

    source_connection = relationship("SourceConnection", back_populates="schemas", foreign_keys=[source_connection_id])
    target_connection = relationship("TargetConnection", back_populates="schemas", foreign_keys=[target_connection_id])
    tables = relationship("TableMetadata", back_populates="schema", cascade="all, delete-orphan")


class TableMetadata(BaseModel):
    __tablename__ = "tables"

    schema_id = Column(String(36), ForeignKey("schemas.id"), nullable=False)
    name = Column(String(255), nullable=False)
    row_count = Column(Integer, nullable=True)

    schema = relationship("SchemaMetadata", back_populates="tables")
    columns = relationship("ColumnMetadata", back_populates="table", cascade="all, delete-orphan")


class ColumnMetadata(BaseModel):
    __tablename__ = "columns"

    table_id = Column(String(36), ForeignKey("tables.id"), nullable=False)
    name = Column(String(255), nullable=False)
    data_type = Column(String(100), nullable=False)
    nullable = Column(Boolean, default=True)
    ordinal_position = Column(Integer, nullable=True)

    table = relationship("TableMetadata", back_populates="columns")
