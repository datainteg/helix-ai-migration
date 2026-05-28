"""Extended connector tests — covers the 4 connectors not in test_connectors.py:
MySQL, SQL Server, Snowflake, S3. Plus custom-registry lifecycle.

Tests are mocked — they do NOT require real databases. Integration tests
against real DBs are skipped unless the corresponding HELIX_TEST_* env var
is set (see the bottom of this file).
"""

from __future__ import annotations

import os

import pytest

from connectors.base.connector import ConnectorType


# ── MySQL ────────────────────────────────────────────────────────────


class TestMySQLConnector:
    def test_builds_with_config(self):
        from connectors.mysql.connector import MySQLConnector

        conn = MySQLConnector({"host": "localhost", "database": "test", "username": "u", "password": "p"})
        assert conn.connector_type == ConnectorType.MYSQL
        assert conn.display_name == "MySQL"
        assert conn.capabilities.test_connection is True

    @pytest.mark.asyncio
    async def test_test_connection_fails_gracefully_on_bad_host(self):
        from connectors.mysql.connector import MySQLConnector

        conn = MySQLConnector({
            "host": "does-not-exist.invalid",
            "database": "test",
            "username": "x",
            "password": "y",
        })
        result = await conn.test_connection()
        assert result.success is False
        # Must be a graceful failure, not a thrown exception.
        assert isinstance(result.message, str) and len(result.message) > 0


# ── SQL Server ───────────────────────────────────────────────────────


class TestSQLServerConnector:
    def test_builds_with_config(self):
        from connectors.sqlserver.connector import SQLServerConnector

        conn = SQLServerConnector({
            "host": "localhost",
            "database": "test",
            "username": "sa",
            "password": "p",
        })
        assert conn.connector_type == ConnectorType.SQLSERVER
        assert conn.display_name == "SQL Server"

    @pytest.mark.asyncio
    async def test_test_connection_fails_gracefully_on_bad_host(self):
        from connectors.sqlserver.connector import SQLServerConnector

        conn = SQLServerConnector({
            "host": "does-not-exist.invalid",
            "database": "test",
            "username": "sa",
            "password": "x",
        })
        result = await conn.test_connection()
        assert result.success is False
        assert isinstance(result.message, str)


# ── Snowflake ────────────────────────────────────────────────────────


class TestSnowflakeConnector:
    def test_builds_with_config(self):
        from connectors.snowflake.connector import SnowflakeConnector

        conn = SnowflakeConnector({
            "account": "abc12345.us-east-1",
            "username": "user",
            "password": "pw",
            "warehouse": "COMPUTE_WH",
            "database": "DEMO",
        })
        assert conn.connector_type == ConnectorType.SNOWFLAKE
        assert conn.display_name == "Snowflake"

    @pytest.mark.asyncio
    async def test_test_connection_fails_gracefully_on_bad_account(self):
        from connectors.snowflake.connector import SnowflakeConnector

        conn = SnowflakeConnector({
            "account": "does-not-exist.invalid",
            "username": "u",
            "password": "p",
            "warehouse": "X",
            "database": "Y",
        })
        result = await conn.test_connection()
        assert result.success is False


# ── S3 ───────────────────────────────────────────────────────────────


class TestS3Connector:
    def test_builds_with_config(self):
        from connectors.s3.connector import S3Connector

        conn = S3Connector({
            "bucket": "my-bucket",
            "region": "us-east-1",
            "access_key_id": "AKIAEXAMPLE",
            "secret_access_key": "secret",
        })
        assert conn.connector_type == ConnectorType.S3
        assert conn.display_name == "Amazon S3"
        # S3 should report file_listing capability.
        assert conn.capabilities.file_listing is True
        # Recon not supported (object storage, not tabular).
        assert conn.capabilities.supports_recon is False

    @pytest.mark.asyncio
    async def test_test_connection_fails_gracefully_with_bad_creds(self):
        from connectors.s3.connector import S3Connector

        conn = S3Connector({
            "bucket": "definitely-not-a-real-bucket-xyz-987654321",
            "region": "us-east-1",
            "access_key_id": "AKIABAD",
            "secret_access_key": "bad",
        })
        result = await conn.test_connection()
        # Either success=False (auth rejected) or graceful error message.
        assert isinstance(result.message, str)


# ── Custom connector — full lifecycle ────────────────────────────────


