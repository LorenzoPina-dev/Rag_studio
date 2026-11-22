import { beforeEach, describe, expect, it, vi } from 'vitest'

const { get } = vi.hoisted(() => ({ get: vi.fn() }))
vi.mock('./client', () => ({ API_BASE: '/api/v1', http: { get }, isMockMode: false }))

import { executionsApi } from './executions.api'

beforeEach(() => {
  get.mockReset()
})

describe('executionsApi.list', () => {
  it('loads the execution history used by the dashboard Runs tab', async () => {
    const runs = [{ id: 'run_1', runNumber: 1, status: 'completed' }]
    get.mockResolvedValue(runs)

    const result = await executionsApi.list()

    expect(get).toHaveBeenCalledWith('/executions')
    expect(result).toEqual(runs)
  })
})

describe('executionsApi.results', () => {
  it('loads the results of a specific run', async () => {
    get.mockResolvedValue({ id: 'res_1', executionId: 'run_1', generatedAnswer: 'answer' })

    const result = await executionsApi.results('run_1')

    expect(get).toHaveBeenCalledWith('/executions/run_1/results')
    expect(result).toMatchObject({ generatedAnswer: 'answer' })
  })
})
