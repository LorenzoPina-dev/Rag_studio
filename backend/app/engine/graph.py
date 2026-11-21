"""Graph utilities over pipeline contracts (engine-internal, domain-contract based)."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Iterable

from app.domain.contracts.pipeline import GraphEdge, GraphNode, PipelineGraph


@dataclass(frozen=True)
class EdgeRef:
    edge: GraphEdge
    source: GraphNode
    target: GraphNode


class PipelineGraphView:
    """Indexed, read-only view over a PipelineGraph for validation/planning."""

    def __init__(self, graph: PipelineGraph):
        self.graph = graph
        self.nodes_by_id: dict[str, GraphNode] = {n.id: n for n in graph.nodes}
        self.edges: list[GraphEdge] = list(graph.edges)
        self._incoming: dict[str, list[GraphEdge]] = defaultdict(list)
        self._outgoing: dict[str, list[GraphEdge]] = defaultdict(list)
        for e in self.edges:
            self._incoming[e.target_node_id].append(e)
            self._outgoing[e.source_node_id].append(e)

    @property
    def node_ids(self) -> set[str]:
        return set(self.nodes_by_id.keys())

    def node(self, node_id: str) -> GraphNode | None:
        return self.nodes_by_id.get(node_id)

    def incoming(self, node_id: str) -> list[GraphEdge]:
        return list(self._incoming.get(node_id, []))

    def outgoing(self, node_id: str) -> list[GraphEdge]:
        return list(self._outgoing.get(node_id, []))

    def in_degree(self, node_id: str) -> int:
        return len(self._incoming.get(node_id, []))

    def out_degree(self, node_id: str) -> int:
        return len(self._outgoing.get(node_id, []))

    def sources(self) -> list[GraphNode]:
        return [n for n in self.graph.nodes if self.in_degree(n.id) == 0]

    def sinks(self) -> list[GraphNode]:
        return [n for n in self.graph.nodes if self.out_degree(n.id) == 0]


def topological_sort(graph: PipelineGraph) -> tuple[list[str], list[list[str]]]:
    """Return (order, cycles_as_scc_like_components_or_remaining).

    If the graph is a DAG, cycles is empty and order contains all node ids in
    a valid topological order. If cycles exist, order contains the partial order
    of acyclic prefix nodes and cycles lists remaining strongly/cyclic groups
    (here: remaining nodes involved in cycles, grouped best-effort).
    """
    view = PipelineGraphView(graph)
    indeg: dict[str, int] = {nid: view.in_degree(nid) for nid in view.node_ids}
    q = deque(sorted([nid for nid, d in indeg.items() if d == 0]))
    order: list[str] = []
    while q:
        nid = q.popleft()
        order.append(nid)
        for e in view.outgoing(nid):
            tgt = e.target_node_id
            if tgt not in indeg:
                continue
            indeg[tgt] -= 1
            if indeg[tgt] == 0:
                q.append(tgt)
                # keep deterministic-ish by sorting queue contents not necessary here
    if len(order) == len(view.node_ids):
        return order, []
    remaining = [nid for nid in view.node_ids if nid not in set(order)]
    # best-effort cycle grouping: return one group (detailed SCC detection can be added later)
    return order, [sorted(remaining)] if remaining else []


def detect_cycles(graph: PipelineGraph) -> list[list[str]]:
    _, cycles = topological_sort(graph)
    return cycles


def dependency_levels(graph: PipelineGraph) -> list[list[str]]:
    """Compute parallelizable execution levels (Kahn's algorithm by waves)."""
    view = PipelineGraphView(graph)
    indeg: dict[str, int] = {nid: view.in_degree(nid) for nid in view.node_ids}
    current = sorted([nid for nid, d in indeg.items() if d == 0])
    seen: set[str] = set()
    levels: list[list[str]] = []
    while current:
        levels.append(list(current))
        next_wave_set: set[str] = set()
        for nid in current:
            seen.add(nid)
            for e in view.outgoing(nid):
                tgt = e.target_node_id
                if tgt in seen or tgt not in indeg:
                    continue
                indeg[tgt] -= 1
                if indeg[tgt] == 0:
                    next_wave_set.add(tgt)
        current = sorted(next_wave_set)
    # if cycles remain, append them as a final blocked level marker is not added; caller checks cycles
    return levels
