/** Componenti con una verifica preventiva lato backend. */

export const TESTABLE_NODE_IDS = new Set([
  'kg-writer',
  'kg-extractor',
  'provider-embeddings',
  'provider-reranker',
  'prompt-generation',
  'hybrid-retrieval',
])

export function isNodeTestable(definitionId?: string | null): boolean {
  if (!definitionId) return false
  return definitionId.startsWith('db-') || TESTABLE_NODE_IDS.has(definitionId)
}
