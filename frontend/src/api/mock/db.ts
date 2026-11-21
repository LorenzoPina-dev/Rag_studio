import type {
  ActivityItem,
  CustomNode,
  CustomNodeTestOutput,
  DashboardData,
  DataSource,
  Dataset,
  DatasetsData,
  EvaluationData,
  Execution,
  ExecutionResult,
  ExperimentData,
  Experiment,
  IngestionJob,
  LogEntry,
  Model,
  ModelResources,
  ModelsData,
  NodeCatalogCategory,
  Pipeline,
  PipelineSummary,
  Project,
  Provider,
  RetrievedDocument,
  TestRun,
  Workspace,
} from '@/types'
import { nodeCategories, nodeDefinitions, seedCustomNode, seedPipeline } from './pipelineSeed'

const ago = (minutes: number) => new Date(Date.now() - minutes * 60 * 1000).toISOString()

export const workspace: Workspace = { id: 'ws_research', name: 'Research lab', plan: 'Team workspace', role: 'Owner' }

export const projects: Project[] = [
  { id: 'pr_knowledge', name: 'Knowledge assistant', description: 'Production-ready document Q&A', health: 'healthy', pipelineCount: 8, chunkCount: 24800, editedAt: '2 hours ago', updatedAt: ago(120), accent: '#7296FF' },
  { id: 'pr_research', name: 'Research copilot', description: 'Multi-source scientific retrieval', health: 'healthy', pipelineCount: 5, chunkCount: 12300, editedAt: '2 hours ago', updatedAt: ago(122), accent: '#A78BFA' },
  { id: 'pr_support', name: 'Support intelligence', description: 'Fast, grounded support answers', health: 'healthy', pipelineCount: 4, chunkCount: 8100, editedAt: '2 hours ago', updatedAt: ago(130), accent: '#35D99B' },
  { id: 'pr_multimodal', name: 'Multimodal document QA', description: 'Vision-aware document understanding', health: 'draft', pipelineCount: 2, chunkCount: 4100, editedAt: 'Yesterday', updatedAt: ago(1400), accent: '#E48EF0' },
]

const pipedNode = (nodeId: string) => seedPipeline.nodes.find((n) => n.id === nodeId)!

export const createdPipelineSummaries: PipelineSummary[] = []

export const pipelineSummaries = (): PipelineSummary[] => [
  ...createdPipelineSummaries,
  { id: 'pl_hybrid_rag', projectId: 'pr_knowledge', projectName: 'Knowledge assistant', name: 'Hybrid RAG pipeline', nodeCount: 8, connectionCount: 9, status: db.pipeline.status, environment: db.pipeline.environment, updatedAt: db.pipeline.updatedAt, lastRunStatus: 'passed', lastRunAt: '2 min ago' },
  { id: 'pl_semantic_v2', projectId: 'pr_research', projectName: 'Research copilot', name: 'Semantic search v2', nodeCount: 6, connectionCount: 7, status: 'valid', environment: 'Production', updatedAt: ago(60), lastRunStatus: 'passed', lastRunAt: '18 min ago' },
  { id: 'pl_support_faq', projectId: 'pr_support', projectName: 'Support intelligence', name: 'Support FAQ retrieval', nodeCount: 7, connectionCount: 8, status: 'valid', environment: 'Production', updatedAt: ago(125), lastRunStatus: 'passed', lastRunAt: '1 hour ago' },
  { id: 'pl_multimodal', projectId: 'pr_knowledge', projectName: 'Knowledge assistant', name: 'Multimodal document QA', nodeCount: 5, connectionCount: 4, status: 'draft', environment: 'Development', updatedAt: ago(220), lastRunStatus: 'draft', lastRunAt: '3 hours ago' },
]

export const activity: ActivityItem[] = [
  { id: 'a1', title: 'Pipeline deployed', detail: 'Hybrid RAG pipeline · v2.4', time: '12 min ago', type: 'pipeline' },
  { id: 'a2', title: 'Evaluation completed', detail: 'Faithfulness improved by 4.5%', time: '38 min ago', type: 'evaluation' },
  { id: 'a3', title: 'Dataset synchronized', detail: 'product_docs · 12 new files', time: '1 hour ago', type: 'dataset' },
  { id: 'a4', title: 'Custom node published', detail: 'Diversity-aware ranker · v1.2.0', time: '2 hours ago', type: 'custom-node' },
]

export const dashboardData = (): DashboardData => ({
  metrics: {
    activeProjects: 12,
    activeProjectsDelta: '+2 this month',
    pipelines: 38,
    pipelinesDelta: '8 updated this week',
    executions: 2486,
    executionsDelta: '↑ 18.6% vs. last week',
    faithfulness: 0.92,
    faithfulnessDelta: '↑ 0.04 vs. baseline',
    sparks: {
      projects: [3, 4, 4, 5, 5, 6, 6, 7, 8, 8, 9, 9, 10, 9, 10, 11, 11, 12],
      pipelines: [5, 6, 6, 8, 9, 9, 12, 13, 14, 13, 16, 17, 18, 20, 22, 25, 28, 38],
      executions: [8, 10, 9, 12, 15, 14, 18, 20, 19, 23, 26, 28, 27, 31, 34, 33, 36, 38],
      faithfulness: [6, 7, 7, 8, 10, 11, 11, 13, 14, 14, 16, 17, 17, 19, 20, 22, 23, 26],
    },
    resources: { memory: '4.2 / 16 GB', gpu: 'CPU · reference', storage: '82 GB available' },
  },
  projects,
  pipelines: pipelineSummaries(),
  activity,
})

