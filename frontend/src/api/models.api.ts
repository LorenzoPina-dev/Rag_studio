import { http } from './client'
import type { Model, ModelsData, ModelResources, Provider } from '@/types'

export interface ModelTestResponse {
  modelId: string
  output: string
  latencyMs: number
  tokens: number
  cost: number
}

export const modelsApi = {
  list: (): Promise<ModelsData> => http.get('/models'),
  providers: (): Promise<Provider[]> => http.get('/models/providers'),
  resources: (): Promise<ModelResources> => http.get('/models/resources'),
  register: (input: { name: string; provider: string; type: string }): Promise<Model> => http.post('/models', input),
  update: (id: string, input: Partial<Model>): Promise<Model> => http.patch(`/models/${id}`, input),
  test: (id: string, prompt: string): Promise<ModelTestResponse> => http.post(`/models/${id}/test`, { prompt }),
}
