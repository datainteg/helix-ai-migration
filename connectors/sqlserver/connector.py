"""SQL Server connector — functional implementation using pyodbc."""

from __future__ import annotations

import logging
from urllib.parse import quote_plus

from connectors.base.connector import (
    BaseConnector, ColumnInfo, ConnectorCapabilities, ConnectorTestResult,
    ConnectorType, RowCountResult, SchemaInfo, TableInfo,
)
from connectors.base.exceptions import DiscoveryError
from connectors.base.identifiers import validate_identifier

logger = logging.getLogger(__name__)


class SQLServerConnector(BaseConnector):
    connector_type = ConnectorType.SQLSERVER
    display_name = "SQL Server"
    capabilities = ConnectorCapabilities(
        test_connection=True,
        schema_discovery=True,
        table_discovery=True,
        column_discovery=True,
        row_count=True,
        table_profile=True,
        supports_recon=True,
    )

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self._engine = None

    def _build_connection_url(self) -> str:
        cfg = self.config
        host = cfg.get("host", "localhost")
        port = cfg.get("port", 1433)
        database = cfg.get("database", "master")
        username = cfg.get("username", "sa")
        password = cfg.get("password", "")
        driver = cfg.get("driver", "ODBC Driver 18 for SQL Server")
        encrypt = "yes" if cfg.get("encrypt", True) else "no"
        trust_cert = "no" if cfg.get("trust_server_certificate", False) else "no"
        params = f"driver={quote_plus(driver)};Encrypt={encrypt};TrustServerCertificate={trust_cert}"
        return f"mssql+pyodbc://{quote_plus(username)}:{quote_plus(password)}@{host}:{port}/{database}?{params}"

    def _get_engine(self):
        from sqlalchemy import create_engine
        if self._engine is None:
            self._engine = create_engine(
                self._build_connection_url(),
                connect_args={"timeout": 10},
                pool_pre_ping=True,
            )
        return self._engine

    def close(self) -> None:
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None

    async def test_connection(self) -> ConnectorTestResult:
        try:
            from sqlalchemy import text
            with self._get_engine().connect() as conn:
                conn.execute(text("SELECT 1"))
            return ConnectorTestResult(success=True, message="Connected to SQL Server")
        except Exception as exc:
            logger.warning("SQL Server connection test failed: %s", exc)
            return ConnectorTestResult(success=False, message=f"Connection failed: {exc}")

    async def list_schemas(self) -> list[SchemaInfo]:
        try:
            from sqlalchemy import text
            with self._get_engine().connect() as conn:
                rows = conn.execute(text("SELECT name FROM sys.schemas ORDER BY name"))
                return [SchemaInfo(schema_name=r[0], connector_type="sqlserver") for r in rows]
        except Exception as exc:
            raise DiscoveryError(f"Schema discovery failed: {exc}", "sqlserver") from exc

    async def list_tables(self, schema_name: str) -> list[TableInfo]:
        validate_identifier(schema_name, "schema_name")
        try:
            from sqlalchemy import text
            with self._get_engine().connect() as conn:
                rows = conn.execute(
                    text(
                        "SELECT TABLE_NAME, TABLE_TYPE FROM INFORMATION_SCHEMA.TABLES "
                        "WHERE TABLE_SCHEMA = :schema ORDER BY TABLE_NAME"
                    ),
                    {"schema": schema_name},
                )
                return [
                    TableInfo(schema_name=schema_name, table_name=r[0], table_type=r[1] or "BASE TABLE")
                    for r in rows
                ]
        except Exception as exc:
            raise DiscoveryError(f"Table discovery failed: {exc}", "sqlserver") from exc

    async def list_columns(self, schema_name: str, table_name: str) -> list[ColumnInfo]:
        validate_identifier(schema_name, "schema_name")
        validate_identifier(table_name, "table_name")
        try:
            from sqlalchemy import text
            with self._get_engine().connect() as conn:
                rows = conn.execute(
                    text(
                        "SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, ORDINAL_POSITION "
                        "FROM INFORMATION_SCHEMA.COLUMNS "
                        "WHERE TABLE_SCHEMA = :schema AND TABLE_NAME = :table "
                        "ORDER BY ORDINAL_POSITION"
                    ),
                    {"schema": schema_name, "table": table_name},
                )
                return [
                    ColumnInfo(
                        schema_name=schema_name, table_name=table_name,
                        column_name=r[0], data_type=r[1],
                        is_nullable=r[2] == "YES", ordinal_position=r[3],
                    )
                    for r in rows
                ]
        except Exception as exc:
            raise DiscoveryError(f"Column discovery failed: {exc}", "sqlserver") from exc

    async def get_row_count(self, schema_name: str, table_name: str) -> RowCountResult:
        validate_identifier(schema_name, "schema_name")
        validate_identifier(table_name, "table_name")
        try:
            from sqlalchemy import text
            with self._get_engine().connect() as conn:
                result = conn.execute(
                    text(f"SELECT COUNT(*) FROM [{schema_name}].[{table_name}]")
                )
                return RowCountResult(schema_name=schema_name, table_name=table_name, row_count=result.scalar())
        except Exception as exc:
            raise DiscoveryError(f"Row count failed: {exc}", "sqlserver") from exc
