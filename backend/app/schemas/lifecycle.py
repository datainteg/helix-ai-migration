"""Request/response schemas + serializers for the stage-gated lifecycle and
markdown-artifact review."""
from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


# ── Stage action request bodies ──────────────────────────────────────
class StageActionRequest(BaseModel):
    comment: Optional[str] = Field(default=None, max_length=4000)
    artifact_id: Optional[str] = None


class StageRejectRequest(BaseModel):
    comment: str = Field(min_length=1, max_length=4000)


class StageSkipRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


class StageResubmitRequest(BaseModel):
    artifact_version_id: Optional[str] = None


class StageAgentRunRequest(BaseModel):
    instructions: Optional[str] = Field(default=None, max_length=4000)


# ── Artifact request bodies ──────────────────────────────────────────
class ArtifactVersionCreate(BaseModel):
    content_markdown: Optional[str] = Field(default=None, max_length=2_000_000)
    content_json: Optional[dict] = None
    change_summary: Optional[str] = Field(default=None, max_length=2000)
    base_version_id: Optional[str] = None


class ArtifactReviewAction(BaseModel):
    comment: Optional[str] = Field(default=None, max_length=4000)
    version_id: Optional[str] = None


class ArtifactRejectAction(BaseModel):
    comment: str = Field(min_length=1, max_length=4000)
    version_id: Optional[str] = None


class ArtifactCommentCreate(BaseModel):
    comment: str = Field(min_length=1, max_length=4000)
    version_id: Optional[str] = None


# ── Serializers (models → dict) ──────────────────────────────────────
def stage_to_dict(s) -> dict[str, Any]:
    return {
        "id": s.id, "project_id": s.project_id, "stage_key": s.stage_key,
        "stage_name": s.stage_name, "stage_order": s.stage_order, "status": s.status,
        "assigned_agent": s.assigned_agent, "is_optional": s.is_optional,
        "current_artifact_id": s.current_artifact_id,
        "started_at": str(s.started_at) if s.started_at else None,
        "generated_at": str(s.generated_at) if s.generated_at else None,
        "submitted_for_review_at": str(s.submitted_for_review_at) if s.submitted_for_review_at else None,
        "approved_at": str(s.approved_at) if s.approved_at else None,
        "rejected_at": str(s.rejected_at) if s.rejected_at else None,
        "completed_at": str(s.completed_at) if s.completed_at else None,
    }


def artifact_to_dict(a) -> dict[str, Any]:
    return {
        "id": a.id, "project_id": a.project_id, "stage_id": a.stage_id,
        "artifact_type": a.artifact_type, "title": a.title, "description": a.description,
        "current_version_id": a.current_version_id, "status": a.status,
        "created_by_agent": a.created_by_agent, "created_by_user_id": a.created_by_user_id,
        "approved_by_user_id": a.approved_by_user_id,
        "approved_at": str(a.approved_at) if a.approved_at else None,
        "created_at": str(a.created_at) if a.created_at else None,
    }


def version_to_dict(v) -> dict[str, Any]:
    return {
        "id": v.id, "artifact_id": v.artifact_id, "version_number": v.version_number,
        "content_markdown": v.content_markdown, "content_json": v.content_json,
        "change_summary": v.change_summary, "created_by_type": v.created_by_type,
        "created_by_agent": v.created_by_agent, "created_by_user_id": v.created_by_user_id,
        "source_version_id": v.source_version_id,
        "created_at": str(v.created_at) if v.created_at else None,
    }


def comment_to_dict(c) -> dict[str, Any]:
    return {
        "id": c.id, "artifact_id": c.artifact_id, "artifact_version_id": c.artifact_version_id,
        "user_id": c.user_id, "comment": c.comment,
        "created_at": str(c.created_at) if c.created_at else None,
    }
