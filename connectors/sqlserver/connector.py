"""SQL Server connector skeleton."""

from connectors.base.connector import BaseConnector, ConnectorCapabilities, ConnectorTestResult, ConnectorType, RowCountResult, SchemaInfo, TableInfo, ColumnInfo

class SQLServerConnector(BaseConnector):
    connector_type = ConnectorType.SQLSERVER
    display_name = "SQL Server"
    capabilities = ConnectorCapabilities(table_profile=True)

    async def test_connection(self) -> ConnectorTestResult:
        return ConnectorTestResult(success=False, message="SQL Server connector not yet implemented")

    async def list_schemas(self) -> list[SchemaInfo]: return []
    async def list_tables(self, schema_name: str) -> list[TableInfo]: return []
    async def list_columns(self, schema_name: str, table_name: str) -> list[ColumnInfo]: return []
    async def get_row_count(self, schema_name: str, table_name: str) -> RowCountResult:
        return RowCountResult(schema_name=schema_name, table_name=table_name, row_count=0)
