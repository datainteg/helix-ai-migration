import uuid
import httpx

from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.llm import LLMProvider, LLMProviderSecret, LLMAgentMapping
from app.schemas.llm import (
    LLMProviderCreate, LLMProviderUpdate, LLMProviderResponse,
    AgentMappingCreate, AgentMappingResponse, TestConnectionResponse,
)
from app.services.secret_service import encrypt_value, decrypt_value, mask_key
from app.core.config import settings


def create_provider(db: Session, org_id: str, data: LLMProviderCreate) -> LLMProviderResponse:
    provider = LLMProvider(
        organization_id=org_id,
        provider_type=data.provider_type,
        name=data.name,
        base_url=data.base_url,
        default_model=data.default_model,
        temperature=data.temperature,
        max_tokens=data.max_tokens,
        timeout=data.timeout,
    )
    db.add(provider)
    db.flush()

    secret = LLMProviderSecret(
        provider_id=provider.id,
        encrypted_api_key=encrypt_value(data.api_key),
        key_version=1,
    )
    db.add(secret)
    db.commit()
    db.refresh(provider)

    return _to_response(provider)


def list_providers(db: Session, org_id: str) -> list[LLMProviderResponse]:
    providers = db.query(LLMProvider).filter(LLMProvider.organization_id == org_id).all()
    return [_to_response(p) for p in providers]


def get_provider(db: Session, org_id: str, provider_id: str) -> LLMProviderResponse:
    provider = db.query(LLMProvider).filter(LLMProvider.id == provider_id, LLMProvider.organization_id == org_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return _to_response(provider)


def update_provider(db: Session, org_id: str, provider_id: str, data: LLMProviderUpdate) -> LLMProviderResponse:
    provider = db.query(LLMProvider).filter(LLMProvider.id == provider_id, LLMProvider.organization_id == org_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(provider, field, value)
    db.commit()
    db.refresh(provider)
    return _to_response(provider)


def rotate_key(db: Session, org_id: str, provider_id: str, new_api_key: str) -> LLMProviderResponse:
    provider = db.query(LLMProvider).filter(LLMProvider.id == provider_id, LLMProvider.organization_id == org_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    latest = db.query(LLMProviderSecret).filter(
        LLMProviderSecret.provider_id == provider_id
    ).order_by(LLMProviderSecret.key_version.desc()).first()

    new_secret = LLMProviderSecret(
        provider_id=provider_id,
        encrypted_api_key=encrypt_value(new_api_key),
        key_version=(latest.key_version + 1) if latest else 1,
        rotated_at=str(uuid.uuid4()),
    )
    db.add(new_secret)
    db.commit()
    return _to_response(provider)


async def test_connection(db: Session, org_id: str, provider_id: str) -> TestConnectionResponse:
    provider = db.query(LLMProvider).filter(LLMProvider.id == provider_id, LLMProvider.organization_id == org_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    if provider.status != "active":
        return TestConnectionResponse(success=False, message="Provider is inactive")

    # Resolve API key
    latest_secret = sorted(provider.secrets, key=lambda s: s.key_version, reverse=True)[0] if provider.secrets else None
    if not latest_secret:
        return TestConnectionResponse(success=False, message="No API key configured")

    try:
        api_key = decrypt_value(latest_secret.encrypted_api_key)
    except Exception:
        return TestConnectionResponse(success=False, message="Failed to decrypt API key")

    # Resolve base URL based on provider type
    base_url = provider.base_url or _default_base_url(provider.provider_type)
    if not base_url:
        return TestConnectionResponse(success=False, message=f"No base URL configured for {provider.provider_type}")

    # Attempt a lightweight API call to verify connectivity
    try:
        async with httpx.AsyncClient(timeout=float(provider.timeout)) as client:
            resp = await client.get(
                f"{base_url.rstrip('/')}/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            if resp.status_code in (200, 401):
                # 401 = valid endpoint, just auth issue (key may have limited scope)
                return TestConnectionResponse(success=True, message=f"Connected to {provider.name} — endpoint reachable")
            return TestConnectionResponse(success=False, message=f"Unexpected response: HTTP {resp.status_code}")
    except httpx.ConnectError:
        return TestConnectionResponse(success=False, message=f"Cannot reach {base_url} — connection refused")
    except httpx.TimeoutException:
        return TestConnectionResponse(success=False, message=f"Connection to {base_url} timed out after {provider.timeout}s")
    except Exception as e:
        return TestConnectionResponse(success=False, message=f"Connection test failed: {str(e)[:200]}")


def _default_base_url(provider_type: str) -> str | None:
    mapping = {
        "openai": "https://api.openai.com/v1",
        "anthropic": "https://api.anthropic.com/v1",
        "google": "https://generativelanguage.googleapis.com/v1",
        "deepseek": "https://api.deepseek.com/v1",
        "openrouter": "https://openrouter.ai/api/v1",
    }
    return mapping.get(provider_type)


def delete_provider(db: Session, org_id: str, provider_id: str):
    provider = db.query(LLMProvider).filter(LLMProvider.id == provider_id, LLMProvider.organization_id == org_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    db.delete(provider)
    db.commit()


def create_agent_mapping(db: Session, org_id: str, data: AgentMappingCreate) -> AgentMappingResponse:
    provider = db.query(LLMProvider).filter(LLMProvider.id == data.provider_id, LLMProvider.organization_id == org_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    mapping = LLMAgentMapping(
        organization_id=org_id,
        agent_type=data.agent_type,
        provider_id=data.provider_id,
        model=data.model,
        temperature=data.temperature,
        max_tokens=data.max_tokens,
    )
    db.add(mapping)
    db.commit()
    db.refresh(mapping)
    return AgentMappingResponse.model_validate(mapping)


def list_agent_mappings(db: Session, org_id: str) -> list[AgentMappingResponse]:
    mappings = db.query(LLMAgentMapping).filter(LLMAgentMapping.organization_id == org_id).all()
    return [AgentMappingResponse.model_validate(m) for m in mappings]


def _to_response(provider: LLMProvider) -> LLMProviderResponse:
    latest_secret = None
    if provider.secrets:
        latest_secret = sorted(provider.secrets, key=lambda s: s.key_version, reverse=True)[0]

    masked = None
    if latest_secret:
        try:
            decrypted = decrypt_value(latest_secret.encrypted_api_key)
            masked = mask_key(decrypted)
        except Exception:
            masked = "***"

    return LLMProviderResponse(
        id=provider.id,
        organization_id=provider.organization_id,
        provider_type=provider.provider_type,
        name=provider.name,
        base_url=provider.base_url,
        default_model=provider.default_model,
        temperature=provider.temperature,
        max_tokens=provider.max_tokens,
        timeout=provider.timeout,
        status=provider.status,
        api_key_masked=masked,
    )
