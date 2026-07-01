"""IBM DB2 source connector (MetadataProvider).

Turns a DB2 catalog description into IR ``Dataset`` objects. The pure mapping —
``build_datasets`` — is fully testable offline; live extraction over the
``ibm_db`` driver is a thin boundary layered on top (not required for codegen or
tests). Pass a ``catalog`` in ``ctx.config`` to run entirely offline.

Catalog shape (list of tables)::

    {"schema": "CORE", "table": "ACCT", "database": "BEDROCK", "kind": "table",
     "row_count": 120000, "primary_key": ["ACCOUNT_ID"],
     "columns": [
        {"name": "ACCOUNT_ID", "type": "DECIMAL", "length": 18, "scale": 0,
         "nullable": False, "ordinal": 1},
        ...
     ]}
"""

from __future__ import annotations

from typing import Any

from migration_engine.ir.model import Column, Dataset, DatasetKind
from migration_engine.spi.contracts import (
    Capability,
    ConnectionContext,
    ConnectorManifest,
    ConnectorRole,
    ConnectorTestResult,
)
from plugins.db2.type_mapping import parse_db2_type

MANIFEST = ConnectorManifest(
    name="db2",
    version="0.1.0",
    role=ConnectorRole.SOURCE,
    capabilities=frozenset({Capability.METADATA}),
    vendor="IBM",
    description="IBM DB2 (LUW / z-series) source — metadata extraction into the IR.",
)

_KIND = {"table": DatasetKind.TABLE, "view": DatasetKind.VIEW, "query": DatasetKind.QUERY}


def _column(row: dict[str, Any]) -> Column:
    return Column(
        name=row["name"],
        type=parse_db2_type(
            row["type"],
            length=row.get("length"),
            scale=row.get("scale"),
            nullable=row.get("nullable", True),
        ),
        ordinal=row.get("ordinal", 0),
        description=row.get("description", ""),
        is_pii=row.get("is_pii", False),
        tags=list(row.get("tags", [])),
    )


def build_dataset(entry: dict[str, Any]) -> Dataset:
    """Build one IR ``Dataset`` from a single catalog table entry."""
    schema = entry.get("schema")
    table = entry["table"]
    database = entry.get("database")
    dataset_id = ".".join(p for p in (database, schema, table) if p)
    return Dataset(
        id=dataset_id,
        name=table,
        kind=_KIND.get(str(entry.get("kind", "table")).lower(), DatasetKind.TABLE),
        database=database,
        schema=schema,
        columns=[_column(c) for c in entry.get("columns", [])],
        row_count=entry.get("row_count"),
        primary_key=list(entry.get("primary_key", [])),
        definition=entry.get("definition"),
        metadata={"source_system": "db2"},
    )


def build_datasets(catalog: list[dict[str, Any]]) -> list[Dataset]:
    """Build IR datasets from a DB2 catalog description."""
    return [build_dataset(entry) for entry in catalog]


class DB2Source:
    """DB2 source connector implementing the ``MetadataProvider`` capability."""

    def test_connection(self, ctx: ConnectionContext) -> ConnectorTestResult:
        if ctx.get("catalog") is not None:
            return ConnectorTestResult(success=True, message="db2 source ready (offline catalog)")
        # A real implementation would open an ibm_db connection here.
        host = ctx.get("host")
        return ConnectorTestResult(
            success=bool(host),
            message="db2 source configured" if host else "no host configured",
        )

    def extract_datasets(self, ctx: ConnectionContext) -> list[Dataset]:
        catalog = ctx.get("catalog")
        if catalog is None:
            raise NotImplementedError(
                "Live DB2 extraction requires the ibm_db driver; pass 'catalog' in "
                "ctx.config to run offline."
            )
        return build_datasets(catalog)
