/**
 * MOCK ADAPTER — development only.
 * Implements the exact same REST contract as the FastAPI routers.
 * Every response is typed by the domain API modules; swapping this for the
 * real backend only requires VITE_USE_MOCKS=false.
 */
import { ApiError } from '../client'
import type {
  CustomNodeDependency,
  CustomNodeTestOutput,
  DashboardData,
  DataSource,
  Dataset,
  DatasetCreateInput,
  DatasetsData,
  EvaluationData,
  Execution,
  ExecutionResult,
  Experiment,
  ExperimentData,
  Model,
  ModelType,
  ModelsData,
  NodeCatalogCategory,
  Pipeline,
  PipelineSummary,
  Project,
  SearchResult,
  SystemStatus,
  TestRun,
} from '@/types'
import {
  activity,
  customNodeData,
  dashboardData,
  datasetsData,
  db,
  evaluationData,
  executionResults,
  executions,
  experimentData,
  modelsData,
  nodeCatalog,
  pipelineSummaries,
  projects,
  runTests,
  testCustomNode,
  workspace,
} from './db'
import { createNodeFromDefinition, nodeDefinitions, seedCustomNode, seedPipeline } from './pipelineSeed'
import { getTechnique, techniqueCategories, techniques, techniquePhases } from './techniques'

const delay = (ms = 180) => new Promise((resolve) => setTimeout(resolve, ms + Math.random() * 120))

function match(path: string, pattern: string): string[] | null {
  const pathParts = path.split('?')[0].split('/').filter(Boolean)
  const patternParts = pattern.split('/').filter(Boolean)
  if (pathParts.length !== patternParts.length) return null
  const params: string[] = []
  for (let i = 0; i < patternParts.length; i++) {
    if (patternParts[i].startsWith(':')) params.push(decodeURIComponent(pathParts[i]))
    else if (patternParts[i] !== pathParts[i]) return null
  }
  return params
}

function nowIso() {
  return new Date().toISOString()
}

const createdPipelines: Record<string, Pipeline> = {}

function makeExecution(pipeline: Pipeline): Execution {
  const runNumber = executions.reduce((max, e) => Math.max(max, e.runNumber ?? 0), 2486) + 1
  const nodeRuns = pipeline.nodes.map((node) => ({
    nodeId: node.id,
    name: node.name,
    kind: node.kind,
    status: 'pending' as const,
    durationMs: 0,
    outputCount: node.kind === 'chunking' ? 24816 : node.kind === 'reranking' ? 5 : node.kind === 'retrieval' ? 20 : node.kind === 'input' ? 1 : 248,
    accent: node.accent,
  }))
  return {
    id: `run_${runNumber}`,
    runNumber,
    pipelineId: pipeline.id,
    pipelineName: pipeline.name,
    status: 'running',
    startedAt: `Today, ${new Date().toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}`,
    durationMs: 0,
    tokens: 0,
    cost: 0,
    environment: pipeline.environment,
    trigger: 'Triggered manually',
    traceId: `tr_${Math.random().toString(16).slice(2, 10)}`,
    errors: 0,
    warnings: 0,
    stagesCached: false,
    logs: [],
    nodeRuns,
  }
}