const datasetSeed: Dataset[] = [
  { id: 'ds_product_docs', name: 'product_docs', sourceType: 'Local directory', format: 'PDF · Markdown', documents: 248, chunks: 24816, lastSync: '2 min ago', status: 'indexed', path: '/data/product_docs/', embedding: 'Hash embeddings (reference)', chunking: 'Semantic · 512 tokens', usedBy: 4, size: '486 MB', health: 'healthy', documentsProcessed: 248, documentsTotal: 248 },
  { id: 'ds_research_papers', name: 'research_papers', sourceType: 'S3', format: 'PDF · arXiv', documents: 1420, chunks: 68284, lastSync: '24 min ago', status: 'indexed', path: 's3://research-corpus/papers/', embedding: 'Hash embeddings (reference)', chunking: 'Recursive · 512 tokens', usedBy: 3, size: '1.2 GB', health: 'healthy', documentsProcessed: 1420, documentsTotal: 1420 },
  { id: 'ds_support_knowledge', name: 'support_knowledge', sourceType: 'Notion', format: 'Notion · HTML', documents: 8642, chunks: 52116, lastSync: '1 hour ago', status: 'indexed', path: 'notion://support-kb', embedding: 'text-embedding-3-small (mock)', chunking: 'Semantic · 384 tokens', usedBy: 2, size: '842 MB', health: 'healthy', documentsProcessed: 8642, documentsTotal: 8642 },
  { id: 'ds_api_reference', name: 'api_reference', sourceType: 'REST API', format: 'OpenAPI · JSON', documents: 368, chunks: 18408, lastSync: '2 hours ago', status: 'indexed', path: 'https://api.internal/openapi.json', embedding: 'Hash embeddings (reference)', chunking: 'Recursive · 256 tokens', usedBy: 5, size: '124 MB', health: 'healthy', documentsProcessed: 368, documentsTotal: 368 },
  { id: 'ds_customer_feedback', name: 'customer_feedback', sourceType: 'PostgreSQL', format: 'CSV · Text', documents: 1912, chunks: 20782, lastSync: 'Syncing…', status: 'ingesting', path: 'postgres://warehouse/feedback', embedding: 'text-embedding-3-small (mock)', chunking: 'Semantic · 512 tokens', usedBy: 1, size: '218 MB', health: 'warning', documentsProcessed: 1402, documentsTotal: 1912 },
  { id: 'ds_onboarding', name: 'onboarding_guides', sourceType: 'Google Drive', format: 'DOCX · PDF', documents: 154, chunks: 9642, lastSync: 'Yesterday', status: 'indexed', path: 'gdrive://onboarding', embedding: 'Hash embeddings (reference)', chunking: 'Semantic · 512 tokens', usedBy: 2, size: '96 MB', health: 'healthy', documentsProcessed: 154, documentsTotal: 154 },
  { id: 'ds_changelog', name: 'release_changelog', sourceType: 'Web crawl', format: 'HTML · Markdown', documents: 96, chunks: 4288, lastSync: 'Yesterday', status: 'indexed', path: 'https://docs.internal/changelog', embedding: 'Hash embeddings (reference)', chunking: 'Recursive · 256 tokens', usedBy: 1, size: '28 MB', health: 'healthy', documentsProcessed: 96, documentsTotal: 96 },
  { id: 'ds_benchmarks', name: 'rag_benchmark_v3', sourceType: 'Local files', format: 'JSONL · Parquet', documents: 200, chunks: 5990, lastSync: '2 days ago', status: 'indexed', path: '/data/benchmarks/rag_v3/', embedding: 'Hash embeddings (reference)', chunking: 'Semantic · 512 tokens', usedBy: 3, size: '42 MB', health: 'healthy', documentsProcessed: 200, documentsTotal: 200 },
]

const datasetSources: DataSource[] = [
  { id: 'src_local', name: 'Local workspace', type: 'Local files', status: 'connected', documents: 1840, lastSync: '2 min ago', config: '2 directories', datasets: 3 },
  { id: 'src_aws', name: 'Research corpus', type: 'S3', status: 'connected', documents: 1420, lastSync: '24 min ago', config: 's3://research-corpus', datasets: 1 },
  { id: 'src_notion', name: 'Support knowledge base', type: 'Notion', status: 'connected', documents: 8642, lastSync: '1 hour ago', config: 'Support workspace', datasets: 1 },
  { id: 'src_gdrive', name: 'Onboarding drive', type: 'Google Drive', status: 'connected', documents: 154, lastSync: 'Yesterday', config: 'onboarding@company', datasets: 1 },
  { id: 'src_pg', name: 'Warehouse feedback', type: 'PostgreSQL', status: 'syncing', documents: 1912, lastSync: 'Syncing…', config: 'warehouse.internal', datasets: 1 },
  { id: 'src_web', name: 'Docs crawler', type: 'Web crawl', status: 'connected', documents: 96, lastSync: 'Yesterday', config: 'docs.internal', datasets: 1 },
  { id: 'src_api', name: 'Internal API index', type: 'REST API', status: 'connected', documents: 368, lastSync: '2 hours ago', config: 'api.internal', datasets: 1 },
]
const datasetJobs: IngestionJob[] = [
  { id: 'job_1', datasetName: 'customer_feedback', status: 'running', progress: 73, startedAt: '2 min ago', duration: '1m 42s', documents: 1912, errors: 0 },
  { id: 'job_2', datasetName: 'product_docs', status: 'completed', progress: 100, startedAt: '6 min ago', duration: '48s', documents: 248, errors: 0 },
  { id: 'job_3', datasetName: 'research_papers', status: 'completed', progress: 100, startedAt: '24 min ago', duration: '4m 12s', documents: 1420, errors: 2 },
  { id: 'job_4', datasetName: 'support_knowledge', status: 'completed', progress: 100, startedAt: '1 hour ago', duration: '2m 05s', documents: 8642, errors: 0 },
  { id: 'job_5', datasetName: 'api_reference', status: 'completed', progress: 100, startedAt: '2 hours ago', duration: '36s', documents: 368, errors: 0 },
]
const datasetConnectors = ['Local files', 'S3', 'Notion', 'Google Drive', 'Web crawl', 'PostgreSQL', 'REST API']

