"""Core node contracts.

These abstractions define the generic, algorithm-agnostic node system:
specification/ports/parameters, instance configuration, runtime context,
implementation interface, execution result, and immutable version metadata.

No FastAPI, database, provider SDK, or algorithm-specific logic belongs here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from .data import ArtifactRef, LineageRecord


class NodeKind(str, Enum):
    SOURCE = "source"
    PARSER = "parser"
    PROCESSOR = "processor"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    VECTOR_STORE = "vector-store"
    RETRIEVAL = "retrieval"
    RERANKING = "reranking"
    SELECTION = "selection"
    CONTEXT = "context"
    GENERATION = "generation"
    VALIDATION = "validation"
    EVALUATION = "evaluation"
    CONTROL = "control"
    CUSTOM = "custom"


class NodeStatus(str, Enum):
    DRAFT = "draft"
    STABLE = "stable"
    DEPRECATED = "deprecated"
    EXPERIMENTAL = "experimental"


class NodeCapability(str, Enum):
    SYNC = "sync"
    ASYNC = "async"
    STREAMING = "streaming"
    BATCH = "batch"
    CACHEABLE = "cacheable"
    GPU = "gpu"
    STATEFUL = "stateful"


class PortDirection(str, Enum):
    INPUT = "input"
    OUTPUT = "output"


class PortMultiplicity(str, Enum):
    ONE = "one"
    MANY = "many"
    OPTIONAL = "optional"


class ParameterType(str, Enum):
    TEXT = "text"
    NUMBER = "number"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    SELECT = "select"
    MULTI_SELECT = "multi_select"
    TEXTAREA = "textarea"
    JSON = "json"
    SECRET_REF = "secret_ref"
    MODEL_REF = "model_ref"
    DATASET_REF = "dataset_ref"
    PROVIDER_REF = "provider_ref"


class PortSpec(BaseModel):
    """Typed, UI-describable port definition for a node."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    name: str
    direction: PortDirection
    data_types: list[str] = Field(default_factory=list)
    required: bool = True
    multiplicity: PortMultiplicity = PortMultiplicity.ONE
    description: str | None = None
    # UI metadata kept generic; frontend mapping can derive labels/colors from data types/category
    ui: dict[str, Any] = Field(default_factory=dict)

    def accepts(self, data_type: str) -> bool:
        if not self.data_types or "any" in self.data_types:
            return True
        return data_type in self.data_types


class ParameterSpec(BaseModel):
    """Declarative parameter definition driving validation and UI forms."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str
    label: str
    type: ParameterType
    description: str | None = None
    required: bool = False
    default: Any = None
    options: list[Any] = Field(default_factory=list)
    min_value: float | int | None = None
    max_value: float | int | None = None
    min_length: int | None = None
    max_length: int | None = None
    pattern: str | None = None
    unit: str | None = None
    visible_when: dict[str, Any] | None = None
    secret: bool = False
    advanced: bool = False
    ui: dict[str, Any] = Field(default_factory=dict)


class NodeSpec(BaseModel):
    """Static, registry/catalog definition of a node type."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    name: str
    description: str
    category: str
    kind: NodeKind | str
    version: str = "1.0.0"
    source: str = "builtin"  # builtin | custom | plugin
    status: NodeStatus = NodeStatus.STABLE
    tags: list[str] = Field(default_factory=list)
    capabilities: list[NodeCapability] = Field(default_factory=list)
    inputs: list[PortSpec] = Field(default_factory=list)
    outputs: list[PortSpec] = Field(default_factory=list)
    parameters: list[ParameterSpec] = Field(default_factory=list)
    documentation: str | None = None
    icon: str | None = None
    accent: str | None = None
    limitations: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def input_map(self) -> dict[str, PortSpec]:
        return {p.id: p for p in self.inputs}

    @property
    def output_map(self) -> dict[str, PortSpec]:
        return {p.id: p for p in self.outputs}

    @property
    def parameter_map(self) -> dict[str, ParameterSpec]:
        return {p.key: p for p in self.parameters}


class NodeConfig(BaseModel):
    """Validated instance configuration for a graph node."""

    model_config = ConfigDict(extra="forbid")

    values: dict[str, Any] = Field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, default)

    @classmethod
    def with_defaults(cls, spec: NodeSpec, overrides: Mapping[str, Any] | None = None) -> "NodeConfig":
        values: dict[str, Any] = {p.key: p.default for p in spec.parameters}
        if overrides:
            values.update(dict(overrides))
        return cls(values=values)


class NodeVersion(BaseModel):
    """Immutable version/compatibility metadata for an implementation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    node_id: str
    version: str
    implementation_ref: str
    contract_version: str = "1.0"
    compatible_with: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    checksum: str | None = None
    changelog: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class NodeResult(BaseModel):
    """Typed execution result for a single node run."""

    model_config = ConfigDict(extra="forbid")

    node_id: str
    status: str = "completed"  # completed | failed | skipped
    outputs: dict[str, Any] = Field(default_factory=dict)
    output_artifacts: dict[str, ArtifactRef] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    logs: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    lineage: list[LineageRecord] = Field(default_factory=list)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = None
    cached: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


@runtime_checkable
class NodeRuntimeContext(Protocol):
    """Execution-time services/capabilities injected into node implementations."""

    execution_id: str
    pipeline_id: str
    pipeline_version: str
    node_execution_id: str
    run_id: str | None

    def emit_event(self, event_type: str, payload: Mapping[str, Any] | None = None) -> None: ...
    def log(self, level: str, message: str, **fields: Any) -> None: ...
    def is_cancelled(self) -> bool: ...
    async def store_artifact(self, name: str, data: Any, *, content_type: str | None = None, metadata: Mapping[str, Any] | None = None) -> ArtifactRef: ...
    async def load_artifact(self, ref: ArtifactRef | str) -> Any: ...
    def resolve_secret(self, ref: str) -> str | None: ...
    def get_provider(self, provider_ref: str) -> Any: ...


class NodeImplementation(ABC):
    """Algorithm-agnostic execution contract for all node types."""

    @abstractmethod
    def spec(self) -> NodeSpec:
        """Return the static node specification."""

    def version(self) -> NodeVersion:
        spec = self.spec()
        return NodeVersion(node_id=spec.id, version=spec.version, implementation_ref=f"{self.__class__.__module__}.{self.__class__.__name__}")

    def validate_config(self, config: NodeConfig) -> list[str]:
        """Return validation error messages for instance config (empty if valid)."""
        errors: list[str] = []
        spec = self.spec()
        for p in spec.parameters:
            if p.required and p.key not in config.values and p.default is None:
                errors.append(f"Missing required parameter: {p.key}")
            if p.key in config.values and p.options and config.values[p.key] not in p.options and p.type == ParameterType.SELECT:
                errors.append(f"Invalid option for {p.key}: {config.values[p.key]}")
        return errors

    def validate_inputs(self, inputs: Mapping[str, Any], config: NodeConfig) -> list[str]:
        """Return validation error messages for bound inputs (empty if valid)."""
        errors: list[str] = []
        spec = self.spec()
        for port in spec.inputs:
            if port.required and port.id not in inputs:
                errors.append(f"Missing required input: {port.id}")
        return errors

    @abstractmethod
    async def execute(self, inputs: Mapping[str, Any], config: NodeConfig, context: NodeRuntimeContext) -> NodeResult:
        """Execute the node and return typed outputs/metrics/lineage/artifacts."""
