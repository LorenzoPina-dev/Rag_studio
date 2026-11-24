import { beforeEach, describe, expect, it, vi } from 'vitest'
import { executionsApi, type ExecutionStreamEvent, type StreamHandler } from '@/api/executions.api'
import type { Execution } from '@/types'

const handlers: StreamHandler[] = []
const unsubscribe = vi.fn()

vi.mock('@/api/executions.api', () => ({
  subscribeExecution: (_execution: Execution, handler: StreamHandler) => {
    handlers.push(handler)
    return unsubscribe
  },
  executionsApi: { get: vi.fn() },
}))

import { activeExecution, restoreActiveExecution } from './activeExecution'

function makeExecution(overrides: Partial<Execution> = {}): Execution {
  return {
    id: 'run_1',
    runNumber: 1,
    pipelineId: 'pl_test',
    pipelineName: 'Test pipeline',
    status: 'queued',
    startedAt: '2026-01-01T00:00:00Z',
    durationMs: 0,
    tokens: 0,
    cost: 0,
    environment: 'Development',
    trigger: 'manual',
    traceId: 'trace_1',
    nodeRuns: [
      { nodeId: 'n1', name: 'First', kind: 'loader', status: 'pending', durationMs: 0, outputCount: 0, accent: '#fff' },
      { nodeId: 'n2', name: 'Second', kind: 'chunking', status: 'pending', durationMs: 0, outputCount: 0, accent: '#fff' },
    ],
    logs: [],
    errors: 0,
    warnings: 0,
    ...overrides,
  }
}

function emit(event: ExecutionStreamEvent) {
  handlers[handlers.length - 1]?.(event)
}

describe('activeExecution', () => {
  beforeEach(() => {
    activeExecution.clear()
    handlers.length = 0
    unsubscribe.mockClear()
  })

  it('owns a single stream and replays the snapshot to late subscribers', () => {
    const seen: string[] = []
    activeExecution.start(makeExecution())
    expect(handlers).toHaveLength(1)

    emit({ type: 'status', status: 'running' })
    emit({ type: 'node', node: { ...makeExecution().nodeRuns[0], status: 'running' } })
    emit({ type: 'log', log: { id: 'log_1', timestamp: '00:00:00', level: 'INFO', message: 'started' } })

    activeExecution.subscribe((snapshot) => {
      if (snapshot) seen.push(snapshot.execution.status)
    })
    const current = activeExecution.get()
    expect(current?.execution.status).toBe('running')
    expect(current?.execution.nodeRuns[0].status).toBe('running')
    expect(current?.logs.map((log) => log.id)).toEqual(['log_1'])
    expect(seen).toEqual(['running'])

    // Re-attaching from another page must not open a second stream.
    activeExecution.start(makeExecution())
    expect(handlers).toHaveLength(1)
  })

  it('closes the stream on completion and lets a new run start', () => {
    activeExecution.start(makeExecution())
    const completed = makeExecution({ status: 'completed', durationMs: 1200 })
    emit({ type: 'done', status: 'completed', execution: completed })

    expect(activeExecution.get()?.terminal).toBe(true)
    expect(activeExecution.get()?.execution.status).toBe('completed')
    expect(unsubscribe).toHaveBeenCalledTimes(1)

    activeExecution.start(makeExecution({ id: 'run_2', runNumber: 2 }))
    expect(handlers).toHaveLength(2)
    expect(activeExecution.get()?.execution.id).toBe('run_2')
  })

  it('records the stream error as a terminal failed state', () => {
    activeExecution.start(makeExecution())
    emit({ type: 'error', status: 'failed', detail: 'Connessione interrotta' })

    expect(activeExecution.get()?.terminal).toBe(true)
    expect(activeExecution.get()?.execution.status).toBe('failed')
    expect(activeExecution.get()?.error).toBe('Connessione interrotta')
    expect(unsubscribe).toHaveBeenCalledTimes(1)
  })

  it('applies an API-side stop without waiting for the next frame', () => {
    activeExecution.start(makeExecution())
    activeExecution.update({ ...makeExecution(), status: 'stopped' })
    expect(activeExecution.get()?.execution.status).toBe('stopped')
  })

  it('reattaches to a still-running run after a page reload', async () => {
    sessionStorage.setItem('rag-studio.active-execution', 'run_1')
    vi.mocked(executionsApi.get).mockResolvedValue(makeExecution({ status: 'running' }))

    await restoreActiveExecution()

    expect(activeExecution.get()?.execution.id).toBe('run_1')
    expect(handlers).toHaveLength(1)
  })
})
