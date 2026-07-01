"""Deterministic JSON (de)serialization for the IR.

The IR crosses process boundaries: connector plugins emit it, the engine
persists it, the catalog/knowledge-graph index it. Serialization is therefore
explicit (not generic ``asdict``) so the on-disk shape is stable, compact
(defaults omitted), and version-checked on load.
"""

from __future__ import annotations

import json
from typing import Any, Optional

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
)
from migration_engine.ir.transforms import Transform, TransformKind
from migration_engine.ir.types import CanonicalType, StructField, TypeKind
from migration_engine.ir.version import IncompatibleIRVersionError, is_compatible


# ----- CanonicalType --------------------------------------------------------
def _type_to_dict(t: CanonicalType) -> dict[str, Any]:
    d: dict[str, Any] = {"kind": t.kind.value}
    if not t.nullable:
        d["nullable"] = False
    for attr in ("precision", "scale", "bit_width", "length", "raw_source_type"):
        val = getattr(t, attr)
        if val is not None:
            d[attr] = val
    if t.fixed:
        d["fixed"] = True
    if t.with_timezone:
        d["with_timezone"] = True
    if t.element is not None:
        d["element"] = _type_to_dict(t.element)
    if t.key is not None:
        d["key"] = _type_to_dict(t.key)
    if t.value is not None:
        d["value"] = _type_to_dict(t.value)
    if t.fields:
        d["fields"] = [{"name": f.name, "type": _type_to_dict(f.type)} for f in t.fields]
    if t.metadata:
        d["metadata"] = t.metadata
    return d


def _type_from_dict(d: dict[str, Any]) -> CanonicalType:
    fields = tuple(
        StructField(name=f["name"], type=_type_from_dict(f["type"]))
        for f in d.get("fields", [])
    )
    return CanonicalType(
        kind=TypeKind(d["kind"]),
        nullable=d.get("nullable", True),
        precision=d.get("precision"),
        scale=d.get("scale"),
        bit_width=d.get("bit_width"),
        length=d.get("length"),
        fixed=d.get("fixed", False),
        with_timezone=d.get("with_timezone", False),
        element=_type_from_dict(d["element"]) if "element" in d else None,
        key=_type_from_dict(d["key"]) if "key" in d else None,
        value=_type_from_dict(d["value"]) if "value" in d else None,
        fields=fields,
        raw_source_type=d.get("raw_source_type"),
        metadata=d.get("metadata", {}),
    )


def _opt_type_to_dict(t: Optional[CanonicalType]) -> Optional[dict[str, Any]]:
    return _type_to_dict(t) if t is not None else None


# ----- Transform ------------------------------------------------------------
def _transform_to_dict(t: Transform) -> dict[str, Any]:
    d: dict[str, Any] = {"id": t.id, "kind": t.kind.value}
    if t.name:
        d["name"] = t.name
    if t.params:
        d["params"] = t.params
    if t.inputs:
        d["inputs"] = t.inputs
    if t.outputs:
        d["outputs"] = t.outputs
    if t.deterministic is not None:
        d["deterministic"] = t.deterministic
    if t.raw is not None:
        d["raw"] = t.raw
    if t.metadata:
        d["metadata"] = t.metadata
    return d


def _transform_from_dict(d: dict[str, Any]) -> Transform:
    return Transform(
        id=d["id"],
        kind=TransformKind(d["kind"]),
        name=d.get("name", ""),
        params=d.get("params", {}),
        inputs=d.get("inputs", []),
        outputs=d.get("outputs", []),
        deterministic=d.get("deterministic"),
        raw=d.get("raw"),
        metadata=d.get("metadata", {}),
    )


# ----- Column / Dataset -----------------------------------------------------
def _column_to_dict(c: Column) -> dict[str, Any]:
    d: dict[str, Any] = {"name": c.name, "type": _type_to_dict(c.type)}
    if c.ordinal:
        d["ordinal"] = c.ordinal
    if c.description:
        d["description"] = c.description
    if c.tags:
        d["tags"] = c.tags
    if c.is_pii:
        d["is_pii"] = True
    if c.metadata:
        d["metadata"] = c.metadata
    return d


def _column_from_dict(d: dict[str, Any]) -> Column:
    return Column(
        name=d["name"],
        type=_type_from_dict(d["type"]),
        ordinal=d.get("ordinal", 0),
        description=d.get("description", ""),
        tags=d.get("tags", []),
        is_pii=d.get("is_pii", False),
        metadata=d.get("metadata", {}),
    )


def _dataset_to_dict(ds: Dataset) -> dict[str, Any]:
    d: dict[str, Any] = {"id": ds.id, "name": ds.name, "kind": ds.kind.value}
    if ds.database:
        d["database"] = ds.database
    if ds.schema:
        d["schema"] = ds.schema
    if ds.columns:
        d["columns"] = [_column_to_dict(c) for c in ds.columns]
    if ds.row_count is not None:
        d["row_count"] = ds.row_count
    if ds.primary_key:
        d["primary_key"] = ds.primary_key
    if ds.definition is not None:
        d["definition"] = ds.definition
    if ds.properties:
        d["properties"] = ds.properties
    if ds.metadata:
        d["metadata"] = ds.metadata
    return d


def _dataset_from_dict(d: dict[str, Any]) -> Dataset:
    return Dataset(
        id=d["id"],
        name=d["name"],
        kind=DatasetKind(d.get("kind", "table")),
        database=d.get("database"),
        schema=d.get("schema"),
        columns=[_column_from_dict(c) for c in d.get("columns", [])],
        row_count=d.get("row_count"),
        primary_key=d.get("primary_key", []),
        definition=d.get("definition"),
        properties=d.get("properties", {}),
        metadata=d.get("metadata", {}),
    )


