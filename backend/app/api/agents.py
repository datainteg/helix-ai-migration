from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.auth.jwt import get_current_user_id
from app.schemas.agents import (
    AgentTaskCreate, AgentTaskResponse,
    AgentOutputCreate, AgentOutputResponse,
    PromptTemplateCreate, PromptTemplateResponse,
    PromptVersionCreate, PromptVersionResponse,
)
from app.services.agent_service import (
    create_task, get_task, add_output, get_outputs,
    create_prompt_template, list_prompt_templates, create_prompt_version,
)

router = APIRouter(tags=["agents"])


@router.post("/projects/{project_id}/agent-tasks", response_model=AgentTaskResponse, status_code=201)
def api_create_task(project_id: str, data: AgentTaskCreate, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return create_task(db, project_id, data)


@router.get("/agent-tasks/{task_id}", response_model=AgentTaskResponse)
def api_get_task(task_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return get_task(db, task_id)


@router.post("/agent-tasks/{task_id}/outputs", response_model=AgentOutputResponse, status_code=201)
def api_add_output(task_id: str, data: AgentOutputCreate, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return add_output(db, task_id, data)


@router.get("/agent-tasks/{task_id}/outputs", response_model=list[AgentOutputResponse])
def api_get_outputs(task_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return get_outputs(db, task_id)


@router.post("/prompt-templates", response_model=PromptTemplateResponse, status_code=201)
def api_create_template(data: PromptTemplateCreate, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return create_prompt_template(db, data)


@router.get("/prompt-templates", response_model=list[PromptTemplateResponse])
def api_list_templates(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return list_prompt_templates(db)


@router.post("/prompt-templates/{template_id}/versions", response_model=PromptVersionResponse, status_code=201)
def api_create_version(template_id: str, data: PromptVersionCreate, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return create_prompt_version(db, template_id, data, user_id)
