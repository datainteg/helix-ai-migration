"""Tests for the IR model + structural validation."""

from __future__ import annotations

from migration_engine.ir.model import (
    Column,
    Dataset,
    DatasetKind,
    EdgeKind,
    Job,
    JobKind,
    Link,
    MigrationIR,
    NodeKind,
    NodeRef,
)
from migration_engine.ir.transforms import Transform, TransformKind
from migration_engine.ir.types import CanonicalType


def _table(dataset_id: str, name: str) -> Dataset:
    return Dataset(
        id=dataset_id,
        name=name,
        kind=DatasetKind.TABLE,
        database="BEDROCK",
        schema="CORE",
        columns=[
            Column("ACCOUNT_ID", CanonicalType.decimal(18, 0)),
            Column("BALANCE", CanonicalType.decimal(15, 2)),
        ],
    )


def test_qualified_name_joins_parts():
    assert _table("d1", "ACCT").qualified_name == "BEDROCK.CORE.ACCT"
    assert Dataset(id="d2", name="ACCT").qualified_name == "ACCT"


def test_valid_ir_has_no_issues():
    ir = MigrationIR(name="bedrock_acct_to_sf")
    src = ir.add_dataset(_table("src", "ACCT"))
    tgt = ir.add_dataset(_table("tgt", "ACCT"))
    ir.add_lineage(NodeRef(NodeKind.DATASET, src.id), NodeRef(NodeKind.DATASET, tgt.id), EdgeKind.DERIVES)
    assert ir.validate() == []


def test_duplicate_dataset_id_flagged():
    ir = MigrationIR()
    ir.add_dataset(_table("dup", "A"))
    ir.add_dataset(_table("dup", "B"))
    codes = {i.code for i in ir.validate()}
    assert "duplicate_id" in codes


def test_dangling_link_and_lineage_flagged():
    ir = MigrationIR()
    job = Job(
        id="j1",
        name="xform",
        kind=JobKind.PARALLEL,
        transforms=[Transform(id="t1", kind=TransformKind.SOURCE, params={"dataset_id": "src"})],
        links=[Link(id="l1", from_transform="t1", to_transform="MISSING")],
    )
    ir.add_job(job)
    ir.add_lineage(
        NodeRef(NodeKind.DATASET, "ghost"),
        NodeRef(NodeKind.JOB, "j1"),
        EdgeKind.READS,
    )
    codes = {i.code for i in ir.validate()}
    assert "link.dangling_target" in codes
    assert "lineage.dangling" in codes


def test_missing_required_param_is_warning_not_error():
    ir = MigrationIR()
    ir.add_job(Job(
        id="j1",
        name="x",
        transforms=[Transform(id="t1", kind=TransformKind.JOIN, params={"join_type": "inner"})],
    ))
    issues = ir.validate()
    warnings = [i for i in issues if i.code == "transform.missing_param"]
    assert len(warnings) == 1 and warnings[0].severity == "warning"
