"""Round-trip + versioning tests for IR serialization."""

from __future__ import annotations

import pytest

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
    Parameter,
)
from migration_engine.ir.serialize import dumps, ir_to_dict, loads
from migration_engine.ir.transforms import Transform, TransformKind
from migration_engine.ir.types import CanonicalType, StructField
from migration_engine.ir.version import IR_SCHEMA_VERSION, IncompatibleIRVersionError


def _rich_ir() -> MigrationIR:
    ir = MigrationIR(name="db2_to_snowflake_sample", metadata={"jira": "DPE-1369"})
    src = ir.add_dataset(Dataset(
        id="src",
        name="HOME_FIXTURES",
        kind=DatasetKind.TABLE,
        database="BEDROCK",
        schema="CORE",
        primary_key=["FIXTURE_ID"],
        row_count=120_000,
        columns=[
            Column("FIXTURE_ID", CanonicalType.decimal(18, 0), ordinal=1, is_pii=False),
            Column("CUSTOMER_SSN", CanonicalType.string(11, fixed=True), ordinal=2, is_pii=True, tags=["pii"]),
            Column("PAYLOAD", CanonicalType.struct((
                StructField("k", CanonicalType.string(10)),
                StructField("v", CanonicalType.array(CanonicalType.integer(32))),
            )), ordinal=3),
            Column("LEGACY_COL", CanonicalType.unknown("DB2.PROPRIETARY"), ordinal=4),
        ],
    ))
    tgt = ir.add_dataset(Dataset(id="tgt", name="HOME_FIXTURES", kind=DatasetKind.TABLE, schema="ANALYTICS"))
    ir.add_job(Job(
        id="job1",
        name="load_home_fixtures",
        kind=JobKind.PARALLEL,
        parameters=[Parameter("ENV", default="prod", scope="environment")],
        transforms=[
            Transform(id="rd", kind=TransformKind.SOURCE, params={"dataset_id": "src"}),
            Transform(id="agg", kind=TransformKind.AGGREGATE,
                      params={"group_by": ["FIXTURE_ID"], "aggregations": [{"fn": "sum", "col": "AMT"}]}),
            Transform(id="wr", kind=TransformKind.TARGET, params={"dataset_id": "tgt"}),
        ],
        links=[
            Link(id="l1", from_transform="rd", to_transform="agg"),
            Link(id="l2", from_transform="agg", to_transform="wr"),
        ],
    ))
    ir.add_lineage(NodeRef(NodeKind.DATASET, src.id), NodeRef(NodeKind.JOB, "job1"), EdgeKind.READS)
    ir.add_lineage(NodeRef(NodeKind.JOB, "job1"), NodeRef(NodeKind.DATASET, tgt.id), EdgeKind.WRITES)
    return ir


def test_round_trip_preserves_everything():
    ir = _rich_ir()
    assert ir.validate() == []  # sanity: the fixture is structurally sound

    restored = loads(dumps(ir))

    # Same canonical dict on both sides == lossless round-trip.
    assert ir_to_dict(restored) == ir_to_dict(ir)


def test_round_trip_preserves_specific_details():
    ir = _rich_ir()
    restored = loads(dumps(ir))

    assert restored.name == "db2_to_snowflake_sample"
    assert restored.metadata["jira"] == "DPE-1369"

    src = restored.dataset("src")
    assert src is not None
    assert src.qualified_name == "BEDROCK.CORE.HOME_FIXTURES"
    assert src.column("CUSTOMER_SSN").is_pii is True
    assert src.column("CUSTOMER_SSN").type.signature() == "char(11)"
    assert src.column("PAYLOAD").type.signature() == "struct<k:string(10),v:array<integer32>>"
    assert src.column("LEGACY_COL").type.is_unknown
    assert src.column("LEGACY_COL").type.raw_source_type == "DB2.PROPRIETARY"

    job = restored.job("job1")
    assert job.kind is JobKind.PARALLEL
    assert [t.kind for t in job.transforms] == [TransformKind.SOURCE, TransformKind.AGGREGATE, TransformKind.TARGET]
    assert len(job.links) == 2


def test_dumps_is_deterministic():
    ir = _rich_ir()
    assert dumps(ir) == dumps(loads(dumps(ir)))


def test_default_version_is_current():
    assert MigrationIR().ir_version == IR_SCHEMA_VERSION


def test_incompatible_major_version_rejected():
    payload = dumps(_rich_ir()).replace(f'"ir_version": "{IR_SCHEMA_VERSION}"', '"ir_version": "9.0.0"')
    with pytest.raises(IncompatibleIRVersionError):
        loads(payload)


def test_missing_version_rejected():
    with pytest.raises(IncompatibleIRVersionError):
        loads("{}")
