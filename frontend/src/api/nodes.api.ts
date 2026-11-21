import { http } from './client'
import type { NodeCatalogCategory, NodeDefinition, NodeImplementation } from '@/types'

export const nodesApi = {
  list: (): Promise<NodeDefinition[]> => http.get('/nodes'),
  catalog: (): Promise<NodeCatalogCategory[]> => http.get('/nodes/catalog'),
  implementation: (id: string): Promise<NodeImplementation> => http.get(`/nodes/${encodeURIComponent(id)}/implementation`),
  testCustom: (id: string): Promise<unknown> => http.post(`/custom-nodes/${id}/test`),
}
