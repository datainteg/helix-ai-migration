"""PostgreSQL connector — functional MVP implementation."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote_plus

from connectors.base.connector import (
    BaseConnector,
    ColumnInfo,
    ConnectorCapabilities,
    ConnectorTestResult,
    ConnectorType,
    RowCountResult,
    SchemaInfo,
    TableInfo,
)
from connectors.base.exceptions import ConnectionFailedError, DiscoveryError
from connectors.base.identifiers import validate_identifier

logger = logging.getLogger(__name__)


class PostgreSQLConnector(BaseConnector):
    connector_type = ConnectorType.POSTGRES
    display_name = "PostgreSQL"
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
        """Build SQLAlchemy connection URL. Never logs password."""
        cfg = self.config
        host = cfg.get("host", "localhost")
        port = cfg.get("port", 5432)
        database = cfg.get("database", "postgres")
        username = cfg.get("username", "postgres")
        password = cfg.get("password", "")
        ssl_mode = cfg.get("ssl_mode", "prefer")
        return f"postgresql://{quote_plus(username)}:{quote_plus(password)}@{host}:{port}/{database}?sslmode={ssl_mode}"

    def _get_engine(self):
        """Lazy-init shared engine. Avoids per-call connection overhead."""
        from sqlalchemy import create_engine
        if self._engine is None:
            self._engine = create_engine(
                self._build_connection_url(),
                connect_args={"connect_timeout": 10},
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
            return ConnectorTestResult(success=True, message="Connected to PostgreSQL")
        except Exception as exc:
            logger.warning("PostgreSQL connection test failed: %s", exc)
            return ConnectorTestResult(success=False, message=f"Connection failed: {exc}")

    async def list_schemas(self) -> list[SchemaInfo]:
        try:
            from sqlalchemy import text
            with self._get_engine().connect() as conn:
                rows = conn.execute(
                    text("SELECT schema_name FROM information_schema.schemata ORDER BY schema_name")
                )
                return [SchemaInfo(schema_name=r[0], connector_type="postgres") for r in rows]
        except Exception as exc:
            raise DiscoveryError(f"Schema discovery failed: {exc}", "postgres") from exc

    async def list_tables(self, schema_name: str) -> list[TableInfo]:
        validate_identifier(schema_name, "schema_name")
        try:
            from sqlalchemy import text
            with self._get_engine().connect() as conn:
                rows = conn.execute(
                    text(
                        "SELECT table_name, table_type FROM information_schema.tables "
                        "WHERE table_schema = :schema ORDER BY table_name"
                    ),
                    {"schema": schema_name},
                )
                return [
                    TableInfo(schema_name=schema_name, table_name=r[0], table_type=r[1] or "TABLE")
                    for r in rows
                ]
        except Exception as exc:
            raise DiscoveryError(f"Table discovery failed: {exc}", "postgres") from exc

    async def list_columns(self, schema_name: str, table_name: str) -> list[ColumnInfo]:
        validate_identifier(schema_name, "schema_name")
        validate_identifier(table_name, "table_name")
        try:
            from sqlalchemy import text
            with self._get_engine().connect() as conn:
                rows = conn.execute(
                    text(
                        "SELECT column_name, data_type, is_nullable, ordinal_position "
                        "FROM information_schema.columns "
                        "WHERE table_schema = :schema AND table_name = :table "
                        "ORDER BY ordinal_position"
                    ),
                    {"schema": schema_name, "table": table_name},
                )
                return [
                    ColumnInfo(
                        schema_name=schema_name,
                        table_name=table_name,
                        column_name=r[0],
                        data_type=r[1],
                        is_nullable=r[2] == "YES",
                        ordinal_position=r[3],
                    )
                    for r in rows
                ]
        except Exception as exc:
            raise DiscoveryError(f"Column discovery failed: {exc}", "postgres") from exc

    async def get_row_count(self, schema_name: str, table_name: str) -> RowCountResult:
        validate_identifier(schema_name, "schema_name")
        validate_identifier(table_name, "table_name")
        try:
            from sqlalchemy import text
            with self._get_engine().connect() as conn:
                result = conn.execute(
                    text(f'SELECT COUNT(*) FROM "{schema_name}"."{table_name}"')
                )
                count = result.scalar()
                return RowCountResult(
                    schema_name=schema_name,
                    table_name=table_name,
                    row_count=count,
                )
        except Exception as exc:
            raise DiscoveryError(f"Row count failed: {exc}", "postgres") from exc

    async def get_null_count(self, schema_name: str, table_name: str, column_name: str) -> int:
        """Count NULL values in a column. Used by validation engine."""
        validate_identifier(schema_name, "schema_name")
        validate_identifier(table_name, "table_name")
        validate_identifier(column_name, "column_name")
        try:
            from sqlalchemy import text
            with self._get_engine().connect() as conn:
                result = conn.execute(
                    text(f'SELECT COUNT(*) FROM "{schema_name}"."{table_name}" WHERE "{column_name}" IS NULL')
                )
                return result.scalar() or 0
        except Exception as exc:
            raise DiscoveryError(f"Null count failed: {exc}", "postgres") from exc
