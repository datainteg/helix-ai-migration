"""Connector API — test, discover, manage connections."""

from fastapi import APIRouter, Depends
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
from app.services.auth_service import get_current_user

router = APIRouter(tags=["connectors"])


class TestConnectionRequest(BaseModel):
    connector_type: str
    config: dict


class DiscoveryRequest(BaseModel):
    connector_type: str
    config: dict
    schema_name: str = "public"
    table_name: str = ""


@router.post("/connectors/test")
async def api_test_connection(data: TestConnectionRequest, user_id: str = Depends(get_current_user_id)):
    result = await test_connection(data.connector_type, data.config)
    return {"success": result.success, "message": result.message}


@router.get("/connectors/registry")
def api_connector_registry(user_id: str = Depends(get_current_user_id)):
    return list_connector_registry()


@router.post("/connectors/discover/schemas")
async def api_discover_schemas(data: DiscoveryRequest, user_id: str = Depends(get_current_user_id)):
    result = await discover_schemas(data.connector_type, data.config)
    return [{"schema_name": s.schema_name} for s in result]


@router.post("/connectors/discover/tables")
async def api_discover_tables(data: DiscoveryRequest, user_id: str = Depends(get_current_user_id)):
    result = await discover_tables(data.connector_type, data.config, data.schema_name)
    return [{"schema_name": t.schema_name, "table_name": t.table_name, "table_type": t.table_type} for t in result]


@router.post("/connectors/discover/columns")
async def api_discover_columns(data: DiscoveryRequest, user_id: str = Depends(get_current_user_id)):
    result = await discover_columns(data.connector_type, data.config, data.schema_name, data.table_name)
    return [{"column_name": c.column_name, "data_type": c.data_type, "is_nullable": c.is_nullable} for c in result]


@router.post("/connectors/row-count")
async def api_get_row_count(data: DiscoveryRequest, user_id: str = Depends(get_current_user_id)):
    result = await get_row_count(data.connector_type, data.config, data.schema_name, data.table_name)
    return {"schema_name": result.schema_name, "table_name": result.table_name, "row_count": result.row_count}
