import { describe, expect, it } from 'vitest'
import { isNodeTestable } from './nodeTest'

describe('isNodeTestable', () => {
  it('include i database e i componenti remoti o non interni', () => {
    for (const id of [
      'db-qdrant',
      'db-neo4j',
      'kg-writer',
      'kg-extractor',
      'provider-embeddings',
      'provider-reranker',
      'prompt-generation',
      'hybrid-retrieval',
    ]) {
      expect(isNodeTestable(id)).toBe(true)
    }
  })

  it('esclude i nodi interni e gli id mancanti', () => {
    for (const id of ['document-source', 'semantic-chunker', 'query-input', '', undefined, null]) {
      expect(isNodeTestable(id)).toBe(false)
    }
  })
})
