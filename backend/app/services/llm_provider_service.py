from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.llm import LLMProvider, LLMProviderSecret, LLMAgentMapping
from app.schemas.llm import (
    LLMProviderCreate,
    LLMProviderUpdate,
    LLMProviderResponse,
    AgentMappingCreate,
    AgentMappingResponse,
    TestConnectionResponse,
)
from app.services.llm_provider_adapters import ProviderConnectionConfig, build_llm_provider_adapter
from app.services.secret_service import encrypt_value, decrypt_value, mask_key


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
        extra_config=data.extra_config,
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
    provider = db.query(LLMProvider).filter(
        LLMProvider.id == provider_id,
        LLMProvider.organization_id == org_id,
    ).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return _to_response(provider)


def update_provider(db: Session, org_id: str, provider_id: str, data: LLMProviderUpdate) -> LLMProviderResponse:
    provider = db.query(LLMProvider).filter(
        LLMProvider.id == provider_id,
        LLMProvider.organization_id == org_id,
    ).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(provider, field, value)
    db.commit()
    db.refresh(provider)
    return _to_response(provider)


def rotate_key(db: Session, org_id: str, provider_id: str, new_api_key: str) -> LLMProviderResponse:
    provider = db.query(LLMProvider).filter(
        LLMProvider.id == provider_id,
        LLMProvider.organization_id == org_id,
    ).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    latest = db.query(LLMProviderSecret).filter(
        LLMProviderSecret.provider_id == provider_id
    ).order_by(LLMProviderSecret.key_version.desc()).first()

    new_secret = LLMProviderSecret(
        provider_id=provider_id,
        encrypted_api_key=encrypt_value(new_api_key),
        key_version=(latest.key_version + 1) if latest else 1,
        rotated_at=datetime.now(timezone.utc).isoformat(),
    )
    db.add(new_secret)
    db.commit()
    return _to_response(provider)


async def test_connection(db: Session, org_id: str, provider_id: str) -> TestConnectionResponse:
    provider = db.query(LLMProvider).filter(
        LLMProvider.id == provider_id,
        LLMProvider.organization_id == org_id,
    ).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    if provider.status != "active":
        return TestConnectionResponse(success=False, message="Provider is inactive")

    latest_secret = sorted(provider.secrets, key=lambda s: s.key_version, reverse=True)[0] if provider.secrets else None
    if not latest_secret:
        return TestConnectionResponse(success=False, message="No API key configured")

    try:
        api_key = decrypt_value(latest_secret.encrypted_api_key)
    except Exception:
        return TestConnectionResponse(success=False, message="Failed to decrypt API key")

    adapter = build_llm_provider_adapter(
        ProviderConnectionConfig(
            provider_type=provider.provider_type,
            name=provider.name,
            base_url=provider.base_url,
            timeout=provider.timeout,
            extra_config=provider.extra_config or {},
        )
    )
    return await adapter.test_connection(api_key)


def delete_provider(db: Session, org_id: str, provider_id: str):
    provider = db.query(LLMProvider).filter(
        LLMProvider.id == provider_id,
        LLMProvider.organization_id == org_id,
    ).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    db.delete(provider)
    db.commit()


def create_agent_mapping(db: Session, org_id: str, data: AgentMappingCreate) -> AgentMappingResponse:
    provider = db.query(LLMProvider).filter(
        LLMProvider.id == data.provider_id,
        LLMProvider.organization_id == org_id,
    ).first()
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


def replace_agent_mappings(
    db: Session,
    org_id: str,
    mappings: list[AgentMappingCreate],
) -> list[AgentMappingResponse]:
    """Replace all agent mappings for an org atomically.

    Validates every provider_id belongs to the org before deleting/inserting.
    Used by the admin agent-mapping page's Save button.
    """
    for m in mappings:
        provider = (
            db.query(LLMProvider)
            .filter(LLMProvider.id == m.provider_id, LLMProvider.organization_id == org_id)
            .first()
        )
        if not provider:
            raise HTTPException(status_code=404, detail=f"Provider {m.provider_id} not found in org")

    db.query(LLMAgentMapping).filter(LLMAgentMapping.organization_id == org_id).delete()

    created = []
    for m in mappings:
        row = LLMAgentMapping(
            organization_id=org_id,
            agent_type=m.agent_type,
            provider_id=m.provider_id,
            model=m.model,
            temperature=m.temperature,
            max_tokens=m.max_tokens,
        )
        db.add(row)
        created.append(row)
    db.commit()
    for row in created:
        db.refresh(row)
    return [AgentMappingResponse.model_validate(m) for m in created]


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
        extra_config=provider.extra_config,
    )
