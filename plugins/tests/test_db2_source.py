"""Tests for the DB2 source plugin: type parsing + catalog -> IR."""

from __future__ import annotations

from migration_engine.ir.model import DatasetKind
from migration_engine.ir.types import TypeKind
from migration_engine.spi.contracts import ConnectionContext, MetadataProvider
from plugins.db2.source import DB2Source, build_datasets
from plugins.db2.type_mapping import parse_db2_type


def test_numeric_type_parsing():
    assert parse_db2_type("SMALLINT").signature() == "integer16"
    assert parse_db2_type("INTEGER").signature() == "integer32"
    assert parse_db2_type("BIGINT").signature() == "integer64"
    assert parse_db2_type("DECIMAL", length=18, scale=0).signature() == "decimal(18,0)"
    assert parse_db2_type("NUMERIC", length=15, scale=2).signature() == "decimal(15,2)"
    assert parse_db2_type("DOUBLE").signature() == "float64"
    assert parse_db2_type("REAL").signature() == "float32"


def test_string_and_temporal_parsing():
    assert parse_db2_type("CHAR", length=11).signature() == "char(11)"
    assert parse_db2_type("VARCHAR", length=40).signature() == "string(40)"
    assert parse_db2_type("DATE").signature() == "date"
    assert parse_db2_type("TIMESTAMP", scale=6).signature() == "timestamp_ntz(6)"
    tz = parse_db2_type("TIMESTAMP WITH TIME ZONE")
    assert tz.with_timezone is True


def test_nullability_is_carried():
    assert parse_db2_type("INTEGER", nullable=False).nullable is False
    assert parse_db2_type("INTEGER", nullable=True).nullable is True


def test_unknown_db2_type_preserved_not_guessed():
    t = parse_db2_type("ROWID")
    assert t.kind is TypeKind.UNKNOWN
    assert t.raw_source_type == "ROWID"


def test_build_datasets_from_catalog():
    catalog = [{
        "schema": "CORE", "table": "ACCT", "database": "BEDROCK", "kind": "table",
        "row_count": 120000, "primary_key": ["ACCOUNT_ID"],
        "columns": [
            {"name": "ACCOUNT_ID", "type": "DECIMAL", "length": 18, "scale": 0, "nullable": False, "ordinal": 1},
            {"name": "STATUS", "type": "CHAR", "length": 1, "nullable": True, "ordinal": 2},
        ],
    }]
    [ds] = build_datasets(catalog)
    assert ds.id == "BEDROCK.CORE.ACCT"
    assert ds.qualified_name == "BEDROCK.CORE.ACCT"
    assert ds.kind is DatasetKind.TABLE
    assert ds.row_count == 120000
    assert ds.primary_key == ["ACCOUNT_ID"]
    acct = ds.column("ACCOUNT_ID").type
    assert (acct.kind, acct.precision, acct.scale) == (TypeKind.DECIMAL, 18, 0)
    assert acct.nullable is False


def test_db2source_is_a_metadata_provider_and_extracts_offline():
    src = DB2Source()
    assert isinstance(src, MetadataProvider)
    ctx = ConnectionContext(config={"catalog": [
        {"schema": "CORE", "table": "T", "columns": [
            {"name": "C1", "type": "INTEGER", "nullable": False, "ordinal": 1},
        ]},
    ]})
    assert src.test_connection(ctx).success is True
    datasets = src.extract_datasets(ctx)
    c1 = datasets[0].column("C1").type
    assert c1.kind is TypeKind.INTEGER and c1.bit_width == 32 and c1.nullable is False
