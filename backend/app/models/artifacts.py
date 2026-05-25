from sqlalchemy import Column, String, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class CodeArtifact(BaseModel):
    __tablename__ = "code_artifacts"

    organization_id = Column(String(36), nullable=False, index=True)
    project_id = Column(String(36), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(20), nullable=False)
    storage_path = Column(String(500), nullable=False)
    content_hash = Column(String(64), nullable=False)
    status = Column(String(50), default="uploaded")
    # Paired rollback script for migrations. NULL when no reversible script
    # exists (e.g., tech-writer docs). When set, GET /artifacts/{id}/rollback
    # returns the metadata of the reverse artifact.
    rollback_artifact_id = Column(String(36), ForeignKey("code_artifacts.id"), nullable=True)

    versions = relationship("CodeArtifactVersion", back_populates="artifact", cascade="all, delete-orphan")
    dependencies = relationship("ArtifactDependency", foreign_keys="ArtifactDependency.artifact_id", back_populates="artifact", cascade="all, delete-orphan")
    lineage = relationship("ArtifactLineage", foreign_keys="ArtifactLineage.source_artifact_id", back_populates="source_artifact", cascade="all, delete-orphan")


class CodeArtifactVersion(BaseModel):
    __tablename__ = "code_artifact_versions"

    artifact_id = Column(String(36), ForeignKey("code_artifacts.id"), nullable=False)
    version_number = Column(String(20), nullable=False)
    content_hash = Column(String(64), nullable=False)
    storage_path = Column(String(500), nullable=False)
    generated_by_agent = Column(String(100), nullable=True)
    llm_provider_id = Column(String(36), ForeignKey("llm_providers.id"), nullable=True)
    llm_model = Column(String(100), nullable=True)
    change_summary = Column(Text, nullable=True)
    approval_status = Column(String(50), default="draft")
    approved_by = Column(String(36), nullable=True)
    approved_at = Column(String(50), nullable=True)

    artifact = relationship("CodeArtifact", back_populates="versions")


class ArtifactDependency(BaseModel):
    __tablename__ = "artifact_dependencies"

    artifact_id = Column(String(36), ForeignKey("code_artifacts.id"), nullable=False)
    depends_on_artifact_id = Column(String(36), ForeignKey("code_artifacts.id"), nullable=False)
    dependency_type = Column(String(50), default="imports")

    artifact = relationship("CodeArtifact", foreign_keys=[artifact_id], back_populates="dependencies")


class ArtifactLineage(BaseModel):
    __tablename__ = "artifact_lineage"

    source_artifact_id = Column(String(36), ForeignKey("code_artifacts.id"), nullable=False)
    generated_artifact_id = Column(String(36), ForeignKey("code_artifacts.id"), nullable=False)
    conversion_run_id = Column(String(100), nullable=True)
    relationship_type = Column(String(50), default="generated_from")

    source_artifact = relationship("CodeArtifact", foreign_keys=[source_artifact_id], back_populates="lineage")


class ArtifactReview(BaseModel):
    __tablename__ = "code_reviews"

    artifact_version_id = Column(String(36), ForeignKey("code_artifact_versions.id"), nullable=False)
    review_type = Column(String(50), default="ai_review")
    summary = Column(Text, nullable=True)
    findings = Column(Text, nullable=True)
    reviewer_id = Column(String(36), nullable=True)


class ArtifactApproval(BaseModel):
    __tablename__ = "artifact_approvals"

    artifact_version_id = Column(String(36), ForeignKey("code_artifact_versions.id"), nullable=False)
    decision = Column(String(20), nullable=False)
    notes = Column(Text, nullable=True)
    approved_by = Column(String(36), nullable=False)