export const datasetsData = (): DatasetsData => ({
  metrics: {
    connectedSources: datasetSources.length,
    documents: datasetSeed.reduce((sum, d) => sum + d.documents, 0),
    documentsDelta: '+248 in the last 24 hours',
    indexedChunks: datasetSeed.reduce((sum, d) => sum + d.chunks, 0),
    coverage: '98.7% indexing coverage',
    storage: '2.84 GB',
    capacity: '18% of workspace capacity',
    sparks: {
      sources: [4, 4, 5, 5, 5, 6, 6, 6, 7, 7, 7, 8],
      documents: [22, 26, 25, 30, 36, 34, 41, 46, 44, 52, 58, 64],
      chunks: [18, 20, 19, 24, 28, 27, 32, 36, 35, 40, 45, 48],
      storage: [8, 9, 10, 10, 12, 13, 14, 15, 16, 17, 17, 18],
    },
  },
  datasets: datasetSeed,
  sources: datasetSources,
  jobs: datasetJobs,
  connectors: datasetConnectors,
})

const modelProviders: Provider[] = [
  { id: 'openai', name: 'OpenAI', type: 'API provider', status: 'connected', models: 3, detail: '3 models available (mock)', accent: '#39D6D0' },
  { id: 'huggingface', name: 'Hugging Face', type: 'Local inference', status: 'connected', models: 6, detail: '6 models installed (mock)', accent: '#F0B45C' },
  { id: 'ollama', name: 'Ollama', type: 'Local runtime', status: 'connected', models: 2, detail: '2 models available (mock)', accent: '#A78BFA' },
  { id: 'anthropic', name: 'Anthropic', type: 'API provider', status: 'connected', models: 1, detail: '1 model available (mock)', accent: '#C9A36A' },
  { id: 'cohere', name: 'Cohere', type: 'API provider', status: 'connected', models: 1, detail: '1 model available (mock)', accent: '#7F95CF' },
]
const modelRecords: Model[] = [
  { id: 'm_gpt4o', name: 'GPT-4o (mock)', provider: 'OpenAI', type: 'Generation', context: '— (mock)', status: 'ready', description: 'Mock generation entry; no OpenAI call is made in mock mode.', architecture: 'Mock', parameters: '—', dimensions: '—', maxSequence: '—', precision: '—', device: 'Mock API', memory: '—', license: 'Mock data', usedBy: 8, local: false },
  { id: 'm_gpt4omini', name: 'GPT-4o mini (mock)', provider: 'OpenAI', type: 'Generation', context: '— (mock)', status: 'ready', description: 'Mock generation entry; no OpenAI call is made in mock mode.', architecture: 'Mock', parameters: '—', dimensions: '—', maxSequence: '—', precision: '—', device: 'Mock API', memory: '—', license: 'Mock data', usedBy: 6, local: false },
  { id: 'm_bge_large', name: 'Mock embedding (reference)', provider: 'Hugging Face', type: 'Embedding', context: '— (mock)', status: 'loaded', description: 'Deterministic 128-dimensional hash embeddings; no BGE model is loaded.', architecture: 'Hash (reference)', parameters: '—', dimensions: '128', maxSequence: '—', precision: '—', device: 'CPU · reference', memory: '— (mock)', license: 'Mock data', usedBy: 12, benchmark: { name: 'MTEB (mock)', score: 64.23, latency: '18ms / batch', throughput: '32 docs / batch' }, local: true },
  { id: 'm_bge_reranker', name: 'Mock reranker (reference)', provider: 'Hugging Face', type: 'Reranking', context: '— (mock)', status: 'loaded', description: 'Reference lexical reranking; no cross-encoder is loaded.', architecture: 'Mock', parameters: '—', dimensions: '—', maxSequence: '—', precision: '—', device: 'CPU · reference', memory: '— (mock)', license: 'Mock data', usedBy: 7, benchmark: { name: 'MTEB rerank (mock)', score: 61.40, latency: '42ms / batch', throughput: '16 docs / batch' }, local: true },
  { id: 'm_llama', name: 'Llama 3.1 8B (mock)', provider: 'Ollama', type: 'Generation', context: '— (mock)', status: 'idle', description: 'Mock local generation entry.', architecture: 'Mock', parameters: '—', dimensions: '—', maxSequence: '—', precision: '—', device: 'CPU · reference', memory: '— (mock)', license: 'Mock data', usedBy: 3, benchmark: { name: 'MMLU (mock)', score: 69.4, latency: '26ms / token', throughput: '38 tok / s' }, local: true },
  { id: 'm_embed3small', name: 'text-embedding-3-small (mock)', provider: 'OpenAI', type: 'Embedding', context: '— (mock)', status: 'ready', description: 'Mock embedding entry; no OpenAI call is made in mock mode.', architecture: 'Mock', parameters: '—', dimensions: '—', maxSequence: '—', precision: '—', device: 'Mock API', memory: '—', license: 'Mock data', usedBy: 4, local: false },
  { id: 'm_nomic', name: 'nomic-embed-text (mock)', provider: 'Ollama', type: 'Embedding', context: '— (mock)', status: 'idle', description: 'Mock local embedding entry.', architecture: 'Mock', parameters: '—', dimensions: '768 (mock)', maxSequence: '—', precision: '—', device: 'CPU · reference', memory: '— (mock)', license: 'Mock data', usedBy: 2, local: true },
  { id: 'm_claude', name: 'Claude 3.5 Sonnet (mock)', provider: 'Anthropic', type: 'Generation', context: '— (mock)', status: 'ready', description: 'Mock generation entry; no Anthropic call is made in mock mode.', architecture: 'Mock', parameters: '—', dimensions: '—', maxSequence: '—', precision: '—', device: 'Mock API', memory: '—', license: 'Mock data', usedBy: 1, local: false },
  { id: 'm_bge_m3', name: 'Mock embedding (multilingual reference)', provider: 'Hugging Face', type: 'Embedding', context: '— (mock)', status: 'loaded', description: 'Deterministic 128-dimensional hash embeddings; no real multilingual model.', architecture: 'Hash (reference)', parameters: '—', dimensions: '128', maxSequence: '—', precision: '—', device: 'CPU · reference', memory: '— (mock)', license: 'Mock data', usedBy: 2, local: true },
  { id: 'm_minilm', name: 'all-MiniLM-L6-v2 (mock)', provider: 'Hugging Face', type: 'Embedding', context: '— (mock)', status: 'idle', description: 'Mock local embedding entry.', architecture: 'Mock', parameters: '—', dimensions: '384 (mock)', maxSequence: '—', precision: '—', device: 'CPU · reference', memory: '— (mock)', license: 'Mock data', usedBy: 1, local: true },
  { id: 'm_cohere_rerank', name: 'Cohere Rerank 3.5 (mock)', provider: 'Cohere', type: 'Reranking', context: '— (mock)', status: 'ready', description: 'Mock managed reranker entry.', architecture: 'Mock', parameters: '—', dimensions: '—', maxSequence: '—', precision: '—', device: 'Mock API', memory: '—', license: 'Mock data', usedBy: 2, local: false },
]
const modelResources: ModelResources = {
  gpu: { used: 0, total: 1, label: 'CPU · reference (no GPU)' },
  system: { used: 4.2, total: 16, label: '4.2 / 16 GB' },
}

