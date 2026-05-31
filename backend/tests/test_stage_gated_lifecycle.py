"""Stage-gated migration lifecycle tests.

Service-layer tests for the lifecycle introduced in the stage-gated BMAD rework:
alias uniqueness, lifecycle init + gating, artifact versioning/approval,
transition logging, sprint generation gating, validation evidence, recon report,
sign-off draft, and organization isolation.

Agent runs use the deterministic mock LLM transport (no network, no cost).
"""
import os
os.environ.setdefault("HELIX_LLM_TRANSPORT", "mock")

import asyncio
import pytest
from fastapi import HTTPException

from app.auth.jwt import hash_password
from app.models.identity import Organization, OrganizationMember, Role, User
from app.models.migration_artifact import MigrationArtifactVersion
from app.models.sprint import Sprint
from app.services.auth_service import seed_permissions, seed_roles
from app.schemas.project import ProjectCreate
from app.services import project_service as ps
from app.services import stage_lifecycle_service as sl
from app.services import stage_agent_service as sa
from app.services import artifact_review_service as ar
from app.services import sprint_generation_service as sgen
from app.services import validation_evidence_service as ve
from app.services import recon_report_service as rr
from app.services import signoff_service as so
from app.services import lifecycle_constants as LC


def _org_user(db, slug, email):
    seed_permissions(db)
    org = Organization(name=slug.title(), slug=slug)
    db.add(org)
    db.flush()
    seed_roles(db, org.id)
    user = User(email=email, name=email, password_hash=hash_password("Test123!"), is_super_admin=True)
    db.add(user)
    db.flush()
    role = db.query(Role).filter(Role.organization_id == org.id, Role.name == "super_admin").first()
    db.add(OrganizationMember(organization_id=org.id, user_id=user.id, role_id=role.id))
    db.commit()
    return org.id, user.id


def _project(db, org_id, user_id, name="Proj", **kw):
    return ps.create_project(db, org_id, user_id, ProjectCreate(name=name, migration_type="db_to_db", **kw))


def _approve_planning(db, org_id, pid, uid):
    for sk in (LC.PROJECT_CONTEXT, LC.BUSINESS_ANALYSIS, LC.ARCHITECTURE, LC.PROJECT_PLANNING):
        sa.run_stage_agent(db, org_id, pid, sk, uid)
        sl.approve_stage(db, org_id, pid, sk, uid, "ok", allow_self_approval=True)


# ── Alias + lifecycle init ───────────────────────────────────────────
def test_alias_generation_is_unique(db_session):
    org_id, uid = _org_user(db_session, "o1", "a@o1.test")
    p1 = _project(db_session, org_id, uid, "P1")
    p2 = _project(db_session, org_id, uid, "P2")
    assert p1.alias and p2.alias and p1.alias != p2.alias
    assert p1.alias.startswith("HXM-")


def test_lifecycle_initializes(db_session):
    org_id, uid = _org_user(db_session, "o1", "a@o1.test")
    p = _project(db_session, org_id, uid)
    stages = sl.get_project_lifecycle(db_session, org_id, p.id)
    assert len(stages) == len(LC.STAGE_KEYS)
    assert stages[0].stage_key == LC.PROJECT_CONTEXT
    assert all(s.status == "not_started" for s in stages)


def test_cannot_start_before_previous_approved(db_session):
    org_id, uid = _org_user(db_session, "o1", "a@o1.test")
    p = _project(db_session, org_id, uid)
    with pytest.raises(HTTPException) as e:
        sl.start_stage(db_session, org_id, p.id, LC.ARCHITECTURE, uid)
    assert e.value.status_code == 409


def test_optional_ux_can_be_skipped_required_cannot(db_session):
    org_id, uid = _org_user(db_session, "o1", "a@o1.test")
    p = _project(db_session, org_id, uid)
    skipped = sl.skip_optional_stage(db_session, org_id, p.id, LC.UX_DESIGN, uid, "not needed")
    assert skipped.status == "skipped"
    with pytest.raises(HTTPException) as e:
        sl.skip_optional_stage(db_session, org_id, p.id, LC.ARCHITECTURE, uid, "nope")
    assert e.value.status_code == 409


