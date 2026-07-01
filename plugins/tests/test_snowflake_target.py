"""Tests for the Snowflake target plugin: DDL generation from IR."""

from __future__ import annotations

from migration_engine.ir.model import Column, Dataset, DatasetKind, MigrationIR
from migration_engine.ir.types import CanonicalType
from migration_engine.spi.contracts import CodeGenerator
from plugins.snowflake.target import SnowflakeDDLGenerator, SnowflakeTarget


def _acct() -> Dataset:
    return Dataset(
        id="tgt", name="ACCT", schema="ANALYTICS",
        primary_key=["ACCOUNT_ID"],
        metadata={"role": "target"},
        columns=[
            Column("ACCOUNT_ID", CanonicalType.decimal(18, 0, nullable=False), ordinal=1),
            Column("BALANCE", CanonicalType.decimal(15, 2), ordinal=2),
            Column("STATUS", CanonicalType.string(1, fixed=True), ordinal=3),
            Column("OPENED_AT", CanonicalType.timestamp(6), ordinal=4),
        ],
    )


def test_create_table_ddl_shape():
    ddl, unmapped = SnowflakeDDLGenerator().create_table(_acct())
    assert unmapped == []
    assert 'CREATE OR REPLACE TABLE "ANALYTICS"."ACCT" (' in ddl
    assert '"ACCOUNT_ID" NUMBER(18,0) NOT NULL' in ddl
    assert '"BALANCE" NUMBER(15,2)' in ddl
    assert '"STATUS" CHAR(1)' in ddl
    assert '"OPENED_AT" TIMESTAMP_NTZ' in ddl
    assert 'PRIMARY KEY ("ACCOUNT_ID")' in ddl
    assert ddl.rstrip().endswith(");")


def test_unmapped_type_is_flagged_in_ddl_and_metadata():
    ds = Dataset(id="t", name="ODD", schema="ANALYTICS", metadata={"role": "target"}, columns=[
        Column("GEO", CanonicalType.unknown("DB2.ST_GEOMETRY"), ordinal=1),
    ])
    art = SnowflakeTarget().generate(MigrationIR(datasets=[ds]))[0]
    assert "WARNING: manual type mapping required for column(s): GEO" in art.body
    assert art.metadata["unmapped_columns"] == ["GEO"]


def test_view_generation_uses_definition():
    ds = Dataset(
        id="v", name="ACTIVE_ACCT", schema="ANALYTICS", kind=DatasetKind.VIEW,
        definition="SELECT * FROM ANALYTICS.ACCT WHERE STATUS = 'A'",
        metadata={"role": "target"},
    )
    art = SnowflakeTarget().generate(MigrationIR(datasets=[ds]))[0]
    assert art.kind == "view"
    assert 'CREATE OR REPLACE VIEW "ANALYTICS"."ACTIVE_ACCT" AS' in art.body
    assert "WHERE STATUS = 'A'" in art.body


def test_snowflake_target_is_a_code_generator():
    assert isinstance(SnowflakeTarget(), CodeGenerator)


def test_generate_targets_only_role_marked_datasets():
    src = Dataset(id="s", name="SRC", metadata={"role": "source"},
                  columns=[Column("A", CanonicalType.integer(32))])
    tgt = Dataset(id="t", name="TGT", schema="ANALYTICS", metadata={"role": "target"},
                  columns=[Column("A", CanonicalType.integer(32))])
    arts = SnowflakeTarget().generate(MigrationIR(datasets=[src, tgt]))
    assert [a.metadata["dataset_id"] for a in arts] == ["t"]


def test_project_override_changes_rendering():
    # Project convention: strings become STRING regardless of length.
    from plugins.snowflake.rules import build_mapper
    mapper = build_mapper(overrides=[{"name": "proj", "rules": [{"kind": "string", "template": "STRING"}]}])
    ddl, _ = SnowflakeDDLGenerator(mapper).create_table(_acct())
    assert '"STATUS" STRING' in ddl
