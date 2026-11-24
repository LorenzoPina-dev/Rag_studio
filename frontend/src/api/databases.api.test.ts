import { beforeEach, describe, expect, it, vi } from 'vitest'

const { get, post } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))
vi.mock('./client', () => ({ http: { get, post } }))

import { databasesApi } from './databases.api'

beforeEach(() => {
  get.mockReset()
  post.mockReset()
})

describe('databasesApi', () => {
  it('loads the catalog and forwards derive/test requests unchanged', async () => {
    const catalog = { databases: [], total: 0 }
    const derived = { database: 'qdrant', url: 'http://qdrant:6333', fields: [] }
    const tested = { ok: false, detail: 'mock', latencyMs: 0, config: derived }
    get.mockResolvedValue(catalog)
    post.mockResolvedValueOnce(derived).mockResolvedValueOnce(tested)

    const request = { database: 'qdrant', mode: 'local' as const, target: 'docker' as const, values: {} }
    await expect(databasesApi.catalog()).resolves.toEqual(catalog)
    await expect(databasesApi.derive(request)).resolves.toEqual(derived)
    await expect(databasesApi.test(request)).resolves.toEqual(tested)

    expect(get).toHaveBeenCalledWith('/databases/catalog')
    expect(post).toHaveBeenNthCalledWith(1, '/databases/derive', request)
    expect(post).toHaveBeenNthCalledWith(2, '/databases/test', request)
  })
})
