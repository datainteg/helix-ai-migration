"""Developer workspaces + generated code artifacts.

Generated code is treated as DRAFT until reviewed/approved; it is never executed
in the backend. code-server (optional) runs in an isolated per-project container.
"""
from sqlalchemy import Column, String, DateTime, Text, ForeignKey

from app.models.base import BaseModel


class DeveloperWorkspace(BaseModel):
    __tablename__ = "developer_workspaces"

    organization_id = Column(String(36), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    sprint_id = Column(String(36), nullable=True, index=True)
    workspace_alias = Column(String(80), nullable=True)
    status = Column(String(30), default="created", nullable=False)        # created|starting|running|stopped|error
    workspace_type = Column(String(30), default="artifact_only", nullable=False)  # code_server|external|artifact_only
    container_name = Column(String(120), nullable=True)
    workspace_url = Column(String(500), nullable=True)
    storage_path = Column(String(500), nullable=True)
    created_by_user_id = Column(String(36), nullable=True)


class GeneratedCodeArtifact(BaseModel):
    __tablename__ = "generated_code_artifacts"

    organization_id = Column(String(36), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    sprint_id = Column(String(36), nullable=True, index=True)
    stage_id = Column(String(36), nullable=True)
    artifact_id = Column(String(36), nullable=True)
    file_name = Column(String(255), nullable=False)
    file_type = Column(String(30), nullable=True)                         # sql|python|notebook|dag|yaml|md
    language = Column(String(40), nullable=True)
    content = Column(Text, nullable=True)
    status = Column(String(30), default="draft", nullable=False, index=True)  # draft|reviewed|approved|rejected
    generated_by_agent = Column(String(80), nullable=True)
    reviewed_by_user_id = Column(String(36), nullable=True)
