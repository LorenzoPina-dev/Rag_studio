export type ID = string

export type NodeCategory =
  | 'Data Sources'
  | 'Document Processing'
  | 'Embeddings'
  | 'Vector Databases'
  | 'Retrieval'
  | 'Selection'
  | 'Reranking'
  | 'LLM Generation'
  | 'Control Flow'
  | 'Evaluation'
  | 'Multimodal Processing'

export type PortDataType = 'documents' | 'chunks' | 'embedding' | 'text' | 'json' | 'query' | 'array' | 'any'

export interface PortDefinition {
  id: string
  label: string
  dataType: PortDataType
  typeLabel: string
  color: string
  required?: boolean
}

export type ParamType = 'text' | 'number' | 'select' | 'boolean' | 'textarea'

export interface ParamDefinition {
  key: string
  label: string
  type: ParamType
  defaultValue: string | number | boolean
  unit?: string
  help?: string
  options?: string[]
}

export interface NodeIO {
  status?: 'idle' | 'running' | 'completed' | 'failed'
}

export interface NodeDefinition {
  id: string
  name: string
  category: NodeCategory
  kind: string
  description: string
  summary?: string
  documentation?: string
  accent: string
  inputs: PortDefinition[]
  outputs: PortDefinition[]
  params: ParamDefinition[]
  tags: string[]
  custom?: boolean
  version?: string
}

export interface XYPosition {
  x: number
  y: number
}

export interface PipelineNode {
  id: ID
  definitionId: ID
  name: string
  category: NodeCategory
  kind: string
  accent: string
  position: XYPosition
  config: Record<string, string | number | boolean>
  inputs: PortDefinition[]
  outputs: PortDefinition[]
  status?: NodeIO['status']
  durationMs?: number
}

export interface PipelineEdge {
  id: ID
  source: ID
  target: ID
  sourceHandle?: string | null
  targetHandle?: string | null
  dataType?: PortDataType
}

export interface Pipeline {
  id: ID
  projectId: ID
  name: string
  description: string
  environment: 'Development' | 'Staging' | 'Production'
  status: 'draft' | 'valid' | 'running' | 'failed'
  version: string
  updatedAt: string
  nodes: PipelineNode[]
  edges: PipelineEdge[]
  lastRun?: {
    status: 'completed' | 'failed'
    at: string
    latencyMs: number
    tokens: number
    cost: number
    output: string
    sources: number
  }
}

export interface PipelineSummary {
  id: ID
  projectId: ID
  projectName: string
  name: string
  nodeCount: number
  connectionCount: number
  status: Pipeline['status']
  environment: Pipeline['environment']
  updatedAt: string
  lastRunStatus?: 'passed' | 'failed' | 'draft'
  lastRunAt?: string
}

export interface ValidationIssue {
  id: string
  severity: 'error' | 'warning'
  message: string
  nodeId?: ID
}

export interface ValidationResult {
  valid: boolean
  errors: ValidationIssue[]
  warnings: ValidationIssue[]
  checkedAt: string
}

export type ExecutionStatus = 'queued' | 'running' | 'completed' | 'failed' | 'stopped'

export interface NodeRun {
  nodeId: ID
  name: string
  kind: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped'
  durationMs: number
  outputCount: number
  accent: string
  startedAt?: string
}

export interface LogEntry {
  id: string
  timestamp: string
  level: 'INFO' | 'WARN' | 'ERROR' | 'DONE' | 'DEBUG'
  message: string
  node?: string
}

export interface Execution {
  id: ID
  runNumber: number
  pipelineId: ID
  pipelineName: string
  status: ExecutionStatus
  startedAt: string
  finishedAt?: string
  durationMs: number
  tokens: number
  cost: number
  environment: string
  trigger: string
  traceId: string
  nodeRuns: NodeRun[]
  logs: LogEntry[]
  stagesCached?: boolean
  errors: number
  warnings: number
}

export interface RetrievedDocument {
  id: ID
  rank: number
  title: string
  source: string
  chunkId: string
  excerpt: string
  content: string
  score: number
  tokens: number
  page: number
  offset: string
  mime: string
}

export interface LineageStep {
  label: string
  detail: string
  indent: number
  accent?: string
}

export interface EmbeddingInspector {
  model: string
  dimensions: number
  cosineSimilarity: number
  values: number[]
  norm: string
  dtype: string
}

export interface StepMetric {
  label: string
  value: string
}

export interface StepItem {
  id: string
  title: string
  source: string
  content: string
  meta: Record<string, unknown>
}

export interface StepOutput {
  nodeId: string
  name: string
  kind: string
  detail: string
  accent: string
  status: string
  durationMs: number
  outputPorts: string[]
  text: string | null
  items: StepItem[]
  metrics: StepMetric[]
  searchHint: string
}

