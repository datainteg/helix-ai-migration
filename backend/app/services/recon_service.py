"""Reconciliation service — row-count comparison MVP."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.validation import ReconRun, ReconResult
from app.services.connector_service import get_row_count

logger = logging.getLogger(__name__)


async def run_row_count_recon(
    db: Session,
    organization_id: str,
    project_id: str,
    source: dict[str, Any],
    target: dict[str, Any],
) -> dict[str, Any]:
    """Run row-count reconciliation between source and target.

    Stores metadata only — no row-level production data.
    """
    recon_run = ReconRun(
        project_id=project_id,
        source_ref=f"{source.get('connector_type')}:{source.get('schema')}.{source.get('table')}",
        target_ref=f"{target.get('connector_type')}:{target.get('schema')}.{target.get('table')}",
        status="running",
    )
    db.add(recon_run)
    db.commit()

    try:
        source_count = await get_row_count(
            source["connector_type"],
            source.get("config", {}),
            source.get("schema", "public"),
            source.get("table", ""),
        )
        target_count = await get_row_count(
            target["connector_type"],
            target.get("config", {}),
            target.get("schema", "public"),
            target.get("table", ""),
        )

        diff = abs(source_count.row_count - target_count.row_count)
        passed = diff == 0

        import json
        result = ReconResult(
            run_id=recon_run.id,
            result_type="row_count",
            summary=json.dumps({
                "source_count": source_count.row_count,
                "target_count": target_count.row_count,
                "difference": diff,
                "status": "passed" if passed else "failed",
            }),
            mismatch_count=str(diff),
        )
        db.add(result)

        recon_run.status = "completed"
        db.commit()

        return {
            "recon_run_id": recon_run.id,
            "status": "completed",
            "source_count": source_count.row_count,
            "target_count": target_count.row_count,
            "difference": diff,
            "passed": passed,
        }
    except Exception as exc:
        recon_run.status = "failed"
        recon_run.error_message = str(exc)
        db.commit()
        raise
