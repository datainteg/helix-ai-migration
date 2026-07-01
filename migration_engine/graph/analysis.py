"""Directed dependency graph + analysis built from IR lineage.

Edge convention: ``source -> target`` is a *flow* edge (data/control flows from
source to target), so **target depends on source**. Therefore:
- ``downstream(n)`` = everything that consumes/derives from ``n`` (impact set),
- ``upstream(n)``   = everything ``n`` depends on (prerequisites),
- ``topological_order()`` lists prerequisites before dependents.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from migration_engine.ir.model import MigrationIR, NodeKind, NodeRef


class GraphCycleError(ValueError):
    """Raised when a topological order is requested on a cyclic graph."""

    def __init__(self, cycle: list[NodeRef]) -> None:
        self.cycle = cycle
        readable = " -> ".join(f"{n.kind.value}:{n.id}" for n in cycle)
        super().__init__(f"Dependency graph contains a cycle: {readable}")


@dataclass
class DependencyGraph:
    """A directed graph of IR nodes keyed by ``NodeRef``."""

    nodes: set[NodeRef] = field(default_factory=set)
    out_edges: dict[NodeRef, set[NodeRef]] = field(default_factory=dict)
    in_edges: dict[NodeRef, set[NodeRef]] = field(default_factory=dict)

    # ----- construction -----------------------------------------------------
    def add_node(self, node: NodeRef) -> None:
        self.nodes.add(node)
        self.out_edges.setdefault(node, set())
        self.in_edges.setdefault(node, set())

    def add_edge(self, source: NodeRef, target: NodeRef) -> None:
        self.add_node(source)
        self.add_node(target)
        self.out_edges[source].add(target)
        self.in_edges[target].add(source)

    # ----- queries ----------------------------------------------------------
    def roots(self) -> set[NodeRef]:
        """Nodes with no prerequisites (no incoming edges)."""
        return {n for n in self.nodes if not self.in_edges.get(n)}

    def leaves(self) -> set[NodeRef]:
        """Nodes nothing depends on (no outgoing edges)."""
        return {n for n in self.nodes if not self.out_edges.get(n)}

    def downstream(self, node: NodeRef) -> set[NodeRef]:
        """Transitive consumers/dependents of ``node`` (its impact set)."""
        return self._reachable(node, self.out_edges)

    def upstream(self, node: NodeRef) -> set[NodeRef]:
        """Transitive prerequisites ``node`` depends on."""
        return self._reachable(node, self.in_edges)

    def _reachable(self, start: NodeRef, edges: dict[NodeRef, set[NodeRef]]) -> set[NodeRef]:
        seen: set[NodeRef] = set()
        queue: deque[NodeRef] = deque(edges.get(start, set()))
        while queue:
            cur = queue.popleft()
            if cur in seen or cur == start:
                continue
            seen.add(cur)
            queue.extend(edges.get(cur, set()))
        return seen

    def topological_order(self) -> list[NodeRef]:
        """Kahn's algorithm; prerequisites first. Raises on cycles.

        Ties are broken deterministically by ``(kind, id)`` so the order is
        stable across runs (important for reproducible migration plans).
        """
        indeg = {n: len(self.in_edges.get(n, set())) for n in self.nodes}
        ready = sorted((n for n, d in indeg.items() if d == 0), key=_sort_key)
        order: list[NodeRef] = []
        ready_dq: deque[NodeRef] = deque(ready)
        while ready_dq:
            node = ready_dq.popleft()
            order.append(node)
            for nxt in sorted(self.out_edges.get(node, set()), key=_sort_key):
                indeg[nxt] -= 1
                if indeg[nxt] == 0:
                    ready_dq.append(nxt)
        if len(order) != len(self.nodes):
            raise GraphCycleError(self._find_cycle())
        return order

    def has_cycle(self) -> bool:
        try:
            self.topological_order()
            return False
        except GraphCycleError:
            return True

    def _find_cycle(self) -> list[NodeRef]:
        """Return one cycle as a node list (best-effort, for diagnostics)."""
        color: dict[NodeRef, int] = {n: 0 for n in self.nodes}  # 0=white,1=grey,2=black
        stack: list[NodeRef] = []

        def dfs(node: NodeRef) -> list[NodeRef] | None:
            color[node] = 1
            stack.append(node)
            for nxt in sorted(self.out_edges.get(node, set()), key=_sort_key):
                if color[nxt] == 1:  # back-edge -> cycle
                    return stack[stack.index(nxt):] + [nxt]
                if color[nxt] == 0:
                    found = dfs(nxt)
                    if found:
                        return found
            color[node] = 2
            stack.pop()
            return None

        for n in sorted(self.nodes, key=_sort_key):
            if color[n] == 0:
                found = dfs(n)
                if found:
                    return found
        return []


def _sort_key(node: NodeRef) -> tuple[str, str]:
    return (node.kind.value, node.id)


def build_dependency_graph(ir: MigrationIR) -> DependencyGraph:
    """Build the dependency graph from an IR.

    All datasets and jobs become nodes (even if isolated); lineage edges become
    directed flow edges. Other node kinds (columns/transforms) are included only
    if they appear in lineage.
    """
    graph = DependencyGraph()
    for ds in ir.datasets:
        graph.add_node(NodeRef(NodeKind.DATASET, ds.id))
    for job in ir.jobs:
        graph.add_node(NodeRef(NodeKind.JOB, job.id))
    for edge in ir.lineage:
        graph.add_edge(edge.source, edge.target)
    return graph


def impact_of(ir: MigrationIR, node: NodeRef) -> set[NodeRef]:
    """Convenience: the transitive blast radius of ``node`` within ``ir``."""
    return build_dependency_graph(ir).downstream(node)
