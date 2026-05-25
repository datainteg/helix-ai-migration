from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.auth.jwt import get_current_user_id
from app.auth.dependencies import require_permission
from app.schemas.llm import (
    LLMProviderCreate, LLMProviderUpdate, LLMProviderResponse,
    AgentMappingCreate, AgentMappingResponse, KeyRotateRequest, TestConnectionResponse,
)
from app.services.llm_provider_service import (
    create_provider, list_providers, get_provider, update_provider,
    rotate_key, test_connection, delete_provider,
    create_agent_mapping, list_agent_mappings, replace_agent_mappings,
)
from app.api.audit import write_audit

from app.rate_limiting import limiter

router = APIRouter(tags=["llm-providers"])

# Catalogue + model registry come from the agents package so there's one
# source of truth shared with the LLM adapters in agents/runtime/providers/.
from agents.runtime.models import MODELS as _AGENTS_MODELS, DEFAULT_MODELS as _DEFAULTS
from agents.runtime.providers import get_provider as _get_provider, list_providers as _list_providers


def _org(db, uid):
    from app.services.auth_service import get_current_user
    return get_current_user(db, uid).memberships[0].organization_id


def _models_by_id(ptype: str) -> list[str]:
    return [m.get("id", "") for m in _AGENTS_MODELS.get(ptype, []) if m.get("id")]


def _default_base_url(ptype: str) -> str:
    p = _get_provider(ptype)
    return (p.default_base_url or "") if p else ""


# Stable enumeration order for the wizard UI.
_PROVIDER_ORDER = [
    "anthropic", "openai", "google", "deepseek", "openrouter",
    "bedrock", "vertex", "azure", "local", "custom",
]


@router.get("/llm-providers/catalogue")
def api_provider_catalogue(user_id: str = Depends(get_current_user_id)):
    """Return supported providers with their model list + default base URL."""
    return [
        {
            "provider_type": ptype,
            "models": _models_by_id(ptype),
            "default_base_url": _default_base_url(ptype),
            "default_model": _DEFAULTS.get(ptype, ""),
        }
        for ptype in _PROVIDER_ORDER if ptype in _list_providers()
    ]


@router.get("/llm-providers/models")
def api_provider_models(user_id: str = Depends(get_current_user_id)):
    """Return full model registry: { provider_type: [{id, name, context_window, ...}] }."""
    return _AGENTS_MODELS


@router.get("/llm-providers", response_model=list[LLMProviderResponse])
def api_list_providers(user_id: str = Depends(require_permission("admin:llm:read")), db: Session = Depends(get_db)):
    return list_providers(db, _org(db, user_id))


@router.post("/llm-providers", response_model=LLMProviderResponse, status_code=201)
def api_create_provider(data: LLMProviderCreate, user_id: str = Depends(require_permission("admin:llm:write")), db: Session = Depends(get_db), request: Request = None):
    org_id = _org(db, user_id)
    result = create_provider(db, org_id, data)
    write_audit(db, org_id, user_id, "llm_provider_created", "llm_provider", result.id, request=request)
    return result


@router.get("/llm-providers/{provider_id}", response_model=LLMProviderResponse)
def api_get_provider(provider_id: str, user_id: str = Depends(require_permission("admin:llm:read")), db: Session = Depends(get_db)):
    return get_provider(db, _org(db, user_id), provider_id)


@router.patch("/llm-providers/{provider_id}", response_model=LLMProviderResponse)
def api_update_provider(provider_id: str, data: LLMProviderUpdate, user_id: str = Depends(require_permission("admin:llm:write")), db: Session = Depends(get_db), request: Request = None):
    org_id = _org(db, user_id)
    result = update_provider(db, org_id, provider_id, data)
    write_audit(db, _org(db, user_id), user_id, "llm_provider_updated", "llm_provider", provider_id, request=request)
    return result


@router.post("/llm-providers/{provider_id}/rotate-key", response_model=LLMProviderResponse)
def api_rotate_key(provider_id: str, data: KeyRotateRequest, user_id: str = Depends(require_permission("admin:llm:write")), db: Session = Depends(get_db), request: Request = None):
    org_id = _org(db, user_id)
    result = rotate_key(db, org_id, provider_id, data.new_api_key)
    write_audit(db, _org(db, user_id), user_id, "llm_key_rotated", "llm_provider", provider_id, request=request)
    return result


@router.post("/llm-providers/{provider_id}/test", response_model=TestConnectionResponse)
@limiter.limit("10/minute")
async def api_test_provider(request: Request, provider_id: str, user_id: str = Depends(require_permission("admin:llm:read")), db: Session = Depends(get_db)):
    return await test_connection(db, _org(db, user_id), provider_id)


@router.delete("/llm-providers/{provider_id}", status_code=204)
def api_delete_provider(provider_id: str, user_id: str = Depends(require_permission("admin:llm:write")), db: Session = Depends(get_db), request: Request = None):
    delete_provider(db, _org(db, user_id), provider_id)
    write_audit(db, _org(db, user_id), user_id, "llm_provider_deleted", "llm_provider", provider_id, request=request)


@router.get("/llm-agent-mappings", response_model=list[AgentMappingResponse])
def api_list_mappings(user_id: str = Depends(require_permission("admin:llm:read")), db: Session = Depends(get_db)):
    return list_agent_mappings(db, _org(db, user_id))


@router.post("/llm-agent-mappings", response_model=AgentMappingResponse, status_code=201)
def api_create_mapping(data: AgentMappingCreate, user_id: str = Depends(require_permission("admin:llm:write")), db: Session = Depends(get_db)):
    return create_agent_mapping(db, _org(db, user_id), data)


@router.put("/llm-agent-mappings", response_model=list[AgentMappingResponse])
def api_replace_mappings(
    data: list[AgentMappingCreate],
    user_id: str = Depends(require_permission("admin:llm:write")),
    db: Session = Depends(get_db),
    request: Request = None,
):
    """Atomically replace all agent mappings for the current organization."""
    org_id = _org(db, user_id)
    result = replace_agent_mappings(db, org_id, data)
    write_audit(db, org_id, user_id, "llm_agent_mappings_replaced", "llm_agent_mapping", "*", request=request)
    return result
