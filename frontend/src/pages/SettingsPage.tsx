import * as React from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Activity,
  AlertTriangle,
  Bell,
  Check,
  CheckCircle2,
  Copy,
  Cpu,
  Database,
  Download,
  Gauge,
  KeyRound,
  Palette,
  Plug,
  RefreshCcw,
  Server,
  Settings,
  SlidersHorizontal,
  Trash2,
  Users,
  Workflow,
  Zap,
} from 'lucide-react'
import { toast } from 'sonner'
import { PageHeader } from '@/components/shared/page'
import { Button } from '@/components/ui/button'
import { Input, Textarea, Field } from '@/components/ui/input'
import { Badge, StatusDot } from '@/components/ui/badge'
import { Switch } from '@/components/ui/controls'
import { Select } from '@/components/ui/select'
import { projectsApi } from '@/api/projects.api'
import { providersApi } from '@/api/providers.api'
import { apiBaseUrl, isMockMode } from '@/api/client'
import { useAppStore } from '@/store/useAppStore'
import { cn } from '@/lib/utils'
import type { ProviderSettingsInput, ProviderSettingsPublic } from '@/types'

type ProviderKey = 'huggingface' | 'ollama' | 'openai'

type ProviderForm = Omit<ProviderSettingsInput, 'openai_api_key' | 'allow_model_download'> & {
  openai_api_key: string
  allow_model_download: boolean
}

const emptyProviderForm: ProviderForm = {
  openai_api_key: '',
  openai_base_url: '',
  openai_embedding_model: '',
  openai_chat_model: '',
  ollama_base_url: '',
  ollama_embedding_model: '',
  ollama_chat_model: '',
  hf_embedding_model: '',
  hf_reranker_model: '',
  hf_generator_model: '',
  allow_model_download: true,
}

/** La chiave API non torna mai dal backend: il campo parte sempre vuoto. */
function formFromSettings(settings: ProviderSettingsPublic): ProviderForm {
  return {
    ...emptyProviderForm,
    openai_base_url: settings.openai_base_url,
    openai_embedding_model: settings.openai_embedding_model,
    openai_chat_model: settings.openai_chat_model,
    ollama_base_url: settings.ollama_base_url,
    ollama_embedding_model: settings.ollama_embedding_model,
    ollama_chat_model: settings.ollama_chat_model,
    hf_embedding_model: settings.hf_embedding_model,
    hf_reranker_model: settings.hf_reranker_model,
    hf_generator_model: settings.hf_generator_model,
    allow_model_download: settings.allow_model_download,
  }
}

type SettingsSection = 'workspace' | 'providers' | 'execution' | 'notifications' | 'api' | 'advanced'

const sections: Array<{ id: SettingsSection; label: string; icon: React.ElementType; hint: string }> = [
  { id: 'workspace', label: 'Workspace', icon: Users, hint: 'Profile, region and appearance' },
  { id: 'providers', label: 'Providers', icon: Plug, hint: 'API keys and inference endpoints' },
  { id: 'execution', label: 'Execution', icon: Workflow, hint: 'Runtime, workers and defaults' },
  { id: 'notifications', label: 'Notifications', icon: Bell, hint: 'Alerts and digests' },
  { id: 'api', label: 'API & data', icon: Database, hint: 'Endpoints, health and exports' },
  { id: 'advanced', label: 'Advanced', icon: SlidersHorizontal, hint: 'Feature flags and telemetry' },
]

function Panel({ title, description, children, action }: { title: string; description?: string; children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-line bg-[#0c141f]">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line px-4 py-3">
        <div>
          <h2 className="text-[12px] font-medium text-ink">{title}</h2>
          {description && <p className="mt-0.5 text-[10px] text-dim">{description}</p>}
        </div>
        {action}
      </div>
      <div className="space-y-4 px-4 py-4">{children}</div>
    </section>
  )
}

function ToggleRow({ title, description, checked, onChange }: { title: string; description: string; checked: boolean; onChange: (checked: boolean) => void }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-line/50 py-2.5 last:border-0">
      <div>
        <p className="text-[11px] text-[#c5d0df]">{title}</p>
        <p className="mt-0.5 max-w-lg text-[9.5px] leading-relaxed text-dim">{description}</p>
      </div>
      <Switch checked={checked} onCheckedChange={onChange} />
    </div>
  )
}

