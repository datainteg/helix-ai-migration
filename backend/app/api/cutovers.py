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

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.auth.dependencies import get_current_organization_id
from app.auth.jwt import get_current_user_id
from app.api.audit import write_audit
from app.models.cutover import MigrationCutover, ALLOWED_TRANSITIONS, VALID_STATES
from app.services.project_service import ensure_project_access
from app.schemas.pagination import PaginatedResponse, paginate
from app.utils.idempotency import idempotent

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
    # Cap row counts at 1e18 so an upstream INT overflow can't poison the
    # diff_summary column (Postgres BIGINT max ~9.2e18; we stay under).
    source_count: int = Field(ge=0, le=10**18)
    target_count: int = Field(ge=0, le=10**18)
    diff_pct: float = Field(ge=0.0, le=100.0)
    sample_size: int = Field(ge=0, le=10**12)
    sample_hash: Optional[str] = Field(default=None, max_length=255)


class CutoverTimestamps(BaseModel):
    """ISO-8601 timestamps for each cutover state transition.

    Each field is the moment the cutover ENTERED that state; `None` means
    it has not yet entered it. Field names match `_STATE_TIMESTAMP_COL`.
    """

    bulk: Optional[str] = None
    tail: Optional[str] = None
    freeze: Optional[str] = None
    diff: Optional[str] = None
    flip: Optional[str] = None
    done: Optional[str] = None
    rolled_back: Optional[str] = None


class CutoverResponse(BaseModel):
    """Persisted cutover row, returned from every cutover endpoint.

    Replaces the previous hand-built dict so OpenAPI describes the shape
    and SDK generators stop emitting `any`. `state` is the only string
    field whose values are constrained by `VALID_STATES` in
    `app.models.cutover`; a real `Literal[...]` will be added once the
    state enum is hoisted to a single source of truth.
    """

    id: str
    project_id: str
    workflow_id: Optional[str] = None
    source_ref: str
    target_ref: str
    state: str
    notes: Optional[str] = None
    diff_summary: Optional[dict] = None
    timestamps: CutoverTimestamps
    created_at: Optional[str] = None


_STATE_TIMESTAMP_COL = {
    "bulk": "bulk_started_at",
    "tail": "tail_started_at",
    "freeze": "freeze_started_at",
    "diff": "diff_started_at",
    "flip": "flip_started_at",
    "done": "done_at",
    "rolled_back": "rolled_back_at",
}


def _iso(value) -> Optional[str]:
    """Return `value.isoformat()` or `None`. Replaces every legacy
    `str(datetime)` call site so timestamps are ISO-8601 instead of
    Python's `__str__` repr (the latter broke Safari `Date` parsing)."""
    return value.isoformat() if value else None


def _serialize(c: MigrationCutover) -> CutoverResponse:
    """Build the typed CutoverResponse used by every cutover endpoint."""
    return CutoverResponse(
        id=c.id,
        project_id=c.project_id,
        workflow_id=c.workflow_id,
        source_ref=c.source_ref,
        target_ref=c.target_ref,
        state=c.state,
        notes=c.notes,
        diff_summary=json.loads(c.diff_summary) if c.diff_summary else None,
        timestamps=CutoverTimestamps(
            bulk=_iso(c.bulk_started_at),
            tail=_iso(c.tail_started_at),
            freeze=_iso(c.freeze_started_at),
            diff=_iso(c.diff_started_at),
            flip=_iso(c.flip_started_at),
            done=_iso(c.done_at),
            rolled_back=_iso(c.rolled_back_at),
        ),
        created_at=_iso(c.created_at),
    )


@router.post(
    "/projects/{project_id}/cutovers",
    status_code=201,
    response_model=CutoverResponse,
)
@idempotent("create_cutover", status_code=201)
async def api_create_cutover(
    project_id: str,
    data: CutoverCreate,
    request: Request,
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Create a new cutover row.

    Idempotent on `Idempotency-Key` header (API-C4): a network retry will
    NOT create a duplicate cutover for the same source→target.
    """
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


@router.get(
    "/projects/{project_id}/cutovers",
    response_model=PaginatedResponse[CutoverResponse],
)
def api_list_cutovers(
    project_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    org_id: str = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
):
    """List cutovers for a project (paginated envelope).

    Breaking change vs v0.x: response is now `{items,total,limit,offset}`
    instead of a bare array. See REVIEW_API_CONTRACT.md §API-C2.
    """
    from sqlalchemy import func
    ensure_project_access(db, org_id, project_id)
    base_filter = (
        MigrationCutover.organization_id == org_id,
        MigrationCutover.project_id == project_id,
    )
    total = int(
        db.query(func.count(MigrationCutover.id))
        .filter(*base_filter)
        .scalar()
        or 0
    )
    rows = (
        db.query(MigrationCutover)
        .filter(*base_filter)
        .order_by(MigrationCutover.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    items = [_serialize(r) for r in rows]
    return PaginatedResponse[CutoverResponse](
        items=items, total=total, limit=limit, offset=offset,
    )


@router.get("/cutovers/{cutover_id}", response_model=CutoverResponse)
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


@router.post("/cutovers/{cutover_id}/transition", response_model=CutoverResponse)
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
        # Structured error body so clients can parse the allowed list
        # without scraping the Python-tuple repr.
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Invalid target_state.",
                "allowed": sorted(VALID_STATES),
                "received": data.target_state,
            },
        )
    allowed = ALLOWED_TRANSITIONS.get(row.state, set())
    if data.target_state not in allowed:
        raise HTTPException(
            status_code=409,
            detail={
                "message": f"Illegal transition from {row.state!r} to {data.target_state!r}.",
                "allowed": sorted(allowed),
                "current_state": row.state,
                "received": data.target_state,
            },
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


@router.post("/cutovers/{cutover_id}/diff", response_model=CutoverResponse)
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