class TestCustomConnectorLifecycle:
    def test_register_lookup_instantiate(self):
        from connectors.base.connector import (
            BaseConnector,
            ColumnInfo,
            ConnectorTestResult,
            RowCountResult,
            SchemaInfo,
            TableInfo,
        )
        from connectors.custom.registry import get_connector, register_connector

        class DemoCustom(BaseConnector):
            connector_type = ConnectorType.CUSTOM
            display_name = "Demo Custom"

            async def test_connection(self):
                return ConnectorTestResult(True, "demo always OK")

            async def list_schemas(self):
                return [SchemaInfo(schema_name="default", connector_type="demo")]

            async def list_tables(self, schema_name):
                return [TableInfo(schema_name=schema_name, table_name="things")]

            async def list_columns(self, schema_name, table_name):
                return [ColumnInfo(
                    schema_name=schema_name, table_name=table_name,
                    column_name="id", data_type="integer",
                )]

            async def get_row_count(self, schema_name, table_name):
                return RowCountResult(schema_name, table_name, 42)

        register_connector("test_demo_v2", DemoCustom)
        cls = get_connector("test_demo_v2")
        assert cls is DemoCustom

        instance = cls({"any": "config"})
        assert instance.config == {"any": "config"}

    @pytest.mark.asyncio
    async def test_custom_connector_returns_data_through_interface(self):
        from connectors.base.connector import (
            BaseConnector,
            ConnectorTestResult,
            RowCountResult,
            SchemaInfo,
        )
        from connectors.custom.registry import get_connector, register_connector

        class FixedCustom(BaseConnector):
            connector_type = ConnectorType.CUSTOM
            display_name = "Fixed Custom"

            async def test_connection(self):
                return ConnectorTestResult(True, "ok")

            async def list_schemas(self):
                return [SchemaInfo(schema_name="s1", connector_type="custom")]

            async def list_tables(self, schema_name):
                return []

            async def list_columns(self, schema_name, table_name):
                return []

            async def get_row_count(self, schema_name, table_name):
                return RowCountResult(schema_name, table_name, 7)

        register_connector("test_fixed_v2", FixedCustom)
        inst = get_connector("test_fixed_v2")({})

        result = await inst.test_connection()
        assert result.success is True

        schemas = await inst.list_schemas()
        assert schemas[0].schema_name == "s1"

        count = await inst.get_row_count("s1", "t1")
        assert count.row_count == 7


# ── API: discover endpoints ──────────────────────────────────────────


class TestConnectorDiscoverAPI:
    def _bootstrap(self, client):
        client.post("/api/v1/auth/first-admin", json={
            "email": "d@t.com", "name": "D", "password": "TestPass123!",
            "organization_name": "O", "organization_slug": "do",
        })
        login = client.post("/api/v1/auth/login", json={"email": "d@t.com", "password": "TestPass123!"})
        return {"Authorization": f"Bearer {login.json()['access_token']}"}

    def test_discover_schemas_endpoint_exists(self, client):
        from unittest.mock import patch

        h = self._bootstrap(client)
        from app.services import connector_service as svc

        class FakeSchema:
            schema_name = "public"

        async def fake_discover(connector_type, config):
            return [FakeSchema()]

        with patch.object(svc, "discover_schemas", new=fake_discover):
            resp = client.post(
                "/api/v1/connectors/discover/schemas",
                json={"connector_type": "postgres", "config": {"host": "x"}},
                headers=h,
            )
        assert resp.status_code == 200
        assert resp.json() == [{"schema_name": "public"}]


# ── Integration markers — skipped unless real DB env vars set ───────


@pytest.mark.skipif(
    not os.getenv("HELIX_TEST_POSTGRES_URL"),
    reason="HELIX_TEST_POSTGRES_URL not set — skipping live Postgres test",
)
@pytest.mark.asyncio
async def test_postgres_live_integration():
    """Live Postgres test. Set HELIX_TEST_POSTGRES_URL=postgresql://user:pw@host:5432/db to enable."""
    from urllib.parse import urlparse

    from connectors.postgres.connector import PostgreSQLConnector

    parsed = urlparse(os.environ["HELIX_TEST_POSTGRES_URL"])
    conn = PostgreSQLConnector({
        "host": parsed.hostname,
        "port": parsed.port or 5432,
        "database": parsed.path.lstrip("/"),
        "username": parsed.username,
        "password": parsed.password,
    })
    result = await conn.test_connection()
    assert result.success is True


@pytest.mark.skipif(
    not os.getenv("HELIX_TEST_MYSQL_URL"),
    reason="HELIX_TEST_MYSQL_URL not set — skipping live MySQL test",
)
@pytest.mark.asyncio
async def test_mysql_live_integration():
    """Live MySQL test. Set HELIX_TEST_MYSQL_URL=mysql://user:pw@host:3306/db to enable."""
    from urllib.parse import urlparse

    from connectors.mysql.connector import MySQLConnector

    parsed = urlparse(os.environ["HELIX_TEST_MYSQL_URL"])
    conn = MySQLConnector({
        "host": parsed.hostname,
        "port": parsed.port or 3306,
        "database": parsed.path.lstrip("/"),
        "username": parsed.username,
        "password": parsed.password,
    })
    result = await conn.test_connection()
    assert result.success is True
