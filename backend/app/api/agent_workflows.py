from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.session import get_db
from app.auth.jwt import get_current_user_id
from app.auth.dependencies import get_current_organization_id
from app.services.project_service import ensure_project_access
from agents.bmad.workflow import run_bmad_workflow


class StartWorkflowRequest(BaseModel):
    requirement_id: str


class ApprovalRequest(BaseModel):
    decision: str  # "approved" or "rejected"
    notes: str = ""


router = APIRouter(tags=["agent-workflows"])


@router.post("/projects/{project_id}/agent-workflows")
def start_workflow(project_id: str, data: StartWorkflowRequest, org_id: str = Depends(get_current_organization_id), user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    ensure_project_access(db, org_id, project_id)
    result = run_bmad_workflow(project_id, data.requirement_id)
    return {"workflow": result}


@router.post("/agent-workflows/{workflow_id}/approve")
def approve_step(workflow_id: str, data: ApprovalRequest, user_id: str = Depends(get_current_user_id)):
    return {"workflow_id": workflow_id, "decision": data.decision, "status": "recorded"}


@router.get("/projects/{project_id}/agent-workflows")
def list_workflows(project_id: str, org_id: str = Depends(get_current_organization_id), user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    ensure_project_access(db, org_id, project_id)
    return {"project_id": project_id, "workflows": []}
