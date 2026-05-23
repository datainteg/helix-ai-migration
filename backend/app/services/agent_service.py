from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.agents import AgentTask, AgentOutput, AgentDefinition, PromptTemplate, PromptVersion
from app.models.project import Project
from app.schemas.agents import (
    AgentTaskCreate, AgentTaskResponse,
    AgentOutputCreate, AgentOutputResponse,
    PromptTemplateCreate, PromptTemplateResponse,
    PromptVersionCreate, PromptVersionResponse,
)


# ── Agent Tasks ──

def _ensure_project_access(db: Session, org_id: str, project_id: str) -> None:
    project = db.query(Project).filter(Project.id == project_id, Project.organization_id == org_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")


def create_task(db: Session, org_id: str, project_id: str, data: AgentTaskCreate) -> AgentTaskResponse:
    _ensure_project_access(db, org_id, project_id)
    task = AgentTask(project_id=project_id, agent_type=data.agent_type, input_payload=data.input_payload)
    db.add(task)
    db.commit()
    db.refresh(task)
    return AgentTaskResponse.model_validate(task)


def get_task(db: Session, org_id: str, task_id: str) -> AgentTaskResponse:
    task = (
        db.query(AgentTask)
        .join(Project, AgentTask.project_id == Project.id)
        .filter(AgentTask.id == task_id, Project.organization_id == org_id)
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return AgentTaskResponse.model_validate(task)


def add_output(db: Session, org_id: str, task_id: str, data: AgentOutputCreate) -> AgentOutputResponse:
    task = (
        db.query(AgentTask)
        .join(Project, AgentTask.project_id == Project.id)
        .filter(AgentTask.id == task_id, Project.organization_id == org_id)
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    output = AgentOutput(task_id=task_id, schema_name=data.schema_name, output_payload=data.output_payload, confidence_score=data.confidence_score)
    db.add(output)
    db.commit()
    db.refresh(output)
    return AgentOutputResponse.model_validate(output)


def get_outputs(db: Session, org_id: str, task_id: str) -> list[AgentOutputResponse]:
    task = (
        db.query(AgentTask)
        .join(Project, AgentTask.project_id == Project.id)
        .filter(AgentTask.id == task_id, Project.organization_id == org_id)
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    outputs = db.query(AgentOutput).filter(AgentOutput.task_id == task_id).all()
    return [AgentOutputResponse.model_validate(o) for o in outputs]


# ── Prompt Templates ──

def create_prompt_template(db: Session, data: PromptTemplateCreate) -> PromptTemplateResponse:
    pt = PromptTemplate(name=data.name, agent_type=data.agent_type, template=data.template)
    db.add(pt)
    db.commit()
    db.refresh(pt)
    return PromptTemplateResponse.model_validate(pt)


def list_prompt_templates(db: Session) -> list[PromptTemplateResponse]:
    templates = db.query(PromptTemplate).all()
    return [PromptTemplateResponse.model_validate(t) for t in templates]


def create_prompt_version(db: Session, template_id: str, data: PromptVersionCreate, user_id: str) -> PromptVersionResponse:
    latest = db.query(PromptVersion).filter(PromptVersion.template_id == template_id).order_by(PromptVersion.version.desc()).first()
    next_version = str(int(latest.version) + 1) if latest else "1"
    pv = PromptVersion(template_id=template_id, version=next_version, content=data.content, created_by=user_id)
    db.add(pv)
    db.commit()
    db.refresh(pv)
    return PromptVersionResponse.model_validate(pv)
