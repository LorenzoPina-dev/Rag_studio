import { apiBaseUrl, http, isMockMode } from './client'
import type { Execution, Pipeline, PipelineSummary, ValidationResult } from '@/types'
import { downloadFile } from '@/lib/utils'

export const pipelinesApi = {
  list: (): Promise<PipelineSummary[]> => http.get('/pipelines'),
  get: (id: string): Promise<Pipeline> => http.get(`/pipelines/${id}`),
  create: (input: { name: string; projectId?: string; template?: 'blank' | 'starter' }): Promise<Pipeline> => http.post('/pipelines', input),
  update: (id: string, input: Partial<Pipeline>): Promise<Pipeline> => http.patch(`/pipelines/${id}`, input),
  remove: (id: string): Promise<{ ok: boolean }> => http.delete(`/pipelines/${id}`),
  validate: (id: string): Promise<ValidationResult> => http.post(`/pipelines/${id}/validate`),
  run: (id: string): Promise<Execution> => http.post(`/pipelines/${id}/run`),
  duplicate: (id: string): Promise<Pipeline> => http.post(`/pipelines/${id}/duplicate`),
  async export(id: string): Promise<void> {
    const pipeline = await http.get<Pipeline>(`/pipelines/${id}`)
    downloadFile(`${pipeline.name.toLowerCase().replace(/\s+/g, '-')}.json`, JSON.stringify(pipeline, null, 2))
  },
  async exportPython(id: string, query?: string): Promise<void> {
    const filename = `pipeline-${id}.py`
    if (isMockMode) {
      const pipeline = await http.get<Pipeline>(`/pipelines/${id}`)
      const config = Object.fromEntries(pipeline.nodes.map((node) => [node.definitionId, node.config]))
      downloadFile(
        filename,
        ['# Mock export from RAG Studio.', '# Avvia il backend e usa VITE_USE_MOCKS=false per lo script eseguibile.', `PIPELINE_CONFIG = ${JSON.stringify(config, null, 2)}`, '', 'print("Set VITE_USE_MOCKS=false and export again to get runnable code.")'].join('\n'),
        'text/x-python',
      )
      return
    }
    const suffix = query ? `&query=${encodeURIComponent(query)}` : ''
    const response = await fetch(`${apiBaseUrl}/pipelines/${id}/export?format=python${suffix}`)
    if (!response.ok) throw new Error(`Export failed with status ${response.status}`)
    downloadFile(filename, await response.text(), 'text/x-python')
  },
}
