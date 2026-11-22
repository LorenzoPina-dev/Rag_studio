import { describe, expect, it } from 'vitest'
import { filterRuns, runStatusTone } from './RunsTab'
import type { Execution } from '@/types'

function makeRun(overrides: Partial<Execution>): Execution {
  return {
    id: 'run_1',
    runNumber: 1,
    pipelineId: 'pl_hf_ready',
    pipelineName: 'HF RAG — pronta da eseguire',
    status: 'completed',
    startedAt: '12:00:00',
    durationMs: 21000,
    tokens: 0,
    cost: 0,
    environment: 'Development',
    trigger: 'Triggered manually',
    traceId: 'tr_1',
    nodeRuns: [],
    logs: [],
    errors: 0,
    warnings: 0,
    ...overrides,
  }
}

const runs = [
  makeRun({}),
  makeRun({ id: 'run_2', runNumber: 2, pipelineName: 'Real model RAG pipeline', status: 'failed' }),
  makeRun({ id: 'run_3', runNumber: 3, status: 'running' }),
]

describe('filterRuns', () => {
  it('filters by pipeline name, run id and run number', () => {
    expect(filterRuns(runs, 'hf rag', 'all').map((run) => run.id)).toEqual(['run_1', 'run_3'])
    expect(filterRuns(runs, 'RUN_2', 'all').map((run) => run.id)).toEqual(['run_2'])
    expect(filterRuns(runs, '#3', 'all').map((run) => run.id)).toEqual(['run_3'])
  })

  it('combines search and status filters', () => {
    expect(filterRuns(runs, '', 'failed').map((run) => run.id)).toEqual(['run_2'])
    expect(filterRuns(runs, 'hf rag', 'failed')).toEqual([])
  })
})

describe('runStatusTone', () => {
  it('maps every execution status to a visible tone', () => {
    expect(runStatusTone('completed')).toBe('success')
    expect(runStatusTone('failed')).toBe('danger')
    expect(runStatusTone('running')).toBe('running')
    expect(runStatusTone('queued')).toBe('warning')
    expect(runStatusTone('stopped')).toBe('idle')
  })
})
