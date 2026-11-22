import { beforeEach, describe, expect, it, vi } from 'vitest'

const { get, patch } = vi.hoisted(() => ({ get: vi.fn(), patch: vi.fn() }))
vi.mock('./client', () => ({ http: { get, patch } }))

import { settingsApi, type WorkspaceSettings, type WorkspaceSettingsUpdate } from './settings.api'

const settings: WorkspaceSettings = {
  workspaceName: 'Research lab',
  workspaceDescription: 'Retrieval research, evaluation and deployment workspace.',
  region: 'local',
  timezone: 'Europe/Rome',
  accent: '#5B7CFA',
  autoSave: true,
  compactMode: true,
  autoRunEval: true,
  concurrency: 4,
  timeout: 120,
  environment: 'Development',
  gpuEnabled: true,
  cacheStages: true,
  notifyFailures: true,
  notifyDeploys: true,
  notifyDigest: false,
  notifyIngestion: true,
  telemetry: false,
  betaFeatures: true,
}

beforeEach(() => {
  get.mockReset()
  patch.mockReset()
})

describe('settingsApi', () => {
  it('reads workspace settings from the backend contract path', async () => {
    get.mockResolvedValue(settings)

    await expect(settingsApi.get()).resolves.toEqual(settings)
    expect(get).toHaveBeenCalledTimes(1)
    expect(get).toHaveBeenCalledWith('/settings/workspace')
  })

  it('sends only the supplied patch to PATCH /settings/workspace', async () => {
    const update: WorkspaceSettingsUpdate = { workspaceName: 'New name', concurrency: 8 }
    patch.mockResolvedValue({ ...settings, ...update })

    await expect(settingsApi.update(update)).resolves.toMatchObject(update)
    expect(patch).toHaveBeenCalledTimes(1)
    expect(patch).toHaveBeenCalledWith('/settings/workspace', update)
  })
})
