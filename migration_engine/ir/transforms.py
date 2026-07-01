"""Canonical transformation vocabulary.

ETL jobs (e.g. DataStage parallel jobs) are represented in the IR as a DAG of
``Transform`` nodes connected by links. Each transform has a vendor-neutral
``TransformKind`` plus a params dict. Target code generators implement each kind
for their dialect; gaps are surfaced (not silently dropped).

``deterministic=False`` marks a transform that has no deterministic mapping for
some/all targets and therefore requires AI-assist or manual conversion — the
Assessment engine counts these toward the manual-effort percentage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class TransformKind(str, Enum):
    """The canonical set of transform operations the IR understands."""

    # I/O
    SOURCE = "source"            # read a dataset
    TARGET = "target"            # write a dataset

    # row/column shaping
    PROJECT = "project"          # select / rename / reorder columns
    DERIVE = "derive"            # computed/derived columns (expressions)
    FILTER = "filter"            # WHERE predicate
    SORT = "sort"

    # set / combine
    JOIN = "join"
    LOOKUP = "lookup"
    UNION = "union"
    MERGE = "merge"

    # grouping / analytics
    AGGREGATE = "aggregate"
    WINDOW = "window"
    PIVOT = "pivot"
    UNPIVOT = "unpivot"

    # data hygiene / change tracking
    DEDUP = "dedup"
    HASH = "hash"
    CDC = "cdc"                  # change data capture
    SCD = "scd"                 # slowly changing dimension (type 1/2/3)

    # semi-structured / formats
    JSON_PARSE = "json_parse"
    XML_PARSE = "xml_parse"
    FORMAT_IO = "format_io"     # csv/excel/parquet/avro read or write

    # integration / escape hatch
    API_CALL = "api_call"
    CUSTOM = "custom"           # opaque vendor stage; carries raw definition


@dataclass(frozen=True)
class TransformSpec:
    """Catalog entry describing a transform kind."""

    kind: TransformKind
    summary: str
    required_params: tuple[str, ...] = ()
    deterministic_default: bool = True


# Coverage catalog. ``deterministic_default=False`` => generally needs
# AI-assist/manual handling unless a target explicitly supports it.
TRANSFORM_CATALOG: dict[TransformKind, TransformSpec] = {
    TransformKind.SOURCE: TransformSpec(TransformKind.SOURCE, "Read rows from a dataset", ("dataset_id",)),
    TransformKind.TARGET: TransformSpec(TransformKind.TARGET, "Write rows to a dataset", ("dataset_id",)),
    TransformKind.PROJECT: TransformSpec(TransformKind.PROJECT, "Select/rename/reorder columns", ("columns",)),
    TransformKind.DERIVE: TransformSpec(TransformKind.DERIVE, "Add derived/computed columns", ("expressions",)),
    TransformKind.FILTER: TransformSpec(TransformKind.FILTER, "Filter rows by predicate", ("predicate",)),
    TransformKind.SORT: TransformSpec(TransformKind.SORT, "Order rows", ("keys",)),
    TransformKind.JOIN: TransformSpec(TransformKind.JOIN, "Join two inputs", ("join_type", "on")),
    TransformKind.LOOKUP: TransformSpec(TransformKind.LOOKUP, "Lookup/enrich from a reference", ("on",)),
    TransformKind.UNION: TransformSpec(TransformKind.UNION, "Union compatible inputs"),
    TransformKind.MERGE: TransformSpec(TransformKind.MERGE, "Merge/upsert into target", ("keys",)),
    TransformKind.AGGREGATE: TransformSpec(TransformKind.AGGREGATE, "Group and aggregate", ("group_by", "aggregations")),
    TransformKind.WINDOW: TransformSpec(TransformKind.WINDOW, "Window/analytic functions", ("functions",)),
    TransformKind.PIVOT: TransformSpec(TransformKind.PIVOT, "Pivot rows to columns", ("on", "values"), False),
    TransformKind.UNPIVOT: TransformSpec(TransformKind.UNPIVOT, "Unpivot columns to rows", ("columns",), False),
    TransformKind.DEDUP: TransformSpec(TransformKind.DEDUP, "Remove duplicate rows", ("keys",)),
    TransformKind.HASH: TransformSpec(TransformKind.HASH, "Compute a hash/checksum column", ("columns",)),
    TransformKind.CDC: TransformSpec(TransformKind.CDC, "Capture inserts/updates/deletes", ("keys",), False),
    TransformKind.SCD: TransformSpec(TransformKind.SCD, "Slowly changing dimension", ("scd_type", "keys"), False),
    TransformKind.JSON_PARSE: TransformSpec(TransformKind.JSON_PARSE, "Parse/extract JSON", ("source_column",)),
    TransformKind.XML_PARSE: TransformSpec(TransformKind.XML_PARSE, "Parse/extract XML", ("source_column",), False),
    TransformKind.FORMAT_IO: TransformSpec(TransformKind.FORMAT_IO, "Read/write a file format", ("format",)),
    TransformKind.API_CALL: TransformSpec(TransformKind.API_CALL, "Call an external API", ("endpoint",), False),
    TransformKind.CUSTOM: TransformSpec(TransformKind.CUSTOM, "Opaque/custom stage", (), False),
}


@dataclass
class Transform:
    """A node in a job's transform DAG."""

    id: str
    kind: TransformKind
    name: str = ""
    params: dict = field(default_factory=dict)
    inputs: list[str] = field(default_factory=list)   # input port ids
    outputs: list[str] = field(default_factory=list)  # output port ids
    deterministic: Optional[bool] = None              # None => use catalog default
    raw: Optional[str] = None                         # original vendor stage definition
    metadata: dict = field(default_factory=dict)

    @property
    def is_deterministic(self) -> bool:
        """Effective determinism: explicit flag wins, else the catalog default."""
        if self.deterministic is not None:
            return self.deterministic
        spec = TRANSFORM_CATALOG.get(self.kind)
        return spec.deterministic_default if spec else False

    def missing_required_params(self) -> list[str]:
        """Required params (per catalog) absent from this transform's params."""
        spec = TRANSFORM_CATALOG.get(self.kind)
        if not spec:
            return []
        return [p for p in spec.required_params if p not in self.params]
