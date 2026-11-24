import { http } from './client'
import type { NodeCatalogCategory, NodeDefinition, NodeImplementation, NodeTestRequest, NodeTestResponse } from '@/types'

export const nodesApi = {
  list: (): Promise<NodeDefinition[]> => http.get('/nodes'),
  catalog: (): Promise<NodeCatalogCategory[]> => http.get('/nodes/catalog'),
  implementation: (id: string): Promise<NodeImplementation> => http.get(`/nodes/${encodeURIComponent(id)}/implementation`),
  test: (request: NodeTestRequest): Promise<NodeTestResponse> => http.post('/nodes/test', request),
  testCustom: (id: string): Promise<unknown> => http.post(`/custom-nodes/${id}/test`),
}