export const modelsData = (): ModelsData => ({
  providers: modelProviders,
  models: modelRecords,
  resources: modelResources,
})

const doc = (i: number, title: string, source: string, chunkId: string, excerpt: string, score: number, content: string, page: number, tokens: number, offset: string): RetrievedDocument => ({
  id: `doc_${i}`,
  rank: i,
  title,
  source,
  chunkId,
  excerpt,
  content,
  score,
  tokens,
  page,
  offset,
  mime: 'text/markdown',
})

const retrievedDocuments: RetrievedDocument[] = [
  doc(1, 'Hybrid search architecture', 'architecture/retrieval.md', 'chunk_0042', 'Combines dense vector search with sparse BM25 retrieval…', 0.982, 'Hybrid retrieval combines dense vector search with sparse keyword matching. Dense retrieval captures semantic meaning, while BM25 excels at exact terms, identifiers and domain-specific vocabulary. Results from both methods are fused using reciprocal rank fusion and passed to a cross-encoder for final relevance scoring.', 4, 312, '2,048–3,296'),
  doc(2, 'Retrieval configuration guide', 'guides/hybrid-search.md', 'chunk_0186', 'The alpha parameter controls the balance between dense…', 0.956, 'The alpha parameter controls the balance between dense and sparse retrieval. A value of 0.7 favors semantic matching while retaining keyword precision for identifiers and error codes.', 2, 248, '1,024–1,978'),
  doc(3, 'Ranking and relevance', 'concepts/ranking.md', 'chunk_0284', 'A cross-encoder reranker scores query-document pairs…', 0.931, 'A cross-encoder reranker scores each query-document pair jointly, producing substantially better ordering than bi-encoder similarity alone. Use top_n to limit the number of documents passed to generation.', 7, 196, '3,810–4,120'),
  doc(4, 'Search quality benchmarks', 'benchmarks/search_evals.md', 'chunk_0363', 'Hybrid retrieval improves recall across keyword-heavy…', 0.908, 'Hybrid retrieval improves recall across keyword-heavy datasets while maintaining semantic robustness. On rag_benchmark_v3 it improves faithfulness by 4.5% over dense-only retrieval.', 1, 284, '512–1,020'),
  doc(5, 'Evaluating grounded answers', 'guides/evaluation.md', 'chunk_0411', 'RAGAS faithfulness measures whether every claim is…', 0.892, 'RAGAS faithfulness measures whether every claim in a generated answer can be supported by the retrieved context. Combine it with answer relevance and context precision for a complete picture.', 3, 221, '2,210–2,684'),
]

