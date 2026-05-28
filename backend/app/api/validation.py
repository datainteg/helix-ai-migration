from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Any

from app.db.session import get_db
from app.auth.jwt import get_current_user_id
from app.auth.dependencies import get_current_organization_id
from app.models.validation import ValidationRule, ValidationRun, ValidationResult, ReconRun, ReconResult
from app.services.project_service import ensure_project_access
from app.services.recon_service import run_row_count_recon
from app.api.audit import write_audit
from app.schemas.pagination import PaginatedResponse, paginate

router = APIRouter(tags=["validation"])


class RuleCreate(BaseModel):
    rule_type: str
    target_ref: str = ""
    definition: str = ""


class ValidationRunCreate(BaseModel):
    connector_configs: dict[str, Any] = {}


class ReconRunCreate(BaseModel):
    source: dict[str, Any]
    target: dict[str, Any]


class ValidationRuleSummary(BaseModel):
    """Lightweight rule row returned by `list_rules`.

    Replaces the previous hand-built dict so OpenAPI lists the fields.
    """

    id: str
    rule_type: str
    target_ref: str | None = None
    status: str | None = None


class ValidationRuleCreated(BaseModel):
    id: str
    rule_type: str
    status: str


@router.post(
    "/projects/{project_id}/validation-rules",
    response_model=ValidationRuleCreated,
    status_code=201,
)
def create_rule(project_id: str, data: RuleCreate, request: Request, org_id: str = Depends(get_current_organization_id), user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    ensure_project_access(db, org_id, project_id)
    rule = ValidationRule(project_id=project_id, rule_type=data.rule_type, target_ref=data.target_ref, definition=data.definition)
    db.add(rule)
    db.commit()
    # Audit emission was missing — REVIEW_API_CONTRACT §Audit emission §2 flag.
    write_audit(
        db, org_id=org_id, actor_id=user_id,
        action="validation_rule_created",
        entity_type="validation_rule", entity_id=rule.id,
        meta={"project_id": project_id, "rule_type": data.rule_type},
        request=request,
    )
    return ValidationRuleCreated(id=rule.id, rule_type=rule.rule_type, status="active")


@router.get(
    "/projects/{project_id}/validation-rules",
    response_model=PaginatedResponse[ValidationRuleSummary],
)
def list_rules(
    project_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """List validation rules for a project (paginated envelope).

    Breaking change vs v0.x: response is now `{items,total,limit,offset}`.
    See REVIEW_API_CONTRACT.md §API-C2.
    """
    ensure_project_access(db, org_id, project_id)
    rules = db.query(ValidationRule).filter(ValidationRule.project_id == project_id).all()
    rows = [
        ValidationRuleSummary(
            id=r.id, rule_type=r.rule_type, target_ref=r.target_ref, status=r.status,
        )
        for r in rules
    ]
    return paginate(rows, limit=limit, offset=offset)


class ValidationRunStarted(BaseModel):
    id: str
    status: str
    rule_count: int


class ValidationResultRow(BaseModel):
    rule_id: str | None = None
    status: str | None = None
    observed: str | None = None
    expected: str | None = None


class ValidationRunDetail(BaseModel):
    id: str
    status: str
    results: list[ValidationResultRow]


@router.post(
    "/projects/{project_id}/validation-runs",
    response_model=ValidationRunStarted,
    status_code=202,
)
async def start_validation(
    request: Request,
    background_tasks: BackgroundTasks,
    project_id: str,
    data: ValidationRunCreate = None,
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Create and execute a validation run against all rules for the project."""
    ensure_project_access(db, org_id, project_id)
    run = ValidationRun(project_id=project_id, started_by=user_id, status="pending")
    db.add(run)
    db.commit()
    write_audit(db, org_id=org_id, actor_id=user_id, action="validation_run_started", entity_type="validation_run", entity_id=run.id, request=request)

    rules = db.query(ValidationRule).filter(ValidationRule.project_id == project_id, ValidationRule.status == "active").all()
    connector_configs = (data.connector_configs if data else None) or {}

    if rules:
        from app.services.validation_service import execute_validation_run
        rule_ids = [r.id for r in rules]
        background_tasks.add_task(execute_validation_run, run.id, rule_ids, connector_configs)
        return ValidationRunStarted(id=run.id, status="pending", rule_count=len(rules))

    run.status = "completed"
    db.commit()
    return ValidationRunStarted(id=run.id, status="completed", rule_count=0)


@router.get(
    "/projects/{project_id}/validation-runs/{run_id}",
    response_model=ValidationRunDetail,
)
def get_validation_run(project_id: str, run_id: str, org_id: str = Depends(get_current_organization_id), user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    ensure_project_access(db, org_id, project_id)
    run = db.query(ValidationRun).filter(ValidationRun.id == run_id, ValidationRun.project_id == project_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Validation run not found")
    results = db.query(ValidationResult).filter(ValidationResult.run_id == run_id).all()
    return ValidationRunDetail(
        id=run.id,
        status=run.status,
        results=[
            ValidationResultRow(rule_id=r.rule_id, status=r.status, observed=r.observed_value, expected=r.expected_value)
            for r in results
        ],
    )


@router.post("/projects/{project_id}/recon-runs")
async def start_recon(request: Request, project_id: str, data: ReconRunCreate, org_id: str = Depends(get_current_organization_id), user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """Run row-count reconciliation between source and target connectors."""
    ensure_project_access(db, org_id, project_id)
    try:
        result = await run_row_count_recon(
            db=db,
            organization_id=org_id,
            project_id=project_id,
            source=data.source,
            target=data.target,
        )
    except Exception:
        # Sanitize: never echo raw exception text to clients — reuses the
        # same pattern as agent_workflows.signal_* (REVIEW_API_CONTRACT
        # `signal-approve` 503 issue). This now only catches programming
        # errors; expected connector failures are returned as a structured
        # dict (H-002) and handled below.
        import logging
        logging.getLogger(__name__).exception("Reconciliation run failed for project %s", project_id)
        raise HTTPException(status_code=502, detail="Reconciliation failed (see server logs)")

    # H-002: the service now returns a structured failure dict instead of
    # raising, so the recon run row carries diagnostic data. Map it to a
    # 422 with detail rather than a generic 500.
    if result.get("status") == "failed":
        write_audit(db, org_id=org_id, actor_id=user_id, action="recon_run_failed",
                    entity_type="recon_run", entity_id=result.get("recon_run_id", ""),
                    request=request)
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Reconciliation could not complete",
                "recon_run_id": result.get("recon_run_id", ""),
                "error": result.get("error_message", "unknown error"),
            },
        )
    write_audit(db, org_id=org_id, actor_id=user_id, action="recon_run_started", entity_type="recon_run", entity_id=result.get("recon_run_id", ""), request=request)
    return result