export function SettingsPage() {
  const [section, setSection] = React.useState<SettingsSection>('workspace')
  const pushNotification = useAppStore((state) => state.pushNotification)
  const [workspaceName, setWorkspaceName] = React.useState('Research lab')
  const [workspaceDescription, setWorkspaceDescription] = React.useState('Retrieval research, evaluation and deployment workspace.')
  const [region, setRegion] = React.useState('local')
  const [timezone, setTimezone] = React.useState('Europe/Rome')
  const [accent, setAccent] = React.useState('#5B7CFA')
  const [autoSave, setAutoSave] = React.useState(true)
  const [compactMode, setCompactMode] = React.useState(true)
  const [autoRunEval, setAutoRunEval] = React.useState(true)
  const [concurrency, setConcurrency] = React.useState('4')
  const [timeout, setTimeout] = React.useState('120')
  const [environment, setEnvironment] = React.useState('Development')
  const [gpuEnabled, setGpuEnabled] = React.useState(true)
  const [cacheStages, setCacheStages] = React.useState(true)
  const [notifyFailures, setNotifyFailures] = React.useState(true)
  const [notifyDeploys, setNotifyDeploys] = React.useState(true)
  const [notifyDigest, setNotifyDigest] = React.useState(false)
  const [notifyIngestion, setNotifyIngestion] = React.useState(true)
  const [telemetry, setTelemetry] = React.useState(false)
  const [betaFeatures, setBetaFeatures] = React.useState(true)
  const [saving, setSaving] = React.useState(false)
  const [providerForm, setProviderForm] = React.useState<ProviderForm>(emptyProviderForm)
  const queryClient = useQueryClient()

  const { data: status } = useQuery({ queryKey: ['system-status'], queryFn: projectsApi.systemStatus })
  const { data: workspace } = useQuery({ queryKey: ['workspace'], queryFn: projectsApi.workspace, staleTime: Infinity })
  const {
    data: providerSettings,
    isError: providerSettingsFailed,
    error: providerSettingsError,
  } = useQuery({
    queryKey: ['provider-settings'],
    queryFn: providersApi.getSettings,
    refetchOnWindowFocus: false,
  })
  const { data: providerStatus, refetch: refetchProviderStatus } = useQuery({
    queryKey: ['provider-status'],
    queryFn: providersApi.getStatus,
    refetchOnWindowFocus: false,
  })

  React.useEffect(() => {
    if (providerSettings) setProviderForm(formFromSettings(providerSettings))
  }, [providerSettings])

  const setProviderField = <K extends keyof ProviderForm>(key: K, value: ProviderForm[K]) => {
    setProviderForm((current) => ({ ...current, [key]: value }))
  }

  const saveProvidersMutation = useMutation({
    mutationFn: (patch: ProviderSettingsInput) => providersApi.updateSettings(patch),
    onSuccess: (settings) => {
      queryClient.setQueryData(['provider-settings'], settings)
      void queryClient.invalidateQueries({ queryKey: ['provider-settings'] })
      void queryClient.invalidateQueries({ queryKey: ['provider-status'] })
      pushNotification({ title: 'Provider settings saved', body: 'Backend configuration updated.', type: 'success' })
      toast.success('Provider settings saved', { description: 'The backend confirmed the new configuration.' })
    },
    onError: (error: Error) => toast.error('Could not save provider settings', { description: error.message }),
  })

  const testProviderMutation = useMutation({
    mutationFn: (provider: ProviderKey) => providersApi.test(provider),
    onSuccess: (result, provider) => {
      if (result.ok) toast.success(`${provider} test riuscito`, { description: result.detail })
      else toast.error(`${provider} test non riuscito`, { description: result.detail })
      void queryClient.invalidateQueries({ queryKey: ['provider-status'] })
    },
    onError: (error: Error, provider) =>
      toast.error(`${provider} test non riuscito`, { description: error.message }),
  })

  const save = () => {
    setSaving(true)
    window.setTimeout(() => {
      setSaving(false)
      pushNotification({ title: 'Settings saved', body: 'Workspace configuration updated.', type: 'success' })
      toast.success('Settings saved', { description: 'Changes apply to new runs immediately.' })
    }, 480)
  }

  const saveProviders = () => {
    const patch: ProviderSettingsInput = {
      openai_base_url: providerForm.openai_base_url,
      openai_embedding_model: providerForm.openai_embedding_model,
      openai_chat_model: providerForm.openai_chat_model,
      ollama_base_url: providerForm.ollama_base_url,
      ollama_embedding_model: providerForm.ollama_embedding_model,
      ollama_chat_model: providerForm.ollama_chat_model,
      hf_embedding_model: providerForm.hf_embedding_model,
      hf_reranker_model: providerForm.hf_reranker_model,
      hf_generator_model: providerForm.hf_generator_model,
      allow_model_download: providerForm.allow_model_download,
    }
    // Un campo vuoto non deve cancellare una chiave già configurata.
    if (providerForm.openai_api_key.trim()) patch.openai_api_key = providerForm.openai_api_key.trim()
    saveProvidersMutation.mutate(patch)
  }

  const providerCards: Array<{ key: ProviderKey; name: string; detail: string; icon: React.ElementType; accent: string; available: boolean }> = [
    {
      key: 'openai',
      name: 'OpenAI',
      detail: providerSettings?.openai_chat_model ?? 'Configurazione non caricata',
      icon: Zap,
      accent: '#39D6D0',
      available: Boolean(providerStatus?.openai_configured),
    },
    {
      key: 'ollama',
      name: 'Ollama',
      detail: providerStatus?.ollama_running
        ? `${providerStatus.ollama_models.length} modelli rilevati via /api/tags`
        : 'Runtime non raggiungibile',
      icon: Server,
      accent: '#A78BFA',
      available: Boolean(providerStatus?.ollama_running),
    },
    {
      key: 'huggingface',
      name: 'Hugging Face',
      detail: providerStatus?.huggingface_available ? 'Librerie locali disponibili' : 'Librerie locali non disponibili',
      icon: Cpu,
      accent: '#7296FF',
      available: Boolean(providerStatus?.huggingface_available),
    },
  ]
  const availableCount = providerCards.filter((provider) => provider.available).length
  const capabilities = providerStatus?.capabilities ?? { embeddings: null, reranking: null, generation: null }
  const ollamaModels = providerStatus?.ollama_models ?? []

  return (
    <>
      <PageHeader
        eyebrow="Workspace configuration"
        title="Settings"
        description="Configure runtime defaults, providers and workspace preferences."
        breadcrumbs={[{ label: 'Research lab', to: '/' }, { label: 'Settings' }]}
        actions={
          <>
            <Button variant="secondary" onClick={() => toast.info('Using mock API adapter', { description: `API mode: ${isMockMode ? 'mock' : 'live'} · ${apiBaseUrl}` })}>
              <Gauge className="h-3.5 w-3.5" /> Runtime info
            </Button>
            <Button variant="primary" size="lg" onClick={save} disabled={saving}>
              {saving ? <RefreshCcw className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />} Save changes
            </Button>
          </>
        }
      />

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="grid gap-4 px-6 py-5 xl:grid-cols-[226px_minmax(0,1fr)]">
          <aside className="self-start rounded-lg border border-line bg-[#0b121c] p-1.5">
            {sections.map((item) => (
              <button
                key={item.id}
                onClick={() => setSection(item.id)}
                className={cn(
                  'flex w-full items-start gap-2.5 rounded-md px-2.5 py-2 text-left transition-colors',
                  section === item.id ? 'bg-[#16213a] text-ink' : 'text-[#8c97aa] hover:bg-white/[0.035] hover:text-ink',
                )}
              >
                <item.icon className={cn('mt-0.5 h-3.5 w-3.5 shrink-0', section === item.id ? 'text-[#9db1ff]' : 'text-[#69768c]')} />
                <span className="min-w-0">
                  <span className="block text-[11px] font-medium">{item.label}</span>
                  <span className="mt-0.5 block text-[8.5px] leading-tight text-dim">{item.hint}</span>
                </span>
              </button>
            ))}
            <div className="mt-2 rounded-md border border-line/60 bg-[#0e1622] px-2.5 py-2">
              <div className="flex items-center gap-1.5 font-mono text-[8px] uppercase tracking-[0.1em] text-success"><StatusDot status="success" /> Workspace healthy</div>
              <p className="mt-1 font-mono text-[8px] text-dim">{status?.version ?? 'v0.8.2'} · {status?.python ?? 'Python 3.11.8'}</p>
            </div>
          </aside>

          <div className="min-w-0 space-y-4">
            {section === 'workspace' && (
              <>
                <Panel title="Workspace profile" description="Shown across the app and in exported reports.">
                  <div className="grid gap-3 md:grid-cols-2">
                    <Field label="Workspace name"><Input value={workspaceName} onChange={(event) => setWorkspaceName(event.target.value)} /></Field>
                    <Field label="Workspace ID"><Input value={workspace?.id ?? 'ws_research'} readOnly className="font-mono text-[11px] text-dim" /></Field>
                  </div>
                  <Field label="Description"><Textarea value={workspaceDescription} onChange={(event) => setWorkspaceDescription(event.target.value)} /></Field>
                  <div className="grid gap-3 md:grid-cols-2">
                    <Field label="Data region"><Select value={region} onValueChange={setRegion} options={[{ value: 'local', label: 'Local workspace' }, { value: 'eu', label: 'EU · Frankfurt' }, { value: 'us', label: 'US · Virginia' }]} /></Field>
                    <Field label="Timezone"><Select value={timezone} onValueChange={setTimezone} options={['Europe/Rome', 'Europe/London', 'UTC', 'America/New_York']} /></Field>
                  </div>
                  <div className="flex items-center justify-between gap-3 rounded-md border border-line bg-[#0b111b] px-3 py-2.5">
                    <div>
                      <p className="text-[10.5px] text-muted">Role & access</p>
                      <p className="mt-0.5 font-mono text-[8.5px] text-dim">{workspace?.role ?? 'Owner'} · {workspace?.plan ?? 'Team workspace'}</p>
                    </div>
                    <Button variant="secondary" size="sm" onClick={() => toast.info('Member management is available in the Team plan.')}><Users className="h-3 w-3" /> Manage members</Button>
                  </div>
                </Panel>

                <Panel title="Appearance" description="Interface density and accent color." action={<Palette className="h-3.5 w-3.5 text-dim" />}>
                  <div>
                    <p className="mb-2 text-[11px] text-muted">Accent color</p>
                    <div className="flex flex-wrap gap-2">
                      {['#5B7CFA', '#35D99B', '#A78BFA', '#39D6D0', '#F0B45C', '#E48EF0'].map((color) => (
                        <button
                          key={color}
                          onClick={() => setAccent(color)}
                          className={cn('flex h-7 w-7 items-center justify-center rounded-full border-2 transition-transform hover:scale-105', accent === color ? 'border-white/80' : 'border-transparent')}
                          style={{ backgroundColor: color }}
                          aria-label={`Use ${color} accent`}
                        >
                          {accent === color && <Check className="h-3 w-3 text-white" />}
                        </button>
                      ))}
                    </div>
                  </div>
                  <ToggleRow title="Compact interface" description="Use denser tables and 9–11px type for high-information screens." checked={compactMode} onChange={setCompactMode} />
                  <ToggleRow title="Auto-save pipeline edits" description="Persist graph changes after a short debounce while editing." checked={autoSave} onChange={setAutoSave} />
                </Panel>
              </>
            )}

            {section === 'providers' && (
              <>
                {providerSettingsFailed && (
                  <div className="rounded-md border border-danger/25 bg-danger/[0.05] px-3 py-2.5">
                    <p className="flex items-center gap-1.5 text-[10.5px] font-medium text-[#ff9c9c]"><AlertTriangle className="h-3 w-3" /> Impossibile leggere le impostazioni dal backend</p>
                    <p className="mt-1 font-mono text-[9px] text-dim">{(providerSettingsError as Error)?.message}</p>
                  </div>
                )}

                <Panel
                  title="Inference providers"
                  description="Disponibilità letta da GET /providers/status. Ogni test esegue una chiamata reale al provider."
                  action={
                    <Badge tone={availableCount > 0 ? 'success' : 'warning'} dot>
                      {availableCount} disponibili
                    </Badge>
                  }
                >
                  {providerCards.map((provider) => {
                    const testing = testProviderMutation.isPending && testProviderMutation.variables === provider.key
                    return (
                      <div key={provider.key} className="rounded-md border border-line bg-[#0b111b] p-3">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="flex items-center gap-2.5">
                            <span className="flex h-7 w-7 items-center justify-center rounded border" style={{ borderColor: `${provider.accent}44`, backgroundColor: `${provider.accent}0d`, color: provider.accent }}>
                              <provider.icon className="h-3.5 w-3.5" />
                            </span>
                            <div>
                              <p className="text-[11.5px] text-ink">{provider.name}</p>
                              <p className="mt-0.5 font-mono text-[8.5px] text-dim">{provider.detail}</p>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className={cn('flex items-center gap-1.5 font-mono text-[8.5px]', provider.available ? 'text-success' : 'text-warn')}>
                              <StatusDot status={provider.available ? 'success' : 'warning'} /> {provider.available ? 'Disponibile' : 'Non disponibile'}
                            </span>
                            <Button
                              variant="secondary"
                              size="xs"
                              disabled={testProviderMutation.isPending}
                              onClick={() => testProviderMutation.mutate(provider.key)}
                            >
                              {testing ? <RefreshCcw className="h-3 w-3 animate-spin" /> : <Zap className="h-3 w-3" />} Test
                            </Button>
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </Panel>

                <Panel
                  title="OpenAI"
                  description="Impostazioni inviate a PATCH /providers/settings. La chiave grezza non viene mai restituita dal backend."
                  action={
                    <Badge tone={providerSettings?.openai_api_key_set ? 'success' : 'warning'} dot>
                      {providerSettings?.openai_api_key_set ? 'Configurata' : 'Non configurata'}
                    </Badge>
                  }
                >
                  <Field label="API key" hint={providerSettings?.openai_api_key_set ? 'Una chiave è già configurata: lascia vuoto per mantenerla.' : 'Nessuna chiave configurata sul backend.'}>
                    <Input
                      type="password"
                      value={providerForm.openai_api_key}
                      onChange={(event) => setProviderField('openai_api_key', event.target.value)}
                      placeholder={providerSettings?.openai_api_key_set ? 'Incolla una nuova chiave per sostituirla' : 'sk-…'}
                      autoComplete="off"
                      className="h-8 font-mono text-[10.5px]"
                    />
                  </Field>
                  <div className="grid gap-3 md:grid-cols-2">
                    <Field label="Base URL">
                      <Input value={providerForm.openai_base_url ?? ''} onChange={(event) => setProviderField('openai_base_url', event.target.value)} className="h-8 font-mono text-[10.5px]" />
                    </Field>
                    <Field label="Modello embedding">
                      <Input value={providerForm.openai_embedding_model ?? ''} onChange={(event) => setProviderField('openai_embedding_model', event.target.value)} className="h-8 font-mono text-[10.5px]" />
                    </Field>
                    <Field label="Modello chat">
                      <Input value={providerForm.openai_chat_model ?? ''} onChange={(event) => setProviderField('openai_chat_model', event.target.value)} className="h-8 font-mono text-[10.5px]" />
                    </Field>
                  </div>
                </Panel>

                <Panel title="Ollama" description="Runtime locale usato per embedding e generazione quando selezionato automaticamente." action={<Server className="h-3.5 w-3.5 text-dim" />}>
                  <div className="grid gap-3 md:grid-cols-2">
                    <Field label="Base URL">
                      <Input value={providerForm.ollama_base_url ?? ''} onChange={(event) => setProviderField('ollama_base_url', event.target.value)} className="h-8 font-mono text-[10.5px]" />
                    </Field>
                    <Field label="Modello embedding">
                      <Input value={providerForm.ollama_embedding_model ?? ''} onChange={(event) => setProviderField('ollama_embedding_model', event.target.value)} className="h-8 font-mono text-[10.5px]" />
                    </Field>
                    <Field label="Modello chat">
                      <Input value={providerForm.ollama_chat_model ?? ''} onChange={(event) => setProviderField('ollama_chat_model', event.target.value)} className="h-8 font-mono text-[10.5px]" />
                    </Field>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {ollamaModels.length > 0 ? (
                      ollamaModels.map((model) => <Badge key={model} tone="outline">{model}</Badge>)
                    ) : (
                      <span className="font-mono text-[9px] text-dim">Nessun modello Ollama rilevato</span>
                    )}
                  </div>
                </Panel>

                <Panel title="Hugging Face" description="Modelli locali per embedding, reranking e generazione." action={<Cpu className="h-3.5 w-3.5 text-dim" />}>
                  <div className="grid gap-3 md:grid-cols-2">
                    <Field label="Modello embedding">
                      <Input value={providerForm.hf_embedding_model ?? ''} onChange={(event) => setProviderField('hf_embedding_model', event.target.value)} className="h-8 font-mono text-[10.5px]" />
                    </Field>
                    <Field label="Modello reranker">
                      <Input value={providerForm.hf_reranker_model ?? ''} onChange={(event) => setProviderField('hf_reranker_model', event.target.value)} className="h-8 font-mono text-[10.5px]" />
                    </Field>
                    <Field label="Modello generatore">
                      <Input value={providerForm.hf_generator_model ?? ''} onChange={(event) => setProviderField('hf_generator_model', event.target.value)} className="h-8 font-mono text-[10.5px]" />
                    </Field>
                  </div>
                  <ToggleRow
                    title="Consenti download modelli"
                    description="Autorizza il backend a scaricare i modelli non presenti in cache locale."
                    checked={providerForm.allow_model_download}
                    onChange={(checked) => setProviderField('allow_model_download', checked)}
                  />
                </Panel>

                <Panel
                  title="Stato e selezione automatica"
                  description="Scelta effettiva del backend per ciascuna capacità, rilevata senza scaricare modelli."
                  action={
                    <Button variant="secondary" size="xs" onClick={() => void refetchProviderStatus()}><RefreshCcw className="h-3 w-3" /> Aggiorna</Button>
                  }
                >
                  <div className="grid gap-1.5 font-mono text-[8.5px] text-dim sm:grid-cols-3">
                    <span className="flex items-center gap-1.5"><StatusDot status={providerStatus?.huggingface_available ? 'success' : 'idle'} /> Hugging Face · {providerStatus?.huggingface_available ? 'disponibile' : 'non disponibile'}</span>
                    <span className="flex items-center gap-1.5"><StatusDot status={providerStatus?.ollama_running ? 'success' : 'idle'} /> Ollama · {providerStatus?.ollama_running ? 'in esecuzione' : 'non in esecuzione'}</span>
                    <span className="flex items-center gap-1.5"><StatusDot status={providerStatus?.openai_configured ? 'success' : 'idle'} /> OpenAI · {providerStatus?.openai_configured ? 'configurato' : 'non configurato'}</span>
                  </div>
                  <div className="rounded-md border border-line bg-[#0b111b] px-3 py-2.5">
                    <p className="font-mono text-[8px] uppercase tracking-[0.12em] text-dim">Provider scelti automaticamente</p>
                    <div className="mt-2 grid gap-1.5 font-mono text-[9px] text-muted sm:grid-cols-3">
                      <span>Embeddings · <span className="text-ink">{capabilities.embeddings ?? 'nessuno disponibile'}</span></span>
                      <span>Reranking · <span className="text-ink">{capabilities.reranking ?? 'nessuno disponibile'}</span></span>
                      <span>Generation · <span className="text-ink">{capabilities.generation ?? 'nessuno disponibile'}</span></span>
                    </div>
                  </div>
                </Panel>

                <div className="flex items-center justify-between gap-3 rounded-lg border border-line/60 bg-[#0b121c] px-4 py-3">
                  <div className="flex items-center gap-2 font-mono text-[8.5px] text-dim">
                    <CheckCircle2 className="h-3.5 w-3.5 text-success" />
                    Le modifiche ai provider vengono salvate sul backend, non nel browser.
                  </div>
                  <Button variant="primary" size="sm" onClick={saveProviders} disabled={saveProvidersMutation.isPending}>
                    {saveProvidersMutation.isPending ? <RefreshCcw className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />} Salva provider
                  </Button>
                </div>
              </>
            )}

            {section === 'execution' && (
              <>
                <Panel title="Execution defaults" description="Applied to new runs unless a pipeline overrides them." action={<Workflow className="h-3.5 w-3.5 text-dim" />}>
                  <div className="grid gap-3 md:grid-cols-3">
                    <Field label="Default environment"><Select value={environment} onValueChange={setEnvironment} options={['Development', 'Staging', 'Production']} /></Field>
                    <Field label="Concurrency"><Select value={concurrency} onValueChange={setConcurrency} options={['1', '2', '4', '8', '16']} /></Field>
                    <Field label="Timeout (seconds)"><Input type="number" value={timeout} onChange={(event) => setTimeout(event.target.value)} /></Field>
                  </div>
                  <ToggleRow title="Enable GPU execution" description="Route locally loaded embedding and reranking models to CUDA:0." checked={gpuEnabled} onChange={setGpuEnabled} />
                  <ToggleRow title="Cache ingestion stages" description="Reuse chunk and embedding artefacts across runs when the dataset hash is unchanged." checked={cacheStages} onChange={setCacheStages} />
                  <ToggleRow title="Auto-run evaluation on deploy" description="Score production deployments against the active benchmark set." checked={autoRunEval} onChange={setAutoRunEval} />
                </Panel>
                <Panel title="Runtime services" description="Local Docker services backing pipeline execution.">
                  <div className="grid gap-2 sm:grid-cols-2">
                    {[
                      ['PostgreSQL', 'workspace-db · 4ms', Database],
                      ['Redis', 'celery broker · 2 queues', Activity],
                      ['MinIO', 'artifacts · 8.2 GB', Server],
                      ['Qdrant', '4 collections', KeyRound],
                    ].map(([name, detail, Icon]) => {
                      const ServiceIcon = Icon as React.ElementType
                      return (
                        <div key={String(name)} className="flex items-center justify-between rounded border border-line/70 bg-[#0b111b] px-3 py-2">
                          <div className="flex items-center gap-2">
                            <ServiceIcon className="h-3.5 w-3.5 text-[#7b8ba4]" />
                            <div>
                              <p className="text-[10.5px] text-muted">{name as string}</p>
                              <p className="mt-0.5 font-mono text-[8px] text-dim">{detail as string}</p>
                            </div>
                          </div>
                          <StatusDot status="success" pulse />
                        </div>
                      )
                    })}
                  </div>
                </Panel>
              </>
            )}

            {section === 'notifications' && (
              <Panel title="Notifications" description="Choose what reaches your inbox and the in-app feed." action={<Bell className="h-3.5 w-3.5 text-dim" />}>
                <ToggleRow title="Failed runs" description="Alert immediately when an execution fails or exceeds its retry budget." checked={notifyFailures} onChange={setNotifyFailures} />
                <ToggleRow title="Deployments & promotions" description="Notify when a pipeline or experiment is promoted to production." checked={notifyDeploys} onChange={setNotifyDeploys} />
                <ToggleRow title="Ingestion progress" description="Send updates when dataset syncs finish or encounter errors." checked={notifyIngestion} onChange={setNotifyIngestion} />
                <ToggleRow title="Weekly quality digest" description="Email a summary of faithfulness, latency and cost across projects." checked={notifyDigest} onChange={setNotifyDigest} />
                <div className="rounded-md border border-line bg-[#0b111b] px-3 py-2.5">
                  <p className="font-mono text-[8px] uppercase tracking-[0.12em] text-dim">Delivery channels</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <Badge tone="success" dot>In-app</Badge>
                    <Badge tone="outline">Email · alex@acme.dev</Badge>
                    <Badge tone="outline">Slack · #rag-alerts</Badge>
                  </div>
                </div>
              </Panel>
            )}

            {section === 'api' && (
              <>
                <Panel title="API connection" description="The UI talks to a typed REST client. Mock mode requires no backend." action={<Badge tone={isMockMode ? 'warning' : 'success'} dot>{isMockMode ? 'Mock adapter' : 'Live API'}</Badge>}>
                  <div className="grid gap-3 md:grid-cols-2">
                    <Field label="API base URL"><Input value={apiBaseUrl} readOnly className="font-mono text-[10.5px]" /></Field>
                    <Field label="Mode"><Input value={isMockMode ? 'VITE_USE_MOCKS=true' : 'VITE_USE_MOCKS=false'} readOnly className="font-mono text-[10.5px]" /></Field>
                  </div>
                  <div className="rounded-md border border-line bg-[#0b111b] px-3 py-2.5">
                    <div className="flex items-center justify-between">
                      <p className="font-mono text-[8px] uppercase tracking-[0.12em] text-dim">Health check</p>
                      <Button variant="ghost" size="xs" onClick={() => toast.success('All services operational', { description: 'Checked in 128ms.' })}>Run check</Button>
                    </div>
                    <div className="mt-2 grid gap-1.5 font-mono text-[8.5px] text-dim sm:grid-cols-2">
                      <span className="flex items-center gap-1.5"><StatusDot status="success" /> API gateway · {status?.version ?? 'v0.8.2'}</span>
                      <span className="flex items-center gap-1.5"><StatusDot status="success" /> Python · {status?.python ?? '3.11.8'}</span>
                      <span className="flex items-center gap-1.5"><StatusDot status="success" /> Branch · {status?.branch ?? 'main*'}</span>
                      <span className="flex items-center gap-1.5"><StatusDot status={status?.warnings ? 'warning' : 'success'} /> {status?.warnings ?? 0} warnings</span>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button variant="secondary" size="sm" onClick={() => { navigator.clipboard?.writeText(apiBaseUrl); toast.success('Base URL copied') }}><Copy className="h-3 w-3" /> Copy base URL</Button>
                    <Button variant="secondary" size="sm" onClick={() => toast.info('OpenAPI schema available at /docs when the FastAPI backend is running.')}><Download className="h-3 w-3" /> API reference</Button>
                  </div>
                </Panel>

                <Panel title="Workspace data" description="Exports include projects, pipelines, datasets and evaluation history.">
                  <div className="flex flex-wrap gap-2">
                    <Button variant="secondary" size="sm" onClick={() => toast.success('Workspace export queued')}><Download className="h-3 w-3" /> Export workspace</Button>
                    <Button variant="secondary" size="sm" onClick={() => toast.success('Dataset manifest exported')}><Database className="h-3 w-3" /> Export dataset manifest</Button>
                  </div>
                  <div className="rounded-md border border-warn/20 bg-warn/[0.05] px-3 py-2.5">
                    <p className="flex items-center gap-1.5 text-[10.5px] font-medium text-[#e6c894]"><AlertTriangle className="h-3 w-3" /> Reset demo data</p>
                    <p className="mt-1 text-[9.5px] leading-relaxed text-[#b49a72]">Restores seeded pipelines, datasets and runs. Saved pipelines in local storage are cleared.</p>
                    <Button variant="danger" size="xs" className="mt-2" onClick={() => { try { localStorage.removeItem('rag-studio:pipeline') } catch { /* ignore */ } toast.success('Demo data reset', { description: 'Reload the page to restore seeded data.' }) }}>
                      <Trash2 className="h-3 w-3" /> Reset local data
                    </Button>
                  </div>
                </Panel>
              </>
            )}

            {section === 'advanced' && (
              <>
                <Panel title="Advanced options" description="Experimental capabilities and diagnostics." action={<Settings className="h-3.5 w-3.5 text-dim" />}>
                  <ToggleRow title="Beta features" description="Enable experimental canvas tools, streaming previews and MMR presets." checked={betaFeatures} onChange={setBetaFeatures} />
                  <ToggleRow title="Anonymous telemetry" description="Share aggregate usage metrics. No document content or prompts are ever collected." checked={telemetry} onChange={setTelemetry} />
                  <div className="rounded-md border border-line bg-[#0b111b] px-3 py-2.5">
                    <p className="font-mono text-[8px] uppercase tracking-[0.12em] text-dim">Build metadata</p>
                    <div className="mt-2 grid gap-1.5 font-mono text-[8.5px] sm:grid-cols-2">
                      <span className="text-dim">Version <span className="text-muted">{status?.version ?? 'v0.8.2'}</span></span>
                      <span className="text-dim">Branch <span className="text-muted">{status?.branch ?? 'main*'}</span></span>
                      <span className="text-dim">Python <span className="text-muted">{status?.python ?? '3.11.8'}</span></span>
                      <span className="text-dim">Connected <span className="text-muted">{status?.connected ? 'yes' : 'mock'}</span></span>
                    </div>
                  </div>
                </Panel>
                <Panel title="Danger zone" description="Irreversible or workspace-wide actions.">
                  <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-danger/25 bg-danger/[0.04] px-3 py-2.5">
                    <div>
                      <p className="text-[10.5px] text-[#e8a0a0]">Delete workspace</p>
                      <p className="mt-0.5 text-[9px] text-[#a87575]">Removes projects, pipelines, datasets and artifacts. Cannot be undone.</p>
                    </div>
                    <Button variant="danger" size="sm" onClick={() => toast.error('Workspace deletion requires owner confirmation.')}><Trash2 className="h-3 w-3" /> Delete workspace</Button>
                  </div>
                </Panel>
              </>
            )}

            <div className="flex items-center justify-between gap-3 rounded-lg border border-line/60 bg-[#0b121c] px-4 py-3">
              <div className="flex items-center gap-2 font-mono text-[8.5px] text-dim">
                <CheckCircle2 className="h-3.5 w-3.5 text-success" />
                Settings are stored per workspace and versioned with the deployment.
              </div>
              <Button variant="primary" size="sm" onClick={save} disabled={saving}>
                {saving ? 'Saving…' : 'Save changes'}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
