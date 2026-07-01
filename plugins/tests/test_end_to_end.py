"""End-to-end: DB2 catalog -> IR -> Snowflake DDL, via the SPI registry.

This is the "Any Source -> Canonical IR -> Any Target" promise made concrete,
running on Python alone (no live DB2/Snowflake). It also exercises the registry
as the orchestration seam: resolve a metadata source and a codegen target by
capability, not by hard-coded pair.
"""

from __future__ import annotations

import dataclasses

from migration_engine.ir.model import MigrationIR
from migration_engine.spi.contracts import Capability, ConnectionContext
from migration_engine.spi.registry import ConnectorRegistry
from plugins.db2.source import MANIFEST as DB2_MANIFEST
from plugins.db2.source import DB2Source
from plugins.snowflake.target import MANIFEST as SF_MANIFEST
from plugins.snowflake.target import SnowflakeTarget

# A realistic Bedrock/Core (DB2) table, mirroring the user's real tickets.
DB2_CATALOG = [{
    "schema": "CORE", "table": "HOME_FIXTURES", "database": "BEDROCK", "kind": "table",
    "row_count": 120000, "primary_key": ["FIXTURE_ID"],
    "columns": [
        {"name": "FIXTURE_ID", "type": "DECIMAL", "length": 18, "scale": 0, "nullable": False, "ordinal": 1},
        {"name": "ACCOUNT_NO", "type": "CHAR", "length": 11, "nullable": False, "ordinal": 2},
        {"name": "DESCRIPTION", "type": "VARCHAR", "length": 240, "nullable": True, "ordinal": 3},
        {"name": "BALANCE", "type": "DECIMAL", "length": 15, "scale": 2, "nullable": True, "ordinal": 4},
        {"name": "OPENED_AT", "type": "TIMESTAMP", "scale": 6, "nullable": True, "ordinal": 5},
        {"name": "LEGACY_LOC", "type": "ROWID", "nullable": True, "ordinal": 6},  # unmapped on purpose
    ],
}]


def _registry() -> ConnectorRegistry:
    reg = ConnectorRegistry()
    reg.register(DB2Source(), DB2_MANIFEST)
    reg.register(SnowflakeTarget(), SF_MANIFEST)
    return reg


def test_registry_resolves_by_capability():
    reg = _registry()
    assert reg.with_capability(Capability.METADATA) == ["db2"]
    assert reg.with_capability(Capability.CODEGEN) == ["snowflake"]


def test_db2_to_snowflake_end_to_end():
    reg = _registry()

    # 1. Source: DB2 catalog -> IR datasets (resolved by capability, not name).
    source = reg.get(reg.with_capability(Capability.METADATA)[0])
    ctx = ConnectionContext(config={"catalog": DB2_CATALOG})
    [src_ds] = source.extract_datasets(ctx)

    # 2. Retarget to Snowflake ANALYTICS schema (a migration decision).
    tgt_ds = dataclasses.replace(
        src_ds, id="tgt", database=None, schema="ANALYTICS",
        metadata={**src_ds.metadata, "role": "target"},
    )
    ir = MigrationIR(name="DPE-1369", datasets=[tgt_ds])
    assert ir.validate() == []

    # 3. Target: IR -> Snowflake DDL.
    target = reg.get(reg.with_capability(Capability.CODEGEN)[0])
    [artifact] = target.generate(ir)
    ddl = artifact.body

    # --- deterministic type mapping proven across the real DB2 types ---
    assert '"FIXTURE_ID" NUMBER(18,0) NOT NULL' in ddl
    assert '"ACCOUNT_NO" CHAR(11) NOT NULL' in ddl
    assert '"DESCRIPTION" VARCHAR(240)' in ddl
    assert '"BALANCE" NUMBER(15,2)' in ddl
    assert '"OPENED_AT" TIMESTAMP_NTZ' in ddl
    assert 'PRIMARY KEY ("FIXTURE_ID")' in ddl
    assert 'CREATE OR REPLACE TABLE "ANALYTICS"."HOME_FIXTURES"' in ddl

    # --- the unmapped DB2 ROWID is surfaced, never silently guessed ---
    assert artifact.metadata["unmapped_columns"] == ["LEGACY_LOC"]
    assert "WARNING: manual type mapping required" in ddl
