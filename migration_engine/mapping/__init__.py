"""Configurable rule engine (vendor-neutral mechanism).

The engine that turns canonical IR into target artifacts must be *configurable
without code changes* — otherwise every new dialect or org convention forces a
core edit, which is the #1 trap that kills extensibility.

This package provides the **mechanism**: declarative, layered rule sets
(global -> org -> project) evaluated first-match-wins. Concrete dialect rule
sets (e.g. how Snowflake renders a DECIMAL) are *data*, supplied by target
connectors or org config — they are deliberately NOT hard-coded here, so the
core stays free of vendor names.
"""

from __future__ import annotations

from migration_engine.mapping.type_mapping import (
    LayeredTypeMapper,
    MappingResult,
    TypeRule,
    TypeRuleSet,
)

__all__ = [
    "LayeredTypeMapper",
    "MappingResult",
    "TypeRule",
    "TypeRuleSet",
]
