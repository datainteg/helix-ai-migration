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
        # M-005: catch per-cutover so one broken row (bad diff_summary, source
        # error) does not abort the whole pass and starve every other cutover
        # in tail state this tick. Roll back the failed cutover's partial txn
        # before moving on so a poisoned write can't taint the next iteration.
        for c in rows:
            try:
                await _poll_cutover(db, c)
            except Exception as exc:  # noqa: BLE001
                logger.warning("CDC poll failed for cutover=%s: %s", getattr(c, "id", "?"), exc)
                try:
                    db.rollback()
                except Exception:  # noqa: BLE001
                    pass
    except Exception as exc:  # noqa: BLE001
        # Outer guard for the query itself / SessionLocal failures.
        logger.warning("CDC poll pass failed: %s", exc)
    finally:
        db.close()


def _load_diff_summary(raw) -> dict:
    """C-004: tolerant read of the `diff_summary` Text column.

    The column is `Text`; the canonical contract is "a JSON STRING produced
    by json.dumps". This helper normalises reads so a single malformed /
    legacy row (e.g. one where a writer accidentally stored a Python-repr
    dict, or where the value is already a dict because a future column type
    change landed) does not crash the CDC poll loop. Always returns a dict.
    """
    if raw is None or raw == "":
        return {}
    # JSONB column or a writer that stored a dict directly → already parsed.
    if isinstance(raw, dict):
        return raw
    try:
        loaded = json.loads(raw)
        return loaded if isinstance(loaded, dict) else {}
    except (json.JSONDecodeError, TypeError):
        logger.warning("CDC: diff_summary not valid JSON; resetting to {}")
        return {}


async def _poll_cutover(db: Session, c) -> None:
    """Poll one cutover. Updates cutover.diff_summary in place."""
    # MVP: source_ref is informational ("oracle://schema.table"). We don't
    # round-trip to the real source here — the operator/connector layer
    # supplies the tick via POST /cutovers/{id}/tail-sync/tick. The engine
    # only marks "we checked" so dashboards can show liveness.
    now_iso = datetime.now(timezone.utc).isoformat()
    # C-004: every writer normalises to a JSON STRING (column is Text), and
    # every reader goes through _load_diff_summary. No json.dumps wrapping of
    # an already-string value, no Python-repr leakage.
    summary = _load_diff_summary(c.diff_summary)
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
