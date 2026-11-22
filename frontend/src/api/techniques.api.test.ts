import { beforeEach, describe, expect, it, vi } from 'vitest'

const { get } = vi.hoisted(() => ({ get: vi.fn() }))
vi.mock('./client', () => ({ http: { get } }))

import { techniquesApi } from './techniques.api'

beforeEach(() => {
  get.mockReset()
})

describe('techniquesApi.list', () => {
  it('sends active filters as backend query params', async () => {
    get.mockResolvedValue({ total: 1, summary: { total: 552 }, techniques: [{ id: 'rrf' }] })

    const result = await techniquesApi.list({ search: 'hybrid fusion', phase: 'Retrieval', category: 'Fusion', status: 'reference' })

    expect(get).toHaveBeenCalledTimes(1)
    const path = String(get.mock.calls[0][0])
    expect(path).toMatch(/^\/techniques\?/)
    const query = new URLSearchParams(path.split('?')[1])
    expect(Object.fromEntries(query)).toEqual({
      search: 'hybrid fusion',
      phase: 'Retrieval',
      category: 'Fusion',
      status: 'reference',
    })
    expect(result).toMatchObject({ total: 1, summary: { total: 552 } })
  })

  it('omits sentinel "all" values and accepts the bare-array legacy shape', async () => {
    get.mockResolvedValue([{ id: 'top-k' }])

    const result = await techniquesApi.list({ phase: 'all', category: 'all', status: 'all', search: '  ' })

    expect(get).toHaveBeenCalledWith('/techniques')
    expect(result).toEqual({ techniques: [{ id: 'top-k' }], total: 1 })
  })
})
