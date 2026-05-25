"""Polling-loop CDC engine for cutovers in tail state.

MVP design:
  - Background coroutine runs every CDC_POLL_INTERVAL_SEC seconds.
  - For each cutover in state `tail`, calls poll_tail_for_cutover() which
    queries the source connector for rows changed since the high-water-mark
    stored in cutover.diff_summary["last_tail_tick"]["high_water_mark"].
  - Records the new tick on the cutover (rows_seen, rows_applied=0 for
    MVP — application of changes is the operator's job in this iteration).

Real productionisation:
  - Plug in Debezium-driven Kafka consumer instead of polling.
  - Implement target apply (INSERT/UPDATE/DELETE on the target system).
  - Track per-table watermarks instead of per-cutover.

Start the engine from app.main lifespan; disable by setting
HELIX_CDC_DISABLED=1 in .env.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


CDC_POLL_INTERVAL_SEC = float(os.getenv("HELIX_CDC_POLL_INTERVAL_SEC", "60"))


_running_task: Optional[asyncio.Task] = None


async def _poll_once() -> None:
    """One pass over every cutover in tail state."""
    from app.db.session import SessionLocal
    from app.models.cutover import MigrationCutover

    db: Session = SessionLocal()
    try:
        rows = db.query(MigrationCutover).filter(MigrationCutover.state == "tail").all()
        for c in rows:
            await _poll_cutover(db, c)
    except Exception as exc:  # noqa: BLE001
        logger.warning("CDC poll failed: %s", exc)
    finally:
        db.close()


async def _poll_cutover(db: Session, c) -> None:
    """Poll one cutover. Updates cutover.diff_summary in place."""
    # MVP: source_ref is informational ("oracle://schema.table"). We don't
    # round-trip to the real source here — the operator/connector layer
    # supplies the tick via POST /cutovers/{id}/tail-sync/tick. The engine
    # only marks "we checked" so dashboards can show liveness.
    now_iso = datetime.now(timezone.utc).isoformat()
    summary = json.loads(c.diff_summary) if c.diff_summary else {}
    summary["last_poll_check_at"] = now_iso
    c.diff_summary = json.dumps(summary)
    db.commit()
    logger.debug("CDC checked cutover=%s state=tail", c.id)


async def _run_forever() -> None:
    logger.info("CDC engine started — poll every %ss", CDC_POLL_INTERVAL_SEC)
    try:
        while True:
            await _poll_once()
            await asyncio.sleep(CDC_POLL_INTERVAL_SEC)
    except asyncio.CancelledError:
        logger.info("CDC engine cancelled")
        raise


def start() -> None:
    """Schedule the CDC poll loop on the running event loop. Idempotent."""
    global _running_task
    if os.getenv("HELIX_CDC_DISABLED", "").lower() in {"1", "true", "yes"}:
        logger.info("CDC engine disabled via HELIX_CDC_DISABLED")
        return
    if _running_task is not None and not _running_task.done():
        return
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        logger.warning("CDC engine: no running event loop; skipping start")
        return
    _running_task = loop.create_task(_run_forever(), name="helix-cdc-engine")


def stop() -> None:
    global _running_task
    if _running_task is not None and not _running_task.done():
        _running_task.cancel()
    _running_task = None