export interface ExecutionResult {
  id: ID
  executionId: ID
  query: string
  retrievedCount: number
  selectedCount: number
  errorCount: number
  stages: string[]
  traceId: string
  documents: RetrievedDocument[]
  chunk: RetrievedDocument
  generatedAnswer: string
  answerMeta: { model: string; temperature: number; citations: number }
  lineage: LineageStep[]
  nodeOutputs: Array<{ nodeId: string; name: string; detail: string; accent: string; kind?: string; selected?: boolean }>
  stepOutputs: StepOutput[]
  embedding: EmbeddingInspector
  runtime: { latencyMs: number; peakMemoryMb: number; tokensPerSecond: number; breakdown: Array<{ label: string; ms: number; color: string }> }
}

export interface Project {
  id: ID
  name: string
  description: string
  health: 'healthy' | 'warning' | 'draft'
  pipelineCount: number
  chunkCount: number
  editedAt: string
  updatedAt: string
  accent: string
  market?: string
}

export interface DashboardMetrics {
  activeProjects: number
  activeProjectsDelta: string
  pipelines: number
  pipelinesDelta: string
  executions: number
  executionsDelta: string
  faithfulness: number
  faithfulnessDelta: string
  sparks: Record<'projects' | 'pipelines' | 'executions' | 'faithfulness', number[]>
  resources: { memory: string; gpu: string; storage: string }
}

export interface ActivityItem {
  id: ID
  title: string
  detail: string
  time: string
  type: 'pipeline' | 'evaluation' | 'dataset' | 'custom-node'
}

export interface DashboardData {
  metrics: DashboardMetrics
  projects: Project[]
  pipelines: PipelineSummary[]
  activity: ActivityItem[]
}

export type DatasetStatus = 'indexed' | 'ingesting' | 'syncing' | 'error'

export interface DatasetItem {
  id: string
  title: string
  source: string
  content: string
  fileType?: string
}

export interface DatasetFile {
  id: string
  name: string
  path: string
  fileType: string
  size: number
  indexed: boolean
}

export interface DatasetOption {
  value: string
  label: string
  description?: string
}

export interface DatasetCreateInput {
  name: string
  sourceType: string
  path: string
  format?: string
  items?: DatasetItem[]
  connection?: Record<string, unknown>
}

export interface Dataset {
  id: ID
  name: string
  sourceType: string
  format: string
  documents: number
  chunks: number
  lastSync: string
  status: DatasetStatus
  path: string
  embedding: string
  chunking: string
  usedBy: number
  size: string
  health: 'healthy' | 'warning'
  documentsProcessed?: number
  documentsTotal?: number
  items?: DatasetItem[]
  files?: DatasetFile[]
  connection?: Record<string, unknown>
}

export interface DatasetMetrics {
  connectedSources: number
  documents: number
  documentsDelta: string
  indexedChunks: number
  coverage: string
  storage: string
  capacity: string
  sparks: Record<'sources' | 'documents' | 'chunks' | 'storage', number[]>
}

export interface DataSource {
  id: ID
  name: string
  type: 'Local files' | 'S3' | 'Notion' | 'Google Drive' | 'Web crawl' | 'PostgreSQL' | 'REST API'
  status: 'connected' | 'syncing' | 'error'
  documents: number
  lastSync: string
  config: string
  datasets: number
}

export interface IngestionJob {
  id: ID
  datasetName: string
  status: 'completed' | 'running' | 'failed'
  progress: number
  startedAt: string
  duration: string
  documents: number
  errors: number
}

export interface DatasetsData {
  metrics: DatasetMetrics
  datasets: Dataset[]
  sources: DataSource[]
  jobs: IngestionJob[]
  connectors: string[]
}

export interface Provider {
  id: ID
  name: string
  type: string
  status: 'connected' | 'configured' | 'disconnected'
  models: number
  detail: string
  accent: string
}

export type ModelType = 'Generation' | 'Embedding' | 'Reranking'

export interface Model {
  id: ID
  name: string
  provider: string
  type: ModelType
  context: string
  status: 'ready' | 'loaded' | 'idle' | 'error'
  description: string
  architecture: string
  parameters: string
  dimensions: string
  maxSequence: string
  precision: string
  device: string
  memory: string
  license: string
  usedBy: number
  benchmark?: { name: string; score: number; latency: string; throughput: string }
  local: boolean
}

export interface ModelResources {
  gpu: { used: number; total: number; label: string }
  system: { used: number; total: number; label: string }
}

export interface ModelsData {
  providers: Provider[]
  models: Model[]
  resources: ModelResources
}

export interface EvaluationMetric {
  id: string
  label: string
  value: number
  delta: string
  trend?: 'up' | 'down' | 'flat'
  series?: number[]
}

export interface TrendPoint {
  date: string
  current: number
  baseline: number
}

export interface ComparisonPoint {
  metric: string
  current: number
  baseline: number
}

