import { http } from './client'
import type { DatabaseCatalogResponse, DatabaseConnectionRequest, DatabaseDeriveResponse, DatabaseTestResponse } from '@/types'

export const databasesApi = {
  catalog: (): Promise<DatabaseCatalogResponse> => http.get('/databases/catalog'),
  derive: (request: DatabaseConnectionRequest): Promise<DatabaseDeriveResponse> => http.post('/databases/derive', request),
  test: (request: DatabaseConnectionRequest): Promise<DatabaseTestResponse> => http.post('/databases/test', request),
}
