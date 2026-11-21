import { http } from './client'
import type { NodeCatalogCategory, NodeDefinition } from '@/types'

export const nodesApi = {
  list: (): Promise<NodeDefinition[]> => http.get('/nodes'),
  catalog: (): Promise<NodeCatalogCategory[]> => http.get('/nodes/catalog'),
  testCustom: (id: string): Promise<unknown> => http.post(`/custom-nodes/${id}/test`),
}
