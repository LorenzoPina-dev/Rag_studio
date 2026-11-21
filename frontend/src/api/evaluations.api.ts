import { http } from './client'
import type { EvaluationData } from '@/types'

export const evaluationsApi = {
  get: (): Promise<EvaluationData> => http.get('/evaluations'),
  run: (input: { pipeline: string; dataset: string; sampleSize: number }): Promise<{ id: string; status: string; startedAt: string }> =>
    http.post('/evaluations/run', input),
  updateSettings: (input: Partial<EvaluationData['settings']>): Promise<EvaluationData['settings']> =>
    http.patch('/evaluations/settings', input),
  async exportReport(): Promise<void> {
    const data = await http.get<EvaluationData>('/evaluations')
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `rag-studio-evaluation-${new Date().toISOString().slice(0, 10)}.json`
    anchor.click()
    URL.revokeObjectURL(url)
  },
}