const embeddingValues = Array.from({ length: 128 }, (_, i) => {
  const a = Math.sin(i * 0.7) * 0.5 + Math.cos(i * 1.3) * 0.3
  return Math.round((0.5 + a * 0.45) * 100) / 100
})

const executionLogs: LogEntry[] = [
  { id: 'l1', timestamp: '14:32:08.000', level: 'INFO', message: 'Pipeline execution started: hybrid-rag-v2.4' },
  { id: 'l2', timestamp: '14:32:08.042', level: 'INFO', message: 'Query parsed and normalized · 8 tokens', node: 'Query input' },
  { id: 'l3', timestamp: '14:32:08.128', level: 'INFO', message: 'Query embedding generated · 128 dimensions (hash reference)', node: 'Embedding' },
  { id: 'l4', timestamp: '14:32:08.144', level: 'WARN', message: 'Qdrant connection reset · retrying (1/3)', node: 'Hybrid Retrieval' },
  { id: 'l5', timestamp: '14:32:08.166', level: 'INFO', message: 'Connection restored after 22ms', node: 'Hybrid Retrieval' },
  { id: 'l6', timestamp: '14:32:08.252', level: 'INFO', message: 'Hybrid retrieval complete · 20 candidates', node: 'Hybrid Retrieval' },
  { id: 'l7', timestamp: '14:32:08.433', level: 'INFO', message: 'Mock reranker selected 5 documents', node: 'Mock reranker' },
  { id: 'l8', timestamp: '14:32:08.641', level: 'INFO', message: 'Context assembled · 1,284 input tokens', node: 'Prompt assembly' },
  { id: 'l9', timestamp: '14:32:09.240', level: 'INFO', message: 'Generation complete · 558 output tokens', node: 'LLM Generation' },
  { id: 'l10', timestamp: '14:32:09.240', level: 'DONE', message: 'Pipeline completed successfully in 1.24s' },
]

export const executions: Execution[] = [
  {
    id: 'run_2486',
    runNumber: 2486,
    pipelineId: 'pl_hybrid_rag',
    pipelineName: 'Hybrid RAG pipeline',
    status: 'completed',
    startedAt: 'Today, 14:32:08',
    durationMs: 1240,
    tokens: 1842,
    cost: 0.0062,
    environment: 'Development',
    trigger: 'Triggered manually',
    traceId: 'tr_8e4c92a1',
    errors: 0,
    warnings: 1,
    stagesCached: true,
    logs: executionLogs,
    nodeRuns: [
      { nodeId: 'n_query', name: 'Query input', kind: 'input', status: 'completed', durationMs: 42, outputCount: 8, accent: '#39D6D0' },
      { nodeId: 'n_embeddings', name: 'Embedding', kind: 'embedding', status: 'completed', durationMs: 86, outputCount: 128, accent: '#7296FF' },
      { nodeId: 'n_hybrid', name: 'Hybrid Retrieval', kind: 'retrieval', status: 'completed', durationMs: 124, outputCount: 20, accent: '#F0B45C' },
      { nodeId: 'n_reranker', name: 'Mock reranker', kind: 'reranking', status: 'completed', durationMs: 181, outputCount: 5, accent: '#35D99B' },
      { nodeId: 'n_prompt', name: 'Prompt assembly', kind: 'generation', status: 'completed', durationMs: 208, outputCount: 1284, accent: '#A78BFA' },
      { nodeId: 'n_llm', name: 'LLM Generation', kind: 'generation', status: 'completed', durationMs: 599, outputCount: 558, accent: '#7296FF' },
    ],
  },
  {
    id: 'run_2485',
    runNumber: 2485,
    pipelineId: 'pl_hybrid_rag',
    pipelineName: 'Hybrid RAG pipeline',
    status: 'failed',
    startedAt: 'Today, 13:04:12',
    durationMs: 860,
    tokens: 640,
    cost: 0.0021,
    environment: 'Development',
    trigger: 'Triggered manually',
    traceId: 'tr_71bd2f9c',
    errors: 1,
    warnings: 0,
    stagesCached: false,
    logs: [
      { id: 'f1', timestamp: '13:04:12.000', level: 'INFO', message: 'Pipeline execution started: hybrid-rag-v2.4' },
      { id: 'f2', timestamp: '13:04:12.880', level: 'ERROR', message: 'Qdrant collection "docs" unreachable after 3 retries', node: 'Hybrid Retrieval' },
    ],
    nodeRuns: [
      { nodeId: 'n_query', name: 'Query input', kind: 'input', status: 'completed', durationMs: 38, outputCount: 8, accent: '#39D6D0' },
      { nodeId: 'n_embeddings', name: 'Embedding', kind: 'embedding', status: 'completed', durationMs: 91, outputCount: 128, accent: '#7296FF' },
      { nodeId: 'n_hybrid', name: 'Hybrid Retrieval', kind: 'retrieval', status: 'failed', durationMs: 731, outputCount: 0, accent: '#F06A6A' },
      { nodeId: 'n_reranker', name: 'Mock reranker', kind: 'reranking', status: 'skipped', durationMs: 0, outputCount: 0, accent: '#5E6B80' },
      { nodeId: 'n_llm', name: 'LLM Generation', kind: 'generation', status: 'skipped', durationMs: 0, outputCount: 0, accent: '#5E6B80' },
    ],
  },
]

