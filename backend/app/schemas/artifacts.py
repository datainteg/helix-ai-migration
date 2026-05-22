from typing import Optional
from pydantic import BaseModel


class ArtifactResponse(BaseModel):
    id: str
    organization_id: str
    project_id: str
    filename: str
    file_type: str
    storage_path: str
    content_hash: str
    status: str

    model_config = {"from_attributes": True}


class ArtifactVersionResponse(BaseModel):
    id: str
    artifact_id: str
    version_number: str
    content_hash: str
    storage_path: str
    generated_by_agent: Optional[str] = None
    llm_model: Optional[str] = None
    change_summary: Optional[str] = None
    approval_status: str
    approved_by: Optional[str] = None

    model_config = {"from_attributes": True}


class ArtifactApprovalCreate(BaseModel):
    decision: str
    notes: Optional[str] = None
