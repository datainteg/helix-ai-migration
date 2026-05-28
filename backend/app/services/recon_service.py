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
            mismatch_count=diff,
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
        # H-002: do NOT re-raise. The empty recon_run row was already
        # committed at the top; persist the failure status + message and
        # return a structured failure dict so the caller can map it to a
        # 422 with detail instead of an opaque 500. Persist a diagnostic
        # ReconResult row too so the recon list shows *why* it failed.
        logger.warning(
            "recon_failed run_id=%s project=%s err=%s",
            recon_run.id, project_id, exc,
        )
        recon_run.status = "failed"
        recon_run.error_message = str(exc)[:2000]
        try:
            import json
            db.add(ReconResult(
                run_id=recon_run.id,
                result_type="row_count",
                summary=json.dumps({"status": "failed", "error": str(exc)[:1000]}),
                mismatch_count=0,
            ))
        except Exception:  # noqa: BLE001 — best-effort forensics row
            pass
        db.commit()
        return {
            "recon_run_id": recon_run.id,
            "status": "failed",
            "passed": False,
            "error_message": str(exc)[:1000],
        }
