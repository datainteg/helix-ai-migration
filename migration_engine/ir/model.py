"""The canonical IR model.

A ``MigrationIR`` is the unit of work the engine operates on. It can represent:

- **pure data migration** — a ``Dataset`` (table/view/file) plus read/write
  lineage, the highest-volume real pattern (DB2/Bedrock -> Snowflake), and
- **ETL job migration** — a ``Job`` holding a DAG of ``Transform`` nodes
  connected by ``Link`` edges (e.g. a DataStage parallel job).

Both share the same canonical types and lineage model, so dependency analysis,
impact analysis, codegen, and documentation work uniformly across them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from migration_engine.ir.transforms import Transform
from migration_engine.ir.types import CanonicalType
from migration_engine.ir.version import IR_SCHEMA_VERSION


class DatasetKind(str, Enum):
    TABLE = "table"
    VIEW = "view"
    FILE = "file"
    QUERY = "query"
    STREAM = "stream"


class JobKind(str, Enum):
    BATCH = "batch"
    PARALLEL = "parallel"        # DataStage parallel job
    SERVER = "server"            # DataStage server job
    SEQUENCE = "sequence"        # DataStage sequence (orchestration)
    PIPELINE = "pipeline"        # generic transform DAG


class NodeKind(str, Enum):
    DATASET = "dataset"
    JOB = "job"
    TRANSFORM = "transform"
    COLUMN = "column"


class EdgeKind(str, Enum):
    READS = "reads"              # job/transform reads a dataset
    WRITES = "writes"            # job/transform writes a dataset
    DERIVES = "derives"          # column/dataset derived from another
    DEPENDS_ON = "depends_on"    # ordering dependency (e.g. sequence step)
    CONTAINS = "contains"        # job contains transform, dataset contains column


@dataclass(frozen=True)
class NodeRef:
    """A typed reference to any IR node — the currency of the lineage graph."""

    kind: NodeKind
    id: str


@dataclass
class Column:
    name: str
    type: CanonicalType
    ordinal: int = 0
    description: str = ""
    tags: list[str] = field(default_factory=list)
    is_pii: bool = False
    metadata: dict = field(default_factory=dict)


@dataclass
class Dataset:
    id: str
    name: str
    kind: DatasetKind = DatasetKind.TABLE
    database: Optional[str] = None
    schema: Optional[str] = None
    columns: list[Column] = field(default_factory=list)
    row_count: Optional[int] = None
    primary_key: list[str] = field(default_factory=list)
    definition: Optional[str] = None    # view SQL / query text / file path
    properties: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)

    @property
    def qualified_name(self) -> str:
        parts = [p for p in (self.database, self.schema, self.name) if p]
        return ".".join(parts) if parts else self.name

    def column(self, name: str) -> Optional[Column]:
        return next((c for c in self.columns if c.name == name), None)


@dataclass
class Parameter:
    name: str
    type: Optional[CanonicalType] = None
    default: Optional[str] = None
    scope: str = "job"           # job | project | environment
    description: str = ""
    secret: bool = False


@dataclass
class Link:
    """An edge between two transforms' ports within a job DAG."""

    id: str
    from_transform: str
    to_transform: str
    from_port: str = "out"
    to_port: str = "in"
    metadata: dict = field(default_factory=dict)


@dataclass
class Job:
    id: str
    name: str
    kind: JobKind = JobKind.PIPELINE
    transforms: list[Transform] = field(default_factory=list)
    links: list[Link] = field(default_factory=list)
    parameters: list[Parameter] = field(default_factory=list)
    description: str = ""
    metadata: dict = field(default_factory=dict)

    def transform(self, transform_id: str) -> Optional[Transform]:
        return next((t for t in self.transforms if t.id == transform_id), None)


@dataclass
class LineageEdge:
    source: NodeRef
    target: NodeRef
    kind: EdgeKind
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ValidationIssue:
    """A structural problem found by ``MigrationIR.validate``."""

    severity: str                # "error" | "warning"
    code: str
    message: str


