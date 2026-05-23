from typing import Optional
from pydantic import BaseModel


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


class ConnectionResponse(BaseModel):
    id: str
    organization_id: str
    project_id: str
    name: str
    connector_type: str
    status: str

    model_config = {"from_attributes": True}


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
