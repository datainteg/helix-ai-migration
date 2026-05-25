"""Cutover orchestration API.

Endpoints:
  POST   /projects/{project_id}/cutovers              create a new cutover row
  GET    /projects/{project_id}/cutovers              list cutovers for a project
  GET    /cutovers/{cutover_id}                       fetch one
  POST   /cutovers/{cutover_id}/transition            advance state
  POST   /cutovers/{cutover_id}/diff                  record pre-flip diff summary

State machine guard rails live in app.models.cutover.ALLOWED_TRANSITIONS — the
endpoint rejects illegal transitions with 409 (Conflict) rather than 400 so
operators can distinguish "validation error" from "wrong state".
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.auth.dependencies import get_current_organization_id
from app.auth.jwt import get_current_user_id
from app.api.audit import write_audit
from app.models.cutover import MigrationCutover, ALLOWED_TRANSITIONS, VALID_STATES
from app.services.project_service import ensure_project_access

router = APIRouter(tags=["cutovers"])


class CutoverCreate(BaseModel):
    source_ref: str = Field(min_length=1, max_length=255)
    target_ref: str = Field(min_length=1, max_length=255)
    workflow_id: Optional[str] = None
    notes: Optional[str] = Field(default=None, max_length=2048)


class CutoverTransition(BaseModel):
    target_state: str = Field(min_length=1, max_length=20)
    notes: Optional[str] = Field(default=None, max_length=2048)


class CutoverDiff(BaseModel):
    source_count: int
    target_count: int
    diff_pct: float
    sample_size: int
    sample_hash: Optional[str] = None


_STATE_TIMESTAMP_COL = {
    "bulk": "bulk_started_at",
    "tail": "tail_started_at",
    "freeze": "freeze_started_at",
    "diff": "diff_started_at",
    "flip": "flip_started_at",
    "done": "done_at",
    "rolled_back": "rolled_back_at",
}


def _serialize(c: MigrationCutover) -> dict:
    return {
        "id": c.id,
        "project_id": c.project_id,
        "workflow_id": c.workflow_id,
        "source_ref": c.source_ref,
        "target_ref": c.target_ref,
        "state": c.state,
        "notes": c.notes,
        "diff_summary": json.loads(c.diff_summary) if c.diff_summary else None,
        "timestamps": {
            "bulk":        str(c.bulk_started_at) if c.bulk_started_at else None,
            "tail":        str(c.tail_started_at) if c.tail_started_at else None,
            "freeze":      str(c.freeze_started_at) if c.freeze_started_at else None,
            "diff":        str(c.diff_started_at) if c.diff_started_at else None,
            "flip":        str(c.flip_started_at) if c.flip_started_at else None,
            "done":        str(c.done_at) if c.done_at else None,
            "rolled_back": str(c.rolled_back_at) if c.rolled_back_at else None,
        },
        "created_at": str(c.created_at) if c.created_at else None,
    }


@router.post("/projects/{project_id}/cutovers", status_code=201)
def api_create_cutover(
    project_id: str,
    data: CutoverCreate,
    request: Request,
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    ensure_project_access(db, org_id, project_id)
    now = datetime.now(timezone.utc)
    row = MigrationCutover(
        organization_id=org_id,
        project_id=project_id,
        source_ref=data.source_ref,
        target_ref=data.target_ref,
        workflow_id=data.workflow_id,
        notes=data.notes,
        state="bulk",
        bulk_started_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    write_audit(db, org_id=org_id, actor_id=user_id, action="cutover_created",
                entity_type="cutover", entity_id=row.id,
                meta={"source": data.source_ref, "target": data.target_ref},
                request=request)
    return _serialize(row)


@router.get("/projects/{project_id}/cutovers")
def api_list_cutovers(
    project_id: str,
    org_id: str = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
):
    ensure_project_access(db, org_id, project_id)
    rows = (
        db.query(MigrationCutover)
        .filter(MigrationCutover.organization_id == org_id, MigrationCutover.project_id == project_id)
        .order_by(MigrationCutover.created_at.desc())
        .all()
    )
    return [_serialize(r) for r in rows]


@router.get("/cutovers/{cutover_id}")
def api_get_cutover(
    cutover_id: str,
    org_id: str = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
):
    row = (
        db.query(MigrationCutover)
        .filter(MigrationCutover.id == cutover_id, MigrationCutover.organization_id == org_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Cutover not found")
    return _serialize(row)


@router.post("/cutovers/{cutover_id}/transition")
def api_transition_cutover(
    cutover_id: str,
    data: CutoverTransition,
    request: Request,
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    row = (
        db.query(MigrationCutover)
        .filter(MigrationCutover.id == cutover_id, MigrationCutover.organization_id == org_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Cutover not found")
    if data.target_state not in VALID_STATES:
        raise HTTPException(status_code=400, detail=f"Invalid state. Must be one of {VALID_STATES}")
    allowed = ALLOWED_TRANSITIONS.get(row.state, set())
    if data.target_state not in allowed:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot transition from {row.state!r} to {data.target_state!r}. "
                   f"Allowed: {sorted(allowed) or 'none (terminal)'}",
        )

    row.state = data.target_state
    setattr(row, _STATE_TIMESTAMP_COL[data.target_state], datetime.now(timezone.utc))
    if data.notes:
        existing = row.notes or ""
        row.notes = (existing + "\n" if existing else "") + f"[{data.target_state}] {data.notes}"
    db.commit()
    db.refresh(row)
    write_audit(db, org_id=org_id, actor_id=user_id, action="cutover_transition",
                entity_type="cutover", entity_id=row.id,
                meta={"to_state": data.target_state, "notes": data.notes},
                request=request)
    return _serialize(row)


@router.post("/cutovers/{cutover_id}/diff")
def api_record_diff(
    cutover_id: str,
    data: CutoverDiff,
    request: Request,
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Attach the pre-flip diff result to the cutover row.

    Operators or the recon agent calls this AFTER state == 'diff' but BEFORE
    transitioning to 'flip'. Stored as JSON in diff_summary; the flip endpoint
    refuses to advance if no diff_summary is present.
    """
    row = (
        db.query(MigrationCutover)
        .filter(MigrationCutover.id == cutover_id, MigrationCutover.organization_id == org_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Cutover not found")
    if row.state != "diff":
        raise HTTPException(status_code=409, detail=f"Diff can only be recorded in state 'diff' (current: {row.state!r})")
    row.diff_summary = json.dumps(data.model_dump())
    db.commit()
    db.refresh(row)
    write_audit(db, org_id=org_id, actor_id=user_id, action="cutover_diff_recorded",
                entity_type="cutover", entity_id=row.id,
                meta=data.model_dump(), request=request)
    return _serialize(row)
