from datetime import datetime, timezone
from typing import Any

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


# SEC-010 — keys inside `extra_config` whose VALUES must be encrypted at rest.
# Anything in this set is wrapped as `{"__encrypted": true, "value": <ciphertext>}`
# before the JSON column hits the DB, and unwrapped transparently on read.
# Bedrock / Vertex / Azure store their long-lived credentials here, not in `api_key`.
_SECRET_KEYS = frozenset({
    "aws_secret_access_key",
    "aws_session_token",
    "service_account_json",
    "client_secret",
    "private_key",
    "passphrase",
    "gcp_service_account_json",
    "azure_client_secret",
})

# Sentinel marker — a dict shaped like this is a "this value is encrypted" envelope.
_ENC_FLAG = "__encrypted"


def _is_encrypted_envelope(value: Any) -> bool:
    return isinstance(value, dict) and value.get(_ENC_FLAG) is True and "value" in value


def encrypt_extra_config(extra: dict | None) -> dict | None:
    """Return a copy of `extra_config` with every sensitive value sealed.

    Non-sensitive keys pass through untouched. Already-encrypted envelopes
    are left as-is so re-saving a previously-encrypted row is idempotent.
    Empty/None inputs return as-is.
    """
    if not extra:
        return extra
    out: dict[str, Any] = {}
    for k, v in extra.items():
        if k in _SECRET_KEYS and v is not None and v != "":
            if _is_encrypted_envelope(v):
                # already encrypted (e.g. round-trip via PATCH echoing GET) — leave alone
                out[k] = v
            else:
                # Stringify before encrypt: aws_session_token / service_account_json
                # may be dict-or-str; we serialise dicts to JSON so decryption returns
                # the exact same shape via json.loads on the consumer side.
                import json as _json
                if not isinstance(v, str):
                    plain = _json.dumps(v, sort_keys=True)
                else:
                    plain = v
                out[k] = {_ENC_FLAG: True, "value": encrypt_value(plain)}
        else:
            out[k] = v
    return out


def decrypt_extra_config(extra: dict | None) -> dict | None:
    """Return a copy of `extra_config` with every encrypted envelope opened.

    Used on read paths that need the plaintext — e.g. when constructing a
    `ProviderConnectionConfig` for the adapter, or building a CallContext
    for the LLM transport. NEVER call this when returning the dict to the
    API client (use `_redact_extra_config` instead).
    """
    if not extra:
        return extra
    out: dict[str, Any] = {}
    for k, v in extra.items():
        if k in _SECRET_KEYS and _is_encrypted_envelope(v):
            try:
                plain = decrypt_value(v.get("value", ""))
                # service_account_json may be JSON — try to deserialise, fall back to str
                if k in {"service_account_json", "gcp_service_account_json"}:
                    import json as _json
                    try:
                        out[k] = _json.loads(plain)
                    except Exception:
                        out[k] = plain
                else:
                    out[k] = plain
            except Exception:
                out[k] = ""
        else:
            out[k] = v
    return out


def _redact_extra_config(extra: dict | None) -> dict | None:
    """Mask sensitive values for client-facing responses.

    The presence of the key is preserved (so the UI can show "configured"),
    but the actual ciphertext is replaced with a fixed mask string. Plaintext
    secrets that somehow slip past the encrypt path (legacy unmigrated rows)
    are ALSO masked here as a belt-and-braces defence.
    """
    if not extra:
        return extra
    out: dict[str, Any] = {}
    for k, v in extra.items():
        if k in _SECRET_KEYS and v not in (None, "", {}):
            out[k] = "***"
        else:
            out[k] = v
    return out


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
        extra_config=encrypt_extra_config(data.extra_config),
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
        if field == "extra_config":
            # SEC-010: re-encrypt sensitive keys on every update so PATCH that
            # supplies fresh aws_secret_access_key never lands plaintext.
            setattr(provider, field, encrypt_extra_config(value))
        else:
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
            # SEC-010: decrypt sealed extra_config values before the adapter
            # signs the upstream request — adapters expect plaintext secrets.
            extra_config=decrypt_extra_config(provider.extra_config) or {},
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
        # SEC-010: never echo plaintext (or ciphertext) of sensitive keys
        # back to the API client; the masked sentinel is enough for the UI.
        extra_config=_redact_extra_config(provider.extra_config),
    )
