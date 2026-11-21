import { http } from './client'

export interface ComparisonVariantInput {
  id: string
  label: string
  pipelineId?: string
  config?: Record<string, string | number | boolean>
}

export interface ComparisonDocument {
  rank: number
  title: string | null
  source: string | null
  chunkId: string | null
  score: number
  excerpt: string
}

export interface ComparisonVariantResult {
  id: string
  label: string
  config: Record<string, string | number | boolean>
  answer: string
  citations: Array<Record<string, unknown>>
  documents: ComparisonDocument[]
  metrics: Record<string, number>
  durationMs: number
}

export interface ComparisonResponse {
  query: string
  variants: ComparisonVariantResult[]
}

export const comparisonApi = {
  run: (query: string, variants: ComparisonVariantInput[], datasetId?: string): Promise<ComparisonResponse> =>
    http.post('/comparison/run', { query, variants, datasetId }),
}
