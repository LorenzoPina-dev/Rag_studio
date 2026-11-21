import { http } from './client'
import type { CategorySummary, PhaseSummary, Technique } from '@/types/techniques'

type CatalogResponse = { techniques?: Technique[] }

export const techniquesApi = {
  // The FastAPI router wraps results in `{ total, summary, techniques }` while
  // the mock adapter returns a bare array; accept both shapes.
  list: async (): Promise<Technique[]> => {
    const response = await http.get<Technique[] | CatalogResponse>('/techniques')
    return Array.isArray(response) ? response : (response?.techniques ?? [])
  },
  categories: (): Promise<CategorySummary[]> => http.get('/techniques/categories'),
  phases: (): Promise<PhaseSummary[]> => http.get('/techniques/phases'),
  get: (id: string): Promise<Technique> => http.get(`/techniques/${encodeURIComponent(id)}`),
}

export type { CategorySummary, PhaseSummary, Technique }