export const executionResults = (): ExecutionResult => ({
  id: 'res_2486',
  executionId: 'run_2486',
  query: 'How does hybrid retrieval work?',
  retrievedCount: 20,
  selectedCount: 5,
  errorCount: 0,
  stages: ['6 stages', 'Ingestion cached', 'Trace ID tr_8e4c92a1'],
  traceId: 'tr_8e4c92a1',
  documents: retrievedDocuments,
  chunk: retrievedDocuments[0],
  generatedAnswer:
    '[Mock generation · reference answer] Hybrid retrieval uses two complementary search methods to find relevant context: [1] dense search understands the semantic meaning of your query through vector embeddings; [2] sparse search (BM25) matches exact words and technical terms where semantic search might miss. The results are fused and reranked to select the most useful context for generation. [1, 3]',
  answerMeta: { model: 'Mock generation', temperature: 0.2, citations: 5 },
  lineage: [
    { label: 'product_docs', detail: '248 documents', indent: 0, accent: '#39D6D0' },
    { label: 'Semantic chunks', detail: '24,816 chunks', indent: 1 },
    { label: 'Hybrid retrieval', detail: '20 retrieved', indent: 1 },
    { label: 'Mock reranker', detail: '5 ranked', indent: 2, accent: '#35D99B' },
  ],
  nodeOutputs: [
    { nodeId: 'n_document', name: 'Document source', detail: '248 documents', accent: '#39D6D0' },
    { nodeId: 'n_chunking', name: 'Semantic Chunking', detail: '24,816 chunks', accent: '#A78BFA' },
    { nodeId: 'n_embeddings', name: 'Mock embeddings (reference)', detail: '128 dimensions (hash)', accent: '#7296FF' },
    { nodeId: 'n_hybrid', name: 'Hybrid Retrieval', detail: '20 candidates', accent: '#F0B45C' },
    { nodeId: 'n_reranker', name: 'Mock reranker', detail: '5 documents selected', accent: '#A78BFA', selected: true },
    { nodeId: 'n_llm', name: 'Mock generation', detail: '558 tokens', accent: '#7296FF' },
  ],
  stepOutputs: [],
  embedding: {
    model: 'Mock embedding (hash reference)',
    dimensions: 128,
    cosineSimilarity: 0.874,
    values: embeddingValues,
    norm: '1.0000',
    dtype: 'float32 (reference)',
  },
  runtime: {
    latencyMs: 1240,
    peakMemoryMb: 428,
    tokensPerSecond: 932,
    breakdown: [
      { label: 'Embedding', ms: 86, color: '#7296FF' },
      { label: 'Hybrid Retrieval', ms: 124, color: '#F0B45C' },
      { label: 'Mock reranker', ms: 181, color: '#35D99B' },
      { label: 'Prompt assembly', ms: 208, color: '#A78BFA' },
      { label: 'Mock generation', ms: 599, color: '#5B7CFA' },
    ],
  },
})

