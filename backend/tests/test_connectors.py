"""Tests for connector framework and recon service."""

import pytest
from connectors.base.connector import ConnectorCapabilities, ConnectorType
from connectors.base.identifiers import validate_identifier
from connectors.base.exceptions import InvalidIdentifierError
from connectors.custom.registry import register_connector, list_registered_connectors
from backend.app.services.connector_service import (
    BUILTIN_CONNECTORS,
    list_connector_registry,
)


class TestConnectorBase:
    def test_connector_type_enum_has_all_types(self):
        assert ConnectorType.POSTGRES == "postgres"
        assert ConnectorType.MYSQL == "mysql"
        assert ConnectorType.CSV_UPLOAD == "csv_upload"
        assert ConnectorType.EXCEL_UPLOAD == "excel_upload"
        assert ConnectorType.CUSTOM == "custom"

    def test_connector_capabilities_to_dict(self):
        caps = ConnectorCapabilities(test_connection=True, row_count=True, file_listing=False)
        d = caps.to_dict()
        assert d["test_connection"] is True
        assert d["row_count"] is True
        assert d["file_listing"] is False

    def test_builtin_connectors_registered(self):
        assert ConnectorType.POSTGRES in BUILTIN_CONNECTORS
        assert ConnectorType.MYSQL in BUILTIN_CONNECTORS
        assert ConnectorType.CSV_UPLOAD in BUILTIN_CONNECTORS
        assert ConnectorType.EXCEL_UPLOAD in BUILTIN_CONNECTORS

    def test_registry_lists_all_connectors(self):
        registry = list_connector_registry()
        types = [r["connector_type"] for r in registry]
        assert "postgres" in types
        assert "csv_upload" in types
        assert "excel_upload" in types


class TestIdentifierValidation:
    def test_valid_identifier_passes(self):
        assert validate_identifier("my_table") == "my_table"
        assert validate_identifier("_private") == "_private"
        assert validate_identifier("TableName123") == "TableName123"

    def test_invalid_identifier_raises(self):
        with pytest.raises(InvalidIdentifierError):
            validate_identifier("drop table")
        with pytest.raises(InvalidIdentifierError):
            validate_identifier("1invalid")
        with pytest.raises(InvalidIdentifierError):
            validate_identifier("table; select")

    def test_empty_identifier_raises(self):
        with pytest.raises(InvalidIdentifierError):
            validate_identifier("")
        with pytest.raises(InvalidIdentifierError):
            validate_identifier(None)


class TestCustomRegistry:
    def test_register_and_list(self):
        from connectors.base.connector import BaseConnector, ConnectorTestResult, SchemaInfo, TableInfo, ColumnInfo, RowCountResult

        class SampleConnector(BaseConnector):
            connector_type = ConnectorType.CUSTOM
            display_name = "Sample Custom"

            async def test_connection(self): return ConnectorTestResult(True, "ok")
            async def list_schemas(self): return []
            async def list_tables(self, s): return []
            async def list_columns(self, s, t): return []
            async def get_row_count(self, s, t): return RowCountResult(s, t, 0)

        # Register using a unique key to avoid collision
        register_connector("test_sample_v1", SampleConnector)
        registered = list_registered_connectors()
        assert "test_sample_v1" in registered


class TestPostgresConnector:
    def test_builds_with_config(self):
        from connectors.postgres.connector import PostgreSQLConnector

        conn = PostgreSQLConnector({"host": "localhost", "database": "test"})
        assert conn.connector_type == ConnectorType.POSTGRES
        assert conn.display_name == "PostgreSQL"
        assert conn.capabilities.supports_recon is True

    @pytest.mark.asyncio
    async def test_test_connection_mocked_fails_gracefully(self):
        from connectors.postgres.connector import PostgreSQLConnector

        conn = PostgreSQLConnector({"host": "invalid-host", "database": "test"})
        result = await conn.test_connection()
        assert result.success is False
        assert "Connection failed" in result.message or "could not translate" in result.message


class TestCSVConnector:
    def test_builds_with_path_config(self, tmp_path):
        from connectors.files.csv_connector import CSVConnector

        csv_file = tmp_path / "test.csv"
        csv_file.write_text("name,age\nAlice,30\nBob,25")

        conn = CSVConnector({"storage_path": str(csv_file)})
        assert conn.connector_type == ConnectorType.CSV_UPLOAD
        assert conn.capabilities.requires_file_upload is True

    @pytest.mark.asyncio
    async def test_test_connection_with_valid_csv(self, tmp_path):
        from connectors.files.csv_connector import CSVConnector

        csv_file = tmp_path / "data.csv"
        csv_file.write_text("col1,col2\n1,2")

        conn = CSVConnector({"storage_path": str(csv_file)})
        result = await conn.test_connection()
        assert result.success is True

    @pytest.mark.asyncio
    async def test_get_row_count(self, tmp_path):
        from connectors.files.csv_connector import CSVConnector

        csv_file = tmp_path / "data.csv"
        csv_file.write_text("a,b\n1,2\n3,4\n5,6")

        conn = CSVConnector({"storage_path": str(csv_file)})
        result = await conn.get_row_count("default", "data")
        assert result.row_count == 3


class TestExcelConnector:
    @pytest.mark.asyncio
    async def test_test_connection_with_valid_xlsx(self, tmp_path):
        import pandas as pd

        from connectors.files.excel_connector import ExcelConnector

        xlsx_file = tmp_path / "data.xlsx"
        pd.DataFrame({"col1": [1, 2], "col2": [3, 4]}).to_excel(xlsx_file, index=False)

        conn = ExcelConnector({"storage_path": str(xlsx_file)})
        result = await conn.test_connection()
        assert result.success is True


class TestConnectorAPIClient:
    def test_registry_endpoint_returns_connectors(self, client):
        client.post("/api/v1/auth/first-admin", json={
            "email": "conn@t.com", "name": "C", "password": "TestPass123!",
            "organization_name": "O", "organization_slug": "o",
        })
        login = client.post("/api/v1/auth/login", json={"email": "conn@t.com", "password": "TestPass123!"})
        token = login.json()["access_token"]
        h = {"Authorization": f"Bearer {token}"}

        resp = client.get("/api/v1/connectors/registry", headers=h)
        assert resp.status_code == 200
        registry = resp.json()
        assert len(registry) >= 7

    def test_test_connection_endpoint(self, client):
        client.post("/api/v1/auth/first-admin", json={
            "email": "tc@t.com", "name": "T", "password": "TestPass123!",
            "organization_name": "O", "organization_slug": "o",
        })
        login = client.post("/api/v1/auth/login", json={"email": "tc@t.com", "password": "TestPass123!"})
        token = login.json()["access_token"]
        h = {"Authorization": f"Bearer {token}"}

        project = client.post("/api/v1/projects", json={"name": "ConnTest"}, headers=h)
        project_id = project.json()["id"]

        resp = client.post("/api/v1/connectors/test", json={
            "project_id": project_id,
            "connector_type": "postgres",
            "config": {"host": "localhost", "database": "test"},
        }, headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert "success" in data
        assert "message" in data
