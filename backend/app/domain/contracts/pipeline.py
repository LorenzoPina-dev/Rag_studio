"""Pipeline and graph domain contracts.

Represents logical pipeline definitions, versioned immutable snapshots, and
graph structure used by validation/planning/execution engines.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .node import NodeConfig


class PipelineStatus(str, Enum):
    DRAFT = "draft"
    VALID = "valid"
    INVALID = "invalid"
    RUNNING = "running"
    FAILED = "failed"
    ARCHIVED = "archived"


class PipelineEnvironment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class GraphNode(BaseModel):
    """A node instance within a pipeline graph."""

    model_config = ConfigDict(extra="forbid")

    id: str
    definition_id: str
    definition_version: str | None = None
    name: str | None = None
    kind: str | None = None
    position: dict[str, float] = Field(default_factory=dict)
    config: NodeConfig | dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    """A directed, typed connection between node ports."""

    model_config = ConfigDict(extra="forbid")

    id: str
    source_node_id: str
    source_port_id: str
    target_node_id: str
    target_port_id: str
    data_type: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PipelineGraph(BaseModel):
    """Graph structure: nodes, edges, and graph-level metadata."""

    model_config = ConfigDict(extra="forbid")

    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def node_ids(self) -> set[str]:
        return {n.id for n in self.nodes}

    def adjacency(self) -> dict[str, list[str]]:
        adj: dict[str, list[str]] = {n.id: [] for n in self.nodes}
        for e in self.edges:
            adj.setdefault(e.source_node_id, []).append(e.target_node_id)
        return adj


class PipelineSpec(BaseModel):
    """Mutable pipeline definition (working draft/current state)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    project_id: str
    name: str
    description: str | None = None
    environment: PipelineEnvironment | str = PipelineEnvironment.DEVELOPMENT
    status: PipelineStatus | str = PipelineStatus.DRAFT
    graph: PipelineGraph = Field(default_factory=PipelineGraph)
    tags: list[str] = Field(default_factory=list)
    current_version: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PipelineVersion(BaseModel):
    """Immutable snapshot of a pipeline definition/config/graph."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    pipeline_id: str
    version: str
    graph: PipelineGraph
    status: PipelineStatus | str = PipelineStatus.DRAFT
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str | None = None
    changelog: str | None = None
    checksum: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
