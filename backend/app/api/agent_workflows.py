from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.session import get_db
from app.auth.jwt import get_current_user_id
from agents.bmad.workflow import run_bmad_workflow


class StartWorkflowRequest(BaseModel):
    requirement_id: str


class ApprovalRequest(BaseModel):
    decision: str  # "approved" or "rejected"
    notes: str = ""


router = APIRouter(tags=["agent-workflows"])


@router.post("/projects/{project_id}/agent-workflows")
def start_workflow(project_id: str, data: StartWorkflowRequest, user_id: str = Depends(get_current_user_id)):
    result = run_bmad_workflow(project_id, data.requirement_id)
    return {"workflow": result}


@router.post("/agent-workflows/{workflow_id}/approve")
def approve_step(workflow_id: str, data: ApprovalRequest, user_id: str = Depends(get_current_user_id)):
    return {"workflow_id": workflow_id, "decision": data.decision, "status": "recorded"}


@router.get("/projects/{project_id}/agent-workflows")
def list_workflows(project_id: str, user_id: str = Depends(get_current_user_id)):
    return {"project_id": project_id, "workflows": []}
