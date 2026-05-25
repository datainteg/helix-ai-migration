"""Schema drift watcher API.

Operators (or a scheduled job) call:
  POST /projects/{project_id}/sources/{source_ref}/schema-snapshots
        → walks the source's information_schema, persists the snapshot.

  GET  /projects/{project_id}/sources/{source_ref}/schema-snapshots
        → list snapshots (descending).

  GET  /projects/{project_id}/sources/{source_ref}/drift
        → diff the latest snapshot against the baseline (oldest) snapshot.

For automated detection wire a Temporal scheduled workflow that hits the
snapshot endpoint nightly and emits a webhook event when drift is found.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.auth.dependencies import get_current_organization_id
from app.auth.jwt import get_current_user_id
from app.api.audit import write_audit
from app.models.schema_snapshot import SourceSchemaSnapshot
from app.services.project_service import ensure_project_access

router = APIRouter(tags=["schema-drift"])


class SnapshotPayload(BaseModel):
    # Caller supplies the schema dump. Lets the discovery service live in the
    # connector layer rather than being duplicated here.
    schemas: list[str] = []
    tables: list[dict]  # [{schema_name, table_name, columns:[{name,data_type,is_nullable}]}]


def _count_columns(tables: list[dict]) -> int:
    return sum(len(t.get("columns", []) or []) for t in tables)


@router.post("/projects/{project_id}/sources/{source_ref}/schema-snapshots", status_code=201)
def take_snapshot(
    project_id: str,
    source_ref: str,
    data: SnapshotPayload,
    request: Request,
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    ensure_project_access(db, org_id, project_id)
    payload = json.dumps(data.model_dump())
    row = SourceSchemaSnapshot(
        organization_id=org_id,
        project_id=project_id,
        source_ref=source_ref,
        payload=payload,
        table_count=len(data.tables),
        column_count=_count_columns(data.tables),
        taken_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    write_audit(db, org_id=org_id, actor_id=user_id, action="schema_snapshot_taken",
                entity_type="source_schema_snapshot", entity_id=row.id,
                meta={"source": source_ref, "tables": row.table_count, "columns": row.column_count},
                request=request)
    return _serialize(row)


@router.get("/projects/{project_id}/sources/{source_ref}/schema-snapshots")
def list_snapshots(
    project_id: str,
    source_ref: str,
    org_id: str = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
):
    ensure_project_access(db, org_id, project_id)
    rows = (
        db.query(SourceSchemaSnapshot)
        .filter(
            SourceSchemaSnapshot.organization_id == org_id,
            SourceSchemaSnapshot.project_id == project_id,
            SourceSchemaSnapshot.source_ref == source_ref,
        )
        .order_by(SourceSchemaSnapshot.taken_at.desc())
        .all()
    )
    return [_serialize(r) for r in rows]


@router.get("/projects/{project_id}/sources/{source_ref}/drift")
def compute_drift(
    project_id: str,
    source_ref: str,
    org_id: str = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
):
    """Compare the latest snapshot against the earliest (baseline) snapshot.

    Returns lists of added / removed / column-changed tables, suitable for a
    UI banner or a webhook payload.
    """
    ensure_project_access(db, org_id, project_id)
    snaps = (
        db.query(SourceSchemaSnapshot)
        .filter(
            SourceSchemaSnapshot.organization_id == org_id,
            SourceSchemaSnapshot.project_id == project_id,
            SourceSchemaSnapshot.source_ref == source_ref,
        )
        .order_by(SourceSchemaSnapshot.taken_at.asc())
        .all()
    )
    if len(snaps) < 2:
        return {
            "baseline_id": snaps[0].id if snaps else None,
            "latest_id": snaps[0].id if snaps else None,
            "added_tables": [],
            "removed_tables": [],
            "column_changes": [],
            "drift_detected": False,
            "note": "Need at least two snapshots to compute drift.",
        }

    baseline = json.loads(snaps[0].payload)
    latest = json.loads(snaps[-1].payload)
    base_idx = {(t["schema_name"], t["table_name"]): t for t in baseline.get("tables", [])}
    latest_idx = {(t["schema_name"], t["table_name"]): t for t in latest.get("tables", [])}

    added = [k for k in latest_idx if k not in base_idx]
    removed = [k for k in base_idx if k not in latest_idx]
    column_changes: list[dict] = []
    for key in set(base_idx) & set(latest_idx):
        b_cols = {c["name"]: c for c in base_idx[key].get("columns", [])}
        l_cols = {c["name"]: c for c in latest_idx[key].get("columns", [])}
        added_cols = [c for c in l_cols if c not in b_cols]
        removed_cols = [c for c in b_cols if c not in l_cols]
        type_changes = [
            {"column": c, "from": b_cols[c].get("data_type"), "to": l_cols[c].get("data_type")}
            for c in set(b_cols) & set(l_cols)
            if b_cols[c].get("data_type") != l_cols[c].get("data_type")
        ]
        if added_cols or removed_cols or type_changes:
            column_changes.append({
                "schema": key[0], "table": key[1],
                "added_columns": added_cols,
                "removed_columns": removed_cols,
                "type_changes": type_changes,
            })

    drift = bool(added or removed or column_changes)
    # added_tables / removed_tables are now structured `{schema, table}`
    # rows instead of dot-joined strings (REVIEW_API_CONTRACT
    # schema_drift HIGH issue) — consumers no longer have to re-parse.
    return {
        "baseline_id": snaps[0].id,
        "baseline_taken_at": snaps[0].taken_at.isoformat() if snaps[0].taken_at else None,
        "latest_id": snaps[-1].id,
        "latest_taken_at": snaps[-1].taken_at.isoformat() if snaps[-1].taken_at else None,
        "added_tables": [{"schema": a[0], "table": a[1]} for a in added],
        "removed_tables": [{"schema": r[0], "table": r[1]} for r in removed],
        "column_changes": column_changes,
        "drift_detected": drift,
    }


def _serialize(row: SourceSchemaSnapshot) -> dict:
    # ISO-8601 timestamps (API-C3).
    return {
        "id": row.id,
        "project_id": row.project_id,
        "source_ref": row.source_ref,
        "table_count": row.table_count,
        "column_count": row.column_count,
        "taken_at": row.taken_at.isoformat() if row.taken_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
