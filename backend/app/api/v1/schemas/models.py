"""Frontend-compatible API schemas (Pydantic v2).

These models mirror the shapes expected by `frontend/src/types/index.ts` and
`frontend/src/api/*.api.ts`. Keep field names/values stable for compatibility.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class APIModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")


# --- Common / system ---
class Workspace(APIModel):
    id: str
    name: str
    plan: str
    role: str


class SystemStatus(APIModel):
    state: Literal["operational", "degraded"]
    version: str
    python: str
    connected: bool
    branch: str
    errors: int
    warnings: int


class SearchResult(APIModel):
    id: str
    type: Literal["pipeline", "project", "dataset", "model", "experiment", "node", "page"]
    title: str
    subtitle: str
    href: str


class ActivityItem(APIModel):
    id: str
    title: str
    detail: str
    time: str
    type: Literal["pipeline", "evaluation", "dataset", "custom-node"]


# --- Projects / dashboard ---
class Project(APIModel):
    id: str
    name: str
    description: str
    health: Literal["healthy", "warning", "draft"]
    pipelineCount: int
    chunkCount: int
    editedAt: str
    updatedAt: str
    accent: str
    market: str | None = None


class ProjectCreate(APIModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    description: str | None = None


class ProjectUpdate(APIModel):
    model_config = ConfigDict(extra="allow")
    name: str | None = None
    description: str | None = None
    health: Literal["healthy", "warning", "draft"] | None = None
    market: str | None = None


class DashboardMetrics(APIModel):
    activeProjects: int
    activeProjectsDelta: str
    pipelines: int
    pipelinesDelta: str
    executions: int
    executionsDelta: str
    faithfulness: float
    faithfulnessDelta: str
    sparks: dict[str, list[int]]
    resources: dict[str, str]


class PipelineSummary(APIModel):
    id: str
    projectId: str
    projectName: str
    name: str
    nodeCount: int
    connectionCount: int
    status: Literal["draft", "valid", "running", "failed"]
    environment: Literal["Development", "Staging", "Production"]
    updatedAt: str
    lastRunStatus: Literal["passed", "failed", "draft"] | None = None
    lastRunAt: str | None = None


class DashboardData(APIModel):
    metrics: DashboardMetrics
    projects: list[Project]
    pipelines: list[PipelineSummary]
    activity: list[ActivityItem]


# --- Nodes / pipeline graph ---
class PortDefinition(APIModel):
    id: str
    label: str
    dataType: Literal["documents", "chunks", "embedding", "text", "json", "query", "array", "any"]
    typeLabel: str
    color: str
    required: bool | None = None


class ParamDefinition(APIModel):
    key: str
    label: str
    type: Literal["text", "number", "select", "boolean", "textarea"]
    defaultValue: str | int | float | bool
    unit: str | None = None
    help: str | None = None
    options: list[str] | None = None


class NodeDefinition(APIModel):
    id: str
    name: str
    category: str
    kind: str
    description: str
    summary: str | None = None
    documentation: str | None = None
    accent: str
    inputs: list[PortDefinition] = Field(default_factory=list)
    outputs: list[PortDefinition] = Field(default_factory=list)
    params: list[ParamDefinition] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    custom: bool | None = None
    version: str | None = None


class NodeCatalogCategory(APIModel):
    category: str
    description: str
    nodes: list[NodeDefinition]


class NodeImplementationResponse(APIModel):
    definitionId: str
    name: str
    implementation: str
    source: str
    language: str = "python"
    reference: bool
    inputs: list[PortDefinition] = Field(default_factory=list)
    outputs: list[PortDefinition] = Field(default_factory=list)
    parameters: list[ParamDefinition] = Field(default_factory=list)


class XYPosition(APIModel):
    x: float
    y: float


class PipelineNode(APIModel):
    id: str
    definitionId: str
    name: str
    category: str
    kind: str
    accent: str
    position: XYPosition
    config: dict[str, Any] = Field(default_factory=dict)
    inputs: list[PortDefinition] = Field(default_factory=list)
    outputs: list[PortDefinition] = Field(default_factory=list)
    status: Literal["idle", "running", "completed", "failed"] | None = None
    durationMs: int | None = None


class PipelineEdge(APIModel):
    id: str
    source: str
    target: str
    sourceHandle: str | None = None
    targetHandle: str | None = None
    dataType: str | None = None


class LastRun(APIModel):
    status: Literal["completed", "failed"]
    at: str
    latencyMs: int
    tokens: int
    cost: float
    output: str
    sources: int


class Pipeline(APIModel):
    id: str
    projectId: str
    name: str
    description: str
    environment: Literal["Development", "Staging", "Production"]
    status: Literal["draft", "valid", "running", "failed"]
    version: str
    updatedAt: str
    nodes: list[PipelineNode] = Field(default_factory=list)
    edges: list[PipelineEdge] = Field(default_factory=list)
    lastRun: LastRun | None = None


class PipelineCreate(APIModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    projectId: str | None = None
    template: Literal["blank", "starter"] | None = None


class PipelineUpdate(APIModel):
    model_config = ConfigDict(extra="allow")


class PipelineRunRequest(APIModel):
    """Optional run overrides; the frontend can call run with no body."""

    model_config = ConfigDict(extra="allow")
    query: str | None = None
    inputs: dict[str, dict[str, Any]] | None = None


class ValidationIssue(APIModel):
    id: str
    severity: Literal["error", "warning"]
    message: str
    nodeId: str | None = None


class ValidationResult(APIModel):
    valid: bool
    errors: list[ValidationIssue] = Field(default_factory=list)
    warnings: list[ValidationIssue] = Field(default_factory=list)
    checkedAt: str


# --- Executions / results ---
class NodeRun(APIModel):
    nodeId: str
    name: str
    kind: str
    status: Literal["pending", "running", "completed", "failed", "skipped"]
    durationMs: int
    outputCount: int
    accent: str
    startedAt: str | None = None


class NodeExecutionRecord(APIModel):
    """Persisted per-node execution detail (projection of NodeExecutionRecord DB row)."""

    id: str
    executionId: str
    nodeId: str
    nodeDefinitionId: str | None = None
    status: str
    attempt: int = 1
    startedAt: str | None = None
    finishedAt: str | None = None
    durationMs: int | None = None
    outputRefs: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None
    cached: bool = False


class LogEntry(APIModel):
    id: str
    timestamp: str
    level: Literal["INFO", "WARN", "ERROR", "DONE", "DEBUG"]
    message: str
    node: str | None = None


class Execution(APIModel):
    id: str
    runNumber: int
    pipelineId: str
    pipelineName: str
    status: Literal["queued", "running", "completed", "failed", "stopped"]
    startedAt: str
    finishedAt: str | None = None
    durationMs: int
    tokens: int
    cost: float
    environment: str
    trigger: str
    traceId: str
    nodeRuns: list[NodeRun] = Field(default_factory=list)
    logs: list[LogEntry] = Field(default_factory=list)
    stagesCached: bool | None = None
    errors: int = 0
    warnings: int = 0


class RetrievedDocument(APIModel):
    id: str
    rank: int
    title: str
    source: str
    chunkId: str
    excerpt: str
    content: str
    score: float
    tokens: int
    page: int
    offset: str
    mime: str


class LineageStep(APIModel):
    label: str
    detail: str
    indent: int
    accent: str | None = None


class EmbeddingInspector(APIModel):
    model: str
    dimensions: int
    cosineSimilarity: float
    values: list[float]
    norm: str
    dtype: str


class AnswerMeta(APIModel):
    model: str
    temperature: float
    citations: int


class RuntimeBreakdown(APIModel):
    label: str
    ms: int
    color: str


class ExecutionRuntime(APIModel):
    latencyMs: int
    peakMemoryMb: int
    tokensPerSecond: int
    breakdown: list[RuntimeBreakdown]


class NodeOutputSummary(APIModel):
    nodeId: str
    name: str
    detail: str
    accent: str
    kind: str = "node"
    selected: bool | None = None


class StepMetric(APIModel):
    label: str
    value: str


class StepItem(APIModel):
    id: str
    title: str
    source: str
    content: str
    meta: dict[str, Any] = Field(default_factory=dict)


class StepOutput(APIModel):
    nodeId: str
    name: str
    kind: str
    detail: str
    accent: str
    status: str
    durationMs: int
    outputPorts: list[str] = Field(default_factory=list)
    text: str | None = None
    items: list[StepItem] = Field(default_factory=list)
    metrics: list[StepMetric] = Field(default_factory=list)
    searchHint: str = ""


class ExecutionResult(APIModel):
    id: str
    executionId: str
    query: str
    retrievedCount: int
    selectedCount: int
    errorCount: int
    stages: list[str]
    traceId: str
    documents: list[RetrievedDocument]
    chunk: RetrievedDocument
    generatedAnswer: str
    answerMeta: AnswerMeta
    lineage: list[LineageStep]
    nodeOutputs: list[NodeOutputSummary]
    stepOutputs: list[StepOutput] = Field(default_factory=list)
    embedding: EmbeddingInspector
    runtime: ExecutionRuntime


# --- Datasets ---
class DatasetMetrics(APIModel):
    connectedSources: int
    documents: int
    documentsDelta: str
    indexedChunks: int
    coverage: str
    storage: str
    capacity: str
    sparks: dict[str, list[int]]


class DatasetDocument(APIModel):
    id: str
    title: str
    source: str
    content: str
    fileType: str | None = None


class DatasetFile(APIModel):
    id: str
    name: str
    path: str
    fileType: str
    size: int
    indexed: bool


class Dataset(APIModel):
    id: str
    name: str
    sourceType: str
    format: str
    documents: int
    chunks: int
    lastSync: str
    status: Literal["indexed", "ingesting", "syncing", "error"]
    path: str
    embedding: str
    chunking: str
    usedBy: int
    size: str
    health: Literal["healthy", "warning"]
    documentsProcessed: int | None = None
    documentsTotal: int | None = None
    items: list[DatasetDocument] = Field(default_factory=list)
    files: list[DatasetFile] = Field(default_factory=list)
    connection: dict[str, Any] = Field(default_factory=dict)


class DataSource(APIModel):
    id: str
    name: str
    type: Literal["Local files", "S3", "Notion", "Google Drive", "Web crawl", "PostgreSQL", "REST API"]
    status: Literal["connected", "syncing", "error"]
    documents: int
    lastSync: str
    config: str
    datasets: int


class IngestionJob(APIModel):
    id: str
    datasetName: str
    status: Literal["completed", "running", "failed"]
    progress: int
    startedAt: str
    duration: str
    documents: int
    errors: int


class DatasetsData(APIModel):
    metrics: DatasetMetrics
    datasets: list[Dataset]
    sources: list[DataSource]
    jobs: list[IngestionJob]
    connectors: list[str]


# --- Models ---
class Provider(APIModel):
    id: str
    name: str
    type: str
    status: Literal["connected", "configured", "disconnected"]
    models: int
    detail: str
    accent: str


class ModelBenchmark(APIModel):
    name: str
    score: float
    latency: str
    throughput: str


class Model(APIModel):
    id: str
    name: str
    provider: str
    type: Literal["Generation", "Embedding", "Reranking"]
    context: str
    status: Literal["ready", "loaded", "idle", "error"]
    description: str
    architecture: str
    parameters: str
    dimensions: str
    maxSequence: str
    precision: str
    device: str
    memory: str
    license: str
    usedBy: int
    benchmark: ModelBenchmark | None = None
    local: bool


class ModelResources(APIModel):
    gpu: dict[str, Any]
    system: dict[str, Any]


class ModelsData(APIModel):
    providers: list[Provider]
    models: list[Model]
    resources: ModelResources


class ModelRegisterRequest(APIModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    provider: str
    type: str


class ModelTestRequest(APIModel):
    model_config = ConfigDict(extra="forbid")
    prompt: str


class ModelTestResponse(APIModel):
    modelId: str
    output: str
    latencyMs: int
    tokens: int
    cost: float


# --- Evaluation ---
class EvaluationMetric(APIModel):
    id: str
    label: str
    value: float
    delta: str
    trend: Literal["up", "down", "flat"] | None = None
    series: list[float] | None = None


class TrendPoint(APIModel):
    date: str
    current: float
    baseline: float


class ComparisonPoint(APIModel):
    metric: str
    current: float
    baseline: float


class QuestionResult(APIModel):
    id: str
    question: str
    faithfulness: float
    relevance: float
    contextPrecision: float
    contextRecall: float
    passed: bool
    reviewStatus: Literal["passed", "failed", "review"]


class EvaluationRun(APIModel):
    id: str
    label: str
    date: str
    score: float
    status: Literal["completed", "running", "failed"]
    questions: int


class EvaluationMeta(APIModel):
    pipeline: str
    dataset: str
    total: int
    passed: int
    failed: int
    threshold: float
    judge: str
    scorer: str
    lastEvaluated: str


class EvaluationSettings(APIModel):
    passThreshold: float
    sampleSize: int
    judge: str
    autoRun: bool
    metricWeights: dict[str, float]


class EvaluationData(APIModel):
    metrics: list[EvaluationMetric]
    trend: list[TrendPoint]
    comparison: list[ComparisonPoint]
    questions: list[QuestionResult]
    meta: EvaluationMeta
    runs: list[EvaluationRun]
    settings: EvaluationSettings


class EvaluationRunRequest(APIModel):
    model_config = ConfigDict(extra="forbid")
    pipeline: str
    dataset: str
    sampleSize: int


# --- Experiments ---
class Experiment(APIModel):
    id: str
    name: str
    chunking: str
    retrieval: str
    selection: str
    faithfulness: float | None
    latency: float | None
    cost: float | None
    status: Literal["complete", "running", "failed", "draft"]
    tags: list[str]
    project: str
    createdAt: str


class ExperimentProject(APIModel):
    name: str
    dataset: str
    questions: int


class ExperimentSummary(APIModel):
    experiments: int
    completed: int
    running: int
    bestScore: float


class ExperimentComparison(APIModel):
    ids: list[str]
    parameters: list[dict[str, Any]]
    scatter: list[dict[str, Any]]
    insight: str


class ExperimentData(APIModel):
    project: ExperimentProject
    summary: ExperimentSummary
    experiments: list[Experiment]
    comparison: ExperimentComparison


class ExperimentCreateRequest(APIModel):
    model_config = ConfigDict(extra="forbid")
    name: str


class ExperimentCompareRequest(APIModel):
    model_config = ConfigDict(extra="forbid")
    ids: list[str]


# --- Custom nodes ---
class CustomNodeFile(APIModel):
    id: str
    name: str
    language: Literal["python", "yaml", "text"]
    content: str
    dirty: bool | None = None


class CustomNodeParameter(APIModel):
    key: str
    label: str
    type: Literal["float", "int", "string", "bool"]
    value: str | int | float | bool


class CustomNodeDependency(APIModel):
    name: str
    version: str
    installed: bool


class CustomNodeVersion(APIModel):
    id: str
    version: str
    label: str
    date: str
    author: str
    changes: str
    current: bool | None = None


class CustomNode(APIModel):
    id: str
    name: str
    slug: str
    category: str
    description: str
    icon: str
    language: Literal["Python"]
    files: list[CustomNodeFile]
    parameters: list[CustomNodeParameter]
    inputDefinitions: list[PortDefinition]
    outputDefinitions: list[PortDefinition]
    dependencies: list[CustomNodeDependency]
    versions: list[CustomNodeVersion]
    updatedAt: str
    draftVersion: str
    basedOn: str


class TestResult(APIModel):
    name: str
    status: Literal["passed", "failed"]
    durationMs: int
    message: str | None = None


class TestRun(APIModel):
    id: str
    status: Literal["passed", "failed"]
    tests: list[TestResult]
    summary: str
    metrics: list[dict[str, str]]
    finishedAt: str
    logs: list[str]


class CustomNodeTestOutput(APIModel):
    id: str
    status: Literal["completed"]
    nodeName: str
    documents: list[RetrievedDocument]
    diversityScore: float
    durationMs: int
    logs: list[str]


class CustomNodeTemplate(APIModel):
    id: str
    name: str
    description: str


class DependencyRequest(APIModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    version: str


class OkResponse(APIModel):
    ok: bool = True
