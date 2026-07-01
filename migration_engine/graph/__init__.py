"""Dependency & impact analysis over the IR lineage graph.

Pure graph algorithms — no I/O, no vendor knowledge. Builds a directed graph
from ``MigrationIR.lineage`` where an edge ``source -> target`` means *data or
control flows from source to target*, hence **target depends on source**.

This powers two headline capabilities:
- **impact analysis** — the transitive downstream of a node (its blast radius),
  e.g. "remove column X / decommission table Y -> what jobs/reports break?".
- **execution ordering** — a topological order so upstream units migrate first.
"""

from __future__ import annotations

from migration_engine.graph.analysis import (
    DependencyGraph,
    GraphCycleError,
    build_dependency_graph,
    impact_of,
)

__all__ = [
    "DependencyGraph",
    "GraphCycleError",
    "build_dependency_graph",
    "impact_of",
]
