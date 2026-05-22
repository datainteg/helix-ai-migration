from sqlalchemy import Column, String, Float, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class AgentDefinition(BaseModel):
    __tablename__ = "agent_definitions"

    name = Column(String(255), nullable=False)
    agent_type = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    schema_version = Column(String(20), default="1.0")


class AgentTask(BaseModel):
    __tablename__ = "agent_tasks"

    project_id = Column(String(36), nullable=False, index=True)
    agent_type = Column(String(100), nullable=False)
    status = Column(String(50), default="created", nullable=False)
    input_payload = Column(Text, nullable=True)
    prompt_template_id = Column(String(36), ForeignKey("prompt_templates.id"), nullable=True)
    prompt_version_id = Column(String(36), ForeignKey("prompt_versions.id"), nullable=True)
    llm_provider_id = Column(String(36), ForeignKey("llm_providers.id"), nullable=True)
    llm_model = Column(String(100), nullable=True)
    token_usage = Column(String(50), nullable=True)
    started_at = Column(String(50), nullable=True)
    finished_at = Column(String(50), nullable=True)

    outputs = relationship("AgentOutput", back_populates="task", cascade="all, delete-orphan")


class AgentOutput(BaseModel):
    __tablename__ = "agent_outputs"

    task_id = Column(String(36), ForeignKey("agent_tasks.id"), nullable=False)
    schema_name = Column(String(100), nullable=False)
    schema_version = Column(String(20), default="1.0")
    output_payload = Column(Text, nullable=False)
    confidence_score = Column(Float, nullable=True)

    task = relationship("AgentTask", back_populates="outputs")


class PromptTemplate(BaseModel):
    __tablename__ = "prompt_templates"

    name = Column(String(255), nullable=False)
    agent_type = Column(String(100), nullable=False)
    template = Column(Text, nullable=False)
    status = Column(String(50), default="active")

    versions = relationship("PromptVersion", back_populates="template", cascade="all, delete-orphan")


class PromptVersion(BaseModel):
    __tablename__ = "prompt_versions"

    template_id = Column(String(36), ForeignKey("prompt_templates.id"), nullable=False)
    version = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    created_by = Column(String(36), nullable=False)

    template = relationship("PromptTemplate", back_populates="versions")
