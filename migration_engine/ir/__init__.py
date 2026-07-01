"""Canonical Intermediate Representation (IR).

The IR is a typed, vendor-neutral model of *what a migration unit is* —
datasets (tables/views/files), jobs (ETL pipelines as transform DAGs),
parameters, and lineage. Everything downstream (dependency analysis, impact
analysis, code generation, reconciliation, documentation) reads the IR; nothing
downstream needs to know the source or target vendor.
"""

from __future__ import annotations

from migration_engine.ir.version import (
    IR_SCHEMA_VERSION,
    IncompatibleIRVersionError,
    is_compatible,
)
from migration_engine.ir.types import CanonicalType, StructField, TypeKind
from migration_engine.ir.transforms import (
    TRANSFORM_CATALOG,
    Transform,
    TransformKind,
    TransformSpec,
)
from migration_engine.ir.model import (
    Column,
    Dataset,
    DatasetKind,
    EdgeKind,
    Job,
    JobKind,
    Link,
    LineageEdge,
    MigrationIR,
    NodeKind,
    NodeRef,
    Parameter,
    ValidationIssue,
)

__all__ = [
    "IR_SCHEMA_VERSION",
    "IncompatibleIRVersionError",
    "is_compatible",
    "CanonicalType",
    "StructField",
    "TypeKind",
    "TRANSFORM_CATALOG",
    "Transform",
    "TransformKind",
    "TransformSpec",
    "Column",
    "Dataset",
    "DatasetKind",
    "EdgeKind",
    "Job",
    "JobKind",
    "Link",
    "LineageEdge",
    "MigrationIR",
    "NodeKind",
    "NodeRef",
    "Parameter",
    "ValidationIssue",
]
