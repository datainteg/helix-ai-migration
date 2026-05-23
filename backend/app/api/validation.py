from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
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


@router.post("/projects/{project_id}/validation-rules")
def create_rule(project_id: str, data: RuleCreate, org_id: str = Depends(get_current_organization_id), user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    ensure_project_access(db, org_id, project_id)
    rule = ValidationRule(project_id=project_id, rule_type=data.rule_type, target_ref=data.target_ref, definition=data.definition)
    db.add(rule)
    db.commit()
    return {"id": rule.id, "rule_type": rule.rule_type, "status": "active"}


@router.get("/projects/{project_id}/validation-rules")
def list_rules(project_id: str, org_id: str = Depends(get_current_organization_id), user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    ensure_project_access(db, org_id, project_id)
    rules = db.query(ValidationRule).filter(ValidationRule.project_id == project_id).all()
    return [{"id": r.id, "rule_type": r.rule_type, "target_ref": r.target_ref, "status": r.status} for r in rules]


@router.post("/projects/{project_id}/validation-runs")
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
        background_tasks.add_task(execute_validation_run, db, run, rules, connector_configs)
        return {"id": run.id, "status": "pending", "rule_count": len(rules)}

    run.status = "completed"
    db.commit()
    return {"id": run.id, "status": "completed", "rule_count": 0}


@router.get("/projects/{project_id}/validation-runs/{run_id}")
def get_validation_run(project_id: str, run_id: str, org_id: str = Depends(get_current_organization_id), user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    ensure_project_access(db, org_id, project_id)
    run = db.query(ValidationRun).filter(ValidationRun.id == run_id, ValidationRun.project_id == project_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Validation run not found")
    results = db.query(ValidationResult).filter(ValidationResult.run_id == run_id).all()
    return {
        "id": run.id,
        "status": run.status,
        "results": [{"rule_id": r.rule_id, "status": r.status, "observed": r.observed_value, "expected": r.expected_value} for r in results],
    }


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
        write_audit(db, org_id=org_id, actor_id=user_id, action="recon_run_started", entity_type="recon_run", entity_id=result.get("recon_run_id", ""), request=request)
        return result
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Reconciliation failed: {exc}")
