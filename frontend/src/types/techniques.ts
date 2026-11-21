/**
 * Types for the RAG techniques catalog exposed by `/api/v1/techniques`.
 * Kept separate from the global index because the backend Pydantic models are
 * still evolving; the shapes below are intentionally tolerant.
 */

export type TechniqueStatus = 'reference' | 'provider' | 'integration' | 'design'

/** Parameters may be returned as a list of descriptors or as a plain map. */
export interface TechniqueParameter {
  name?: string
  key?: string
  label?: string
  type?: string
  default?: unknown
  defaultValue?: unknown
  description?: string
  help?: string
  required?: boolean
  options?: unknown[]
}

export type TechniqueParameters = TechniqueParameter[] | Record<string, unknown> | null | undefined

export interface Technique {
  id: string
  name: string
  category: string
  phase: string
  description: string
  status: TechniqueStatus
  implementation: string
  tags: string[]
  parameters: TechniqueParameters
}

export interface CategorySummary {
  category: string
  count: number
  byStatus: Partial<Record<TechniqueStatus, number>> | Record<string, number>
}

export interface PhaseSummary {
  phase: string
  count: number
}

export interface TechniqueFilters {
  search: string
  phase: string
  category: string
  status: TechniqueStatus | 'all'
}

export const TECHNIQUE_STATUSES: TechniqueStatus[] = ['reference', 'provider', 'integration', 'design']
