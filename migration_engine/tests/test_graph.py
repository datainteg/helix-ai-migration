"""Tests for dependency + impact graph analysis."""

from __future__ import annotations

import pytest

from migration_engine.graph.analysis import (
    GraphCycleError,
    build_dependency_graph,
    impact_of,
)
from migration_engine.ir.model import (
    Dataset,
    EdgeKind,
    Job,
    JobKind,
    MigrationIR,
    NodeKind,
    NodeRef,
)


def _ds(ir: MigrationIR, dataset_id: str) -> NodeRef:
    ir.add_dataset(Dataset(id=dataset_id, name=dataset_id.upper()))
    return NodeRef(NodeKind.DATASET, dataset_id)


def _chain_ir() -> MigrationIR:
    # src -> job -> stg -> report   (a typical Bedrock -> Snowflake -> BI chain)
    ir = MigrationIR(name="chain")
    src = _ds(ir, "src")
    stg = _ds(ir, "stg")
    report = _ds(ir, "report")
    ir.add_job(Job(id="job", name="load", kind=JobKind.PARALLEL))
    job = NodeRef(NodeKind.JOB, "job")
    ir.add_lineage(src, job, EdgeKind.READS)
    ir.add_lineage(job, stg, EdgeKind.WRITES)
    ir.add_lineage(stg, report, EdgeKind.DERIVES)
    return ir


def test_graph_includes_all_datasets_and_jobs_as_nodes():
    ir = _chain_ir()
    g = build_dependency_graph(ir)
    assert NodeRef(NodeKind.DATASET, "src") in g.nodes
    assert NodeRef(NodeKind.JOB, "job") in g.nodes
    assert len(g.nodes) == 4  # 3 datasets + 1 job


def test_impact_is_transitive_downstream():
    ir = _chain_ir()
    # Changing src impacts the job, the staging table, and the report.
    impacted = impact_of(ir, NodeRef(NodeKind.DATASET, "src"))
    assert impacted == {
        NodeRef(NodeKind.JOB, "job"),
        NodeRef(NodeKind.DATASET, "stg"),
        NodeRef(NodeKind.DATASET, "report"),
    }


def test_upstream_returns_prerequisites():
    ir = _chain_ir()
    g = build_dependency_graph(ir)
    ups = g.upstream(NodeRef(NodeKind.DATASET, "report"))
    assert ups == {
        NodeRef(NodeKind.DATASET, "stg"),
        NodeRef(NodeKind.JOB, "job"),
        NodeRef(NodeKind.DATASET, "src"),
    }


def test_roots_and_leaves():
    ir = _chain_ir()
    g = build_dependency_graph(ir)
    assert g.roots() == {NodeRef(NodeKind.DATASET, "src")}
    assert g.leaves() == {NodeRef(NodeKind.DATASET, "report")}


def test_topological_order_prerequisites_first_and_stable():
    ir = _chain_ir()
    g = build_dependency_graph(ir)
    order = g.topological_order()
    pos = {n: i for i, n in enumerate(order)}
    assert pos[NodeRef(NodeKind.DATASET, "src")] < pos[NodeRef(NodeKind.JOB, "job")]
    assert pos[NodeRef(NodeKind.JOB, "job")] < pos[NodeRef(NodeKind.DATASET, "stg")]
    assert pos[NodeRef(NodeKind.DATASET, "stg")] < pos[NodeRef(NodeKind.DATASET, "report")]
    assert g.topological_order() == order  # deterministic


def test_cycle_detected():
    ir = MigrationIR(name="cyclic")
    a = _ds(ir, "a")
    b = _ds(ir, "b")
    ir.add_lineage(a, b, EdgeKind.DERIVES)
    ir.add_lineage(b, a, EdgeKind.DERIVES)
    g = build_dependency_graph(ir)
    assert g.has_cycle() is True
    with pytest.raises(GraphCycleError):
        g.topological_order()