export async function mockRequest<T>(method: string, path: string, body?: unknown): Promise<T> {
  await delay()
  const cleanPath = path.split('?')[0]
  let params: string[] | null

  if (method === 'GET' && (params = match(cleanPath, '/system/status'))) {
    return {
      state: 'operational',
      version: 'v0.8.2',
      python: 'Python 3.11.8',
      connected: true,
      branch: 'main*',
      errors: 0,
      warnings: 0,
    } satisfies SystemStatus as T
  }

  if (method === 'GET' && (params = match(cleanPath, '/workspace'))) {
    return workspace as T
  }

  if (method === 'GET' && match(cleanPath, '/dashboard')) {
    return dashboardData() as T
  }

  if (method === 'GET' && match(cleanPath, '/projects')) {
    return projects as T
  }

  if (method === 'POST' && match(cleanPath, '/projects')) {
    const input = body as { name: string; description?: string }
    const project: Project = {
      id: `pr_${Date.now()}`,
      name: input.name,
      description: input.description ?? 'New retrieval workspace',
      health: 'draft',
      pipelineCount: 0,
      chunkCount: 0,
      editedAt: 'just now',
      updatedAt: nowIso(),
      accent: '#7296FF',
    }
    db.projects.unshift(project)
    return project as T
  }

  if (method === 'PATCH' && (params = match(cleanPath, '/projects/:id'))) {
    const project = db.projects.find((p) => p.id === params![0])
    if (!project) throw new ApiError(404, 'Project not found')
    Object.assign(project, body)
    return project as T
  }

  if (method === 'DELETE' && (params = match(cleanPath, '/projects/:id'))) {
    const idx = db.projects.findIndex((p) => p.id === params![0])
    if (idx >= 0) db.projects.splice(idx, 1)
    return { ok: true } as T
  }

  if (method === 'GET' && match(cleanPath, '/pipelines')) {
    return pipelineSummaries() as T
  }

  if (method === 'POST' && match(cleanPath, '/pipelines')) {
    const input = body as { name: string; projectId?: string; template?: string }
    const id = `pl_${Date.now()}`
    const pipeline: Pipeline = {
      id,
      projectId: input.projectId ?? 'pr_knowledge',
      name: input.name,
      description: 'A new retrieval-augmented generation pipeline.',
      environment: 'Development',
      status: 'draft',
      version: 'v0.1.0',
      updatedAt: nowIso(),
      nodes:
        input.template === 'blank'
          ? []
          : [createNodeFromDefinition('document-source', `n_${id}_1`, { x: 80, y: 80 })],
      edges: [],
    }
    createdPipelines[id] = pipeline
    db.createdPipelineSummaries.unshift({
      id,
      projectId: pipeline.projectId,
      projectName: projects.find((p) => p.id === pipeline.projectId)?.name ?? 'Knowledge assistant',
      name: pipeline.name,
      nodeCount: pipeline.nodes.length,
      connectionCount: pipeline.edges.length,
      status: pipeline.status,
      environment: pipeline.environment,
      updatedAt: pipeline.updatedAt,
      lastRunStatus: 'draft',
      lastRunAt: 'never',
    })
    db.savePipeline(pipeline)
    return pipeline as T
  }

  if (method === 'GET' && (params = match(cleanPath, '/pipelines/:id'))) {
    const id = params[0]
    if (createdPipelines[id]) return createdPipelines[id] as T
    if (id === db.pipeline.id) return db.pipeline as T
    if (id === 'pl_semantic_v2') {
      const clone = JSON.parse(JSON.stringify(seedPipeline)) as Pipeline
      clone.id = 'pl_semantic_v2'
      clone.name = 'Semantic search v2'
      clone.environment = 'Production'
      clone.version = 'v1.8.0'
      return clone as T
    }
    return db.pipeline as T
  }

  if (method === 'PATCH' && (params = match(cleanPath, '/pipelines/:id'))) {
    const id = params[0]
    const base = createdPipelines[id] ?? db.pipeline
    const updated = { ...base, ...(body as Partial<Pipeline>), id, updatedAt: nowIso() }
    if (createdPipelines[id]) {
      createdPipelines[id] = updated
      const summary = db.createdPipelineSummaries.find((p) => p.id === id)
      if (summary) {
        summary.name = updated.name
        summary.status = updated.status
        summary.environment = updated.environment
        summary.nodeCount = updated.nodes.length
        summary.connectionCount = updated.edges.length
        summary.updatedAt = updated.updatedAt
      }
    } else {
      db.savePipeline(updated)
    }
    return updated as T
  }

  if (method === 'DELETE' && (params = match(cleanPath, '/pipelines/:id'))) {
    return { ok: true, id: params[0] } as T
  }

  if (method === 'POST' && (params = match(cleanPath, '/pipelines/:id/validate'))) {
    const nodes = db.pipeline.nodes
    const incoming = new Map<string, number>()
    db.pipeline.edges.forEach((e) => incoming.set(e.target, (incoming.get(e.target) ?? 0) + 1))
    const errors = nodes
      .filter((n) => n.inputs.length > 0 && !incoming.has(n.id))
      .map((n, i) => ({
        id: `err_${i}`,
        severity: 'error' as const,
        message: `Required input is not connected on “${n.name}”.`,
        nodeId: n.id,
      }))
    const warnings = db.pipeline.nodes.some((n) => n.kind === 'generation' && n.config.temperature === 0)
      ? []
      : [
          {
            id: 'warn_temp',
            severity: 'warning' as const,
            message: 'LLM temperature is above 0 — answers may vary between runs.',
            nodeId: db.pipeline.nodes.find((n) => n.kind === 'generation')?.id,
          },
        ]
    return {
      valid: errors.length === 0,
      errors,
      warnings,
      checkedAt: nowIso(),
    } as T
  }

  if (method === 'POST' && (params = match(cleanPath, '/pipelines/:id/run'))) {
    const existing = makeExecution(db.pipeline)
    executions.unshift(existing)
    db.pipeline = { ...db.pipeline, status: 'running' }
    return existing as T
  }

  if (method === 'POST' && (params = match(cleanPath, '/pipelines/:id/duplicate'))) {
    const clone = { ...JSON.parse(JSON.stringify(db.pipeline)), id: `pl_${Date.now()}`, name: `${db.pipeline.name} (copy)`, version: 'v0.1.0', status: 'draft' as const }
    return clone as T
  }

  if (method === 'POST' && match(cleanPath, '/comparison/run')) {
    const input = body as { query: string; variants: Array<{ id: string; label: string; config?: Record<string, string | number | boolean> }> }
    return {
      query: input.query,
      variants: input.variants.map((variant, index) => ({
        id: variant.id,
        label: variant.label,
        config: { retrievalAlgorithm: 'mock', ...(variant.config ?? {}) },
        answer: `[mock] Risposta seedata per "${input.query}". Avvia il backend con VITE_USE_MOCKS=false per il confronto reale.`,
        citations: [],
        documents: [
          {
            rank: 1,
            title: 'Mock retrieval result',
            source: 'docs/mock.md',
            chunkId: `mock_chunk_${index + 1}`,
            score: 0.9 - index * 0.1,
            excerpt: 'Questo risultato è generato dal mock adapter frontend.',
          },
        ],
        metrics: { chunks: 8, retrieved: 8, selected: 5, tokens: 120 + index * 20, documents: 8, dimensions: 128 },
        durationMs: 12 + index * 4,
      })),
    } as T
  }

  if (method === 'GET' && (params = match(cleanPath, '/nodes'))) {
    return nodeDefinitions as T
  }

  if (method === 'GET' && match(cleanPath, '/nodes/catalog')) {
    return nodeCatalog() as unknown as T
  }

  if (method === 'GET' && match(cleanPath, '/techniques')) {
    return techniques as T
  }

  if (method === 'GET' && match(cleanPath, '/techniques/categories')) {
    return techniqueCategories() as T
  }

  if (method === 'GET' && match(cleanPath, '/techniques/phases')) {
    return techniquePhases() as T
  }

  if (method === 'GET' && (params = match(cleanPath, '/techniques/:id'))) {
    const technique = getTechnique(params[0])
    if (!technique) throw new ApiError(404, 'Technique not found')
    return technique as T
  }

  if (method === 'GET' && match(cleanPath, '/datasets/metrics')) {
    return datasetsData().metrics as T
  }

  if (method === 'GET' && match(cleanPath, '/datasets')) {
    return datasetsData() as T
  }

  if (method === 'GET' && match(cleanPath, '/datasets/options')) {
    return datasetsData().datasets.map((dataset) => ({ value: dataset.id, label: dataset.name, description: dataset.sourceType })) as T
  }

  if (method === 'POST' && match(cleanPath, '/datasets')) {
    const input = body as DatasetCreateInput
    const dataset: Dataset = {
      id: `ds_${Date.now()}`,
      name: input.name,
      sourceType: input.sourceType,
      format: input.format ?? 'Text · JSON',
      documents: input.items?.length ?? 0,
      chunks: input.items?.length ?? 0,
      lastSync: 'Just now',
      status: input.items?.length ? 'indexed' : 'ingesting',
      path: input.path,
      embedding: 'Hash embeddings (reference)',
      chunking: 'Semantic · 512 tokens',
      usedBy: 0,
      size: '—',
      health: 'healthy',
      items: input.items ?? [],
      connection: input.connection ?? {},
    }
    const data = datasetsData()
    data.datasets.unshift(dataset)
    data.sources.unshift({
      id: `src_${Date.now()}`,
      name: input.name,
      type: input.sourceType as DataSource['type'],
      status: 'connected',
      documents: dataset.documents,
      lastSync: 'Just now',
      config: input.path || input.name,
      datasets: 1,
    })
    return dataset as T
  }

  if (method === 'POST' && match(cleanPath, '/datasets/sync')) {
    const data = datasetsData()
    data.datasets.forEach((d) => {
      if (d.status === 'ingesting') {
        d.status = 'indexed'
        d.documentsProcessed = d.documentsTotal
        d.health = 'healthy'
      }
      d.lastSync = 'just now'
    })
    data.jobs.forEach((j) => {
      if (j.status === 'running') {
        j.status = 'completed'
        j.progress = 100
        j.duration = '2m 10s'
      }
    })
    return { ok: true, syncedAt: nowIso() } as T
  }

  if (method === 'GET' && (params = match(cleanPath, '/datasets/:id'))) {
    const dataset = datasetsData().datasets.find((d) => d.id === params![0])
    if (!dataset) throw new ApiError(404, 'Dataset not found')
    return dataset as T
  }

  if (method === 'PATCH' && (params = match(cleanPath, '/datasets/:id'))) {
    const data = datasetsData()
    const dataset = data.datasets.find((d) => d.id === params![0])
    if (!dataset) throw new ApiError(404, 'Dataset not found')
    Object.assign(dataset, body)
    return dataset as T
  }

  if (method === 'DELETE' && (params = match(cleanPath, '/datasets/:id'))) {
    const data = datasetsData()
    const index = data.datasets.findIndex((d) => d.id === params![0])
    if (index < 0) throw new ApiError(404, 'Dataset not found')
    data.datasets.splice(index, 1)
    return undefined as T
  }

  if (method === 'POST' && (params = match(cleanPath, '/datasets/:id/documents'))) {
    const dataset = datasetsData().datasets.find((d) => d.id === params![0])
    if (!dataset) throw new ApiError(404, 'Dataset not found')
    const input = body as { filename?: string; text?: string }
    const text = input.text ?? ''
    const filename = input.filename ?? 'pasted.txt'
    let items: Array<{ id: string; title: string; source: string; content: string }> = []
    if (filename.endsWith('.jsonl')) {
      items = text.split('\n').filter(Boolean).map((line, index) => {
        const record = JSON.parse(line) as Record<string, string>
        return { id: record.id ?? `doc_${index}`, title: record.title ?? `Document ${index + 1}`, source: record.source ?? filename, content: record.content ?? '' }
      })
    } else if (filename.endsWith('.json')) {
      const parsed = JSON.parse(text) as Array<Record<string, string>>
      items = (Array.isArray(parsed) ? parsed : [parsed]).map((record, index) => ({
        id: record.id ?? `doc_${index}`, title: record.title ?? `Document ${index + 1}`, source: record.source ?? filename, content: record.content ?? '',
      }))
    } else {
      items = [{ id: `doc_${Date.now()}`, title: filename, source: filename, content: text }]
    }
    dataset.items = [...(dataset.items ?? []), ...items]
    dataset.documents = dataset.items.length
    dataset.chunks = dataset.items.length
    dataset.status = 'indexed'
    dataset.lastSync = 'Just now'
    return dataset as T
  }

  if (method === 'POST' && (params = match(cleanPath, '/datasets/:id/sync'))) {
    const dataset = datasetsData().datasets.find((d) => d.id === params![0])
    if (!dataset) throw new ApiError(404, 'Dataset not found')
    dataset.lastSync = 'Just now'
    dataset.status = 'indexed'
    return dataset as T
  }

  if (method === 'POST' && (params = match(cleanPath, '/datasets/:id/reindex'))) {
    return { ok: true, datasetId: params[0], jobId: `job_${Date.now()}` } as T
  }

  if (method === 'POST' && match(cleanPath, '/datasources')) {
    const input = body as { name: string; type: string }
    const source: DataSource = {
      id: `src_${Date.now()}`,
      name: input.name,
      type: input.type as DataSource['type'],
      status: 'connected',
      documents: 0,
      lastSync: 'just now',
      config: 'Configured just now',
      datasets: 0,
    }
    datasetsData().sources.unshift(source)
    return source as T
  }

  if (method === 'POST' && (params = match(cleanPath, '/datasources/:id/sync'))) {
    return { ok: true, sourceId: params[0], syncedAt: nowIso() } as T
  }

  if (method === 'GET' && match(cleanPath, '/datasources')) {
    return datasetsData().sources as T
  }

  if (method === 'GET' && match(cleanPath, '/ingestion-jobs')) {
    return datasetsData().jobs as T
  }

  if (method === 'GET' && match(cleanPath, '/models')) {
    return modelsData() as T
  }

  if (method === 'GET' && match(cleanPath, '/models/providers')) {
    return modelsData().providers as T
  }

  if (method === 'GET' && match(cleanPath, '/models/resources')) {
    return modelsData().resources as T
  }

  if (method === 'POST' && match(cleanPath, '/models')) {
    const input = body as { name: string; provider: string; type: string }
    const data = modelsData()
    const model: Model = {
      id: `m_${Date.now()}`,
      name: input.name,
      provider: input.provider,
      type: input.type as ModelType,
      context: '—',
      status: 'ready',
      description: 'Newly registered model.',
      architecture: '—',
      parameters: '—',
      dimensions: '—',
      maxSequence: '—',
      precision: '—',
      device: input.provider,
      memory: '—',
      license: '—',
      usedBy: 0,
      local: !['OpenAI', 'Anthropic', 'Cohere'].includes(input.provider),
    }
    data.models.unshift(model)
    const provider = data.providers.find((p) => p.name === input.provider)
    if (provider) {
      provider.models += 1
      provider.detail = `${provider.models} models ${provider.type === 'Local runtime' || provider.type === 'Local inference' ? 'installed' : 'available'}`
    }
    return model as T
  }

  if (method === 'POST' && (params = match(cleanPath, '/models/:id/test'))) {
    const input = body as { prompt: string }
    return {
      modelId: params[0],
      output: `[Mock generation · reference] Grounded response for “${input.prompt}”: hybrid retrieval fuses dense and sparse candidates before reranking. [1][2]`,
      latencyMs: 842 + Math.round(Math.random() * 400),
      tokens: 156,
      cost: 0.0018,
    } as T
  }

  if (method === 'GET' && match(cleanPath, '/executions')) {
    return executions as T
  }

  if (method === 'POST' && match(cleanPath, '/executions')) {
    const execution = makeExecution(db.pipeline)
    executions.unshift(execution)
    return execution as T
  }

  if (method === 'GET' && (params = match(cleanPath, '/executions/:id'))) {
    const execution = executions.find((e) => e.id === params![0])
    if (!execution) throw new ApiError(404, 'Execution not found')
    if (execution.status === 'running' && execution.logs.length > 0) {
      return { ...execution, status: 'completed', durationMs: 1240, tokens: 1842, cost: 0.0062 } as T
    }
    return execution as T
  }

  if (method === 'POST' && (params = match(cleanPath, '/executions/:id/stop'))) {
    const execution = executions.find((e) => e.id === params![0])
    if (execution) execution.status = 'stopped'
    return { ok: true, status: 'stopped' } as T
  }

  if (method === 'GET' && (params = match(cleanPath, '/executions/:id/logs'))) {
    const execution = executions.find((e) => e.id === params![0])
    return (execution?.logs ?? []) as T
  }

  if (method === 'GET' && (params = match(cleanPath, '/executions/:id/results'))) {
    return executionResults() as T
  }

  if (method === 'GET' && (params = match(cleanPath, '/executions/:id/artifacts/:artifact'))) {
    return { id: params[1], executionId: params[0], url: `https://artifacts.local/${params[0]}/${params[1]}` } as T
  }

  if (method === 'GET' && match(cleanPath, '/experiments')) {
    return experimentData() as T
  }

  if (method === 'POST' && match(cleanPath, '/experiments')) {
    const input = body as { name: string }
    const experiment: Experiment = {
      id: `exp_${Date.now()}`,
      name: input.name,
      chunking: 'Semantic · 512',
      retrieval: 'Hybrid α0.7',
      selection: 'MMR · λ0.7',
      faithfulness: null,
      latency: null,
      cost: null,
      status: 'running',
      tags: ['new'],
      project: 'Knowledge assistant',
      createdAt: 'just now',
    }
    db.experimentList.unshift(experiment)
    return experiment as T
  }

  if (method === 'POST' && match(cleanPath, '/experiments/compare')) {
    return experimentData().comparison as T
  }

  if (method === 'POST' && (params = match(cleanPath, '/experiments/:id/promote'))) {
    return { ok: true, experimentId: params[0], promotedAt: nowIso() } as T
  }

  if (method === 'GET' && match(cleanPath, '/evaluations')) {
    return evaluationData() as T
  }

  if (method === 'POST' && match(cleanPath, '/evaluations/run')) {
    return { id: `ev_${Date.now()}`, status: 'running', startedAt: nowIso() } as T
  }

  if (method === 'PATCH' && match(cleanPath, '/evaluations/settings')) {
    return { ...evaluationData().settings, ...(body as object) } as T
  }

  if (method === 'GET' && match(cleanPath, '/custom-nodes')) {
    return [customNodeData()] as T
  }

  if (method === 'GET' && match(cleanPath, '/custom-nodes/templates')) {
    return [
      { id: 'ranking', name: 'Ranking algorithm', description: 'Reorder candidates with a custom scoring function.' },
      { id: 'reward', name: 'Reward function', description: 'Score documents against a learned objective.' },
      { id: 'selection', name: 'Selection strategy', description: 'Choose context under a token budget.' },
      { id: 'transform', name: 'Document transform', description: 'Normalize or enrich documents before indexing.' },
    ] as T
  }

  if (method === 'GET' && (params = match(cleanPath, '/custom-nodes/:id/test-results'))) {
    return runTests() as unknown as T
  }

  if (method === 'GET' && (params = match(cleanPath, '/custom-nodes/:id/versions'))) {
    return seedCustomNode.versions as T
  }

  if (method === 'GET' && (params = match(cleanPath, '/custom-nodes/:id'))) {
    return customNodeData() as T
  }

  if (method === 'PATCH' && (params = match(cleanPath, '/custom-nodes/:id'))) {
    return { ...customNodeData(), ...(body as object), updatedAt: nowIso() } as T
  }

  if (method === 'POST' && (params = match(cleanPath, '/custom-nodes/:id/tests'))) {
    return runTests() as unknown as T
  }

  if (method === 'POST' && (params = match(cleanPath, '/custom-nodes/:id/test'))) {
    return testCustomNode() as unknown as T
  }

  if (method === 'POST' && (params = match(cleanPath, '/custom-nodes/:id/dependencies'))) {
    const input = body as CustomNodeDependency
    return { ...input, installed: true } as T
  }

  if (method === 'POST' && (params = match(cleanPath, '/custom-nodes/:id/publish'))) {
    return { id: params[0], version: 'v1.3.0', status: 'published', publishedAt: nowIso() } as T
  }

  if (method === 'POST' && (params = match(cleanPath, '/custom-nodes/:id/versions/:version/restore'))) {
    return { ...customNodeData(), draftVersion: params[1] } as T
  }

  if (method === 'GET' && match(cleanPath, '/search')) {
    const q = new URL(path, 'http://localhost').searchParams.get('q')?.toLowerCase() ?? ''
    const results: SearchResult[] = [
      ...db.projects
        .filter((p) => p.name.toLowerCase().includes(q))
        .map((p) => ({ id: p.id, type: 'project' as const, title: p.name, subtitle: p.description, href: '/projects' })),
      ...pipelineSummaries()
        .filter((p) => p.name.toLowerCase().includes(q))
        .map((p) => ({ id: p.id, type: 'pipeline' as const, title: p.name, subtitle: p.projectName, href: '/pipelines/pl_hybrid_rag' })),
      ...datasetsData()
        .datasets.filter((d) => d.name.toLowerCase().includes(q))
        .map((d) => ({ id: d.id, type: 'dataset' as const, title: d.name, subtitle: `${d.documents.toLocaleString()} documents`, href: '/datasets' })),
      ...modelsData()
        .models.filter((m) => m.name.toLowerCase().includes(q))
        .map((m) => ({ id: m.id, type: 'model' as const, title: m.name, subtitle: `${m.provider} · ${m.type}`, href: '/models' })),
      ...experimentData()
        .experiments.filter((e) => e.name.toLowerCase().includes(q))
        .map((e) => ({ id: e.id, type: 'experiment' as const, title: e.name, subtitle: e.status, href: '/experiments' })),
      ...nodeDefinitions
        .filter((n) => n.name.toLowerCase().includes(q))
        .map((n) => ({ id: n.id, type: 'node' as const, title: n.name, subtitle: n.category, href: '/nodes' })),
    ].slice(0, 20)
    return results as T
  }

  if (method === 'GET' && match(cleanPath, '/activity')) {
    return activity as T
  }

  throw new ApiError(404, `Mock endpoint not found: ${method} ${path}`)
}

export type { DashboardData, DatasetsData, ModelsData, ExperimentData, EvaluationData, ExecutionResult, Dataset, Project, Pipeline }
