"""CSV file connector — functional MVP using pandas."""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
from typing import Any

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
from connectors.base.exceptions import DiscoveryError

logger = logging.getLogger(__name__)


class CSVConnector(BaseConnector):
    connector_type = ConnectorType.CSV_UPLOAD
    display_name = "CSV Upload"
    capabilities = ConnectorCapabilities(
        test_connection=True,
        schema_discovery=False,
        table_discovery=False,
        column_discovery=False,
        row_count=True,
        file_listing=True,
        file_schema_inference=True,
        table_profile=True,
        supports_recon=True,
        requires_file_upload=True,
    )

    def _resolve_path(self) -> Path:
        path = self.config.get("storage_path", "")
        if not path or not os.path.exists(path):
            raise DiscoveryError(f"CSV file not found: {path}", "csv_upload")
        return Path(path)

    async def test_connection(self) -> ConnectorTestResult:
        try:
            path = self._resolve_path()
            if path.suffix.lower() != ".csv":
                return ConnectorTestResult(success=False, message="File is not a CSV")
            import pandas as pd

            pd.read_csv(path, nrows=1)
            return ConnectorTestResult(success=True, message=f"CSV file accessible: {path.name}")
        except Exception as exc:
            return ConnectorTestResult(success=False, message=f"CSV access failed: {exc}")

    async def list_schemas(self) -> list[SchemaInfo]:
        return [SchemaInfo(schema_name="default", connector_type="csv_upload")]

    async def list_tables(self, schema_name: str) -> list[TableInfo]:
        path = self._resolve_path()
        return [TableInfo(schema_name=schema_name, table_name=path.stem, table_type="FILE")]

    async def list_columns(self, schema_name: str, table_name: str) -> list[ColumnInfo]:
        try:
            import pandas as pd

            path = self._resolve_path()
            df = pd.read_csv(path, nrows=0)
            return [
                ColumnInfo(
                    schema_name=schema_name,
                    table_name=table_name or path.stem,
                    column_name=col,
                    data_type=str(dtype),
                    ordinal_position=idx + 1,
                )
                for idx, (col, dtype) in enumerate(df.dtypes.items())
            ]
        except Exception as exc:
            raise DiscoveryError(f"CSV column inference failed: {exc}", "csv_upload") from exc

    async def get_row_count(self, schema_name: str, table_name: str) -> RowCountResult:
        try:
            path = self._resolve_path()
            # L-006: count rows by streaming lines instead of loading the whole
            # CSV into a pandas DataFrame (which materialises every cell in RAM
            # just to call len()). Subtract one for the header row. This handles
            # arbitrarily large files in constant memory.
            with open(path, "rb") as fh:
                line_count = sum(1 for _ in fh)
            row_count = max(line_count - 1, 0)  # drop the header line
            return RowCountResult(
                schema_name=schema_name,
                table_name=table_name or path.stem,
                row_count=row_count,
            )
        except Exception as exc:
            raise DiscoveryError(f"CSV row count failed: {exc}", "csv_upload") from exc
