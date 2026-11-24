import * as React from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  ArrowLeft,
  ArrowRight,
  Copy,
  Download,
  GitBranch,
  Layers,
  Loader2,
  ListTree,
  Search,
  Sparkles,
} from 'lucide-react'
import { toast } from 'sonner'
import { PageHeader } from '@/components/shared/page'
import { Button } from '@/components/ui/button'
import { Badge, EmptyState, ErrorState, LoadingState, ProgressBar, StatusDot } from '@/components/ui/badge'
import { executionsApi } from '@/api/executions.api'
import { useActiveExecution } from '@/lib/activeExecution'
import { cn, downloadFile, formatMs, formatNumber } from '@/lib/utils'
import type { NodeRun, StepItem, StepOutput } from '@/types'

function Copyable({ value, label }: { value: string; label: string }) {
  return (
    <button
      onClick={() => { navigator.clipboard?.writeText(value); toast.success(`${label} copied`) }}
      className="flex items-center gap-1 font-mono text-[8.5px] text-dim transition-colors hover:text-ink"
    >
      <Copy className="h-2.5 w-2.5" /> {label}
    </button>
  )
}

function StepItemRow({ item, index, active, onSelect }: { item: StepItem; index: number; active: boolean; onSelect: () => void }) {
  return (
    <button
      onClick={onSelect}
      className={cn(
        'flex w-full items-start gap-2.5 border-b border-line/60 px-3 py-2.5 text-left transition-colors last:border-0',
        active ? 'bg-accent/[0.08]' : 'hover:bg-white/[0.02]',
      )}
    >
      <span className={cn('mt-0.5 flex h-4 min-w-4 items-center justify-center rounded border font-mono text-[7.5px]', active ? 'border-accent/50 bg-accent/15 text-[#b5c6ff]' : 'border-line-strong bg-[#0b111b] text-dim')}>
        {String(index + 1).padStart(2, '0')}
      </span>
      <div className="min-w-0 flex-1">
        <p className={cn('truncate text-[10.5px]', active ? 'text-ink' : 'text-[#c1ccdb]')}>{item.title}</p>
        <p className="mt-0.5 truncate font-mono text-[8px] text-dim">
          {item.source || '—'} <span className="text-[#344158]">·</span> {item.id}
        </p>
        <p className="mt-1 truncate font-mono text-[8.5px] text-[#71809a]">{item.content}</p>
      </div>
    </button>
  )
}

