"""Execution planning: DAG ordering and dependency-aware scheduling plans."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.contracts.pipeline import PipelineGraph

from .graph import dependency_levels, detect_cycles, topological_sort


@dataclass
class PlannedNode:
    node_id: str
    level: int
    dependencies: list[str] = field(default_factory=list)


@dataclass
class ExecutionPlan:
    valid: bool
    order: list[str] = field(default_factory=list)
    levels: list[list[str]] = field(default_factory=list)
    nodes: list[PlannedNode] = field(default_factory=list)
    cycles: list[list[str]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def is_parallelizable(self) -> bool:
        return any(len(level) > 1 for level in self.levels)


def build_execution_plan(graph: PipelineGraph) -> ExecutionPlan:
    """Build a dependency-resolved execution plan from a pipeline graph.

    - Produces a topological order and parallel execution levels when acyclic.
    - Reports cycles and marks the plan invalid when cycles exist.
    - Does not execute nodes; runtime/scheduler concerns are handled elsewhere.
    """
    order, cycles = topological_sort(graph)
    if cycles:
        return ExecutionPlan(valid=False, order=order, levels=[], nodes=[], cycles=cycles, errors=["Graph contains cycles and cannot be scheduled."])

    levels = dependency_levels(graph)
    # build dependency map
    deps: dict[str, list[str]] = {n.id: [] for n in graph.nodes}
    for e in graph.edges:
        deps.setdefault(e.target_node_id, []).append(e.source_node_id)

    nodes: list[PlannedNode] = []
    level_index = {nid: i for i, lvl in enumerate(levels) for nid in lvl}
    for nid in order:
        nodes.append(PlannedNode(node_id=nid, level=level_index.get(nid, 0), dependencies=sorted(set(deps.get(nid, [])))))

    return ExecutionPlan(valid=True, order=order, levels=levels, nodes=nodes, cycles=[], errors=[])
