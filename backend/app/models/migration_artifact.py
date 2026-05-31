"""Stage-document artifact lifecycle (markdown-in-DB).

Distinct from the file-based `code_artifacts` (generated code/SQL): these hold
the human-reviewed stage documents (project-context, business-analysis, …) with
full version history, review status, and comment threads. The UI bridges both.

Tables are namespaced `migration_artifact*` so they never collide with the
existing `code_artifacts` / `code_artifact_versions` / `code_reviews`.
"""
from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey, JSON, Index

from app.models.base import BaseModel


class MigrationArtifact(BaseModel):
    __tablename__ = "migration_artifacts"

    organization_id = Column(String(36), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    stage_id = Column(String(36), ForeignKey("migration_stages.id", ondelete="SET NULL"), nullable=True, index=True)
    artifact_type = Column(String(60), nullable=False, index=True)   # project-context|business-analysis|...
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    current_version_id = Column(String(36), nullable=True)           # points at the active artifact_version
    status = Column(String(30), default="draft", nullable=False, index=True)  # draft|generated|under_review|changes_requested|resubmitted|approved|rejected|superseded
    created_by_agent = Column(String(80), nullable=True)
    created_by_user_id = Column(String(36), nullable=True)
    approved_by_user_id = Column(String(36), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)


class MigrationArtifactVersion(BaseModel):
    __tablename__ = "migration_artifact_versions"

    artifact_id = Column(String(36), ForeignKey("migration_artifacts.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)                 # 1, 2, 3 … (integer → correct ordering)
    content_markdown = Column(Text, nullable=True)
    content_json = Column(JSON, nullable=True)
    file_path = Column(String(500), nullable=True)                   # optional pointer to a file artifact
    change_summary = Column(Text, nullable=True)
    created_by_type = Column(String(20), nullable=False, default="agent")   # agent|user|system
    created_by_agent = Column(String(80), nullable=True)
    created_by_user_id = Column(String(36), nullable=True)
    source_version_id = Column(String(36), nullable=True)            # the version this was edited/resubmitted from

    __table_args__ = (
        Index("ix_migration_artifact_versions_artifact_ver", "artifact_id", "version_number"),
    )


class MigrationArtifactReview(BaseModel):
    __tablename__ = "migration_artifact_reviews"

    organization_id = Column(String(36), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    artifact_id = Column(String(36), ForeignKey("migration_artifacts.id", ondelete="CASCADE"), nullable=False, index=True)
    artifact_version_id = Column(String(36), ForeignKey("migration_artifact_versions.id", ondelete="CASCADE"), nullable=False)
    reviewer_user_id = Column(String(36), nullable=True)
    status = Column(String(30), default="pending", nullable=False)   # pending|approved|rejected|changes_requested
    comments = Column(Text, nullable=True)


class MigrationArtifactComment(BaseModel):
    __tablename__ = "migration_artifact_comments"

    organization_id = Column(String(36), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    artifact_id = Column(String(36), ForeignKey("migration_artifacts.id", ondelete="CASCADE"), nullable=False, index=True)
    artifact_version_id = Column(String(36), nullable=True)
    user_id = Column(String(36), nullable=True)
    comment = Column(Text, nullable=False)
