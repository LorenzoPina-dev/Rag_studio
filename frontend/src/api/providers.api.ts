import { http } from './client'
import type { ProviderSettingsInput, ProviderSettingsPublic, ProviderStatus } from '@/types'

/**
 * Il backend espone le capacità auto-rilevate sia dentro `capabilities` sia,
 * per compatibilità con versioni precedenti, direttamente nella risposta.
 * Normalizziamo sempre nel secondo formato prima di passarlo alla UI.
 */
type ProviderStatusResponse = Omit<ProviderStatus, 'capabilities'> & {
  capabilities?: ProviderStatus['capabilities']
  embeddings?: string | null
  reranking?: string | null
  generation?: string | null
}

export const providersApi = {
  getSettings: (): Promise<ProviderSettingsPublic> => http.get('/providers/settings'),

  updateSettings: (patch: ProviderSettingsInput): Promise<ProviderSettingsPublic> =>
    http.patch('/providers/settings', patch),

  getStatus: async (): Promise<ProviderStatus> => {
    const status = await http.get<ProviderStatusResponse>('/providers/status')
    return {
      huggingface_available: status.huggingface_available,
      ollama_running: status.ollama_running,
      ollama_models: status.ollama_models ?? [],
      openai_configured: status.openai_configured,
      capabilities: status.capabilities ?? {
        embeddings: status.embeddings ?? null,
        reranking: status.reranking ?? null,
        generation: status.generation ?? null,
      },
    }
  },

  test: (provider: 'huggingface' | 'ollama' | 'openai'): Promise<{ ok: boolean; detail: string }> =>
    http.post(`/providers/test/${provider}`),
}
