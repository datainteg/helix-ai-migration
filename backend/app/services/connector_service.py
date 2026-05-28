"""Connector service — unified interface for all Helix connectors."""

from __future__ import annotations

import logging
from typing import Any

from connectors.base.connector import (
    BaseConnector,
    ConnectorTestResult,
    ConnectorType,
    RowCountResult,
    SchemaInfo,
    TableInfo,
    ColumnInfo,
)
from connectors.postgres.connector import PostgreSQLConnector
from connectors.mysql.connector import MySQLConnector
from connectors.sqlserver.connector import SQLServerConnector
from connectors.snowflake.connector import SnowflakeConnector
from connectors.s3.connector import S3Connector
from connectors.files.csv_connector import CSVConnector
from connectors.files.excel_connector import ExcelConnector
from connectors.custom.registry import get_connector as get_custom_connector

logger = logging.getLogger(__name__)

BUILTIN_CONNECTORS: dict[str, type[BaseConnector]] = {
    ConnectorType.POSTGRES: PostgreSQLConnector,
    ConnectorType.MYSQL: MySQLConnector,
    ConnectorType.SQLSERVER: SQLServerConnector,
    ConnectorType.SNOWFLAKE: SnowflakeConnector,
    ConnectorType.S3: S3Connector,
    ConnectorType.CSV_UPLOAD: CSVConnector,
    ConnectorType.EXCEL_UPLOAD: ExcelConnector,
}


def _build_connector(connector_type: str, config: dict[str, Any]) -> BaseConnector:
    """Build a connector instance by type."""
    cls = BUILTIN_CONNECTORS.get(ConnectorType(connector_type))
    if cls is None:
        # Try custom registry
        cls = get_custom_connector(connector_type)
    if cls is None:
        raise ValueError(f"Unknown connector type: {connector_type}")
    return cls(config)


async def test_connection(connector_type: str, config: dict[str, Any]) -> ConnectorTestResult:
    """Test connectivity for any connector type."""
    connector = _build_connector(connector_type, config)
    return await connector.test_connection()


async def discover_schemas(connector_type: str, config: dict[str, Any]) -> list[SchemaInfo]:
    connector = _build_connector(connector_type, config)
    return await connector.list_schemas()


async def discover_tables(connector_type: str, config: dict[str, Any], schema_name: str) -> list[TableInfo]:
    connector = _build_connector(connector_type, config)
    return await connector.list_tables(schema_name)


async def discover_columns(connector_type: str, config: dict[str, Any], schema_name: str, table_name: str) -> list[ColumnInfo]:
    connector = _build_connector(connector_type, config)
    return await connector.list_columns(schema_name, table_name)


async def get_row_count(connector_type: str, config: dict[str, Any], schema_name: str, table_name: str) -> RowCountResult:
    connector = _build_connector(connector_type, config)
    return await connector.get_row_count(schema_name, table_name)


def list_connector_registry() -> list[dict[str, Any]]:
    """List all available connectors (built-in + custom)."""
    registry = []
    for ctype, cls in BUILTIN_CONNECTORS.items():
        registry.append({
            "connector_type": ctype.value,
            "display_name": cls.display_name,
            "capabilities": cls.capabilities.to_dict(),
            "mode": "built_in",
        })
    from connectors.custom.registry import list_registered_connectors
    for ctype, display_name in list_registered_connectors().items():
        # M-007: custom connectors previously reported `capabilities={}`, which
        # greyed out every action button in the marketplace UI. Derive the real
        # capabilities from the registered class (every connector subclasses
        # BaseConnector and declares a `capabilities` attribute). Fall back to
        # {} only if the class is missing or doesn't declare them.
        cls = get_custom_connector(ctype)
        caps = {}
        if cls is not None:
            class_caps = getattr(cls, "capabilities", None)
            if class_caps is not None:
                caps = class_caps.to_dict() if hasattr(class_caps, "to_dict") else dict(class_caps)
        registry.append({
            "connector_type": ctype,
            "display_name": display_name,
            "capabilities": caps,
            "mode": "custom",
        })
    return registry