# ── Artifact versioning + approval ───────────────────────────────────
def test_agent_creates_v1_and_user_edit_creates_v2(db_session):
    org_id, uid = _org_user(db_session, "o1", "a@o1.test")
    p = _project(db_session, org_id, uid)
    run = sa.run_stage_agent(db_session, org_id, p.id, LC.PROJECT_CONTEXT, uid)
    vers = ar.get_artifact_versions(db_session, org_id, run["artifact_id"])
    assert len(vers) == 1 and vers[0].version_number == 1 and vers[0].created_by_type == "agent"
    ar.edit_artifact_version(db_session, org_id, run["artifact_id"], vers[0].id, "# edited", uid, "user edit")
    vers = ar.get_artifact_versions(db_session, org_id, run["artifact_id"])
    assert len(vers) == 2 and vers[0].version_number == 2 and vers[0].created_by_type == "user"


def test_approval_locks_correct_version(db_session):
    org_id, uid = _org_user(db_session, "o1", "a@o1.test")
    p = _project(db_session, org_id, uid)
    run = sa.run_stage_agent(db_session, org_id, p.id, LC.PROJECT_CONTEXT, uid)
    v1 = ar.get_artifact_versions(db_session, org_id, run["artifact_id"])[0]
    art = ar.approve_artifact(db_session, org_id, run["artifact_id"], v1.id, uid, "ok")
    assert art.status == "approved" and art.current_version_id == v1.id


def test_resubmit_creates_new_version(db_session):
    org_id, uid = _org_user(db_session, "o1", "a@o1.test")
    p = _project(db_session, org_id, uid)
    run = sa.run_stage_agent(db_session, org_id, p.id, LC.PROJECT_CONTEXT, uid)
    v1 = ar.get_artifact_versions(db_session, org_id, run["artifact_id"])[0]
    ar.approve_artifact(db_session, org_id, run["artifact_id"], v1.id, uid, "ok")
    # An edit after approval re-opens the artifact as a new version.
    ar.edit_artifact_version(db_session, org_id, run["artifact_id"], v1.id, "# v2", uid, "resubmit")
    vers = ar.get_artifact_versions(db_session, org_id, run["artifact_id"])
    assert len(vers) == 2 and {v.version_number for v in vers} == {1, 2}


def test_transition_logs_written(db_session):
    org_id, uid = _org_user(db_session, "o1", "a@o1.test")
    p = _project(db_session, org_id, uid)
    sa.run_stage_agent(db_session, org_id, p.id, LC.PROJECT_CONTEXT, uid)
    logs = sl.get_stage_transitions(db_session, org_id, p.id)
    actions = {l.action for l in logs}
    assert {"start", "generate", "submit"}.issubset(actions)


# ── Sprint generation gating ─────────────────────────────────────────
def test_sprint_generation_requires_approved_planning(db_session):
    org_id, uid = _org_user(db_session, "o1", "a@o1.test")
    p = _project(db_session, org_id, uid)
    with pytest.raises(HTTPException) as e:
        sgen.generate_sprints_from_approved_artifacts(db_session, org_id, p.id, uid)
    assert e.value.status_code == 409
    _approve_planning(db_session, org_id, p.id, uid)
    sprints = sgen.generate_sprints_from_approved_artifacts(db_session, org_id, p.id, uid)
    assert len(sprints) >= 2
    assert db_session.query(Sprint).filter(Sprint.project_id == p.id).count() == len(sprints)


# ── Validation / recon / sign-off ────────────────────────────────────
def test_validation_evidence_upload(db_session):
    org_id, uid = _org_user(db_session, "o1", "a@o1.test")
    p = _project(db_session, org_id, uid)
    ev = ve.create_evidence(db_session, org_id, p.id, uid, evidence_type="summary",
                            title="counts match", content_json={"passed": 10, "failed": 0})
    assert ev.status == "uploaded"
    assert ve.has_accepted_evidence(db_session, org_id, p.id) is False
    ve.accept_evidence(db_session, org_id, ev.id, uid)
    assert ve.has_accepted_evidence(db_session, org_id, p.id) is True


def test_recon_report_creation(db_session):
    org_id, uid = _org_user(db_session, "o1", "a@o1.test")
    p = _project(db_session, org_id, uid)
    rep = rr.generate_report(db_session, org_id, p.id, uid)
    assert rep.status == "generated" and rep.report_markdown


