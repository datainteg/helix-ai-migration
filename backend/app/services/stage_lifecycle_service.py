"""Stage-gated lifecycle state machine.

Drives the project through the 13 lifecycle stages. Each stage is gated: a
stage cannot start until the previous required stage is done (approved/skipped/
completed). Approval is a DB action (no long-lived Temporal workflow). Every
transition is logged to stage_transition_logs AND the security audit log, and
emits a best-effort notification.

This service owns ONLY stage state; artifact content lives in
artifact_review_service. Approval of a stage is tied to its current artifact
version (you cannot approve a stage with no generated artifact).
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.lifecycle import MigrationStage, StageTransitionLog
from app.models.project import Project
from app.services import lifecycle_constants as LC


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_project(db: Session, org_id: str, project_id: str) -> Project:
    p = db.query(Project).filter(Project.id == project_id, Project.organization_id == org_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return p


def _get_stage(db: Session, org_id: str, project_id: str, stage_key: str) -> MigrationStage:
    st = (
        db.query(MigrationStage)
        .filter(
            MigrationStage.project_id == project_id,
            MigrationStage.organization_id == org_id,
            MigrationStage.stage_key == stage_key,
        )
        .first()
    )
    if not st:
        raise HTTPException(status_code=404, detail=f"Stage {stage_key} not found")
    return st


def _log_transition(db: Session, stage: MigrationStage, from_status: str | None, to_status: str,
                    action: str, actor_type: str, actor_id: str | None, comment: str | None = None) -> None:
    db.add(StageTransitionLog(
        organization_id=stage.organization_id, project_id=stage.project_id, stage_id=stage.id,
        from_status=from_status, to_status=to_status, action=action,
        actor_type=actor_type, actor_id=actor_id, comment=comment,
    ))


def _notify(db: Session, org_id: str, project: Project, title: str, body: str, link: str) -> None:
    """Best-effort lifecycle notification — never fails the transition."""
    try:
        from app.services import notification_service as ns
        ns.emit(db, org_id=org_id, type="lifecycle", severity="info",
                title=title, body=body, link=link,
                dedupe_key=None)
    except Exception:  # noqa: BLE001
        pass


def _audit(db: Session, org_id: str, actor_id: str | None, action: str, project_id: str, stage_key: str, comment: str | None) -> None:
    # entity_id is the project id (audit_logs.entity_id is varchar(36)); the
    # stage key lives in metadata so the value can never overflow the column.
    try:
        from app.api.audit import write_audit
        meta: dict = {"stage_key": stage_key}
        if comment:
            meta["comment"] = comment
        write_audit(db, org_id=org_id, actor_id=actor_id, action=f"stage_{action}",
                    entity_type="migration_stage", entity_id=project_id, meta=meta)
    except Exception:  # noqa: BLE001
        pass


# ── Initialization ───────────────────────────────────────────────────
def initialize_project_lifecycle(db: Session, organization_id: str, project_id: str,
                                 include_ux: bool = False, actor_user_id: str | None = None) -> list[MigrationStage]:
    """Create the default 13 stages for a project (idempotent). UX_DESIGN is
    created but marked optional; if include_ux is False it stays skippable."""
    existing = db.query(MigrationStage).filter(MigrationStage.project_id == project_id).count()
    if existing:
        return get_project_lifecycle(db, organization_id, project_id)

    stages: list[MigrationStage] = []
    for order, spec in enumerate(LC.DEFAULT_LIFECYCLE, start=1):
        st = MigrationStage(
            organization_id=organization_id, project_id=project_id,
            stage_key=spec["key"], stage_name=spec["name"], stage_order=order,
            status="not_started", assigned_agent=spec["agent"], is_optional=spec["optional"],
            created_by=actor_user_id, updated_by=actor_user_id,
        )
        db.add(st)
        stages.append(st)
    proj = _get_project(db, organization_id, project_id)
    proj.lifecycle_status = LC.LIFECYCLE_NOT_STARTED
    proj.current_stage = LC.PROJECT_CONTEXT
    proj.stage_progress_percent = 0
    db.commit()
    return stages


def get_project_lifecycle(db: Session, organization_id: str, project_id: str) -> list[MigrationStage]:
    _get_project(db, organization_id, project_id)
    return (
        db.query(MigrationStage)
        .filter(MigrationStage.project_id == project_id, MigrationStage.organization_id == organization_id)
        .order_by(MigrationStage.stage_order)
        .all()
    )


def _is_blocking(st: MigrationStage) -> bool:
    """A stage that still pins the lifecycle pointer. Done stages don't; an
    OPTIONAL stage left at not_started doesn't either (it is passively skipped
    unless someone explicitly starts it), so the project can still complete."""
    if st.status in LC.STAGE_DONE_STATUSES:
        return False
    if st.is_optional and st.status == "not_started":
        return False
    return True


def get_stage_transitions(db: Session, organization_id: str, project_id: str, limit: int = 200) -> list[StageTransitionLog]:
    """The append-only domain audit trail for a project's lifecycle (newest
    first) — powers the project timeline + audit view."""
    _get_project(db, organization_id, project_id)
    return (
        db.query(StageTransitionLog)
        .filter(StageTransitionLog.project_id == project_id, StageTransitionLog.organization_id == organization_id)
        .order_by(StageTransitionLog.created_at.desc())
        .limit(limit)
        .all()
    )


def get_current_stage(db: Session, organization_id: str, project_id: str) -> MigrationStage | None:
    """First blocking stage in order (the active gate)."""
    for st in get_project_lifecycle(db, organization_id, project_id):
        if _is_blocking(st):
            return st
    return None


def _prior_required_stage(stages: list[MigrationStage], target: MigrationStage) -> MigrationStage | None:
    """The closest preceding non-optional stage (the gate that must be done)."""
    prior = [s for s in stages if s.stage_order < target.stage_order and not s.is_optional]
    return prior[-1] if prior else None


def _require_prior_done(stages: list[MigrationStage], stage: MigrationStage, verb: str) -> None:
    """Enforce stage ordering: the closest preceding REQUIRED stage must be
    done (approved/skipped/completed) before this stage can be acted on. This
    is the single ordering gate shared by start/submit/generate/approve so a
    later stage can never leapfrog an un-approved required gate."""
    prior = _prior_required_stage(stages, stage)
    if prior is not None and prior.status not in LC.STAGE_DONE_STATUSES:
        raise HTTPException(status_code=409, detail=f"Cannot {verb} {stage.stage_key}: previous stage {prior.stage_key} is not approved.")


# Statuses a stage may be (re)started from. Already-done or in-flight stages
# are rejected so /start can never regress a closed gate back to 'running'.
_STARTABLE_STATUSES = {"not_started", "rejected", "edit_requested", "failed"}


# ── Transitions ──────────────────────────────────────────────────────
def start_stage(db: Session, organization_id: str, project_id: str, stage_key: str, actor_user_id: str) -> MigrationStage:
    stages = get_project_lifecycle(db, organization_id, project_id)
    stage = next((s for s in stages if s.stage_key == stage_key), None)
    if not stage:
        raise HTTPException(status_code=404, detail=f"Stage {stage_key} not found")
    if stage.status not in _STARTABLE_STATUSES:
        raise HTTPException(status_code=409, detail=f"Stage {stage_key} is {stage.status}; cannot start (only {sorted(_STARTABLE_STATUSES)}).")
    _require_prior_done(stages, stage, "start")
    prev = stage.status
    stage.status = "running"
    stage.started_at = _now()
    stage.updated_by = actor_user_id
    _log_transition(db, stage, prev, "running", "start", "user", actor_user_id)
    proj = _get_project(db, organization_id, project_id)
    proj.current_stage = stage_key
    proj.lifecycle_status = LC.LIFECYCLE_IN_PROGRESS
    db.commit()
    return stage


def mark_stage_generated(db: Session, organization_id: str, project_id: str, stage_key: str,
                         artifact_id: str, actor_type: str = "agent", actor_id: str | None = None) -> MigrationStage:
    stages = get_project_lifecycle(db, organization_id, project_id)
    stage = next((s for s in stages if s.stage_key == stage_key), None)
    if not stage:
        raise HTTPException(status_code=404, detail=f"Stage {stage_key} not found")
    _require_prior_done(stages, stage, "generate")
    prev = stage.status
    stage.status = "generated"
    stage.generated_at = _now()
    stage.current_artifact_id = artifact_id
    _log_transition(db, stage, prev, "generated", "generate", actor_type, actor_id)
    db.commit()
    return stage


_SUBMITTABLE_STATUSES = {"running", "generated", "edit_requested", "resubmitted", "rejected"}


def submit_stage_for_review(db: Session, organization_id: str, project_id: str, stage_key: str,
                            artifact_id: str | None, actor_user_id: str) -> MigrationStage:
    stages = get_project_lifecycle(db, organization_id, project_id)
    stage = next((s for s in stages if s.stage_key == stage_key), None)
    if not stage:
        raise HTTPException(status_code=404, detail=f"Stage {stage_key} not found")
    _require_prior_done(stages, stage, "submit")
    if stage.status not in _SUBMITTABLE_STATUSES:
        raise HTTPException(status_code=409, detail=f"Stage {stage_key} is {stage.status}; only an active stage can be submitted for review.")
    if artifact_id:
        stage.current_artifact_id = artifact_id
    if not stage.current_artifact_id:
        raise HTTPException(status_code=409, detail="Cannot submit for review: stage has no artifact.")
    prev = stage.status
    stage.status = "under_review"
    stage.submitted_for_review_at = _now()
    stage.submitted_for_review_by = actor_user_id  # SoD: this user may not self-approve
    stage.updated_by = actor_user_id
    _log_transition(db, stage, prev, "under_review", "submit", "user", actor_user_id)
    proj = _get_project(db, organization_id, project_id)
    _notify(db, organization_id, proj, f"Review needed: {stage.stage_name}",
            f"{proj.alias or proj.name}: {stage.stage_name} is ready for review.",
            f"/projects/{proj.slug or project_id}/lifecycle/{stage_key}")
    db.commit()
    return stage


def approve_stage(db: Session, organization_id: str, project_id: str, stage_key: str,
                  user_id: str, comment: str | None = None, allow_self_approval: bool = False) -> MigrationStage:
    stages = get_project_lifecycle(db, organization_id, project_id)
    stage = next((s for s in stages if s.stage_key == stage_key), None)
    if not stage:
        raise HTTPException(status_code=404, detail=f"Stage {stage_key} not found")
    # 'edit_requested' is intentionally approvable: an approver may reverse their
    # own change-request and approve directly without forcing a resubmit cycle.
    if stage.status not in LC.STAGE_REVIEWABLE_STATUSES and stage.status != "edit_requested":
        raise HTTPException(status_code=409, detail=f"Stage {stage_key} is {stage.status}; only a generated/under-review/resubmitted stage can be approved.")
    if not stage.current_artifact_id and stage.assigned_agent not in ("__human__", "__system__", "__orchestration__"):
        raise HTTPException(status_code=409, detail="Cannot approve a stage with no current artifact version.")
    # Ordering gate: a later stage can never be approved ahead of an un-approved
    # required predecessor (the only other gate is start_stage).
    _require_prior_done(stages, stage, "approve")
    # Separation of duties: whoever submitted the stage for review may not also
    # approve it, unless they are an admin/super_admin (allow_self_approval).
    if not allow_self_approval and stage.submitted_for_review_by and stage.submitted_for_review_by == user_id:
        raise HTTPException(status_code=403, detail="Separation of duties: the user who submitted this stage cannot approve it.")
    # VALIDATION can only be approved once at least one evidence item is accepted.
    if stage.stage_key == LC.VALIDATION:
        try:
            from app.services.validation_evidence_service import has_accepted_evidence
            _has = has_accepted_evidence(db, organization_id, project_id)
        except Exception:  # noqa: BLE001
            _has = True   # never hard-fail approval on an import/availability error
        if not _has:
            raise HTTPException(status_code=409, detail="Validation cannot be approved until at least one evidence item is accepted.")
    prev = stage.status
    stage.status = "approved"
    stage.approved_at = _now()
    stage.completed_at = _now()
    stage.updated_by = user_id
    _log_transition(db, stage, prev, "approved", "approve", "user", user_id, comment)
    _audit(db, organization_id, user_id, "approve", project_id, stage_key, comment)
    db.commit()
    # Advance the project pointer + progress.
    advance_to_next_stage(db, organization_id, project_id)
    return stage


def reject_stage(db: Session, organization_id: str, project_id: str, stage_key: str, user_id: str, comment: str) -> MigrationStage:
    stage = _get_stage(db, organization_id, project_id, stage_key)
    prev = stage.status
    stage.status = "rejected"
    stage.rejected_at = _now()
    stage.updated_by = user_id
    _log_transition(db, stage, prev, "rejected", "reject", "user", user_id, comment)
    _audit(db, organization_id, user_id, "reject", project_id, stage_key, comment)
    db.commit()
    return stage


def request_stage_changes(db: Session, organization_id: str, project_id: str, stage_key: str, user_id: str, comment: str) -> MigrationStage:
    stage = _get_stage(db, organization_id, project_id, stage_key)
    prev = stage.status
    stage.status = "edit_requested"
    stage.updated_by = user_id
    _log_transition(db, stage, prev, "edit_requested", "request_changes", "user", user_id, comment)
    db.commit()
    return stage


def resubmit_stage(db: Session, organization_id: str, project_id: str, stage_key: str,
                   artifact_version_id: str | None, user_id: str) -> MigrationStage:
    stage = _get_stage(db, organization_id, project_id, stage_key)
    # Resubmit only makes sense after a reviewer pushed back; it must not be a
    # back-door to leapfrog start→generate→submit on a fresh stage.
    if stage.status not in ("rejected", "edit_requested"):
        raise HTTPException(status_code=409, detail=f"Stage {stage_key} is {stage.status}; only a rejected/edit-requested stage can be resubmitted.")
    prev = stage.status
    stage.status = "resubmitted"
    stage.submitted_for_review_at = _now()
    stage.submitted_for_review_by = user_id  # SoD: the resubmitter may not self-approve
    stage.updated_by = user_id
    _log_transition(db, stage, prev, "resubmitted", "resubmit", "user", user_id,
                    f"artifact_version_id={artifact_version_id}" if artifact_version_id else None)
    db.commit()
    return stage


def skip_optional_stage(db: Session, organization_id: str, project_id: str, stage_key: str, user_id: str, reason: str) -> MigrationStage:
    stage = _get_stage(db, organization_id, project_id, stage_key)
    if not stage.is_optional:
        raise HTTPException(status_code=409, detail=f"Stage {stage_key} is not optional and cannot be skipped.")
    prev = stage.status
    stage.status = "skipped"
    stage.completed_at = _now()
    stage.updated_by = user_id
    _log_transition(db, stage, prev, "skipped", "skip", "user", user_id, reason)
    db.commit()
    advance_to_next_stage(db, organization_id, project_id)
    return stage


def advance_to_next_stage(db: Session, organization_id: str, project_id: str) -> MigrationStage | None:
    """Recompute current stage + progress; close the project when all done."""
    stages = get_project_lifecycle(db, organization_id, project_id)
    nxt = next((s for s in stages if _is_blocking(s)), None)
    proj = _get_project(db, organization_id, project_id)
    proj.stage_progress_percent = calculate_project_progress(db, organization_id, project_id, _stages=stages)
    if nxt is None:
        proj.lifecycle_status = LC.LIFECYCLE_COMPLETED
        proj.current_stage = None
    else:
        proj.current_stage = nxt.stage_key
        proj.lifecycle_status = LC.LIFECYCLE_IN_PROGRESS
    db.commit()
    return nxt


def calculate_project_progress(db: Session, organization_id: str, project_id: str, _stages=None) -> int:
    stages = _stages if _stages is not None else get_project_lifecycle(db, organization_id, project_id)
    # Optional stages left untouched (not_started) don't count against completion,
    # so progress can reach 100% once every required + actioned stage is done.
    relevant = [s for s in stages if not (s.is_optional and s.status == "not_started")]
    if not relevant:
        return 0
    done = sum(1 for s in relevant if s.status in LC.STAGE_DONE_STATUSES)
    return round(100 * done / len(relevant))
