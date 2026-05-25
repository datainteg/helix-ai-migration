"""Connector API — test, discover, manage connections."""

import ipaddress
import os
import socket

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.auth.jwt import get_current_user_id
from app.auth.dependencies import get_current_organization_id
from app.services.connector_service import (
    test_connection,
    discover_schemas,
    discover_tables,
    discover_columns,
    get_row_count,
    list_connector_registry,
)
from app.services.project_service import ensure_project_access
from app.api.audit import write_audit
from app.rate_limiting import limiter

router = APIRouter(tags=["connectors"])


class TestConnectionRequest(BaseModel):
    project_id: str
    connector_type: str
    config: dict


class DiscoveryRequest(BaseModel):
    project_id: str            # discovery now requires project context (SSRF guard)
    connector_type: str
    config: dict
    schema_name: str = "public"
    table_name: str = ""


def _safe_config(config: dict) -> dict:
    """Strip password from config before storing in audit log."""
    return {k: v for k, v in config.items() if k not in ("password", "secret", "token", "api_key")}


# ── SSRF guard ──────────────────────────────────────────────────────
# Any user can paste an arbitrary `host` into a connector config; without a
# filter that lets a logged-in tenant probe internal network ranges, cloud
# metadata IPs (IMDS), and localhost services. Block by default; operators
# who legitimately need to reach private hosts (self-hosted Postgres on
# the same VPC) set HELIX_ALLOW_PRIVATE_HOSTS=1.

_ALLOW_PRIVATE = os.environ.get("HELIX_ALLOW_PRIVATE_HOSTS", "").lower() in {"1", "true", "yes"}
_BLOCK_HOST_KEYS = ("host", "hostname", "server", "endpoint", "endpoint_url", "url", "base_url")
_BLOCK_IPS = {"169.254.169.254", "169.254.170.2"}  # AWS + ECS task metadata


def _resolve_host(value: str) -> list[str]:
    """Return all IPs a host string resolves to. Best-effort; empty on failure."""
    if not value:
        return []
    # Strip URL scheme / port / path so we can resolve the host alone.
    s = value.strip()
    for prefix in ("https://", "http://", "tcp://", "postgres://", "postgresql://", "mysql://"):
        if s.startswith(prefix):
            s = s[len(prefix):]
            break
    s = s.split("/")[0].split("@")[-1]
    if ":" in s:
        s = s.split(":")[0]
    try:
        return [ai[4][0] for ai in socket.getaddrinfo(s, None)]
    except Exception:  # noqa: BLE001
        return []


def _is_blocked(ip: str) -> bool:
    if ip in _BLOCK_IPS:
        return True
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved


def _enforce_host_allowlist(config: dict) -> None:
    """Raise 400 if the config points at an internal / metadata address."""
    if _ALLOW_PRIVATE:
        return
    for key in _BLOCK_HOST_KEYS:
        if key not in config:
            continue
        for ip in _resolve_host(str(config[key])):
            if _is_blocked(ip):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Connector config '{key}' resolves to a restricted address ({ip}). "
                        "Set HELIX_ALLOW_PRIVATE_HOSTS=1 on the backend if this is intentional."
                    ),
                )


@router.post("/connectors/test")
@limiter.limit("20/minute")
async def api_test_connection(
    request: Request,
    data: TestConnectionRequest,
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    ensure_project_access(db, org_id, data.project_id)
    _enforce_host_allowlist(data.config)
    result = await test_connection(data.connector_type, data.config)
    write_audit(
        db, org_id, user_id,
        "connector_tested",
        "connector", data.connector_type,
        meta={"success": result.success, "connector_type": data.connector_type, "config": _safe_config(data.config)},
        request=request,
    )
    return {"success": result.success, "message": result.message}


@router.get("/connectors/registry")
def api_connector_registry(user_id: str = Depends(get_current_user_id)):
    return list_connector_registry()


@router.post("/connectors/discover/schemas")
@limiter.limit("30/minute")
async def api_discover_schemas(
    request: Request,
    data: DiscoveryRequest,
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    ensure_project_access(db, org_id, data.project_id)
    _enforce_host_allowlist(data.config)
    result = await discover_schemas(data.connector_type, data.config)
    return [{"schema_name": s.schema_name} for s in result]


@router.post("/connectors/discover/tables")
@limiter.limit("30/minute")
async def api_discover_tables(
    request: Request,
    data: DiscoveryRequest,
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    ensure_project_access(db, org_id, data.project_id)
    _enforce_host_allowlist(data.config)
    result = await discover_tables(data.connector_type, data.config, data.schema_name)
    return [{"schema_name": t.schema_name, "table_name": t.table_name, "table_type": t.table_type} for t in result]


@router.post("/connectors/discover/columns")
@limiter.limit("30/minute")
async def api_discover_columns(
    request: Request,
    data: DiscoveryRequest,
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    ensure_project_access(db, org_id, data.project_id)
    _enforce_host_allowlist(data.config)
    result = await discover_columns(data.connector_type, data.config, data.schema_name, data.table_name)
    return [{"column_name": c.column_name, "data_type": c.data_type, "is_nullable": c.is_nullable} for c in result]


@router.post("/connectors/row-count")
@limiter.limit("30/minute")
async def api_get_row_count(
    request: Request,
    data: DiscoveryRequest,
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    ensure_project_access(db, org_id, data.project_id)
    _enforce_host_allowlist(data.config)
    result = await get_row_count(data.connector_type, data.config, data.schema_name, data.table_name)
    return {"schema_name": result.schema_name, "table_name": result.table_name, "row_count": result.row_count}
