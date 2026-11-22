import { describe, expect, it } from 'vitest'
import { ApiError } from '../client'
import { mockRequest } from './adapter'

describe('mock adapter contract parity', () => {
  it('serves the health endpoint used by checkApiHealth', async () => {
    await expect(mockRequest('GET', '/health')).resolves.toEqual({ status: 'ok' })
  })

  it('round-trips workspace settings without accepting unknown keys', async () => {
    const before = await mockRequest<Record<string, unknown>>('GET', '/settings/workspace')
    expect(before).toMatchObject({ workspaceName: 'Research lab', concurrency: 4 })

    const updated = await mockRequest<Record<string, unknown>>('PATCH', '/settings/workspace', {
      workspaceName: 'Mock lab',
      unknownKey: 'must not leak',
    })
    expect(updated.workspaceName).toBe('Mock lab')
    expect(updated).not.toHaveProperty('unknownKey')

    await mockRequest('PATCH', '/settings/workspace', { workspaceName: 'Research lab' })
  })

  it('keeps provider secrets unset and never marks a fake successful test', async () => {
    const settings = await mockRequest<Record<string, unknown>>('GET', '/providers/settings')
    expect(settings.openai_api_key).toBeNull()
    expect(settings.openai_api_key_set).toBe(false)

    const status = await mockRequest<Record<string, unknown>>('GET', '/providers/status')
    expect(status).toMatchObject({ huggingface_available: false, ollama_running: false })
    expect(status.capabilities).toBeDefined()

    await expect(mockRequest('POST', '/providers/test/unknown')).rejects.toBeInstanceOf(ApiError)
    await expect(mockRequest<{ ok: boolean; detail: string }>('POST', '/providers/test/ollama')).resolves.toMatchObject({ ok: false })
  })

  it('updates an existing model and 404s for unknown ones', async () => {
    const models = await mockRequest<{ models: Array<{ id: string; name: string }> }>('GET', '/models')
    const id = models.models[0].id

    await expect(mockRequest('PATCH', `/models/${id}`, { name: 'Renamed model' })).resolves.toMatchObject({ id, name: 'Renamed model' })
    await expect(mockRequest('PATCH', '/models/m_missing', { name: 'Nope' })).rejects.toMatchObject({ status: 404 })
  })

  it('validates the requested pipeline graph instead of a fixed seed', async () => {
    await expect(mockRequest('POST', '/pipelines/pl_missing/validate')).rejects.toMatchObject({ status: 404 })
    await expect(mockRequest('POST', '/pipelines/pl_semantic_v2/validate')).resolves.toHaveProperty('checkedAt')
  })

  it('applies techniques query params server-side', async () => {
    const response = await mockRequest<{ total: number; techniques: Array<{ status: string }>; summary: { total: number } }>(
      'GET',
      '/techniques?status=integration',
    )
    expect(response.total).toBe(response.techniques.length)
    expect(response.total).toBeGreaterThan(0)
    expect(response.techniques.every((t) => t.status === 'integration')).toBe(true)
    expect(response.summary.total).toBeGreaterThan(response.total)
  })
})
