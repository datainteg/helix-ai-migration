"""Snowflake target connector (CodeGenerator).

Generates Snowflake DDL from IR datasets using the mapping rule engine. Types
that have no deterministic mapping are rendered with their canonical signature
and called out in a header ``WARNING`` comment plus the artifact metadata, so
nothing is silently guessed and the Assessment engine can count manual effort.
"""

from __future__ import annotations

from typing import Optional

from migration_engine.ir.model import Dataset, DatasetKind, MigrationIR
from migration_engine.mapping.type_mapping import LayeredTypeMapper
from migration_engine.spi.contracts import (
    Capability,
    ConnectorManifest,
    ConnectorRole,
    GeneratedArtifact,
)
from plugins.snowflake.rules import build_mapper

MANIFEST = ConnectorManifest(
    name="snowflake",
    version="0.1.0",
    role=ConnectorRole.TARGET,
    capabilities=frozenset({Capability.CODEGEN}),
    vendor="Snowflake",
    description="Snowflake target — generates DDL from the IR.",
)


def _q(identifier: str) -> str:
    """Quote a Snowflake identifier, escaping embedded quotes."""
    return '"' + identifier.replace('"', '""') + '"'


class SnowflakeDDLGenerator:
    """Render CREATE TABLE / CREATE VIEW DDL for a single IR dataset."""

    def __init__(self, mapper: Optional[LayeredTypeMapper] = None) -> None:
        self._mapper = mapper or build_mapper()

    def qualified_name(self, ds: Dataset) -> str:
        parts = [p for p in (ds.database, ds.schema, ds.name) if p]
        return ".".join(_q(p) for p in parts)

    def create_table(self, ds: Dataset) -> tuple[str, list[str]]:
        """Return (ddl, unmapped_columns)."""
        col_defs: list[str] = []
        unmapped: list[str] = []
        for col in sorted(ds.columns, key=lambda c: c.ordinal or 0):
            rendered = self._mapper.render(col.type)
            if not rendered.matched:
                unmapped.append(col.name)
            null = "" if col.type.nullable else " NOT NULL"
            col_defs.append(f"    {_q(col.name)} {rendered.text}{null}")
        if ds.primary_key:
            pk = ", ".join(_q(k) for k in ds.primary_key)
            col_defs.append(f"    PRIMARY KEY ({pk})")

        header = ""
        if unmapped:
            header = (
                "-- WARNING: manual type mapping required for column(s): "
                + ", ".join(unmapped)
                + "\n"
            )
        body = (
            f"{header}CREATE OR REPLACE TABLE {self.qualified_name(ds)} (\n"
            + ",\n".join(col_defs)
            + "\n);\n"
        )
        return body, unmapped

    def create_view(self, ds: Dataset) -> tuple[str, list[str]]:
        if ds.definition:
            body = f"CREATE OR REPLACE VIEW {self.qualified_name(ds)} AS\n{ds.definition.rstrip()};\n"
        else:
            body = (
                f"-- TODO: view {ds.qualified_name} has no definition to translate\n"
                f"CREATE OR REPLACE VIEW {self.qualified_name(ds)} AS SELECT 1;\n"
            )
        return body, []

    def generate_for(self, ds: Dataset) -> GeneratedArtifact:
        if ds.kind is DatasetKind.VIEW:
            body, unmapped = self.create_view(ds)
            kind = "view"
        else:
            body, unmapped = self.create_table(ds)
            kind = "ddl"
        return GeneratedArtifact(
            path=f"{ds.qualified_name}.sql",
            language="sql",
            body=body,
            kind=kind,
            metadata={"unmapped_columns": unmapped, "dataset_id": ds.id},
        )


class SnowflakeTarget:
    """Snowflake target connector implementing the ``CodeGenerator`` capability."""

    def __init__(self, mapper: Optional[LayeredTypeMapper] = None) -> None:
        self._gen = SnowflakeDDLGenerator(mapper)

    def generate(self, ir: MigrationIR) -> list[GeneratedArtifact]:
        # Prefer datasets explicitly marked as targets; else emit for all.
        targets = [d for d in ir.datasets if d.metadata.get("role") == "target"]
        datasets = targets or ir.datasets
        return [self._gen.generate_for(ds) for ds in datasets]
