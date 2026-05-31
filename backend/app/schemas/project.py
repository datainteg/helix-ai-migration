from typing import Any, Optional
from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    # SC-019: bound free-text inputs so unbounded blobs can't flow into
    # storage / downstream prompts. Names are short; description is a small
    # paragraph.
    name: str = Field(max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    risk_level: str = "unknown"
    migration_type: Optional[str] = Field(default=None, max_length=100)
    # The new-project form collects these; create_project provisions matching
    # SourceConnection / TargetConnection rows and stores environment.
    source_system: Optional[str] = Field(default=None, max_length=100)
    target_system: Optional[str] = Field(default=None, max_length=100)
    environment: Optional[str] = Field(default=None, max_length=50)
    # Optional explicit owner (defaults to the creator) + initial status.
    owner_id: Optional[str] = Field(default=None, max_length=36)
    status: Optional[str] = Field(default=None, max_length=50)


class ProjectResponse(BaseModel):
    id: str
    organization_id: str
    name: str
    slug: Optional[str] = None
    description: Optional[str] = None
    status: str
    risk_level: str
    migration_type: Optional[str] = None
    owner_id: str
    # Resolved owner display name (from the User row), for the UI.
    owner_name: Optional[str] = None
    # Operational hold — when True, new workflow starts are refused.
    on_hold: bool = False
    # Pre-start approval gate — when True, runs need manager approval first.
    require_run_approval: bool = True
    # Derived from the project's source/target connection rows (first of each).
    source_system: Optional[str] = None
    target_system: Optional[str] = None
    environment: Optional[str] = None

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
    # SC-019: source_text becomes the BMAD requirement that is concatenated
    # into every agent's LLM prompt. Cap at 10 KB.
    source_text: str = Field(max_length=10_000)


class RequirementResponse(BaseModel):
    id: str
    project_id: str
    source_text: str
    status: str
    version: str
    root_id: Optional[str] = None
    created_at: Optional[Any] = None

    model_config = {"from_attributes": True}


class RequirementUpdate(BaseModel):
    # SC-019: same 10 KB cap as create — this becomes the agent prompt.
    source_text: str = Field(max_length=10_000)


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
