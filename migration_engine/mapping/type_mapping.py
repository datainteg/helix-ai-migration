"""Declarative, layered canonical-type -> target-dialect rendering.

A ``TypeRule`` matches a ``CanonicalType`` (by kind + optional param conditions)
and renders a target type string from a template. A ``TypeRuleSet`` is an
ordered list (first match wins). ``LayeredTypeMapper`` composes several rule
sets — project overrides org overrides the dialect baseline — so customers can
tweak conventions without touching code.

Rule sets are plain data and can be loaded from JSON/YAML config:

    {"name": "snowflake", "dialect": "snowflake", "rules": [
        {"kind": "decimal",   "template": "NUMBER({precision},{scale})"},
        {"kind": "string",    "when": {"fixed": true}, "template": "CHAR({length})"},
        {"kind": "string",    "template": "VARCHAR({length})"},
        {"kind": "string",    "when": {"length": null}, "template": "VARCHAR"},
        {"kind": "timestamp", "when": {"with_timezone": true}, "template": "TIMESTAMP_TZ"},
        {"kind": "timestamp", "template": "TIMESTAMP_NTZ"}
    ]}

Anything with no matching rule yields ``MappingResult(matched=False, ...)`` —
never a silent guess — so the Assessment engine can count it as manual effort.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

from migration_engine.ir.types import CanonicalType

_PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")

# Params a rule may condition on / render from. All map to CanonicalType attrs.
_CONDITION_ATTRS = {
    "fixed", "with_timezone", "nullable",
    "precision", "scale", "length", "bit_width",
}


@dataclass(frozen=True)
class MappingResult:
    """Outcome of rendering one canonical type."""

    text: str
    matched: bool
    rule: Optional[str] = None      # "<ruleset>#<index>" of the winning rule
    note: str = ""


@dataclass(frozen=True)
class TypeRule:
    """One match->render rule."""

    kind: str                       # TypeKind value, e.g. "decimal"
    template: str                   # e.g. "NUMBER({precision},{scale})"
    when: dict[str, Any] = field(default_factory=dict)

    def matches(self, ctype: CanonicalType) -> bool:
        if ctype.kind.value != self.kind:
            return False
        for key, expected in self.when.items():
            if key not in _CONDITION_ATTRS:
                return False
            actual = getattr(ctype, key)
            if expected is None:
                if actual is not None:
                    return False
            elif actual != expected:
                return False
        # All template placeholders must resolve to a non-None value.
        for ph in _PLACEHOLDER_RE.findall(self.template):
            if ph not in _CONDITION_ATTRS or getattr(ctype, ph, None) is None:
                return False
        return True

    def render(self, ctype: CanonicalType) -> str:
        values = {ph: getattr(ctype, ph) for ph in _PLACEHOLDER_RE.findall(self.template)}
        return self.template.format(**values)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "TypeRule":
        return cls(kind=d["kind"], template=d["template"], when=dict(d.get("when", {})))


@dataclass(frozen=True)
class TypeRuleSet:
    """An ordered, named collection of type rules for one layer."""

    name: str
    rules: tuple[TypeRule, ...]
    dialect: str = ""

    def find(self, ctype: CanonicalType) -> Optional[tuple[int, TypeRule]]:
        for idx, rule in enumerate(self.rules):
            if rule.matches(ctype):
                return idx, rule
        return None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "TypeRuleSet":
        return cls(
            name=d["name"],
            dialect=d.get("dialect", ""),
            rules=tuple(TypeRule.from_dict(r) for r in d.get("rules", [])),
        )


class LayeredTypeMapper:
    """Render canonical types through layered rule sets (most specific first).

    Pass rule sets in priority order, e.g. ``[project, org, dialect_base]``.
    The first rule (in the first layer) that matches wins.
    """

    def __init__(self, layers: list[TypeRuleSet]) -> None:
        self._layers = layers

    def render(self, ctype: CanonicalType) -> MappingResult:
        for layer in self._layers:
            hit = layer.find(ctype)
            if hit is not None:
                idx, rule = hit
                return MappingResult(
                    text=rule.render(ctype),
                    matched=True,
                    rule=f"{layer.name}#{idx}",
                )
        return MappingResult(
            text=ctype.signature(),
            matched=False,
            note=f"no rule for {ctype.signature()} (manual mapping required)",
        )

    @classmethod
    def from_dicts(cls, layers: list[dict[str, Any]]) -> "LayeredTypeMapper":
        return cls([TypeRuleSet.from_dict(d) for d in layers])