export interface QuestionResult {
  id: ID
  question: string
  faithfulness: number
  relevance: number
  contextPrecision: number
  contextRecall: number
  passed: boolean
  reviewStatus: 'passed' | 'failed' | 'review'
}

export interface EvaluationRun {
  id: ID
  label: string
  date: string
  score: number
  status: 'completed' | 'running' | 'failed'
  questions: number
}

export interface EvaluationData {
  metrics: EvaluationMetric[]
  trend: TrendPoint[]
  comparison: ComparisonPoint[]
  questions: QuestionResult[]
  meta: {
    pipeline: string
    dataset: string
    total: number
    passed: number
    failed: number
    threshold: number
    judge: string
    scorer: string
    lastEvaluated: string
  }
  runs: EvaluationRun[]
  settings: { passThreshold: number; sampleSize: number; judge: string; autoRun: boolean; metricWeights: { faithfulness: number; relevance: number; precision: number; recall: number } }
}

export type ExperimentStatus = 'complete' | 'running' | 'failed' | 'draft'

export interface Experiment {
  id: ID
  name: string
  chunking: string
  retrieval: string
  selection: string
  faithfulness: number | null
  latency: number | null
  cost: number | null
  status: ExperimentStatus
  tags: string[]
  project: string
  createdAt: string
}

export interface ExperimentData {
  project: { name: string; dataset: string; questions: number }
  summary: { experiments: number; completed: number; running: number; bestScore: number }
  experiments: Experiment[]
  comparison: {
    ids: string[]
    parameters: Array<{ key: string; values: string[] }>
    scatter: Array<{ id: string; name: string; latency: number; faithfulness: number; accent: string }>
    insight: string
  }
}

export type CustomNodeFile = {
  id: ID
  name: string
  language: 'python' | 'yaml' | 'text'
  content: string
  dirty?: boolean
}

export interface CustomNodeParameter {
  key: string
  label: string
  type: 'float' | 'int' | 'string' | 'bool'
  value: string | number | boolean
}

export interface CustomNodeDependency {
  name: string
  version: string
  installed: boolean
}

export interface CustomNodeVersion {
  id: ID
  version: string
  label: string
  date: string
  author: string
  changes: string
  current?: boolean
}

export interface CustomNode {
  id: ID
  name: string
  slug: string
  category: string
  description: string
  icon: string
  language: 'Python'
  files: CustomNodeFile[]
  parameters: CustomNodeParameter[]
  inputDefinitions: PortDefinition[]
  outputDefinitions: PortDefinition[]
  dependencies: CustomNodeDependency[]
  versions: CustomNodeVersion[]
  updatedAt: string
  draftVersion: string
  basedOn: string
}

export interface TestResult {
  name: string
  status: 'passed' | 'failed'
  durationMs: number
  message?: string
}

export interface TestRun {
  id: ID
  status: 'passed' | 'failed'
  tests: TestResult[]
  summary: string
  metrics: Array<{ label: string; value: string }>
  finishedAt: string
  logs: string[]
}

export interface CustomNodeTestInput {
  id: ID
  name: string
  category: string
  limit: number
  alpha: number
  query: string
}

export interface CustomNodeTestOutput {
  id: ID
  status: 'completed'
  nodeName: string
  documents: RetrievedDocument[]
  diversityScore: number
  durationMs: number
  logs: string[]
}

export interface NodeCatalogCategory {
  category: NodeCategory
  description: string
  nodes: NodeDefinition[]
}

export interface SearchResult {
  id: ID
  type: 'pipeline' | 'project' | 'dataset' | 'model' | 'experiment' | 'node' | 'page'
  title: string
  subtitle: string
  href: string
}

export interface AppNotification {
  id: ID
  title: string
  body: string
  time: string
  read: boolean
  type: 'success' | 'info' | 'warning'
}

export interface Workspace {
  id: ID
  name: string
  plan: string
  role: string
}

export interface SystemStatus {
  state: 'operational' | 'degraded'
  version: string
  python: string
  connected: boolean
  branch: string
  errors: number
  warnings: number
}

export interface ProviderSettingsPublic {
  openai_api_key: string | null
  openai_api_key_set: boolean
  openai_base_url: string
  openai_embedding_model: string
  openai_chat_model: string
  ollama_base_url: string
  ollama_embedding_model: string
  ollama_chat_model: string
  hf_embedding_model: string
  hf_reranker_model: string
  hf_generator_model: string
  allow_model_download: boolean
}

export type ProviderSettingsInput = Partial<Omit<ProviderSettingsPublic, 'openai_api_key_set'>>

export interface ProviderStatus {
  huggingface_available: boolean
  ollama_running: boolean
  ollama_models: string[]
  openai_configured: boolean
  capabilities: {
    embeddings: string | null
    reranking: string | null
    generation: string | null
  }
  /** Il backend può restituire le stesse capacità anche senza il wrapper. */
  embeddings?: string | null
  reranking?: string | null
  generation?: string | null
}
