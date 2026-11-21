import * as React from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  BookOpen,
  Check,
  Cpu,
  Download,
  HardDrive,
  Layers,
  Loader2,
  MemoryStick,
  MoreHorizontal,
  Plus,
  Search,
  Settings2,
  Sparkles,
  Terminal,
  Wand2,
  Zap,
} from 'lucide-react'
import { toast } from 'sonner'
import { PageHeader } from '@/components/shared/page'
import { Button } from '@/components/ui/button'
import { SearchInput, Input, Field } from '@/components/ui/input'
import { EmptyState, ErrorState, LoadingState, ProgressBar, StatusDot } from '@/components/ui/badge'
import { Dialog, DialogBody, DialogContent, DialogFooter, DialogHeader } from '@/components/ui/dialog'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/controls'
import { Select } from '@/components/ui/select'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown'
import { modelsApi } from '@/api/models.api'
import { cn } from '@/lib/utils'
import type { Model, ModelType } from '@/types'

const typeIcon: Record<ModelType, React.ElementType> = {
  Generation: Sparkles,
  Embedding: Layers,
  Reranking: Wand2,
}

const typeAccent: Record<ModelType, string> = {
  Generation: '#7296FF',
  Embedding: '#35D99B',
  Reranking: '#A78BFA',
}

const statusLabel: Record<Model['status'], { label: string; dot: 'success' | 'running' | 'idle' | 'danger'; className: string }> = {
  ready: { label: 'Ready', dot: 'success', className: 'text-success' },
  loaded: { label: 'Loaded', dot: 'success', className: 'text-success' },
  idle: { label: 'Idle', dot: 'idle', className: 'text-dim' },
  error: { label: 'Error', dot: 'danger', className: 'text-danger' },
}

function DetailRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-line/40 py-[7px] last:border-0">
      <span className="font-mono text-[8.5px] uppercase tracking-[0.08em] text-dim">{label}</span>
      <span className="text-right font-mono text-[9.5px] text-[#bcc8d9]">{value}</span>
    </div>
  )
}

