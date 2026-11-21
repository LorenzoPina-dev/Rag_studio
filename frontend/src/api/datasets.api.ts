import { http } from './client'
import type {
  Dataset,
  DatasetCreateInput,
  DatasetMetrics,
  DatasetOption,
  DatasetsData,
  IngestionJob,
} from '@/types'

export const datasetsApi = {
  list: (): Promise<DatasetsData> => http.get('/datasets'),
  metrics: (): Promise<DatasetMetrics> => http.get('/datasets/metrics'),
  get: (id: string): Promise<Dataset> => http.get(`/datasets/${id}`),
  options: (): Promise<DatasetOption[]> => http.get('/datasets/options'),
  create: (input: DatasetCreateInput): Promise<Dataset> => http.post('/datasets', input),
  update: (id: string, input: Partial<Dataset>): Promise<Dataset> => http.patch(`/datasets/${id}`, input),
  remove: (id: string): Promise<void> => http.delete(`/datasets/${id}`),
  sync: (id: string): Promise<Dataset> => http.post(`/datasets/${id}/sync`),
  syncAll: (): Promise<{ ok: boolean; syncedAt: string }> => http.post('/datasets/sync'),
  reindex: (id: string): Promise<{ ok: boolean; datasetId: string; jobId: string }> => http.post(`/datasets/${id}/reindex`),
  jobs: (): Promise<IngestionJob[]> => http.get('/ingestion-jobs'),
}
