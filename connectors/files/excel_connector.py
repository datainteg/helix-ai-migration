"""Excel file connector — functional MVP using pandas + openpyxl."""

from __future__ import annotations

import logging
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


class ExcelConnector(BaseConnector):
    connector_type = ConnectorType.EXCEL_UPLOAD
    display_name = "Excel Upload"
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
        import os
        path = self.config.get("storage_path", "")
        if not path or not os.path.exists(path):
            raise DiscoveryError(f"Excel file not found: {path}", "excel_upload")
        return Path(path)

    async def test_connection(self) -> ConnectorTestResult:
        try:
            path = self._resolve_path()
            if path.suffix.lower() not in (".xlsx", ".xls"):
                return ConnectorTestResult(success=False, message="File is not an Excel file")
            import pandas as pd

            sheet = self.config.get("sheet_name", 0)
            pd.read_excel(path, sheet_name=sheet, nrows=1)
            return ConnectorTestResult(success=True, message=f"Excel file accessible: {path.name}")
        except Exception as exc:
            return ConnectorTestResult(success=False, message=f"Excel access failed: {exc}")

    async def list_schemas(self) -> list[SchemaInfo]:
        path = self._resolve_path()
        import pandas as pd

        xl = pd.ExcelFile(path)
        return [SchemaInfo(schema_name=s, connector_type="excel_upload") for s in xl.sheet_names]

    async def list_tables(self, schema_name: str) -> list[TableInfo]:
        return [TableInfo(schema_name=schema_name, table_name=schema_name, table_type="SHEET")]

    async def list_columns(self, schema_name: str, table_name: str) -> list[ColumnInfo]:
        try:
            import pandas as pd

            path = self._resolve_path()
            sheet = schema_name or 0
            df = pd.read_excel(path, sheet_name=sheet, nrows=0)
            return [
                ColumnInfo(
                    schema_name=schema_name,
                    table_name=table_name or str(sheet),
                    column_name=col,
                    data_type=str(dtype),
                    ordinal_position=idx + 1,
                )
                for idx, (col, dtype) in enumerate(df.dtypes.items())
            ]
        except Exception as exc:
            raise DiscoveryError(f"Excel column inference failed: {exc}", "excel_upload") from exc

    async def get_row_count(self, schema_name: str, table_name: str) -> RowCountResult:
        try:
            import pandas as pd

            path = self._resolve_path()
            sheet = schema_name or 0
            df = pd.read_excel(path, sheet_name=sheet)
            return RowCountResult(
                schema_name=schema_name,
                table_name=table_name or str(sheet),
                row_count=len(df),
            )
        except Exception as exc:
            raise DiscoveryError(f"Excel row count failed: {exc}", "excel_upload") from exc