# ----- Parameter / Link / Job ----------------------------------------------
def _param_to_dict(p: Parameter) -> dict[str, Any]:
    d: dict[str, Any] = {"name": p.name}
    if p.type is not None:
        d["type"] = _type_to_dict(p.type)
    if p.default is not None:
        d["default"] = p.default
    if p.scope != "job":
        d["scope"] = p.scope
    if p.description:
        d["description"] = p.description
    if p.secret:
        d["secret"] = True
    return d


def _param_from_dict(d: dict[str, Any]) -> Parameter:
    return Parameter(
        name=d["name"],
        type=_type_from_dict(d["type"]) if "type" in d else None,
        default=d.get("default"),
        scope=d.get("scope", "job"),
        description=d.get("description", ""),
        secret=d.get("secret", False),
    )


def _link_to_dict(link: Link) -> dict[str, Any]:
    d: dict[str, Any] = {
        "id": link.id,
        "from_transform": link.from_transform,
        "to_transform": link.to_transform,
    }
    if link.from_port != "out":
        d["from_port"] = link.from_port
    if link.to_port != "in":
        d["to_port"] = link.to_port
    if link.metadata:
        d["metadata"] = link.metadata
    return d


def _link_from_dict(d: dict[str, Any]) -> Link:
    return Link(
        id=d["id"],
        from_transform=d["from_transform"],
        to_transform=d["to_transform"],
        from_port=d.get("from_port", "out"),
        to_port=d.get("to_port", "in"),
        metadata=d.get("metadata", {}),
    )


def _job_to_dict(job: Job) -> dict[str, Any]:
    d: dict[str, Any] = {"id": job.id, "name": job.name, "kind": job.kind.value}
    if job.transforms:
        d["transforms"] = [_transform_to_dict(t) for t in job.transforms]
    if job.links:
        d["links"] = [_link_to_dict(link) for link in job.links]
    if job.parameters:
        d["parameters"] = [_param_to_dict(p) for p in job.parameters]
    if job.description:
        d["description"] = job.description
    if job.metadata:
        d["metadata"] = job.metadata
    return d


def _job_from_dict(d: dict[str, Any]) -> Job:
    return Job(
        id=d["id"],
        name=d["name"],
        kind=JobKind(d.get("kind", "pipeline")),
        transforms=[_transform_from_dict(t) for t in d.get("transforms", [])],
        links=[_link_from_dict(link) for link in d.get("links", [])],
        parameters=[_param_from_dict(p) for p in d.get("parameters", [])],
        description=d.get("description", ""),
        metadata=d.get("metadata", {}),
    )


# ----- Lineage --------------------------------------------------------------
def _noderef_to_dict(ref: NodeRef) -> dict[str, Any]:
    return {"kind": ref.kind.value, "id": ref.id}


def _noderef_from_dict(d: dict[str, Any]) -> NodeRef:
    return NodeRef(kind=NodeKind(d["kind"]), id=d["id"])


def _lineage_to_dict(edge: LineageEdge) -> dict[str, Any]:
    d: dict[str, Any] = {
        "source": _noderef_to_dict(edge.source),
        "target": _noderef_to_dict(edge.target),
        "kind": edge.kind.value,
    }
    if edge.metadata:
        d["metadata"] = edge.metadata
    return d


def _lineage_from_dict(d: dict[str, Any]) -> LineageEdge:
    return LineageEdge(
        source=_noderef_from_dict(d["source"]),
        target=_noderef_from_dict(d["target"]),
        kind=EdgeKind(d["kind"]),
        metadata=d.get("metadata", {}),
    )


# ----- MigrationIR ----------------------------------------------------------
def ir_to_dict(ir: MigrationIR) -> dict[str, Any]:
    d: dict[str, Any] = {"ir_version": ir.ir_version}
    if ir.name:
        d["name"] = ir.name
    if ir.datasets:
        d["datasets"] = [_dataset_to_dict(x) for x in ir.datasets]
    if ir.jobs:
        d["jobs"] = [_job_to_dict(x) for x in ir.jobs]
    if ir.parameters:
        d["parameters"] = [_param_to_dict(x) for x in ir.parameters]
    if ir.lineage:
        d["lineage"] = [_lineage_to_dict(x) for x in ir.lineage]
    if ir.metadata:
        d["metadata"] = ir.metadata
    return d


def ir_from_dict(d: dict[str, Any]) -> MigrationIR:
    version = d.get("ir_version", "")
    if not is_compatible(version):
        raise IncompatibleIRVersionError(version or "<missing>")
    return MigrationIR(
        ir_version=version,
        name=d.get("name", ""),
        datasets=[_dataset_from_dict(x) for x in d.get("datasets", [])],
        jobs=[_job_from_dict(x) for x in d.get("jobs", [])],
        parameters=[_param_from_dict(x) for x in d.get("parameters", [])],
        lineage=[_lineage_from_dict(x) for x in d.get("lineage", [])],
        metadata=d.get("metadata", {}),
    )


def dumps(ir: MigrationIR, *, indent: Optional[int] = None) -> str:
    """Serialize an IR to a JSON string (keys sorted for stable diffs)."""
    return json.dumps(ir_to_dict(ir), indent=indent, sort_keys=True)


def loads(text: str) -> MigrationIR:
    """Parse a JSON string into a ``MigrationIR`` (raises on version mismatch)."""
    return ir_from_dict(json.loads(text))
