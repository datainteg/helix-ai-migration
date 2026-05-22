from typing import Optional, List
from pydantic import BaseModel


class AgentTaskCreate(BaseModel):
    agent_type: str
    input_payload: Optional[str] = None


class AgentTaskResponse(BaseModel):
    id: str
    project_id: str
    agent_type: str
    status: str
    llm_model: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None

    model_config = {"from_attributes": True}


class AgentOutputCreate(BaseModel):
    schema_name: str
    output_payload: str
    confidence_score: Optional[float] = None


class AgentOutputResponse(BaseModel):
    id: str
    task_id: str
    schema_name: str
    schema_version: str
    output_payload: str
    confidence_score: Optional[float] = None

    model_config = {"from_attributes": True}


class PromptTemplateCreate(BaseModel):
    name: str
    agent_type: str
    template: str


class PromptTemplateResponse(BaseModel):
    id: str
    name: str
    agent_type: str
    template: str
    status: str

    model_config = {"from_attributes": True}


class PromptVersionCreate(BaseModel):
    content: str


class PromptVersionResponse(BaseModel):
    id: str
    template_id: str
    version: str
    content: str
    created_by: str

    model_config = {"from_attributes": True}
