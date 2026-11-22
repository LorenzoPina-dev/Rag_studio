import { http } from './client'
import type { CategorySummary, PhaseSummary, Technique, TechniqueStatus } from '@/types/techniques'

export interface TechniqueFilters {
  phase?: string
  category?: string
  status?: TechniqueStatus | 'all'
  search?: string
}

export interface TechniqueCatalog {
  techniques: Technique[]
  total: number
  summary?: {
    total?: number
    by_status?: Record<string, number>
    by_category?: Record<string, number>
    by_phase?: Record<string, number>
  }
}

type CatalogResponse = {
  techniques?: Technique[]
  total?: number
  summary?: TechniqueCatalog['summary']
}

function buildQuery(filters: TechniqueFilters): string {
  const params = new URLSearchParams()
  const search = filters.search?.trim()
  if (search) params.set('search', search)
  if (filters.phase && filters.phase !== 'all') params.set('phase', filters.phase)
  if (filters.category && filters.category !== 'all') params.set('category', filters.category)
  if (filters.status && filters.status !== 'all') params.set('status', filters.status)
  const query = params.toString()
  return query ? `?${query}` : ''
}

export const techniquesApi = {
  /**
   * Filtering happens on the backend: the catalog has 500+ entries and the
   * router already exposes phase/category/status/search query params.
   * The bare-array shape is kept for older/mock responses.
   */
  list: async (filters: TechniqueFilters = {}): Promise<TechniqueCatalog> => {
    const response = await http.get<Technique[] | CatalogResponse>(`/techniques${buildQuery(filters)}`)
    if (Array.isArray(response)) return { techniques: response, total: response.length }
    return {
      techniques: response?.techniques ?? [],
      total: response?.total ?? response?.techniques?.length ?? 0,
      summary: response?.summary,
    }
  },
  categories: (): Promise<CategorySummary[]> => http.get('/techniques/categories'),
  phases: (): Promise<PhaseSummary[]> => http.get('/techniques/phases'),
  get: (id: string): Promise<Technique> => http.get(`/techniques/${encodeURIComponent(id)}`),
}

export type { CategorySummary, PhaseSummary, Technique }
