"""Tests for the canonical type system."""

from __future__ import annotations

from migration_engine.ir.types import CanonicalType, StructField, TypeKind


def test_constructors_set_expected_params():
    assert CanonicalType.integer(64).bit_width == 64
    d = CanonicalType.decimal(10, 2)
    assert (d.kind, d.precision, d.scale) == (TypeKind.DECIMAL, 10, 2)
    s = CanonicalType.string(50, fixed=True)
    assert (s.kind, s.length, s.fixed) == (TypeKind.STRING, 50, True)
    ts = CanonicalType.timestamp(6, with_timezone=True)
    assert ts.with_timezone and ts.precision == 6


def test_signatures_are_stable_and_readable():
    assert CanonicalType.integer(32).signature() == "integer32"
    assert CanonicalType.decimal(10, 2).signature() == "decimal(10,2)"
    assert CanonicalType.string(20).signature() == "string(20)"
    assert CanonicalType.string(8, fixed=True).signature() == "char(8)"
    assert CanonicalType.timestamp(with_timezone=True).signature() == "timestamp_tz"
    assert CanonicalType.timestamp().signature() == "timestamp_ntz"


def test_not_null_signature_suffix():
    assert CanonicalType.integer(32, nullable=False).signature() == "integer32 not null"


def test_nested_types_signature_and_flags():
    arr = CanonicalType.array(CanonicalType.string(10))
    assert arr.is_nested and arr.signature() == "array<string(10)>"

    mp = CanonicalType.map_(CanonicalType.string(), CanonicalType.integer(32))
    assert mp.signature() == "map<string,integer32>"

    st = CanonicalType.struct((
        StructField("id", CanonicalType.integer(64)),
        StructField("name", CanonicalType.string(100)),
    ))
    assert st.signature() == "struct<id:integer64,name:string(100)>"


def test_unknown_preserves_raw_source_type():
    u = CanonicalType.unknown("SYS.PROPRIETARY_GEOM")
    assert u.is_unknown
    assert u.raw_source_type == "SYS.PROPRIETARY_GEOM"
    assert u.signature() == "unknown(SYS.PROPRIETARY_GEOM)"