export function ModelsPage() {
  const queryClient = useQueryClient()
  const [tab, setTab] = React.useState('all')
  const [search, setSearch] = React.useState('')
  const [provider, setProvider] = React.useState('all')
  const [scope, setScope] = React.useState('all')
  const [selectedId, setSelectedId] = React.useState<string | null>(null)
  const [addOpen, setAddOpen] = React.useState(false)
  const [testOpen, setTestOpen] = React.useState(false)
  const [docsOpen, setDocsOpen] = React.useState(false)
  const [configureProvider, setConfigureProvider] = React.useState<string | null>(null)
  const [newModel, setNewModel] = React.useState({ name: '', provider: 'OpenAI', type: 'Generation' })
  const [prompt, setPrompt] = React.useState('Explain how hybrid retrieval fuses dense and sparse candidates.')

  const { data, isLoading, isError, error, refetch } = useQuery({ queryKey: ['models'], queryFn: modelsApi.list })

  const registerMutation = useMutation({
    mutationFn: () => modelsApi.register(newModel),
    onSuccess: (model) => {
      queryClient.invalidateQueries({ queryKey: ['models'] })
      toast.success('Model registered', { description: `${model.name} is available in the node inspector.` })
      setAddOpen(false)
      setNewModel({ name: '', provider: 'OpenAI', type: 'Generation' })
      setSelectedId(model.id)
    },
    onError: (err: Error) => toast.error('Could not register model', { description: err.message }),
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, input }: { id: string; input: Partial<Model> }) => modelsApi.update(id, input),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['models'] })
      toast.success(variables.input.status === 'loaded' ? 'Model loaded' : 'Model updated')
    },
    onError: (err: Error) => toast.error('Update failed', { description: err.message }),
  })

  const testMutation = useMutation({
    mutationFn: () => modelsApi.test(selected!.id, prompt),
    onError: (err: Error) => toast.error('Inference failed', { description: err.message }),
  })

  const models = data?.models ?? []
  const selected = models.find((model) => model.id === selectedId) ?? models.find((model) => model.id === 'm_bge_large') ?? models[0]

  const filtered = models
    .filter((model) => (tab === 'all' ? true : model.type === ({ generation: 'Generation', embedding: 'Embedding', reranking: 'Reranking' } as Record<string, ModelType>)[tab]))
    .filter((model) => (provider === 'all' ? true : model.provider === provider))
    .filter((model) => (scope === 'all' ? true : scope === 'local' ? model.local : !model.local))
    .filter((model) => `${model.name} ${model.provider} ${model.description}`.toLowerCase().includes(search.toLowerCase()))

  if (isLoading) {
    return (
      <>
        <PageHeader eyebrow="Inference workspace" title="Model manager" description="One place for language models, embeddings and rerankers." />
        <div className="flex-1 overflow-y-auto"><LoadingState label="Loading model registry…" rows={8} /></div>
      </>
    )
  }

  if (isError || !data) {
    return (
      <>
        <PageHeader eyebrow="Inference workspace" title="Model manager" description="One place for language models, embeddings and rerankers." />
        <div className="flex-1 overflow-y-auto"><ErrorState message={(error as Error)?.message} onRetry={() => void refetch()} /></div>
      </>
    )
  }

  const gpuPct = (data.resources.gpu.used / data.resources.gpu.total) * 100
  const systemPct = (data.resources.system.used / data.resources.system.total) * 100

  return (
    <>
      <PageHeader
        eyebrow="Inference workspace"
        title="Model manager"
        description="One place for language models, embeddings and rerankers."
        breadcrumbs={[{ label: 'Research lab', to: '/' }, { label: 'Models' }]}
        actions={
          <Button variant="primary" size="lg" onClick={() => setAddOpen(true)}>
            <Plus className="h-3.5 w-3.5" /> Add model
          </Button>
        }
      />

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="px-6 py-5">
          <section className="grid gap-3 md:grid-cols-3">
            {data.providers.map((item) => (
              <div key={item.id} className="rounded-lg border border-line bg-gradient-to-b from-[#101927] to-[#0d1622] px-4 py-3.5">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h2 className="text-[13px] font-medium text-ink">{item.name}</h2>
                    <p className="mt-0.5 font-mono text-[8.5px] text-dim">{item.type}</p>
                  </div>
                  <span className={cn('flex items-center gap-1.5 font-mono text-[8.5px] uppercase tracking-[0.08em]', item.status === 'connected' ? 'text-success' : item.status === 'configured' ? 'text-warn' : 'text-dim')}>
                    <StatusDot status={item.status === 'connected' ? 'success' : item.status === 'configured' ? 'warning' : 'idle'} pulse={item.id === 'huggingface'} />
                    {item.status === 'connected' ? 'Connected' : item.status === 'configured' ? 'Configured' : 'Disconnected'}
                  </span>
                </div>
                <div className="mt-4 flex items-center justify-between">
                  <span className="font-mono text-[9px] text-muted">{item.detail}</span>
                  <button onClick={() => setConfigureProvider(item.name)} className="flex items-center gap-1 font-mono text-[8.5px] text-[#7f95cf] hover:text-[#b5c6ff]">
                    Configure <Settings2 className="h-2.5 w-2.5" />
                  </button>
                </div>
              </div>
            ))}
          </section>

          <div className="mt-5 flex flex-wrap items-end justify-between gap-3">
            <Tabs value={tab} onValueChange={setTab}>
              <TabsList>
                <TabsTrigger value="all">All models <span className="ml-1.5 rounded bg-white/[0.05] px-1 font-mono text-[8.5px] text-dim">{models.length}</span></TabsTrigger>
                <TabsTrigger value="generation">Language models</TabsTrigger>
                <TabsTrigger value="embedding">Embeddings</TabsTrigger>
                <TabsTrigger value="reranking">Rerankers</TabsTrigger>
              </TabsList>
            </Tabs>
            <span className="font-mono text-[8.5px] text-dim">{data.resources.gpu.label} VRAM in use</span>
          </div>

          <div className="mt-3 grid gap-4 xl:grid-cols-[minmax(0,1fr)_318px]">
            <div className="min-w-0">
              <div className="mb-2.5 flex flex-wrap items-center gap-2">
                <SearchInput value={search} onChange={setSearch} placeholder="Search models…" className="w-[230px]" />
                <Select
                  value={provider}
                  onValueChange={setProvider}
                  options={[{ value: 'all', label: 'All providers' }, ...data.providers.map((item) => ({ value: item.name, label: item.name }))]}
                  className="w-[155px]"
                  aria-label="Filter by provider"
                />
                <Select
                  value={scope}
                  onValueChange={setScope}
                  options={[
                    { value: 'all', label: 'Local & remote' },
                    { value: 'local', label: 'Local only' },
                    { value: 'remote', label: 'Remote only' },
                  ]}
                  className="w-[150px]"
                  aria-label="Filter by deployment"
                />
                <span className="ml-auto font-mono text-[8.5px] text-dim">{filtered.length} models</span>
              </div>

              {filtered.length === 0 ? (
                <div className="rounded-lg border border-line bg-surface">
                  <EmptyState icon={<Search className="h-4 w-4" />} title="No models found" description="Adjust the provider or deployment filters." action={<Button variant="secondary" size="sm" onClick={() => { setSearch(''); setProvider('all'); setScope('all') }}>Clear filters</Button>} />
                </div>
              ) : (
                <div className="overflow-hidden rounded-lg border border-line bg-[#0c141f]">
                  <table className="w-full border-collapse">
                    <thead>
                      <tr className="border-b border-line">
                        {['Model', 'Type', 'Context / dims', 'Provider', 'Status', ''].map((header) => (
                          <th key={header} className={cn('table-head h-8 px-3 text-left first:pl-4 last:pr-4', header === '' && 'sr-only')}>{header || 'Actions'}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {filtered.map((model) => {
                        const Icon = typeIcon[model.type]
                        const status = statusLabel[model.status]
                        return (
                          <tr key={model.id} onClick={() => setSelectedId(model.id)} className={cn('table-row cursor-pointer last:border-0', selected?.id === model.id && 'bg-accent/[0.07] hover:bg-accent/[0.09]')}>
                            <td className="px-3 py-2.5 pl-4">
                              <div className="flex items-center gap-2.5">
                                <span className="flex h-6 w-6 items-center justify-center rounded border" style={{ borderColor: `${typeAccent[model.type]}44`, backgroundColor: `${typeAccent[model.type]}0c`, color: typeAccent[model.type] }}>
                                  <Icon className="h-3 w-3" />
                                </span>
                                <div>
                                  <p className="text-[11px] text-[#c5d0df]">{model.name}</p>
                                  <p className="mt-0.5 font-mono text-[8px] text-dim">{model.local ? 'Local inference' : 'API provider'}</p>
                                </div>
                              </div>
                            </td>
                            <td className="px-3 py-2.5 font-mono text-[9px] text-muted">{model.type}</td>
                            <td className="px-3 py-2.5 font-mono text-[9px] text-muted">{model.type === 'Embedding' ? `${model.dimensions} dims` : model.context}</td>
                            <td className="px-3 py-2.5 font-mono text-[9px] text-muted">{model.provider}</td>
                            <td className="px-3 py-2.5">
                              <span className={cn('flex items-center gap-1.5 font-mono text-[9px]', status.className)}>
                                <StatusDot status={status.dot} pulse={model.status === 'loaded'} /> {status.label}
                              </span>
                            </td>
                            <td className="px-3 py-2.5 pr-4" onClick={(event) => event.stopPropagation()}>
                              <DropdownMenu>
                                <DropdownMenuTrigger asChild>
                                  <button className="rounded p-1 text-dim hover:bg-white/5 hover:text-ink" aria-label={`Actions for ${model.name}`}><MoreHorizontal className="h-4 w-4" /></button>
                                </DropdownMenuTrigger>
                                <DropdownMenuContent className="w-48">
                                  <DropdownMenuItem icon={<Zap className="h-3.5 w-3.5" />} onSelect={() => { setSelectedId(model.id); setTestOpen(true) }}>Test inference</DropdownMenuItem>
                                  <DropdownMenuItem icon={<BookOpen className="h-3.5 w-3.5" />} onSelect={() => { setSelectedId(model.id); setDocsOpen(true) }}>Model documentation</DropdownMenuItem>
                                  {model.local && (
                                    <DropdownMenuItem icon={<Cpu className="h-3.5 w-3.5" />} onSelect={() => updateMutation.mutate({ id: model.id, input: { status: model.status === 'loaded' ? 'idle' : 'loaded' } })}>
                                      {model.status === 'loaded' ? 'Unload from GPU' : 'Load on GPU'}
                                    </DropdownMenuItem>
                                  )}
                                  <DropdownMenuSeparator />
                                  <DropdownMenuItem onSelect={() => toast.success('Model configuration copied')}>Copy model ID</DropdownMenuItem>
                                </DropdownMenuContent>
                              </DropdownMenu>
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              )}

              <div className="mt-4 rounded-lg border border-line bg-[#0c141f] px-4 py-3">
                <div className="flex items-center justify-between">
                  <p className="text-[11.5px] font-medium text-ink">Local resource allocation</p>
                  <span className="font-mono text-[8.5px] text-dim">{models.filter((model) => model.local && model.status === 'loaded').length} models loaded</span>
                </div>
                <div className="mt-3 grid gap-x-8 gap-y-3 md:grid-cols-2">
                  <div>
                    <div className="flex items-center justify-between font-mono text-[8.5px] text-dim">
                      <span className="flex items-center gap-1.5"><MemoryStick className="h-3 w-3" /> GPU memory</span>
                      <span className="text-muted">{data.resources.gpu.label}</span>
                    </div>
                    <ProgressBar value={gpuPct} color="#7C6AF0" className="mt-1.5" height={5} />
                  </div>
                  <div>
                    <div className="flex items-center justify-between font-mono text-[8.5px] text-dim">
                      <span className="flex items-center gap-1.5"><HardDrive className="h-3 w-3" /> System memory</span>
                      <span className="text-muted">{data.resources.system.label}</span>
                    </div>
                    <ProgressBar value={systemPct} color="#5277EC" className="mt-1.5" height={5} />
                  </div>
                </div>
              </div>

              <p className="mt-2.5 font-mono text-[8px] text-[#4e5c70]">API keys are encrypted and stored locally. Manage provider credentials in Settings → Providers.</p>
            </div>

            {selected && (
              <aside className="rounded-lg border border-line bg-[#0c141f]">
                <div className="border-b border-line px-4 py-3.5">
                  <p className="font-mono text-[8px] uppercase tracking-[0.15em] text-dim">Model details</p>
                  <h2 className="mt-1.5 text-[14px] font-semibold text-ink">{selected.name}</h2>
                  <p className="mt-0.5 break-all font-mono text-[8.5px] text-dim">{selected.id.replace('m_', '')} · {selected.architecture}</p>
                  <div className="mt-2">
                    <span className={cn('flex items-center gap-1.5 font-mono text-[9px]', statusLabel[selected.status].className)}>
                      <StatusDot status={statusLabel[selected.status].dot} pulse={selected.status === 'loaded'} />
                      {selected.status === 'loaded' ? `Loaded on ${selected.device.includes('CUDA') ? 'GPU 0' : selected.device}` : statusLabel[selected.status].label}
                    </span>
                  </div>
                </div>
                <div className="px-4 py-2">
                  <DetailRow label="Architecture" value={selected.architecture} />
                  <DetailRow label="Parameters" value={selected.parameters} />
                  <DetailRow label="Dimensions" value={selected.dimensions} />
                  <DetailRow label="Max sequence" value={selected.maxSequence} />
                  <DetailRow label="Precision" value={selected.precision} />
                  <DetailRow label="Device" value={selected.device} />
                  <DetailRow label="Memory usage" value={selected.memory} />
                  <DetailRow label="License" value={selected.license} />
                  <DetailRow label="Used by" value={`${selected.usedBy} pipelines`} />
                </div>
                {selected.benchmark && (
                  <div className="mx-4 mb-3 rounded-md border border-line-strong bg-[#0b121c] px-3 py-2.5">
                    <div className="flex items-center justify-between">
                      <p className="font-mono text-[8px] uppercase tracking-[0.12em] text-dim">Benchmark · {selected.benchmark.name}</p>
                      <span className="h-1.5 w-1.5 rounded-full bg-success" />
                    </div>
                    <div className="mt-1.5 flex items-end justify-between gap-3">
                      <span className="text-[22px] font-semibold leading-none tracking-[-0.03em] text-success">{selected.benchmark.score.toFixed(2)}</span>
                      <div className="text-right font-mono text-[8.5px] text-[#7f8da2]">
                        <p>{selected.benchmark.latency}</p>
                        <p>{selected.benchmark.throughput}</p>
                      </div>
                    </div>
                  </div>
                )}
                <div className="flex gap-2 border-t border-line px-4 py-3">
                  <Button variant="primary" size="sm" className="flex-1" onClick={() => setTestOpen(true)}><Zap className="h-3 w-3" /> Test inference</Button>
                  <Button variant="secondary" size="sm" className="flex-1" onClick={() => setDocsOpen(true)}>Model docs</Button>
                </div>
              </aside>
            )}
          </div>
        </div>
      </div>

      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent size="md">
          <DialogHeader eyebrow="Model registry" title="Add a model" description="Register a hosted model or discover a local checkpoint." />
          <DialogBody className="space-y-4">
            <Field label="Model name">
              <Input value={newModel.name} onChange={(event) => setNewModel((value) => ({ ...value, name: event.target.value }))} placeholder="e.g. Llama 3.2 3B" autoFocus />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Provider">
                <Select value={newModel.provider} onValueChange={(value) => setNewModel((current) => ({ ...current, provider: value }))} options={data.providers.map((item) => ({ value: item.name, label: item.name }))} />
              </Field>
              <Field label="Model type">
                <Select value={newModel.type} onValueChange={(value) => setNewModel((current) => ({ ...current, type: value }))} options={['Generation', 'Embedding', 'Reranking']} />
              </Field>
            </div>
            <div className="rounded-md border border-line bg-[#0b111b] px-3 py-2.5 text-[10.5px] text-muted">
              Ensure provider credentials are configured in Settings → Providers before running inference.
            </div>
          </DialogBody>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setAddOpen(false)}>Cancel</Button>
            <Button variant="primary" disabled={!newModel.name.trim() || registerMutation.isPending} onClick={() => registerMutation.mutate()}>
              {registerMutation.isPending ? 'Registering…' : 'Add model'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={testOpen} onOpenChange={(open) => { setTestOpen(open); if (!open) testMutation.reset() }}>
        <DialogContent size="lg">
          <DialogHeader eyebrow={selected?.provider} title={`Test ${selected?.name ?? 'model'}`} description="Run a single request against the configured inference endpoint." />
          <DialogBody className="space-y-3">
            <Field label="Prompt">
              <textarea
                value={prompt}
                onChange={(event) => setPrompt(event.target.value)}
                className="min-h-[92px] w-full resize-y rounded-md border border-line-strong bg-[#0a1019] px-3 py-2.5 font-mono text-[11px] leading-relaxed text-ink outline-none focus:border-accent/70 focus:ring-1 focus:ring-accent/25"
              />
            </Field>
            <div className="flex flex-wrap gap-2">
              {['Summarize retrieval quality.', 'Write a grounded answer.', 'Score this chunk 0–1.'].map((suggestion) => (
                <button key={suggestion} onClick={() => setPrompt(suggestion)} className="rounded border border-line-strong bg-[#0b111b] px-2 py-1 font-mono text-[8.5px] text-dim transition-colors hover:border-accent/40 hover:text-ink">
                  {suggestion}
                </button>
              ))}
            </div>
            <div className="rounded-lg border border-line bg-[#080d15] p-3">
              <div className="flex items-center justify-between border-b border-line/60 pb-2">
                <span className="flex items-center gap-1.5 font-mono text-[8.5px] uppercase tracking-[0.12em] text-dim"><Terminal className="h-3 w-3" /> Response</span>
                {testMutation.data && <span className="font-mono text-[8.5px] text-success">{testMutation.data.latencyMs}ms · {testMutation.data.tokens} tokens · ${testMutation.data.cost.toFixed(4)}</span>}
              </div>
              {testMutation.isPending ? (
                <div className="flex items-center gap-2 py-5 font-mono text-[10px] text-muted"><Loader2 className="h-3.5 w-3.5 animate-spin text-accent" /> Running inference…</div>
              ) : testMutation.data ? (
                <p className="py-2.5 font-mono text-[10.5px] leading-relaxed text-[#b8c4d6]">{testMutation.data.output}</p>
              ) : testMutation.isError ? (
                <p className="py-2.5 font-mono text-[10px] text-danger">{(testMutation.error as Error).message}</p>
              ) : (
                <p className="py-5 text-center font-mono text-[9.5px] text-dim">Send a request to inspect latency and output.</p>
              )}
            </div>
          </DialogBody>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setTestOpen(false)}>Close</Button>
            <Button variant="primary" disabled={!prompt.trim() || testMutation.isPending || !selected} onClick={() => testMutation.mutate()}>
              {testMutation.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Zap className="h-3.5 w-3.5" />} Run inference
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={docsOpen} onOpenChange={setDocsOpen}>
        <DialogContent size="lg">
          <DialogHeader eyebrow="Documentation" title={selected?.name ?? 'Model'} description={selected?.description} />
          <DialogBody className="space-y-4">
            <div className="grid grid-cols-2 gap-2">
              {selected && [
                ['Provider', selected.provider],
                ['Type', selected.type],
                ['License', selected.license],
                ['Parameters', selected.parameters],
                ['Context', selected.maxSequence],
                ['Device', selected.device],
              ].map(([label, value]) => (
                <div key={label} className="rounded border border-line/70 bg-[#0b111b] px-3 py-2">
                  <p className="font-mono text-[8px] uppercase tracking-wider text-dim">{label}</p>
                  <p className="mt-1 font-mono text-[10px] text-[#bcc8d9]">{value}</p>
                </div>
              ))}
            </div>
            <div className="rounded-md border border-line bg-[#0b111b] p-3">
              <p className="text-[11px] font-medium text-ink">Using this model in a pipeline</p>
              <p className="mt-1.5 text-[10.5px] leading-relaxed text-muted">
                Select a node that references this model in the graph inspector. Model IDs are resolved at run time, so swapping a model here updates every pipeline that uses the registry alias.
              </p>
              <pre className="mt-2 overflow-x-auto rounded border border-line/70 bg-[#080d15] p-2.5 font-mono text-[9.5px] leading-relaxed text-[#9db1d4]">{`from rag_studio import model\n\nllm = model.load("${selected?.id ?? 'model'}")`}</pre>
            </div>
          </DialogBody>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setDocsOpen(false)}>Close</Button>
            <Button variant="secondary" onClick={() => { setDocsOpen(false); setTestOpen(true) }}><Zap className="h-3.5 w-3.5" /> Test inference</Button>
            <Button variant="primary" onClick={() => toast.success('Documentation copied to clipboard')}><Download className="h-3.5 w-3.5" /> Copy reference</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(configureProvider)} onOpenChange={(open) => !open && setConfigureProvider(null)}>
        <DialogContent size="md">
          <DialogHeader eyebrow="Provider" title={`Configure ${configureProvider}`} description="Credentials are stored in the local encrypted vault." />
          <DialogBody className="space-y-3">
            <Field label="API key"><Input type="password" placeholder="sk-••••••••••••••••" /></Field>
            <Field label="Base URL" hint="Leave blank to use the provider default endpoint."><Input placeholder="https://api.provider.com/v1" /></Field>
            <div className="flex items-center gap-2 rounded-md border border-success/20 bg-success/[0.05] px-3 py-2 font-mono text-[9px] text-success"><Check className="h-3 w-3" /> Connection verified · 48ms</div>
          </DialogBody>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setConfigureProvider(null)}>Cancel</Button>
            <Button variant="primary" onClick={() => { toast.success(`${configureProvider} credentials saved`); setConfigureProvider(null) }}>Save credentials</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
