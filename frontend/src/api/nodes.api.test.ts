import { beforeEach, describe, expect, it, vi } from 'vitest'

const { get, post } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))
vi.mock('./client', () => ({ http: { get, post } }))

import { nodesApi } from './nodes.api'

beforeEach(() => {
  get.mockReset()
  post.mockReset()
})

describe('nodesApi', () => {
  it('invia la richiesta di test preventivo a /nodes/test', async () => {
    const response = {
      ok: true,
      detail: 'Embedding OK',
      category: 'model',
      latencyMs: 12,
      supported: true,
      provider: 'huggingface',
      model: 'BAAI/bge-small-en-v1.5',
    }
    post.mockResolvedValue(response)

    const request = { definitionId: 'provider-embeddings', config: { provider: 'huggingface' } }
    await expect(nodesApi.test(request)).resolves.toEqual(response)
    expect(post).toHaveBeenCalledWith('/nodes/test', request)
  })
})
