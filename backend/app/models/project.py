from sqlalchemy import Column, String, ForeignKey, Text, Integer, Boolean
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class Project(BaseModel):
    __tablename__ = "projects"

    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(50), default="draft", nullable=False)
    risk_level = Column(String(20), default="unknown")
    migration_type = Column(String(50), nullable=True)
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


class MigrationRequirement(BaseModel):
    __tablename__ = "migration_requirements"

    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)
    source_text = Column(Text, nullable=False)
    status = Column(String(50), default="draft")
    version = Column(String(20), default="1")

    project = relationship("Project", back_populates="requirements")


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
