"""Cutover orchestration model.

A `MigrationCutover` row tracks one end-to-end source→target transition:

    bulk    → initial full-load completed
    tail    → incremental (CDC) sync running
    freeze  → source writes paused / read-only window
    diff    → final pre-flip sample diff in progress
    flip    → traffic + writes routed to target
    done    → release sealed
    rolled_back  → terminal: writes routed back to source

State transitions are explicit (POST /transition) and recorded via the audit
chain. Each state stores entered_at + (optional) entered_by so the post-mortem
shows the timing of every step.

Driving the actual CDC + freeze is out of scope here — the orchestration row
gives operators (and Mary's recon agent) a stable record of where each
migration is in the cutover window.
"""

from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


VALID_STATES = ("bulk", "tail", "freeze", "diff", "flip", "done", "rolled_back")

# Allowed transitions. Forbid skipping straight to flip without diff so the
# pre-cutover verification gate cannot be bypassed.
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "bulk":        {"tail", "rolled_back"},
    "tail":        {"freeze", "rolled_back"},
    "freeze":      {"diff", "rolled_back"},
    "diff":        {"flip", "rolled_back"},
    "flip":        {"done", "rolled_back"},
    "done":        set(),          # terminal
    "rolled_back": set(),          # terminal
}


class MigrationCutover(BaseModel):
    __tablename__ = "migration_cutovers"

    organization_id = Column(String(36), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    workflow_id = Column(String(255), nullable=True)
    source_ref = Column(String(255), nullable=False)
    target_ref = Column(String(255), nullable=False)
    state = Column(String(20), default="bulk", nullable=False)

    # Snapshot of when the row entered each state. NULL = state never reached.
    bulk_started_at = Column(DateTime(timezone=True), nullable=True)
    tail_started_at = Column(DateTime(timezone=True), nullable=True)
    freeze_started_at = Column(DateTime(timezone=True), nullable=True)
    diff_started_at = Column(DateTime(timezone=True), nullable=True)
    flip_started_at = Column(DateTime(timezone=True), nullable=True)
    done_at = Column(DateTime(timezone=True), nullable=True)
    rolled_back_at = Column(DateTime(timezone=True), nullable=True)

    # Diff result captured at the freeze→flip gate. JSON-encoded summary
    # (source_count, target_count, diff_pct, sample_size, hash).
    diff_summary = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