@dataclass
class MigrationIR:
    """Top-level IR container for one migration unit (or a related set)."""

    ir_version: str = IR_SCHEMA_VERSION
    name: str = ""
    datasets: list[Dataset] = field(default_factory=list)
    jobs: list[Job] = field(default_factory=list)
    parameters: list[Parameter] = field(default_factory=list)
    lineage: list[LineageEdge] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    # ----- lookups / builders ----------------------------------------------
    def dataset(self, dataset_id: str) -> Optional[Dataset]:
        return next((d for d in self.datasets if d.id == dataset_id), None)

    def job(self, job_id: str) -> Optional[Job]:
        return next((j for j in self.jobs if j.id == job_id), None)

    def add_dataset(self, dataset: Dataset) -> Dataset:
        self.datasets.append(dataset)
        return dataset

    def add_job(self, job: Job) -> Job:
        self.jobs.append(job)
        return job

    def add_lineage(self, source: NodeRef, target: NodeRef, kind: EdgeKind) -> LineageEdge:
        edge = LineageEdge(source=source, target=target, kind=kind)
        self.lineage.append(edge)
        return edge

    # ----- validation -------------------------------------------------------
    def validate(self) -> list[ValidationIssue]:
        """Return structural issues. Empty list == structurally sound IR.

        Pure and cheap — safe to run after every parse and before codegen.
        """
        issues: list[ValidationIssue] = []

        # Duplicate dataset / job ids.
        self._check_duplicates([d.id for d in self.datasets], "dataset", issues)
        self._check_duplicates([j.id for j in self.jobs], "job", issues)

        dataset_ids = {d.id for d in self.datasets}
        job_ids = {j.id for j in self.jobs}

        # Per-job structural checks: links must reference existing transforms,
        # transform ids unique, required params present.
        for job in self.jobs:
            t_ids = {t.id for t in job.transforms}
            self._check_duplicates([t.id for t in job.transforms], f"transform in job {job.id}", issues)
            for link in job.links:
                if link.from_transform not in t_ids:
                    issues.append(ValidationIssue(
                        "error", "link.dangling_source",
                        f"Job {job.id!r} link {link.id!r} references unknown source transform "
                        f"{link.from_transform!r}.",
                    ))
                if link.to_transform not in t_ids:
                    issues.append(ValidationIssue(
                        "error", "link.dangling_target",
                        f"Job {job.id!r} link {link.id!r} references unknown target transform "
                        f"{link.to_transform!r}.",
                    ))
            for t in job.transforms:
                for missing in t.missing_required_params():
                    issues.append(ValidationIssue(
                        "warning", "transform.missing_param",
                        f"Job {job.id!r} transform {t.id!r} ({t.kind.value}) is missing "
                        f"required param {missing!r}.",
                    ))

        # Lineage endpoints must resolve to known nodes.
        for edge in self.lineage:
            for role, ref in (("source", edge.source), ("target", edge.target)):
                if ref.kind is NodeKind.DATASET and ref.id not in dataset_ids:
                    issues.append(ValidationIssue(
                        "error", "lineage.dangling",
                        f"Lineage {edge.kind.value} {role} references unknown dataset {ref.id!r}.",
                    ))
                elif ref.kind is NodeKind.JOB and ref.id not in job_ids:
                    issues.append(ValidationIssue(
                        "error", "lineage.dangling",
                        f"Lineage {edge.kind.value} {role} references unknown job {ref.id!r}.",
                    ))

        return issues

    @staticmethod
    def _check_duplicates(ids: list[str], label: str, issues: list[ValidationIssue]) -> None:
        seen: set[str] = set()
        for i in ids:
            if i in seen:
                issues.append(ValidationIssue(
                    "error", "duplicate_id", f"Duplicate {label} id {i!r}."
                ))
            seen.add(i)
