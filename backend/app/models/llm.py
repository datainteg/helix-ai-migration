from sqlalchemy import Column, String, Float, Integer, ForeignKey, Boolean, JSON
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class LLMProvider(BaseModel):
    __tablename__ = "llm_providers"

    organization_id = Column(String(36), nullable=False, index=True)
    provider_type = Column(String(50), nullable=False)
    name = Column(String(255), nullable=False)
    base_url = Column(String(500), nullable=True)
    default_model = Column(String(100), nullable=False)
    temperature = Column(Float, default=0.7)
    max_tokens = Column(Integer, default=4096)
    timeout = Column(Integer, default=60)
    status = Column(String(50), default="active", nullable=False)
    # Provider-specific config: aws_region, gcp_project, azure_endpoint, etc.
    extra_config = Column(JSON, nullable=True)

    secrets = relationship("LLMProviderSecret", back_populates="provider", cascade="all, delete-orphan")
    agent_mappings = relationship("LLMAgentMapping", back_populates="provider", cascade="all, delete-orphan")


class LLMProviderSecret(BaseModel):
    __tablename__ = "llm_provider_secrets"

    provider_id = Column(String(36), ForeignKey("llm_providers.id"), nullable=False)
    encrypted_api_key = Column(String(500), nullable=False)
    key_version = Column(Integer, default=1, nullable=False)
    rotated_at = Column(String(50), nullable=True)

    provider = relationship("LLMProvider", back_populates="secrets")


class LLMAgentMapping(BaseModel):
    __tablename__ = "llm_agent_mappings"

    organization_id = Column(String(36), nullable=False, index=True)
    agent_type = Column(String(100), nullable=False)
    provider_id = Column(String(36), ForeignKey("llm_providers.id"), nullable=False)
    model = Column(String(100), nullable=False)
    temperature = Column(Float, default=0.7)
    max_tokens = Column(Integer, default=4096)

    provider = relationship("LLMProvider", back_populates="agent_mappings")
