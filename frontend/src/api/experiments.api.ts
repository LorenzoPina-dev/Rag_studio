import { http } from './client'
import type { Experiment, ExperimentData } from '@/types'

export interface ComparisonData {
  ids: string[]
  parameters: Array<{ key: string; values: string[] }>
  scatter: Array<{ id: string; name: string; latency: number; faithfulness: number; accent: string }>
  insight: string
}

export const experimentsApi = {
  get: (): Promise<ExperimentData> => http.get('/experiments'),
  create: (input: { name: string }): Promise<Experiment> => http.post('/experiments', input),
  compare: (ids: string[]): Promise<ComparisonData> => http.post('/experiments/compare', { ids }),
  promote: (id: string): Promise<{ ok: boolean; experimentId: string }> => http.post(`/experiments/${id}/promote`),
}
