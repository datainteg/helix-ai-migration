from typing import Any, Optional
from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    risk_level: str = "unknown"
    migration_type: Optional[str] = None


class ProjectResponse(BaseModel):
    id: str
    organization_id: str
    name: str
    description: Optional[str] = None
    status: str
    risk_level: str
    migration_type: Optional[str] = None
    owner_id: str

    model_config = {"from_attributes": True}


class SubProjectCreate(BaseModel):
    name: str
    migration_domain: Optional[str] = None


class SubProjectResponse(BaseModel):
    id: str
    project_id: str
    name: str
    migration_domain: Optional[str] = None
    status: str

    model_config = {"from_attributes": True}


class RequirementCreate(BaseModel):
    source_text: str


class RequirementResponse(BaseModel):
    id: str
    project_id: str
    source_text: str
    status: str
    version: str

    model_config = {"from_attributes": True}


class ConnectionCreate(BaseModel):
    name: str
    connector_type: str
    # Full credentials dict (host, port, username, password, etc.).
    # Encrypted server-side before persistence; never returned via API.
    config: dict[str, Any] = Field(default_factory=dict)


class ConnectionUpdate(BaseModel):
    """Partial update — only provided fields are touched."""

    name: Optional[str] = None
    status: Optional[str] = None
    config: Optional[dict[str, Any]] = None


class ConnectionResponse(BaseModel):
    id: str
    organization_id: str
    project_id: str
    name: str
    connector_type: str
    status: str
    # Safe-to-display masked preview of the config (passwords redacted).
    config_masked: Optional[str] = None

    model_config = {"from_attributes": True}


class ConnectionTestResponse(BaseModel):
    success: bool
    message: str


class SchemaCreate(BaseModel):
    name: str
    schema_type: str = "source"


class SchemaResponse(BaseModel):
    id: str
    project_id: str
    name: str
    schema_type: str

    model_config = {"from_attributes": True}


class TableCreate(BaseModel):
    name: str
    row_count: Optional[int] = None


class TableResponse(BaseModel):
    id: str
    schema_id: str
    name: str
    row_count: Optional[int] = None

    model_config = {"from_attributes": True}


class ColumnCreate(BaseModel):
    name: str
    data_type: str
    nullable: bool = True
    ordinal_position: Optional[int] = None
