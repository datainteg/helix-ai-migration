"""Snowflake canonical-type -> dialect rendering rules (as data).

This is a rule *set* consumed by the engine's mapping engine — no engine code
changes are needed to add or tune a dialect. Org/project layers can override
these via ``build_mapper(overrides=...)``.
"""

from __future__ import annotations

from typing import Any, Optional

from migration_engine.mapping.type_mapping import LayeredTypeMapper, TypeRuleSet

SNOWFLAKE_TYPE_RULES: dict[str, Any] = {
    "name": "snowflake",
    "dialect": "snowflake",
    "rules": [
        {"kind": "decimal", "template": "NUMBER({precision},{scale})"},
        {"kind": "integer", "template": "NUMBER(38,0)"},
        {"kind": "float", "template": "FLOAT"},
        {"kind": "boolean", "template": "BOOLEAN"},
        {"kind": "date", "template": "DATE"},
        {"kind": "time", "template": "TIME"},
        {"kind": "string", "when": {"fixed": True}, "template": "CHAR({length})"},
        {"kind": "string", "template": "VARCHAR({length})"},
        {"kind": "string", "when": {"length": None}, "template": "VARCHAR"},
        {"kind": "binary", "template": "BINARY({length})"},
        {"kind": "binary", "when": {"length": None}, "template": "BINARY"},
        {"kind": "timestamp", "when": {"with_timezone": True}, "template": "TIMESTAMP_TZ"},
        {"kind": "timestamp", "template": "TIMESTAMP_NTZ"},
        {"kind": "json", "template": "VARIANT"},
        {"kind": "xml", "template": "VARIANT"},
        {"kind": "variant", "template": "VARIANT"},
        {"kind": "array", "template": "ARRAY"},
        {"kind": "struct", "template": "OBJECT"},
        {"kind": "map", "template": "OBJECT"},
    ],
}


def build_mapper(overrides: Optional[list[dict[str, Any]]] = None) -> LayeredTypeMapper:
    """Build a layered mapper: overrides (project/org) first, Snowflake base last."""
    layers = [TypeRuleSet.from_dict(o) for o in (overrides or [])]
    layers.append(TypeRuleSet.from_dict(SNOWFLAKE_TYPE_RULES))
    return LayeredTypeMapper(layers)
