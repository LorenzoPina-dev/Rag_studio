import * as React from 'react'
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Execution, ExecutionResult } from '@/types'

const { useQueryMock, useActiveExecutionMock } = vi.hoisted(() => ({
  useQueryMock: vi.fn(),
  useActiveExecutionMock: vi.fn(() => null),
}))

vi.mock('@tanstack/react-query', () => ({ useQuery: useQueryMock }))
vi.mock('@/lib/activeExecution', () => ({ useActiveExecution: useActiveExecutionMock }))
vi.mock('@/api/executions.api', () => ({ executionsApi: { get: vi.fn(), results: vi.fn() } }))
vi.mock('react-router-dom', () => ({
  useParams: () => ({ runId: 'run_1' }),
  useNavigate: () => vi.fn(),
  Link: ({ children }: { children: React.ReactNode }) => React.createElement('span', null, children),
}))

import { ResultsPage } from './ResultsPage'

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

const execution = (status: Execution['status'], secondStatus: string): Execution => ({
  id: 'run_1',
  runNumber: 1,
  pipelineId: 'pl_1',
  pipelineName: 'Hybrid RAG pipeline',
  status,
  startedAt: 'Today, 12:00:00',
  durationMs: 1000,
  tokens: 10,
  cost: 0,
  environment: 'Development',
  trigger: 'manual',
  traceId: 'tr_1',
  errors: 0,
  warnings: 0,
  nodeRuns: [
    { nodeId: 'n_query', name: 'Query input', kind: 'input', status: 'completed', durationMs: 10, outputCount: 1, accent: '#fff' },
    { nodeId: 'n_llm', name: 'LLM Generation', kind: 'generation', status: secondStatus as never, durationMs: 0, outputCount: 0, accent: '#fff' },
    { nodeId: 'n_embed', name: 'Hash embeddings', kind: 'embedding', status: (status === 'completed' ? 'completed' : 'pending') as never, durationMs: 0, outputCount: 0, accent: '#fff' },
  ],
  logs: [],
} as unknown as Execution)

const results = (withAnswer: boolean): ExecutionResult => ({
  id: 'res_1',
  executionId: 'run_1',
  query: 'cheap RAG?',
  retrievedCount: 0,
  selectedCount: 0,
  errorCount: 0,
  stages: [],
  traceId: 'tr_1',
  documents: [],
  chunk: {} as never,
  generatedAnswer: withAnswer ? 'Risposta finale [1]' : '',
  answerMeta: { model: 'reference', temperature: 0.2, citations: 0 },
  lineage: [{ label: 'Query input', detail: '1 query', indent: 0, accent: '#fff' }],
  nodeOutputs: [],
  stepOutputs: [
    {
      nodeId: 'n_query',
      name: 'Query input',
      kind: 'input',
      detail: '1 query',
      accent: '#fff',
      status: 'completed',
      durationMs: 10,
      outputPorts: ['out_query'],
      text: 'cheap RAG?',
      items: [],
      metrics: [{ label: 'Stato', value: 'completed' }],
      searchHint: 'Cerca…',
    },
  ],
  embedding: { model: 'reference', dimensions: 0, cosineSimilarity: 0, values: [], norm: '1', dtype: 'float32' },
  runtime: { latencyMs: 10, peakMemoryMb: 0, tokensPerSecond: 0, breakdown: [] },
} as unknown as ExecutionResult)

function mockQueries(run: Execution, result: ExecutionResult) {
  useQueryMock.mockImplementation((options: { queryKey: string[] }) =>
    options.queryKey[0] === 'execution'
      ? { data: run, isLoading: false, isError: false, error: null, refetch: vi.fn() }
      : { data: result, isLoading: false, isError: false, error: null, refetch: vi.fn() },
  )
}

describe('ResultsPage mixed intermediate view', () => {
  let container: HTMLDivElement
  let root: Root

  afterEach(() => {
    act(() => root.unmount())
    container.remove()
    vi.clearAllMocks()
    useActiveExecutionMock.mockReturnValue(null)
  })

  it('shows completed step results and marks unfinished nodes as in progress', () => {
    mockQueries(execution('running', 'running'), results(false))
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)

    act(() => root.render(React.createElement(ResultsPage)))

    const text = container.textContent ?? ''
    expect(text).toContain('cheap RAG?')
    expect(text).toContain('in corso')
    expect(text).toContain('in attesa')
    expect(text).toContain('Risultati parziali')
    expect(text).not.toContain('Risposta finale')
  })

  it('renders the complete result once the run has finished', () => {
    mockQueries(execution('completed', 'completed'), results(true))
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)

    act(() => root.render(React.createElement(ResultsPage)))

    const text = container.textContent ?? ''
    expect(text).toContain('Risposta finale')
    expect(text).toContain('All intermediate outputs are persisted')
    expect(text).not.toContain('Risultati parziali')
  })
})
