import { http } from './client'
import type { CategorySummary, PhaseSummary, Technique } from '@/types/techniques'

export const techniquesApi = {
  list: (): Promise<Technique[]> => http.get('/techniques'),
  categories: (): Promise<CategorySummary[]> => http.get('/techniques/categories'),
  phases: (): Promise<PhaseSummary[]> => http.get('/techniques/phases'),
  get: (id: string): Promise<Technique> => http.get(`/techniques/${encodeURIComponent(id)}`),
}

export type { CategorySummary, PhaseSummary, Technique }
