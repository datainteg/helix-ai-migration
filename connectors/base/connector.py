"""Connector framework — abstract base class and type definitions."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, TypeVar


class ConnectorType(str, Enum):
    POSTGRES = "postgres"
    MYSQL = "mysql"
    SQLSERVER = "sqlserver"
    SNOWFLAKE = "snowflake"
    S3 = "s3"
    CSV_UPLOAD = "csv_upload"
    EXCEL_UPLOAD = "excel_upload"
    CUSTOM = "custom"


@dataclass
class ConnectorCapabilities:
    test_connection: bool = True
    schema_discovery: bool = True
    table_discovery: bool = True
    column_discovery: bool = True
    row_count: bool = True
    file_listing: bool = False
    file_schema_inference: bool = False
    table_profile: bool = False
    supports_recon: bool = True
    requires_file_upload: bool = False

    def to_dict(self) -> dict[str, bool]:
        return {
            "test_connection": self.test_connection,
            "schema_discovery": self.schema_discovery,
            "table_discovery": self.table_discovery,
            "column_discovery": self.column_discovery,
            "row_count": self.row_count,
            "file_listing": self.file_listing,
            "file_schema_inference": self.file_schema_inference,
            "table_profile": self.table_profile,
            "supports_recon": self.supports_recon,
            "requires_file_upload": self.requires_file_upload,
        }


@dataclass
class ConnectionConfig:
    connector_type: ConnectorType
    name: str
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConnectorTestResult:
    success: bool
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class SchemaInfo:
    schema_name: str
    connector_type: str


@dataclass
class TableInfo:
    schema_name: str
    table_name: str
    table_type: str = "TABLE"
    row_count: int | None = None


@dataclass
class ColumnInfo:
    schema_name: str
    table_name: str
    column_name: str
    data_type: str
    is_nullable: bool = True
    ordinal_position: int = 0


@dataclass
class RowCountResult:
    schema_name: str
    table_name: str
    row_count: int


@dataclass
class TableProfileResult:
    schema_name: str
    table_name: str
    row_count: int
    column_count: int
    columns: list[ColumnInfo] = field(default_factory=list)


@dataclass
class FileInfo:
    file_name: str
    file_path: str
    size_bytes: int
    content_hash: str | None = None


@dataclass
class FileSchemaInfo:
    file_name: str
    columns: list[ColumnInfo] = field(default_factory=list)
    row_count: int = 0
    sheet_name: str | None = None


class BaseConnector(ABC):
    """Abstract base for all Helix connectors."""

    connector_type: ConnectorType
    display_name: str = "Base Connector"
    capabilities: ConnectorCapabilities = field(default_factory=ConnectorCapabilities)

    def __init__(self, config: dict[str, Any]):
        self.config = config

    @abstractmethod
    async def test_connection(self) -> ConnectorTestResult:
        """Test connectivity to the source/target system."""

    @abstractmethod
    async def list_schemas(self) -> list[SchemaInfo]:
        """List available schemas/databases."""

    @abstractmethod
    async def list_tables(self, schema_name: str) -> list[TableInfo]:
        """List tables in a schema."""

    @abstractmethod
    async def list_columns(self, schema_name: str, table_name: str) -> list[ColumnInfo]:
        """List columns in a table."""

    @abstractmethod
    async def get_row_count(self, schema_name: str, table_name: str) -> RowCountResult:
        """Get row count for a table."""

    def get_capabilities(self) -> dict[str, bool]:
        return self.capabilities.to_dict()

    @staticmethod
    async def _run_sync(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Run a blocking callable in the default thread pool.

        Used by sync-DB connectors (psycopg2, pymysql, pyodbc, snowflake.connector)
        to avoid blocking the event loop. SQLAlchemy core/pool calls return after
        the thread completes; the awaiting coroutine remains schedulable.
        """
        return await asyncio.to_thread(fn, *args, **kwargs)
