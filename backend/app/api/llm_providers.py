from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.auth.jwt import get_current_user_id
from app.schemas.llm import (
    LLMProviderCreate, LLMProviderUpdate, LLMProviderResponse,
    AgentMappingCreate, AgentMappingResponse, KeyRotateRequest, TestConnectionResponse,
)
from app.services.llm_provider_service import (
    create_provider, list_providers, get_provider, update_provider,
    rotate_key, test_connection, delete_provider,
    create_agent_mapping, list_agent_mappings,
)
from app.api.audit import write_audit

router = APIRouter(tags=["llm-providers"])


def _org(db, uid):
    from app.services.auth_service import get_current_user
    return get_current_user(db, uid).memberships[0].organization_id


@router.get("/llm-providers", response_model=list[LLMProviderResponse])
def api_list_providers(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return list_providers(db, _org(db, user_id))


@router.post("/llm-providers", response_model=LLMProviderResponse, status_code=201)
def api_create_provider(data: LLMProviderCreate, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db), request: Request = None):
    org_id = _org(db, user_id)
    result = create_provider(db, org_id, data)
    write_audit(db, org_id, user_id, "llm_provider_created", "llm_provider", result.id, request=request)
    return result


@router.get("/llm-providers/{provider_id}", response_model=LLMProviderResponse)
def api_get_provider(provider_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return get_provider(db, provider_id)


@router.patch("/llm-providers/{provider_id}", response_model=LLMProviderResponse)
def api_update_provider(provider_id: str, data: LLMProviderUpdate, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db), request: Request = None):
    result = update_provider(db, provider_id, data)
    write_audit(db, _org(db, user_id), user_id, "llm_provider_updated", "llm_provider", provider_id, request=request)
    return result


@router.post("/llm-providers/{provider_id}/rotate-key", response_model=LLMProviderResponse)
def api_rotate_key(provider_id: str, data: KeyRotateRequest, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db), request: Request = None):
    result = rotate_key(db, provider_id, data.new_api_key)
    write_audit(db, _org(db, user_id), user_id, "llm_key_rotated", "llm_provider", provider_id, request=request)
    return result


@router.post("/llm-providers/{provider_id}/test", response_model=TestConnectionResponse)
async def api_test_provider(provider_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return await test_connection(db, provider_id)


@router.delete("/llm-providers/{provider_id}", status_code=204)
def api_delete_provider(provider_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db), request: Request = None):
    delete_provider(db, provider_id)
    write_audit(db, _org(db, user_id), user_id, "llm_provider_deleted", "llm_provider", provider_id, request=request)


@router.get("/llm-agent-mappings", response_model=list[AgentMappingResponse])
def api_list_mappings(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return list_agent_mappings(db, _org(db, user_id))


@router.post("/llm-agent-mappings", response_model=AgentMappingResponse, status_code=201)
def api_create_mapping(data: AgentMappingCreate, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return create_agent_mapping(db, _org(db, user_id), data)
