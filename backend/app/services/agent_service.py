from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.agents import AgentTask, AgentOutput, AgentDefinition, PromptTemplate, PromptVersion
from app.schemas.agents import (
    AgentTaskCreate, AgentTaskResponse,
    AgentOutputCreate, AgentOutputResponse,
    PromptTemplateCreate, PromptTemplateResponse,
    PromptVersionCreate, PromptVersionResponse,
)


# ── Agent Tasks ──

def create_task(db: Session, project_id: str, data: AgentTaskCreate) -> AgentTaskResponse:
    task = AgentTask(project_id=project_id, agent_type=data.agent_type, input_payload=data.input_payload)
    db.add(task)
    db.commit()
    db.refresh(task)
    return AgentTaskResponse.model_validate(task)


def get_task(db: Session, task_id: str) -> AgentTaskResponse:
    task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return AgentTaskResponse.model_validate(task)


def add_output(db: Session, task_id: str, data: AgentOutputCreate) -> AgentOutputResponse:
    output = AgentOutput(task_id=task_id, schema_name=data.schema_name, output_payload=data.output_payload, confidence_score=data.confidence_score)
    db.add(output)
    db.commit()
    db.refresh(output)
    return AgentOutputResponse.model_validate(output)


def get_outputs(db: Session, task_id: str) -> list[AgentOutputResponse]:
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
