from typing import Optional, List
from pydantic import BaseModel


class LLMProviderCreate(BaseModel):
    provider_type: str
    name: str
    api_key: str
    base_url: Optional[str] = None
    default_model: str = "gpt-4.1"
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: int = 60


class LLMProviderUpdate(BaseModel):
    name: Optional[str] = None
    base_url: Optional[str] = None
    default_model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    timeout: Optional[int] = None
    status: Optional[str] = None


class LLMProviderResponse(BaseModel):
    id: str
    organization_id: str
    provider_type: str
    name: str
    base_url: Optional[str] = None
    default_model: str
    temperature: float
    max_tokens: int
    timeout: int
    status: str
    api_key_masked: Optional[str] = None

    model_config = {"from_attributes": True}


class AgentMappingCreate(BaseModel):
    agent_type: str
    provider_id: str
    model: str
    temperature: float = 0.7
    max_tokens: int = 4096


class AgentMappingResponse(BaseModel):
    id: str
    organization_id: str
    agent_type: str
    provider_id: str
    model: str
    temperature: float
    max_tokens: int

    model_config = {"from_attributes": True}


class KeyRotateRequest(BaseModel):
    new_api_key: str


class TestConnectionResponse(BaseModel):
    success: bool
    message: str