export const evaluationData = (): EvaluationData => ({
  metrics: [
    { id: 'faithfulness', label: 'Faithfulness', value: 0.92, delta: '↑ 4.5% vs. baseline', trend: 'up' },
    { id: 'relevance', label: 'Answer relevance', value: 0.89, delta: '↑ 6.0% vs. baseline', trend: 'up' },
    { id: 'precision', label: 'Context precision', value: 0.86, delta: '↑ 7.5% vs. baseline', trend: 'up' },
    { id: 'recall', label: 'Context recall', value: 0.94, delta: '↑ 3.3% vs. baseline', trend: 'up' },
  ],
  trend: [
    { date: 'May 01', current: 0.71, baseline: 0.69 },
    { date: 'May 03', current: 0.74, baseline: 0.7 },
    { date: 'May 06', current: 0.73, baseline: 0.72 },
    { date: 'May 08', current: 0.76, baseline: 0.73 },
    { date: 'May 11', current: 0.79, baseline: 0.74 },
    { date: 'May 13', current: 0.78, baseline: 0.76 },
    { date: 'May 16', current: 0.83, baseline: 0.77 },
    { date: 'May 18', current: 0.82, baseline: 0.79 },
    { date: 'May 21', current: 0.86, baseline: 0.8 },
    { date: 'May 23', current: 0.88, baseline: 0.81 },
    { date: 'May 26', current: 0.92, baseline: 0.87 },
  ],
  comparison: [
    { metric: 'Faithfulness', current: 0.92, baseline: 0.87 },
    { metric: 'Relevance', current: 0.89, baseline: 0.84 },
    { metric: 'Precision', current: 0.86, baseline: 0.79 },
    { metric: 'Recall', current: 0.94, baseline: 0.88 },
  ],
  questions: [
    { id: 'q1', question: 'How does hybrid retrieval work?', faithfulness: 0.98, relevance: 0.96, contextPrecision: 0.94, contextRecall: 0.97, passed: true, reviewStatus: 'passed' },
    { id: 'q2', question: 'What embedding models are supported?', faithfulness: 0.95, relevance: 0.92, contextPrecision: 0.9, contextRecall: 0.93, passed: true, reviewStatus: 'passed' },
    { id: 'q3', question: 'How do I configure semantic chunking?', faithfulness: 0.94, relevance: 0.91, contextPrecision: 0.87, contextRecall: 0.92, passed: true, reviewStatus: 'passed' },
    { id: 'q4', question: 'What is the maximum document size?', faithfulness: 0.71, relevance: 0.74, contextPrecision: 0.68, contextRecall: 0.7, passed: false, reviewStatus: 'review' },
    { id: 'q5', question: 'Can I use a local reranker with Ollama?', faithfulness: 0.89, relevance: 0.9, contextPrecision: 0.84, contextRecall: 0.88, passed: true, reviewStatus: 'passed' },
    { id: 'q6', question: 'How are API keys stored?', faithfulness: 0.93, relevance: 0.88, contextPrecision: 0.91, contextRecall: 0.9, passed: true, reviewStatus: 'passed' },
    { id: 'q7', question: 'Which fusion strategy is the default?', faithfulness: 0.85, relevance: 0.86, contextPrecision: 0.82, contextRecall: 0.84, passed: true, reviewStatus: 'passed' },
    { id: 'q8', question: 'What happens when Qdrant is unavailable?', faithfulness: 0.69, relevance: 0.72, contextPrecision: 0.66, contextRecall: 0.68, passed: false, reviewStatus: 'failed' },
  ],
  meta: {
    pipeline: 'Hybrid RAG pipeline',
    dataset: 'rag_benchmark_v3',
    total: 200,
    passed: 192,
    failed: 8,
    threshold: 0.8,
    judge: 'Mock generation',
    scorer: 'RAGAS 0.8.2',
    lastEvaluated: 'today at 14:35',
  },
  runs: [
    { id: 'ev_1', label: 'rag_benchmark_v3', date: 'Today, 14:35', score: 0.92, status: 'completed', questions: 200 },
    { id: 'ev_2', label: 'rag_benchmark_v3', date: 'Yesterday, 09:12', score: 0.89, status: 'completed', questions: 200 },
    { id: 'ev_3', label: 'support_golden_set', date: 'May 24, 16:40', score: 0.86, status: 'completed', questions: 120 },
    { id: 'ev_4', label: 'rag_benchmark_v3', date: 'May 21, 11:05', score: 0.84, status: 'completed', questions: 200 },
  ],
  settings: { passThreshold: 0.8, sampleSize: 200, judge: 'Mock generation', autoRun: true, metricWeights: { faithfulness: 0.4, relevance: 0.3, precision: 0.2, recall: 0.1 } },
})

export const experiments: Experiment[] = [
  { id: 'exp_024', name: 'EXP-024 Hybrid + MMR', chunking: 'Semantic · 512', retrieval: 'Hybrid α0.7', selection: 'MMR · λ0.7', faithfulness: 0.92, latency: 1.24, cost: 0.0062, status: 'complete', tags: ['retrieval', 'best'], project: 'Knowledge assistant', createdAt: 'Today, 14:02' },
  { id: 'exp_023', name: 'EXP-023 mock reranked', chunking: 'Semantic · 512', retrieval: 'Hybrid α0.5', selection: 'Top-K · 5', faithfulness: 0.9, latency: 1.18, cost: 0.0056, status: 'complete', tags: ['reranker'], project: 'Knowledge assistant', createdAt: 'Today, 13:48' },
  { id: 'exp_022', name: 'EXP-022 Baseline', chunking: 'Recursive · 512', retrieval: 'Dense only', selection: 'Top-K · 5', faithfulness: 0.88, latency: 0.82, cost: 0.0048, status: 'complete', tags: ['baseline'], project: 'Knowledge assistant', createdAt: 'Today, 13:31' },
  { id: 'exp_025', name: 'EXP-025 Custom ranking', chunking: 'Semantic · 768', retrieval: 'Hybrid α0.7', selection: 'DiversityRanker', faithfulness: null, latency: null, cost: null, status: 'running', tags: ['custom-node'], project: 'Knowledge assistant', createdAt: 'Today, 14:28' },
  { id: 'exp_021', name: 'EXP-021 Reward-guided', chunking: 'Recursive · 256', retrieval: 'BM25', selection: 'Reward function', faithfulness: null, latency: null, cost: null, status: 'failed', tags: ['exploration'], project: 'Knowledge assistant', createdAt: 'Today, 12:58' },
  { id: 'exp_020', name: 'EXP-020 Dense + MMR', chunking: 'Semantic · 512', retrieval: 'Dense only', selection: 'MMR · λ0.5', faithfulness: 0.87, latency: 0.91, cost: 0.0051, status: 'complete', tags: ['diversity'], project: 'Knowledge assistant', createdAt: 'Yesterday, 17:20' },
  { id: 'exp_019', name: 'EXP-019 Wide recall', chunking: 'Semantic · 768', retrieval: 'Hybrid α0.6', selection: 'Top-K · 10', faithfulness: 0.89, latency: 1.62, cost: 0.0078, status: 'complete', tags: ['recall'], project: 'Knowledge assistant', createdAt: 'Yesterday, 16:05' },
  { id: 'exp_018', name: 'EXP-018 Small chunks', chunking: 'Recursive · 256', retrieval: 'Hybrid α0.7', selection: 'Top-K · 5', faithfulness: 0.85, latency: 0.74, cost: 0.0041, status: 'complete', tags: ['chunking'], project: 'Knowledge assistant', createdAt: 'Yesterday, 14:44' },
]

