"""Tests for the transformation vocabulary + coverage catalog."""

from __future__ import annotations

from migration_engine.ir.transforms import (
    TRANSFORM_CATALOG,
    Transform,
    TransformKind,
)


def test_catalog_covers_every_kind():
    # Every enum member must have a catalog entry (codegen relies on this).
    assert set(TRANSFORM_CATALOG) == set(TransformKind)


def test_effective_determinism_uses_catalog_default():
    join = Transform(id="t1", kind=TransformKind.JOIN, params={"join_type": "inner", "on": ["id"]})
    assert join.is_deterministic is True

    scd = Transform(id="t2", kind=TransformKind.SCD, params={"scd_type": 2, "keys": ["id"]})
    assert scd.is_deterministic is False  # SCD defaults to needing assist/manual


def test_explicit_determinism_flag_overrides_catalog():
    custom = Transform(id="t3", kind=TransformKind.CUSTOM, deterministic=True)
    assert custom.is_deterministic is True


def test_missing_required_params_detected():
    join = Transform(id="t4", kind=TransformKind.JOIN, params={"join_type": "inner"})
    assert join.missing_required_params() == ["on"]

    complete = Transform(id="t5", kind=TransformKind.FILTER, params={"predicate": "x > 0"})
    assert complete.missing_required_params() == []
