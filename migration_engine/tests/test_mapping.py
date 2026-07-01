"""Tests for the layered type-mapping rule engine.

The Snowflake-like rule set lives here as *config* (not in the engine core),
demonstrating that a new dialect needs only data, not code.
"""

from __future__ import annotations

from migration_engine.ir.types import CanonicalType
from migration_engine.mapping.type_mapping import LayeredTypeMapper, TypeRuleSet

SNOWFLAKE = {
    "name": "snowflake",
    "dialect": "snowflake",
    "rules": [
        {"kind": "decimal", "template": "NUMBER({precision},{scale})"},
        {"kind": "integer", "template": "NUMBER(38,0)"},
        {"kind": "float", "template": "FLOAT"},
        {"kind": "boolean", "template": "BOOLEAN"},
        {"kind": "date", "template": "DATE"},
        {"kind": "string", "when": {"fixed": True}, "template": "CHAR({length})"},
        {"kind": "string", "template": "VARCHAR({length})"},
        {"kind": "string", "when": {"length": None}, "template": "VARCHAR"},
        {"kind": "timestamp", "when": {"with_timezone": True}, "template": "TIMESTAMP_TZ"},
        {"kind": "timestamp", "template": "TIMESTAMP_NTZ"},
        {"kind": "variant", "template": "VARIANT"},
        {"kind": "json", "template": "VARIANT"},
    ],
}


def _mapper() -> LayeredTypeMapper:
    return LayeredTypeMapper.from_dicts([SNOWFLAKE])


def test_db2_style_decimals_map_to_number():
    m = _mapper()
    assert m.render(CanonicalType.decimal(18, 0)).text == "NUMBER(18,0)"
    assert m.render(CanonicalType.decimal(15, 2)).text == "NUMBER(15,2)"


def test_integer_maps_to_number_38():
    assert _mapper().render(CanonicalType.integer(32)).text == "NUMBER(38,0)"


def test_fixed_vs_varying_strings():
    m = _mapper()
    assert m.render(CanonicalType.string(11, fixed=True)).text == "CHAR(11)"
    assert m.render(CanonicalType.string(50)).text == "VARCHAR(50)"
    assert m.render(CanonicalType.string()).text == "VARCHAR"  # no length


def test_timestamp_timezone_variants():
    m = _mapper()
    assert m.render(CanonicalType.timestamp(with_timezone=True)).text == "TIMESTAMP_TZ"
    assert m.render(CanonicalType.timestamp()).text == "TIMESTAMP_NTZ"


def test_simple_kinds():
    m = _mapper()
    assert m.render(CanonicalType.boolean()).text == "BOOLEAN"
    assert m.render(CanonicalType.date()).text == "DATE"
    assert m.render(CanonicalType.json()).text == "VARIANT"


def test_unmapped_type_is_flagged_not_guessed():
    m = _mapper()
    result = m.render(CanonicalType.unknown("DB2.PROPRIETARY_GEOM"))
    assert result.matched is False
    assert "manual mapping required" in result.note
    # falls back to the canonical signature rather than inventing a target type
    assert result.text == "unknown(DB2.PROPRIETARY_GEOM)"


def test_winning_rule_is_reported():
    result = _mapper().render(CanonicalType.decimal(10, 2))
    assert result.rule == "snowflake#0"


def test_project_layer_overrides_baseline():
    # A project convention: render strings as Databricks STRING regardless of length.
    project = TypeRuleSet.from_dict({
        "name": "acme_project",
        "rules": [{"kind": "string", "template": "STRING"}],
    })
    layered = LayeredTypeMapper([project, TypeRuleSet.from_dict(SNOWFLAKE)])
    out = layered.render(CanonicalType.string(50))
    assert out.text == "STRING"
    assert out.rule == "acme_project#0"
    # non-overridden kinds still fall through to the baseline
    assert layered.render(CanonicalType.decimal(9, 2)).text == "NUMBER(9,2)"
