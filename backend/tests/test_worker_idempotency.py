"""Idempotency test for worker.activities.bmad_node_activities.persist_workflow_step_activity.

Regression coverage for the 2026-05-25 review finding that Temporal activity
retries duplicated workflow_steps rows. The activity now upserts on
(workflow_run_id, step_order); this test exercises that path twice with the
same key and asserts a single row exists.
"""

import uuid

from app.models.workflow import WorkflowRun, WorkflowStep


def _make_run(db_session):
    run = WorkflowRun(
        organization_id="org-test",
        project_id="proj-test",
        requirement_id="req-test",
        workflow_id=f"wf-{uuid.uuid4().hex[:8]}",
        run_id=f"rid-{uuid.uuid4().hex[:8]}",
        status="started",
        mode="temporal",
    )
    db_session.add(run)
    db_session.commit()
    return run


def test_persist_step_is_idempotent(db_session, monkeypatch):
    """Calling the activity twice with the same step_order must not duplicate rows."""
    # Force the activity to use the test's db_session instead of opening a new one.
    monkeypatch.setattr("worker.db.session.SessionLocal", lambda: db_session)

    from worker.activities.bmad_node_activities import persist_workflow_step_activity

    run = _make_run(db_session)
    payload = {
        "workflow_run_id": run.id,
        "agent_name": "analyst",
        "step_order": 2,
        "status": "completed",
        "parsed": {"summary": "first attempt"},
        "artifact_path": "/tmp/analyst.md",
        "mode": "temporal",
        "model_name": "claude-opus-4-7",
        "errors": [],
    }

    persist_workflow_step_activity.__wrapped__(payload) if hasattr(
        persist_workflow_step_activity, "__wrapped__"
    ) else persist_workflow_step_activity(payload)

    # Retry — should overwrite, not duplicate.
    payload["parsed"] = {"summary": "second attempt"}
    persist_workflow_step_activity.__wrapped__(payload) if hasattr(
        persist_workflow_step_activity, "__wrapped__"
    ) else persist_workflow_step_activity(payload)

    rows = (
        db_session.query(WorkflowStep)
        .filter(WorkflowStep.workflow_run_id == run.id, WorkflowStep.step_order == 2)
        .all()
    )
    assert len(rows) == 1
    assert rows[0].parsed_output_json == {"summary": "second attempt"}