def test_signoff_draft_creation(db_session):
    org_id, uid = _org_user(db_session, "o1", "a@o1.test")
    p = _project(db_session, org_id, uid)
    rep = rr.generate_report(db_session, org_id, p.id, uid)
    rr.approve_report(db_session, org_id, rep.id, uid)
    draft = so.create_draft(db_session, org_id, p.id, uid)
    assert draft.status == "draft" and p.alias in (draft.subject or "")
    assert draft.recon_report_id == rep.id


# ── Full lifecycle completion (sentinel stages) — covers C1 ──────────
def test_lifecycle_completes_through_sentinel_stages(db_session):
    org_id, uid = _org_user(db_session, "o1", "a@o1.test")
    p = _project(db_session, org_id, uid)
    for s in sl.get_project_lifecycle(db_session, org_id, p.id):
        agent = s.assigned_agent
        if agent in ("__orchestration__", "__human__", "__system__"):
            sl.complete_stage(db_session, org_id, p.id, s.stage_key, uid)
        elif sa.is_agent_runnable(s.stage_key):
            sa.run_stage_agent(db_session, org_id, p.id, s.stage_key, uid)
            if s.stage_key == LC.VALIDATION:
                ev = ve.create_evidence(db_session, org_id, p.id, uid, evidence_type="summary", title="ok", content_json={"passed": 1})
                ve.accept_evidence(db_session, org_id, ev.id, uid)
            sl.approve_stage(db_session, org_id, p.id, s.stage_key, uid, "ok", allow_self_approval=True)
        # UX_DESIGN (optional) left not_started — non-blocking.
    proj = sl._get_project(db_session, org_id, p.id)
    assert proj.lifecycle_status == LC.LIFECYCLE_COMPLETED
    assert sl.get_current_stage(db_session, org_id, p.id) is None


def test_complete_stage_rejects_agent_stage(db_session):
    org_id, uid = _org_user(db_session, "o1", "a@o1.test")
    p = _project(db_session, org_id, uid)
    with pytest.raises(HTTPException) as e:
        sl.complete_stage(db_session, org_id, p.id, LC.PROJECT_CONTEXT, uid)  # agent stage
    assert e.value.status_code == 409


# ── Sprint generation must not collide with a manual sprint — covers C2 ──
def test_sprint_generation_reindexes_around_manual_sprint(db_session):
    from app.services import sprint_service
    from app.schemas.sprint import SprintCreate
    org_id, uid = _org_user(db_session, "o1", "a@o1.test")
    p = _project(db_session, org_id, uid)
    _approve_planning(db_session, org_id, p.id, uid)
    # A manual sprint (no created_from_artifact_id) at index 1 survives generation.
    manual = sprint_service.create_sprint(db_session, org_id, p.id, SprintCreate(index=1, name="Manual"))
    gen = sgen.generate_sprints_from_approved_artifacts(db_session, org_id, p.id, uid)  # must NOT raise IntegrityError
    assert len(gen) >= 2
    assert db_session.query(Sprint).filter(Sprint.id == manual.id).count() == 1   # manual survived
    idxs = [s.index for s in db_session.query(Sprint).filter(Sprint.project_id == p.id).all()]
    assert len(idxs) == len(set(idxs))  # no duplicate indexes


# ── Sign-off requires an approved recon report — covers H1 ───────────
def test_signoff_requires_approved_recon(db_session):
    org_id, uid = _org_user(db_session, "o1", "a@o1.test")
    p = _project(db_session, org_id, uid)
    rr.generate_report(db_session, org_id, p.id, uid)   # generated, NOT approved
    with pytest.raises(HTTPException) as e:
        so.create_draft(db_session, org_id, p.id, uid)
    assert e.value.status_code == 409


# ── Organization isolation ───────────────────────────────────────────
def test_organization_isolation(db_session):
    org_a, ua = _org_user(db_session, "orga", "a@orga.test")
    org_b, ub = _org_user(db_session, "orgb", "b@orgb.test")
    p = _project(db_session, org_a, ua, "A-only")
    # org B cannot read org A's lifecycle.
    with pytest.raises(HTTPException) as e:
        sl.get_project_lifecycle(db_session, org_b, p.id)
    assert e.value.status_code == 404
    # org B cannot run an agent on org A's stage.
    with pytest.raises(HTTPException) as e:
        sa.run_stage_agent(db_session, org_b, p.id, LC.PROJECT_CONTEXT, ub)
    assert e.value.status_code == 404
