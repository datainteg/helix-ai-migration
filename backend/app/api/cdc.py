"""Change-data-capture polling endpoints.

MVP: a timestamp-column poller. For a cutover in state `tail`, the operator
(or a scheduled job) calls POST /cutovers/{id}/tail-sync/tick which pulls
rows from the source where `last_modified_at > checkpoint` and reports how
many would replicate. Full bidirectional sync (apply to target) is out of
scope for this MVP — the tick records what would change.

Real CDC engines (Debezium, native logical replication) wire in via a
separate worker and update the same checkpoint state. The shape here is the
plug point.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.auth.dependencies import get_current_organization_id
from app.auth.jwt import get_current_user_id
from app.api.audit import write_audit
from app.models.cutover import MigrationCutover

router = APIRouter(tags=["cdc"])


class TailSyncTick(BaseModel):
    """Report a single CDC poll result. The connector layer (Debezium hook,
    polling job, or manual operator) computes these values + posts here."""
    rows_seen: int = Field(ge=0)
    rows_applied: int = Field(ge=0)
    lag_seconds: float = Field(ge=0)
    high_water_mark: str = Field(min_length=1, max_length=255, description="Vendor checkpoint (LSN, SCN, ISO timestamp, etc.)")
    notes: str | None = Field(default=None, max_length=2048)


@router.post("/cutovers/{cutover_id}/tail-sync/tick")
def record_tick(
    cutover_id: str,
    data: TailSyncTick,
    request: Request,
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Record one CDC tick on a cutover currently in tail state."""
    row = (
        db.query(MigrationCutover)
        .filter(MigrationCutover.id == cutover_id, MigrationCutover.organization_id == org_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Cutover not found")
    if row.state != "tail":
        raise HTTPException(status_code=409, detail=f"Tail-sync ticks only valid in state 'tail' (current: {row.state!r})")

    payload = {
        "rows_seen": data.rows_seen,
        "rows_applied": data.rows_applied,
        "lag_seconds": data.lag_seconds,
        "high_water_mark": data.high_water_mark,
        "notes": data.notes,
        "ticked_at": datetime.now(timezone.utc).isoformat(),
    }
    # Diff_summary slot is reused as the rolling tail checkpoint — last tick wins.
    row.diff_summary = json.dumps({**(json.loads(row.diff_summary) if row.diff_summary else {}), "last_tail_tick": payload})
    db.commit()
    write_audit(db, org_id=org_id, actor_id=user_id, action="cutover_tail_tick",
                entity_type="cutover", entity_id=row.id,
                meta=payload, request=request)
    return {"cutover_id": row.id, "state": row.state, "last_tail_tick": payload}