export const experimentData = (): ExperimentData => ({
  project: { name: 'Retrieval optimization', dataset: 'rag_benchmark_v3', questions: 200 },
  summary: { experiments: 24, completed: 21, running: 2, bestScore: 0.92 },
  experiments,
  comparison: {
    ids: ['EXP-024', 'EXP-023', 'EXP-022'],
    parameters: [
      { key: 'Chunking', values: ['Semantic', 'Semantic', 'Recursive'] },
      { key: 'Selection', values: ['MMR', 'Top-K', 'Top-K'] },
      { key: 'Hybrid alpha', values: ['0.7', '0.5', '0.0'] },
      { key: 'Faithfulness', values: ['0.92  +4.5%', '0.90  +2.3%', '0.88'] },
    ],
    scatter: [
      { id: 'exp_024', name: 'Hybrid + MMR', latency: 1.24, faithfulness: 0.92, accent: '#35D99B' },
      { id: 'exp_023', name: 'Mock reranked', latency: 1.18, faithfulness: 0.9, accent: '#7296FF' },
      { id: 'exp_022', name: 'Baseline', latency: 0.82, faithfulness: 0.88, accent: '#A78BFA' },
      { id: 'exp_019', name: 'Wide recall', latency: 1.62, faithfulness: 0.89, accent: '#64748B' },
      { id: 'exp_018', name: 'Small chunks', latency: 0.74, faithfulness: 0.85, accent: '#64748B' },
    ],
    insight: 'Best configuration: EXP-024 improves faithfulness by 4.5% over the baseline.',
  },
})

export const customNodeData = (): CustomNode => seedCustomNode

export const nodeCatalog = (): NodeCatalogCategory[] =>
  nodeCategories.map((category) => ({
    category,
    description: {
      'Data Sources': 'Bring documents in from files, APIs and databases.',
      'Document Processing': 'Parse, normalize and chunk raw content.',
      Embeddings: 'Turn text into dense vector representations.',
      'Vector Databases': 'Store and index vectors for fast retrieval.',
      Retrieval: 'Find candidate context with lexical and semantic search.',
      Selection: 'Choose and diversify the final context window.',
      Reranking: 'Reorder candidates with cross-encoder precision.',
      'LLM Generation': 'Assemble prompts and generate grounded answers.',
      'Control Flow': 'Branch, merge and orchestrate pipeline stages.',
      Evaluation: 'Score quality inline with production traffic.',
      'Multimodal Processing': 'Understand images, tables and rich documents.',
    }[category],
    nodes: nodeDefinitions.filter((n) => n.category === category),
  }))

export const runTests = (): TestRun => ({
  id: `test_${Date.now()}`,
  status: 'passed',
  tests: [
    { name: 'test_returns_expected_count', status: 'passed', durationMs: 12 },
    { name: 'test_diversity_improves_coverage', status: 'passed', durationMs: 18 },
    { name: 'test_handles_empty_documents', status: 'passed', durationMs: 2 },
  ],
  summary: '3 tests passed',
  metrics: [
    { label: '5 ranked documents', value: '5 ranked documents' },
    { label: 'Diversity score', value: '0.89' },
    { label: 'Total time', value: '32ms' },
  ],
  finishedAt: new Date().toISOString(),
  logs: ['$ pytest test_ranker.py -v', 'collected 3 items', 'test_returns_expected_count PASSED [ 33%]', 'test_diversity_improves_coverage PASSED [ 66%]', 'test_handles_empty_documents PASSED [100%]', '3 passed in 0.32s'],
})

export const testCustomNode = (): CustomNodeTestOutput => ({
  id: `custom_test_${Date.now()}`,
  status: 'completed',
  nodeName: 'Diversity-aware ranker',
  documents: retrievedDocuments.slice(0, 5),
  diversityScore: 0.89,
  durationMs: 32,
  logs: ['Loaded node v1.3.0 (draft)', 'Input: 5 documents · query_embedding[128] (hash reference)', 'Applied MMR-like diversity selection · alpha=0.7', 'Selected 5 documents · diversity=0.89', 'Execution finished in 32ms'],
})

const pipelineStore: { pipeline: Pipeline } = {
  pipeline: JSON.parse(JSON.stringify(seedPipeline)) as Pipeline,
}

try {
  const saved = typeof window !== 'undefined' ? window.localStorage.getItem('rag-studio:pipeline') : null
  if (saved) pipelineStore.pipeline = { ...pipelineStore.pipeline, ...JSON.parse(saved) }
} catch {
  /* ignore */
}

export const db = {
  workspace,
  projects,
  pipeline: pipelineStore.pipeline,
  executions,
  experimentList: experiments,
  createdPipelineSummaries,
  savePipeline(pipeline: Pipeline) {
    this.pipeline = pipeline
    try {
      window.localStorage.setItem('rag-studio:pipeline', JSON.stringify(pipeline))
    } catch {
      /* ignore */
    }
    return pipeline
  },
  resetPipeline() {
    this.pipeline = JSON.parse(JSON.stringify(seedPipeline)) as Pipeline
    window.localStorage.removeItem('rag-studio:pipeline')
    return this.pipeline
  },
}

export { nodeCategories, nodeDefinitions, seedCustomNode, seedPipeline, retrievedDocuments }
export { pipedNode }