function StepDetail({ item }: { item: StepItem }) {
  const entries = Object.entries(item.meta)
  return (
    <div className="border-t border-line/60 px-3 py-2.5">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="min-w-0 truncate text-[11px] font-medium text-ink">{item.title}</h3>
        {item.source && <span className="truncate font-mono text-[8px] text-dim">{item.source}</span>}
        <div className="ml-auto"><Copyable value={item.content} label="Copy item" /></div>
      </div>
      <p className="mt-2 whitespace-pre-wrap text-[10.5px] leading-[1.65] text-[#b3c0d2]">{item.content || '—'}</p>
      {entries.length > 0 && (
        <div className="mt-2.5 flex flex-wrap gap-1.5 border-t border-line/60 pt-2">
          {entries.map(([key, value]) => (
            <span key={key} className="rounded border border-line-strong bg-[#0b111b] px-1.5 py-0.5 font-mono text-[8px] text-dim">
              {key} <span className="text-[#a6b8ff]">{String(value)}</span>
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

function InProgress({ node }: { node?: NodeRun }) {
  const running = node?.status === 'running'
  return (
    <div className="overflow-hidden rounded-lg border border-accent/25 bg-[#0c141f]">
      <div className="flex flex-wrap items-center gap-2 border-b border-line bg-accent/[0.04] px-3 py-2">
        {running ? <Loader2 className="h-3.5 w-3.5 animate-spin text-accent" /> : <StatusDot status="idle" />}
        <h2 className="text-[11.5px] font-medium text-ink">{node?.name ?? 'Fase in attesa'}</h2>
        <Badge tone={running ? 'accent' : 'neutral'}>{running ? 'in corso' : 'in attesa'}</Badge>
        {node && <span className="ml-auto font-mono text-[8.5px] text-dim">{node.kind}</span>}
      </div>
      <div className="px-3 py-8 text-center">
        <p className="text-[11px] text-muted">
          {running ? 'Questa fase sta producendo i suoi output.' : 'Questa fase non è ancora stata eseguita.'}
        </p>
        <p className="mt-1 font-mono text-[9px] text-dim">Gli output appariranno qui appena il nodo termina.</p>
      </div>
    </div>
  )
}

interface NodeEntry {
  nodeId: string
  name: string
  kind: string
  accent: string
  status: string
  step?: StepOutput
}

function statusDot(status: string) {
  if (status === 'running') return 'running' as const
  if (status === 'completed') return 'success' as const
  if (status === 'failed') return 'danger' as const
  if (status === 'skipped') return 'warning' as const
  return 'idle' as const
}

export function ResultsPage() {
  const { runId } = useParams()
  const navigate = useNavigate()
  const [selectedNode, setSelectedNode] = React.useState<string | null>(null)
  const [search, setSearch] = React.useState('')
  const [selectedItemId, setSelectedItemId] = React.useState<string | null>(null)
  const [expandedEmbedding, setExpandedEmbedding] = React.useState(false)

  const active = useActiveExecution()
  const liveSnapshot = active?.execution.id === runId ? active : null

  const { data: execution, isLoading: isExecutionLoading } = useQuery({
    queryKey: ['execution', runId],
    queryFn: () => executionsApi.get(runId!),
    enabled: Boolean(runId),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === 'running' || status === 'queued' ? 1500 : false
    },
  })
  const executionStatus = liveSnapshot?.execution.status ?? execution?.status
  const isRunning = executionStatus === 'running' || executionStatus === 'queued'
  const nodeRuns = liveSnapshot?.execution.nodeRuns ?? execution?.nodeRuns ?? []
  const finishedCount = nodeRuns.filter((node) =>
    node.status === 'completed' || node.status === 'skipped' || node.status === 'failed',
  ).length

  // The backend now persists a partial result after each node, so completed
  // nodes can be inspected while the remaining ones are still running.
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['results', runId],
    queryFn: () => executionsApi.results(runId!),
    enabled: Boolean(runId) && Boolean(execution),
    refetchInterval: isRunning ? 1200 : false,
  })

  const steps = data?.stepOutputs ?? []
  const fallbackStep = steps.find((step) => step.kind === 'reranking') ?? steps[steps.length - 1]
  const activeStep = steps.find((step) => step.nodeId === selectedNode) ?? fallbackStep
  const activeNodeId = activeStep?.nodeId ?? selectedNode
  const activeNode = nodeRuns.find((node) => node.nodeId === activeNodeId)
  const showInProgress = !activeStep && (isRunning || Boolean(activeNode))

  const nodeEntries: NodeEntry[] = nodeRuns.length > 0
    ? nodeRuns.map((node) => ({
        nodeId: node.nodeId,
        name: node.name,
        kind: node.kind,
        accent: node.accent,
        status: node.status,
        step: steps.find((step) => step.nodeId === node.nodeId),
      }))
    : steps.map((step) => ({
        nodeId: step.nodeId,
        name: step.name,
        kind: step.kind,
        accent: step.accent,
        status: step.status,
        step,
      }))

  React.useEffect(() => {
    setSearch('')
    setSelectedItemId(null)
  }, [activeNodeId])

  const filteredItems = React.useMemo(() => {
    const term = search.trim().toLowerCase()
    const items = activeStep?.items ?? []
    if (!term) return items
    return items.filter((item) =>
      [item.title, item.source, item.content, ...Object.values(item.meta).map((value) => String(value))]
        .some((value) => value.toLowerCase().includes(term)),
    )
  }, [activeStep, search])

  const activeItem = filteredItems.find((item) => item.id === selectedItemId) ?? filteredItems[0]

  if (!runId) {
    return (
      <>
        <PageHeader eyebrow="Run results" title="Intermediate results" />
        <div className="flex-1 overflow-y-auto"><EmptyState icon={<Layers className="h-4 w-4" />} title="Nessuna esecuzione selezionata" description="Esegui una pipeline, poi apri i risultati dal pannello dell’editor." /></div>
      </>
    )
  }

  if (isExecutionLoading) {
    return (
      <>
        <PageHeader eyebrow="Run results" title="Intermediate results" />
        <div className="flex-1 overflow-y-auto"><LoadingState label="Loading run status…" rows={6} /></div>
      </>
    )
  }

  if (isRunning && !data) {
    const currentNode = nodeRuns.find((node) => node.status === 'running')
    return (
      <>
        <PageHeader eyebrow="Run results" title="Intermediate results" />
        <div className="flex-1 overflow-y-auto p-5">
          <div className="rounded-lg border border-accent/30 bg-accent/[0.05] p-4">
            <div className="flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin text-accent" />
              <h3 className="text-[13px] font-medium text-ink">Esecuzione ancora in corso</h3>
              <Badge tone="accent">Running</Badge>
            </div>
            <p className="mt-1.5 text-[11.5px] leading-relaxed text-muted">
              I risultati dei nodi completati compariranno qui appena disponibili; gli altri restano segnati come in corso. Stato attuale: {finishedCount}/{nodeRuns.length} nodi terminati.
            </p>
            <ProgressBar value={finishedCount} max={Math.max(1, nodeRuns.length)} className="mt-3" color="#5277EC" />
            {currentNode && <p className="mt-2 font-mono text-[9px] text-dim">Nodo corrente: {currentNode.name}</p>}
            <div className="mt-4 flex flex-wrap gap-2">
              <Button size="sm" onClick={() => navigate(`/runs/${runId}`)}>Apri monitor live <ArrowRight className="h-3 w-3" /></Button>
              <Button variant="secondary" size="sm" onClick={() => navigate(-1)}><ArrowLeft className="h-3 w-3" /> Torna indietro</Button>
            </div>
          </div>
          {nodeRuns.length > 0 && (
            <div className="mt-4 rounded-lg border border-line bg-surface2/40">
              <p className="border-b border-line px-3 py-2 font-mono text-[9px] uppercase tracking-[0.12em] text-dim">Stato nodi</p>
              <ul className="divide-y divide-line/60">
                {nodeRuns.map((node) => (
                  <li key={node.nodeId} className="flex items-center gap-2 px-3 py-2 text-[10.5px]">
                    <StatusDot status={statusDot(node.status)} pulse={node.status === 'running'} />
                    <span className="min-w-0 flex-1 truncate text-ink">{node.name}</span>
                    <span className="font-mono text-[9px] text-dim">{node.status}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </>
    )
  }

  if (isLoading) {
    return (
      <>
        <PageHeader eyebrow="Run results" title="Intermediate results" />
        <div className="flex-1 overflow-y-auto"><LoadingState label="Loading intermediate outputs…" rows={8} /></div>
      </>
    )
  }

  if (isError || !data) {
    return (
      <>
        <PageHeader eyebrow="Run results" title="Intermediate results" />
        <div className="flex-1 overflow-y-auto"><ErrorState message={(error as Error)?.message} onRetry={() => void refetch()} /></div>
      </>
    )
  }

  const exportResults = () => {
    downloadFile(`rag-studio-results-${runId}.json`, JSON.stringify(data, null, 2))
    toast.success('Results exported')
  }

  const embeddingValues = expandedEmbedding ? data.embedding.values : data.embedding.values.slice(0, 128)
  const cosine = data.embedding.cosineSimilarity
  const cosineLabel = Number.isFinite(cosine) && cosine !== 0 ? cosine.toFixed(3) : 'n/d'

  return (
    <>
      <PageHeader
        eyebrow={`Hybrid RAG pipeline / Run ${runId}`}
        title="Intermediate results"
        description="Seleziona una fase a sinistra per ispezionare gli output reali di quello step."
        breadcrumbs={[{ label: 'Pipelines', to: '/pipelines' }, { label: 'Hybrid RAG pipeline', to: '/pipelines/pl_hybrid_rag' }, { label: `Run ${runId}`, to: `/runs/${runId}` }, { label: 'Results' }]}
        actions={
          <>
            <Button variant="secondary" onClick={exportResults}><Download className="h-3.5 w-3.5" /> Export results</Button>
            <Button variant="secondary" onClick={() => navigate(`/runs/${runId}`)}><ArrowLeft className="h-3.5 w-3.5" /> Back to run</Button>
          </>
        }
      />

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="space-y-3 px-6 py-4">
          {isRunning && (
            <section className="flex flex-wrap items-center gap-3 rounded-lg border border-accent/30 bg-accent/[0.05] px-4 py-2.5">
              <Loader2 className="h-4 w-4 animate-spin text-accent" />
              <span className="text-[11.5px] text-ink">Esecuzione in corso · risultati parziali aggiornati in tempo reale</span>
              <Badge tone="accent">{finishedCount}/{nodeRuns.length} nodi terminati</Badge>
              <ProgressBar value={finishedCount} max={Math.max(1, nodeRuns.length)} className="w-[160px]" color="#5277EC" />
              <Button variant="secondary" size="sm" onClick={() => navigate(`/runs/${runId}`)}>
                Monitor live <ArrowRight className="h-3 w-3" />
              </Button>
            </section>
          )}

          <section className="flex flex-wrap items-center gap-3 rounded-lg border border-line bg-[#0c141f] px-4 py-3">
            <span className="font-mono text-[8px] uppercase tracking-[0.14em] text-dim">Query</span>
            <p className="min-w-0 flex-1 truncate text-[13px] font-medium tracking-[-0.01em] text-ink">{data.query}</p>
            <div className="flex items-center gap-3 font-mono text-[8.5px] text-dim">
              <span className="flex items-center gap-1.5 text-success">
                <StatusDot status={isRunning ? 'running' : executionStatus === 'failed' ? 'danger' : 'success'} pulse={isRunning} />
                {isRunning ? 'Running' : executionStatus === 'failed' ? 'Failed' : 'Completed'}
              </span>
              <span className="text-[#344158]">·</span>
              <span>{formatMs(data.runtime.latencyMs)}</span>
              <span className="text-[#344158]">·</span>
              <span>{data.selectedCount} source documents</span>
            </div>
          </section>

          <div className="grid gap-3 xl:grid-cols-[194px_minmax(0,1fr)_360px]">
            <aside className="space-y-3">
              <section className="overflow-hidden rounded-lg border border-line bg-[#0c141f]">
                <div className="border-b border-line px-3 py-2">
                  <p className="font-mono text-[8px] uppercase tracking-[0.14em] text-dim">Node outputs</p>
                </div>
                <div className="py-1">
                  {nodeEntries.map((node) => {
                    const active = activeNodeId === node.nodeId
                    return (
                      <button
                        key={node.nodeId}
                        onClick={() => setSelectedNode(node.nodeId)}
                        className={cn('flex w-full items-start gap-2 px-3 py-[6px] text-left transition-colors', active ? 'bg-accent/[0.08]' : 'hover:bg-white/[0.02]')}
                      >
                        <span className="mt-[3px] shrink-0"><StatusDot status={statusDot(node.status)} pulse={node.status === 'running'} /></span>
                        <span className="min-w-0 flex-1">
                          <span className={cn('block truncate text-[10px]', active ? 'text-ink' : 'text-[#9eacbf]')}>{node.name}</span>
                          <span className="mt-0.5 block truncate font-mono text-[8px] text-dim">
                            {node.step?.detail ?? (node.status === 'running' ? 'in corso…' : 'in attesa…')}
                          </span>
                        </span>
                        {!node.step && node.status === 'running' && <span className="mt-0.5 shrink-0 font-mono text-[7px] uppercase text-accent">live</span>}
                      </button>
                    )
                  })}
                </div>
              </section>

              <section className="overflow-hidden rounded-lg border border-line bg-[#0c141f]">
                <div className="flex items-center justify-between border-b border-line px-3 py-2">
                  <p className="font-mono text-[8px] uppercase tracking-[0.14em] text-dim">Data lineage</p>
                  <ListTree className="h-3 w-3 text-dim" />
                </div>
                <div className="py-2">
                  {data.lineage.map((step, index) => (
                    <div key={`${step.label}-${index}`} className="flex items-start gap-2 px-3 py-[5px]" style={{ paddingLeft: 12 + step.indent * 13 }}>
                      <span className="mt-[3px] h-1.5 w-1.5 shrink-0 rounded-full" style={{ backgroundColor: step.accent ?? '#4d5c73' }} />
                      <div className="min-w-0">
                        <p className="truncate font-mono text-[9px] text-[#aebacc]">{step.label}</p>
                        <p className="truncate font-mono text-[8px] text-dim">{step.detail}</p>
                      </div>
                    </div>
                  ))}
                  {isRunning && nodeEntries.filter((node) => !node.step).map((node) => (
                    <div key={`pending-${node.nodeId}`} className="flex items-start gap-2 px-3 py-[5px] opacity-70">
                      <StatusDot status={statusDot(node.status)} pulse={node.status === 'running'} />
                      <div className="min-w-0">
                        <p className="truncate font-mono text-[9px] text-[#aebacc]">{node.name}</p>
                        <p className="truncate font-mono text-[8px] text-dim">{node.status === 'running' ? 'in corso…' : 'in attesa…'}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </section>

              <div className="rounded-lg border border-line bg-[#0b121c] px-3 py-2.5">
                <p className="font-mono text-[8px] uppercase tracking-[0.12em] text-dim">Trace</p>
                <p className="mt-1 break-all font-mono text-[8.5px] text-[#7f8da2]">{data.traceId}</p>
                <Copyable value={data.traceId} label="Copy trace ID" />
              </div>
            </aside>

            <section className="min-w-0">
              {showInProgress ? (
                <InProgress node={activeNode} />
              ) : activeStep ? (
                <div className="overflow-hidden rounded-lg border border-line bg-[#0c141f]">
                  <div className="flex flex-wrap items-center gap-2 border-b border-line px-3 py-2">
                    <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: activeStep.accent }} />
                    <h2 className="text-[11.5px] font-medium text-ink">{activeStep.name}</h2>
                    <Badge tone="outline">{activeStep.kind}</Badge>
                    <span className="ml-auto font-mono text-[8.5px] text-dim">{activeStep.detail} · {activeStep.durationMs} ms</span>
                  </div>

                  <div className="grid grid-cols-2 gap-x-4 gap-y-2 border-b border-line/60 px-3 py-2.5 sm:grid-cols-3">
                    {activeStep.metrics.map((metric) => (
                      <div key={metric.label} className="min-w-0">
                        <p className="font-mono text-[8px] uppercase tracking-[0.1em] text-dim">{metric.label}</p>
                        <p className="mt-0.5 truncate text-[10.5px] text-[#c1ccdb]" title={metric.value}>{metric.value}</p>
                      </div>
                    ))}
                  </div>

                  {activeStep.text !== null && (
                    <div className="border-b border-line/60 px-3 py-3">
                      <div className="mb-1.5 flex items-center justify-between">
                        <p className="font-mono text-[8px] uppercase tracking-[0.12em] text-dim">
                          {activeStep.kind === 'generation' ? 'Generated text' : 'Query text'}
                        </p>
                        <Copyable value={activeStep.text} label="Copy text" />
                      </div>
                      <p className="whitespace-pre-wrap rounded border border-line-strong bg-[#0a1019] px-2.5 py-2 text-[11px] leading-[1.7] text-[#b8c4d6]">
                        {activeStep.text || '—'}
                      </p>
                    </div>
                  )}

                  {activeStep.items.length > 0 && (
                    <>
                      <div className="flex items-center gap-2 border-b border-line/60 bg-[#0a1019] px-3 py-1.5">
                        <Search className="h-3 w-3 shrink-0 text-dim" />
                        <input
                          value={search}
                          onChange={(event) => setSearch(event.target.value)}
                          placeholder={activeStep.searchHint}
                          aria-label="Cerca negli output della fase"
                          className="min-w-0 flex-1 bg-transparent font-mono text-[9px] text-[#c1ccdb] outline-none placeholder:text-[#4d5c73]"
                        />
                        <span className="shrink-0 font-mono text-[8px] text-dim">{filteredItems.length}/{activeStep.items.length}</span>
                      </div>
                      <div className="max-h-[300px] overflow-y-auto border-b border-line/60">
                        {filteredItems.length === 0 ? (
                          <EmptyState icon={<Search className="h-4 w-4" />} title="Nessun risultato" description="Prova con un altro termine di ricerca." />
                        ) : (
                          filteredItems.map((item, index) => (
                            <StepItemRow
                              key={`${item.id}-${index}`}
                              item={item}
                              index={index}
                              active={activeItem?.id === item.id}
                              onSelect={() => setSelectedItemId(item.id)}
                            />
                          ))
                        )}
                      </div>
                      {activeItem && <StepDetail item={activeItem} />}
                    </>
                  )}

                  {activeStep.text === null && activeStep.items.length === 0 && (
                    <EmptyState
                      icon={<Layers className="h-4 w-4" />}
                      title="Nessun output catturato per questa fase"
                      description="La fase è stata eseguita ma non ha prodotto dati ispezionabili."
                    />
                  )}
                </div>
              ) : (
                <div className="overflow-hidden rounded-lg border border-line bg-[#0c141f]">
                  <EmptyState icon={<Layers className="h-4 w-4" />} title="Seleziona una fase" description="Clicca su un nodo output per vedere i risultati di quello step." />
                </div>
              )}
            </section>

            <aside className="space-y-3">
              {data.generatedAnswer ? (
              <section className="overflow-hidden rounded-lg border border-line bg-[#0c141f]">
                <div className="flex items-center justify-between border-b border-line px-3 py-2">
                  <h2 className="text-[11.5px] font-medium text-ink">Generated answer</h2>
                  <Badge tone="outline">{data.answerMeta.model}</Badge>
                </div>
                <div className="px-3 py-3">
                  <p className="text-[10.5px] leading-[1.72] text-[#b8c4d6]">
                    {data.generatedAnswer.split(/(\[\d+(?:,\s*\d+)*\])/g).map((part, index) =>
                      /^\[/.test(part) ? (
                        <span key={index} className="mx-0.5 rounded bg-accent/15 px-1 font-mono text-[8.5px] text-[#a6b8ff]">{part}</span>
                      ) : (
                        <React.Fragment key={index}>{part}</React.Fragment>
                      ),
                    )}
                  </p>
                  <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-line/60 pt-2.5 font-mono text-[8px] text-dim">
                    <span>Temperature {data.answerMeta.temperature}</span>
                    <span className="text-[#344158]">·</span>
                    <span>{data.answerMeta.citations} citations</span>
                    <button onClick={() => { navigator.clipboard?.writeText(data.generatedAnswer); toast.success('Answer copied') }} className="ml-auto flex items-center gap-1 text-[#7f95cf] hover:text-[#b5c6ff]"><Copy className="h-2.5 w-2.5" /> Copy</button>
                  </div>
                  <div className="mt-2 flex items-center gap-1.5 font-mono text-[8px] text-success"><StatusDot status="success" /> Grounded in {data.selectedCount} source documents</div>
                </div>
              </section>
              ) : (
                <section className="overflow-hidden rounded-lg border border-accent/25 bg-[#0c141f]">
                  <div className="flex items-center justify-between border-b border-line px-3 py-2">
                    <h2 className="text-[11.5px] font-medium text-ink">Generated answer</h2>
                    <Badge tone="accent">in corso</Badge>
                  </div>
                  <div className="px-3 py-6 text-center font-mono text-[9px] text-dim">In attesa del nodo di generazione…</div>
                </section>
              )}

              {data.embedding.values.length > 0 ? (
              <section className="overflow-hidden rounded-lg border border-line bg-[#0c141f]">
                <div className="flex items-center justify-between border-b border-line px-3 py-2">
                  <h2 className="text-[11.5px] font-medium text-ink">Embedding inspector</h2>
                  <Layers className="h-3.5 w-3.5 text-dim" />
                </div>
                <div className="px-3 py-3">
                  <div className="flex items-center justify-between font-mono text-[8px] text-dim">
                    <span>{data.embedding.model}</span>
                    <span>{formatNumber(data.embedding.dimensions)} dimensions</span>
                  </div>
                  <div className="mt-2.5 grid gap-[3px]" style={{ gridTemplateColumns: 'repeat(16, minmax(0, 1fr))' }}>
                    {embeddingValues.map((value, index) => {
                      const intensity = Math.max(0.08, Math.min(1, value))
                      const hue = value > 0.62 ? '124, 140, 255' : value > 0.4 ? '167, 139, 250' : '72, 88, 122'
                      return (
                        <span
                          key={index}
                          title={`dim ${index}: ${value}`}
                          className="aspect-square rounded-[2px] transition-transform hover:scale-125"
                          style={{ backgroundColor: `rgba(${hue}, ${intensity * 0.85 + 0.12})` }}
                        />
                      )
                    })}
                  </div>
                  <div className="mt-2 flex items-center justify-between font-mono text-[7.5px] text-dim">
                    <span>−1.0</span>
                    <span>Cosine similarity <span className="text-[#b8c4d6]">{cosineLabel}</span></span>
                    <span>+1.0</span>
                  </div>
                  <div className="mt-2 flex items-center gap-3 border-t border-line/60 pt-2 font-mono text-[8px] text-dim">
                    <span>L2 norm <span className="text-muted">{data.embedding.norm}</span></span>
                    <span>dtype <span className="text-muted">{data.embedding.dtype}</span></span>
                    <button onClick={() => setExpandedEmbedding((value) => !value)} className="ml-auto text-[#7f95cf] hover:text-[#b5c6ff]">
                      {expandedEmbedding ? 'Show fewer' : 'View all dimensions'} <ArrowRight className="inline h-2.5 w-2.5" />
                    </button>
                  </div>
                </div>
              </section>
              ) : (
                <section className="overflow-hidden rounded-lg border border-accent/25 bg-[#0c141f]">
                  <div className="flex items-center justify-between border-b border-line px-3 py-2">
                    <h2 className="text-[11.5px] font-medium text-ink">Embedding inspector</h2>
                    <Badge tone="accent">in corso</Badge>
                  </div>
                  <div className="px-3 py-6 text-center font-mono text-[9px] text-dim">In attesa del nodo embedding…</div>
                </section>
              )}

              {data.runtime.breakdown.length > 0 && (
              <section className="rounded-lg border border-line bg-[#0b121c] px-3 py-2.5">
                <div className="flex items-center gap-1.5 font-mono text-[8px] uppercase tracking-[0.12em] text-dim"><GitBranch className="h-3 w-3" /> Runtime breakdown</div>
                <div className="mt-2 space-y-1.5">
                  {data.runtime.breakdown.map((item) => (
                    <div key={item.label} className="flex items-center gap-2">
                      <span className="w-[92px] truncate font-mono text-[8px] text-[#8a98ad]">{item.label}</span>
                      <div className="h-[3px] flex-1 overflow-hidden rounded-full bg-[#1a2433]">
                        <div className="h-full rounded-full" style={{ width: `${Math.min(100, (item.ms / Math.max(1, data.runtime.latencyMs)) * 100)}%`, backgroundColor: item.color }} />
                      </div>
                      <span className="w-[34px] text-right font-mono text-[8px] text-dim">{item.ms}ms</span>
                    </div>
                  ))}
                </div>
              </section>
              )}
            </aside>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-2 border-t border-line/60 pt-2 font-mono text-[8.5px] text-dim">
            <span className="flex items-center gap-1.5">
              <StatusDot status={isRunning ? 'running' : 'success'} pulse={isRunning} />
              {isRunning
                ? `Risultati parziali: ${steps.length} di ${nodeRuns.length} fasi disponibili · aggiornamento automatico`
                : 'All intermediate outputs are persisted with this run for reproducibility'}
            </span>
            <Link to={`/evaluation`} className="flex items-center gap-1 text-[#7f95cf] hover:text-[#b5c6ff]"><Sparkles className="h-2.5 w-2.5" /> Evaluate this run <ArrowRight className="h-2.5 w-2.5" /></Link>
          </div>
        </div>
      </div>
    </>
  )
}
