import { http } from './client'
import type { DataSource } from '@/types'

export const dataSourcesApi = {
  list: (): Promise<DataSource[]> => http.get('/datasources'),
  create: (input: { name: string; type: string }): Promise<DataSource> => http.post('/datasources', input),
  sync: (id: string): Promise<{ ok: boolean; syncedAt: string }> => http.post(`/datasources/${id}/sync`),
}
