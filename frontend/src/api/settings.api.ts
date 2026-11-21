import { http } from './client'

/** Contract of GET/PATCH /settings/workspace (backend WorkspaceSettings). */
export interface WorkspaceSettings {
  workspaceName: string
  workspaceDescription: string
  region: string
  timezone: string
  accent: string
  autoSave: boolean
  compactMode: boolean
  autoRunEval: boolean
  concurrency: number
  timeout: number
  environment: string
  gpuEnabled: boolean
  cacheStages: boolean
  notifyFailures: boolean
  notifyDeploys: boolean
  notifyDigest: boolean
  notifyIngestion: boolean
  telemetry: boolean
  betaFeatures: boolean
}

export type WorkspaceSettingsUpdate = Partial<WorkspaceSettings>

export const settingsApi = {
  get: (): Promise<WorkspaceSettings> => http.get<WorkspaceSettings>('/settings/workspace'),

  /** Only known fields are sent: the backend rejects unknown keys (extra="forbid"). */
  update: (patch: WorkspaceSettingsUpdate): Promise<WorkspaceSettings> =>
    http.patch<WorkspaceSettings>('/settings/workspace', patch),
}
