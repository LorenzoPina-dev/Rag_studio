import * as React from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft,
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronDown,
  Clock,
  Copy,
  Download,
  Gauge,
  Pause,
  Play,
  RefreshCcw,
  RotateCcw,
  Search,
  Terminal,
  Trash2,
  XCircle,
} from 'lucide-react'
import { toast } from 'sonner'
import { PageHeader } from '@/components/shared/page'
import { Button } from '@/components/ui/button'
import { EmptyState, ErrorState, LoadingState, StatusDot } from '@/components/ui/badge'
import { Switch } from '@/components/ui/controls'
import { Select } from '@/components/ui/select'
import { executionsApi, subscribeExecution } from '@/api/executions.api'
import { pipelinesApi } from '@/api/pipelines.api'
import { bus } from '@/lib/bus'
import { cn, downloadFile, formatCurrency, formatMs, formatNumber } from '@/lib/utils'
import type { Execution, LogEntry, NodeRun } from '@/types'

const levelStyle: Record<LogEntry['level'], string> = {
  INFO: 'text-[#8fa0b8]',
  WARN: 'text-warn',
  ERROR: 'text-danger',
  DONE: 'text-success',
  DEBUG: 'text-[#7c8aa0]',
}

function Metric({ label, children, tone }: { label: string; children: React.ReactNode; tone?: string }) {
  return (
    <div className="min-w-0 px-4 py-3">
      <p className="font-mono text-[8px] uppercase tracking-[0.13em] text-dim">{label}</p>
      <div className={cn('mt-1.5 flex items-baseline gap-1.5 text-[17px] font-semibold leading-none tracking-[-0.02em] text-ink', tone)}>{children}</div>
    </div>
  )
}

export function ExecutionPage() {
  const { runId = 'run_2486' } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [live, setLive] = React.useState<Execution | null>(null)
  const [level, setLevel] = React.useState<'all' | LogEntry['level']>('all')
  const [search, setSearch] = React.useState('')
  const [autoScroll, setAutoScroll] = React.useState(true)
  const [clearedAt, setClearedAt] = React.useState(0)
  const [expanded, setExpanded] = React.useState<string | null>(null)
  const logRef = React.useRef<HTMLDivElement>(null)
  const subscribed = React.useRef<string | null>(null)

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['execution', runId],
    queryFn: () => executionsApi.get(runId),
    refetchInterval: (query) => (query.state.data?.status === 'running' ? 1500 : false),
  })

  const execution = live?.id === runId ? live : data

  React.useEffect(() => {
    setLive(null)
    subscribed.current = null
    setClearedAt(0)
  }, [runId])

  React.useEffect(() => {
    if (!execution || execution.status !== 'running' || subscribed.current === execution.id) return
    subscribed.current = execution.id
    const unsubscribe = subscribeExecution(execution, (event) => {
      setLive((current) => {
        const base = current ?? execution
        if (event.type === 'status' && event.status) return { ...base, status: event.status }
        if (event.type === 'node' && event.node) {
          const exists = base.nodeRuns.some((node) => node.nodeId === event.node!.nodeId)
          return {
            ...base,
            status: 'running',
            nodeRuns: exists
              ? base.nodeRuns.map((node) => (node.nodeId === event.node!.nodeId ? { ...node, ...event.node } : node))
              : [...base.nodeRuns, event.node],
          }
        }
        if (event.type === 'log' && event.log) return { ...base, logs: [...base.logs, event.log] }
        if (event.type === 'done' && event.execution) return { ...event.execution, logs: base.logs }
        if (event.type === 'error') return { ...base, status: 'failed' }
        return base
      })
      if (event.type === 'done') {
        toast.success('Run completed', { description: `${execution.pipelineName} finished successfully.` })
        queryClient.invalidateQueries({ queryKey: ['execution', execution.id] })
      }
    })
    return () => {
      unsubscribe()
      subscribed.current = null
    }
  }, [execution, queryClient])

  const stopMutation = useMutation({
    mutationFn: (id: string) => executionsApi.stop(id),
    onSuccess: () => {
      setLive((current) => (current ? { ...current, status: 'stopped' } : current))
      toast.success('Execution stopped')
    },
    onError: (err: Error) => toast.error('Could not stop execution', { description: err.message }),
  })

  const runAgainMutation = useMutation({
    mutationFn: () => pipelinesApi.run(execution?.pipelineId ?? 'pl_hybrid_rag'),
    onSuccess: (run) => {
      queryClient.setQueryData(['execution', run.id], run)
      setLive(run)
      toast.success(`Run #${run.runNumber.toLocaleString()} started`)
      if (run.id === runId) {
        void refetch()
      } else {
        navigate(`/runs/${run.id}`)
      }
    },
    onError: (err: Error) => toast.error('Could not start run', { description: err.message }),
  })

  const logs = execution?.logs ?? []
  const visibleLogs = logs
    .slice(clearedAt)
    .filter((entry) => (level === 'all' ? true : entry.level === level))
    .filter((entry) => `${entry.message} ${entry.node ?? ''}`.toLowerCase().includes(search.toLowerCase()))

  React.useEffect(() => {
    if (autoScroll && logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [visibleLogs.length, autoScroll])

  if (isLoading) {
    return (
      <>
        <PageHeader eyebrow="Execution" title="Execution monitor" />
        <div className="flex-1 overflow-y-auto"><LoadingState label="Loading run trace…" rows={8} /></div>
      </>
    )
  }

  if (isError || !execution) {
    return (
      <>
        <PageHeader eyebrow="Execution" title="Execution monitor" />
        <div className="flex-1 overflow-y-auto"><ErrorState message={(error as Error)?.message} onRetry={() => void refetch()} /></div>
      </>
    )
  }

  const completed = execution.status === 'completed'
  const failed = execution.status === 'failed'
  const retrieved = execution.nodeRuns.find((node) => node.kind === 'retrieval')?.outputCount ?? 20
  const selected = execution.nodeRuns.find((node) => node.kind === 'reranking')?.outputCount ?? 5
  const maxDuration = Math.max(...execution.nodeRuns.map((node) => node.durationMs), 1)
  const totalNodeDuration = execution.nodeRuns.reduce((sum, node) => sum + node.durationMs, 0)

  const exportTrace = () => {
    downloadFile(`rag-studio-run-${execution.runNumber}.json`, JSON.stringify(execution, null, 2))
    toast.success('Trace exported')
  }

  return (
    <>
      <PageHeader
        eyebrow={`Pipelines / ${execution.pipelineName}`}
        title="Execution monitor"
        breadcrumbs={[{ label: 'Pipelines', to: '/pipelines' }, { label: execution.pipelineName, to: `/pipelines/${execution.pipelineId}` }, { label: `Run #${execution.runNumber.toLocaleString()}` }]}
        description={
          <span className="font-mono text-[10px] text-dim">
            Run #{execution.runNumber.toLocaleString()} <span className="text-[#344158]">·</span> {execution.startedAt} <span className="text-[#344158]">·</span> {execution.environment} <span className="text-[#344158]">·</span> {execution.trigger}
          </span>
        }
        actions={
          <>
            <Button variant="secondary" onClick={exportTrace}><Download className="h-3.5 w-3.5" /> Export trace</Button>
            {execution.status === 'running' ? (
              <Button variant="danger" onClick={() => stopMutation.mutate(execution.id)} disabled={stopMutation.isPending}><Pause className="h-3.5 w-3.5" /> Stop run</Button>
            ) : (
              <Button variant="primary" size="lg" onClick={() => runAgainMutation.mutate()} disabled={runAgainMutation.isPending}>
                <Play className="h-3.5 w-3.5" /> {runAgainMutation.isPending ? 'Starting…' : 'Run again'}
              </Button>
            )}
          </>
        }
      />

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="space-y-4 px-6 py-4">
          <section className="grid grid-cols-2 divide-x divide-line rounded-lg border border-line bg-[#0c141f] sm:grid-cols-3 xl:grid-cols-6">
            <Metric label="Status">
              <span className={cn('flex items-center gap-1.5 text-[15px]', completed ? 'text-success' : failed ? 'text-danger' : 'text-accent')}>
                {completed ? <CheckCircle2 className="h-4 w-4" /> : failed ? <XCircle className="h-4 w-4" /> : <RefreshCcw className="h-4 w-4 animate-spin" />}
                {execution.status === 'completed' ? 'Completed' : execution.status === 'running' ? 'Running' : execution.status === 'stopped' ? 'Stopped' : 'Failed'}
              </span>
            </Metric>
            <Metric label="Total latency">{formatMs(execution.durationMs || totalNodeDuration)}</Metric>
            <Metric label="Tokens">{formatNumber(execution.tokens)}</Metric>
            <Metric label="Est. cost">{formatCurrency(execution.cost)}</Metric>
            <Metric label="Retrieved">
              <span>{retrieved}</span><ArrowRight className="h-3.5 w-3.5 text-dim" /><span>{selected}</span><span className="text-[10px] font-normal text-dim">docs</span>
            </Metric>
            <Metric label="Errors">
              <span className={execution.errors > 0 ? 'text-danger' : 'text-success'}>{execution.errors}</span>
              <span className="text-[10px] font-normal text-dim">unresolved</span>
            </Metric>
          </section>

          <section>
            <div className="mb-2.5 flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-[13.5px] font-semibold tracking-[-0.01em] text-ink">Execution trace</h2>
              <div className="flex items-center gap-2 font-mono text-[8.5px] text-dim">
                <span>{execution.nodeRuns.length} stages</span>
                <span className="text-[#344158]">·</span>
                <span>{execution.stagesCached ? 'Ingestion cached' : 'Fresh ingestion'}</span>
                <span className="text-[#344158]">·</span>
                <span>Trace ID {execution.traceId}</span>
                <button onClick={() => { navigator.clipboard?.writeText(execution.traceId); toast.success('Trace ID copied') }} className="rounded p-0.5 hover:bg-white/5 hover:text-ink" aria-label="Copy trace ID"><Copy className="h-2.5 w-2.5" /></button>
              </div>
            </div>
            <div className="relative flex gap-2 overflow-x-auto rounded-lg border border-line bg-[#0b121c] px-3 py-3">
              {execution.nodeRuns.map((node, index) => {
                const isOpen = expanded === node.nodeId
                return (
                  <React.Fragment key={node.nodeId}>
                    <button
                      onClick={() => setExpanded(isOpen ? null : node.nodeId)}
                      className={cn(
                        'relative min-w-[132px] flex-1 rounded-md border bg-[#0c141f] px-3 py-2.5 text-left transition-colors',
                        isOpen ? 'border-accent/60' : 'border-line-strong/80 hover:border-[#3b4c66]',
                      )}
                    >
                      <div className="flex items-center gap-1.5">
                        {node.status === 'completed' ? <CheckCircle2 className="h-3 w-3 text-success" /> : node.status === 'running' ? <RefreshCcw className="h-3 w-3 animate-spin text-accent" /> : node.status === 'failed' ? <XCircle className="h-3 w-3 text-danger" /> : <Clock className="h-3 w-3 text-dim" />}
                        <span className="truncate text-[10px] text-[#b8c4d6]">{node.name}</span>
                        <ChevronDown className={cn('ml-auto h-2.5 w-2.5 shrink-0 text-dim transition-transform', isOpen && 'rotate-180')} />
                      </div>
                      <p className="mt-2 font-mono text-[16px] font-medium leading-none tracking-[-0.02em]" style={{ color: node.status === 'failed' ? '#F06A6A' : node.accent }}>
                        {node.durationMs ? `${node.durationMs}ms` : node.status === 'running' ? '…' : '—'}
                      </p>
                      <p className="mt-1 font-mono text-[7.5px] uppercase tracking-[0.1em] text-dim">{node.status}</p>
                      {isOpen && (
                        <div className="absolute left-0 right-0 top-[calc(100%+6px)] z-20 w-[240px] rounded-md border border-line-strong bg-[#0f1724] p-3 shadow-pop">
                          <p className="font-mono text-[8px] uppercase tracking-[0.12em] text-dim">Stage detail</p>
                          <div className="mt-2 space-y-1.5 font-mono text-[9px]">
                            <div className="flex justify-between"><span className="text-dim">Kind</span><span className="text-muted">{node.kind}</span></div>
                            <div className="flex justify-between"><span className="text-dim">Outputs</span><span className="text-muted">{formatNumber(node.outputCount)}</span></div>
                            <div className="flex justify-between"><span className="text-dim">Duration</span><span className="text-muted">{formatMs(node.durationMs)}</span></div>
                            <div className="flex justify-between"><span className="text-dim">Share</span><span className="text-muted">{Math.round((node.durationMs / Math.max(totalNodeDuration, 1)) * 100)}%</span></div>
                          </div>
                        </div>
                      )}
                    </button>
                    {index < execution.nodeRuns.length - 1 && <span className="mt-[22px] h-px w-2 shrink-0 bg-[#354864]" />}
                  </React.Fragment>
                )
              })}
            </div>
          </section>

          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_310px]">
            <section className="min-w-0 overflow-hidden rounded-lg border border-line bg-[#0c141f]">
              <div className="flex flex-wrap items-center gap-2 border-b border-line px-3 py-2">
                <div className="flex items-center gap-3">
                  {(['Logs', 'Metrics', 'Errors'] as const).map((label) => (
                    <span key={label} className={cn('border-b px-0.5 pb-1 text-[10.5px]', label === 'Logs' ? 'border-accent text-ink' : 'border-transparent text-dim')}>
                      {label}
                      {label === 'Errors' && <span className="ml-1 font-mono text-[8.5px] text-danger">{execution.errors}</span>}
                      {label === 'Metrics' && <span className="ml-1 font-mono text-[8.5px] text-warn">{execution.warnings}</span>}
                    </span>
                  ))}
                </div>
                <div className="ml-auto flex items-center gap-1.5">
                  <Select
                    value={level}
                    onValueChange={(value) => setLevel(value as typeof level)}
                    options={[
                      { value: 'all', label: 'All levels' },
                      { value: 'INFO', label: 'INFO' },
                      { value: 'WARN', label: 'WARN' },
                      { value: 'ERROR', label: 'ERROR' },
                      { value: 'DONE', label: 'DONE' },
                    ]}
                    className="w-[112px]"
                    aria-label="Filter logs"
                  />
                  <div className="relative">
                    <Search className="pointer-events-none absolute left-2 top-1/2 h-3 w-3 -translate-y-1/2 text-dim" />
                    <input
                      value={search}
                      onChange={(event) => setSearch(event.target.value)}
                      placeholder="Filter…"
                      className="h-7 w-[104px] rounded border border-line-strong bg-[#0a1019] pl-7 pr-2 font-mono text-[9px] text-ink outline-none placeholder:text-dim focus:border-accent/60"
                    />
                  </div>
                  <button onClick={() => setClearedAt(logs.length)} className="flex h-7 items-center gap-1 rounded border border-line-strong px-2 font-mono text-[8.5px] text-dim hover:text-ink" title="Clear visible logs">
                    Clear
                  </button>
                  <button
                    onClick={() => {
                      downloadFile(`run-${execution.runNumber}-logs.txt`, logs.map((entry) => `${entry.timestamp} ${entry.level.padEnd(5)} ${entry.node ? `[${entry.node}] ` : ''}${entry.message}`).join('\n'), 'text/plain')
                      toast.success('Logs downloaded')
                    }}
                    className="flex h-7 w-7 items-center justify-center rounded border border-line-strong text-dim hover:text-ink"
                    aria-label="Download logs"
                  >
                    <Download className="h-3 w-3" />
                  </button>
                </div>
              </div>
              <div ref={logRef} className="h-[236px] overflow-y-auto px-3 py-2 font-mono text-[9.5px] leading-[1.85]">
                {visibleLogs.length === 0 ? (
                  <div className="flex h-full flex-col items-center justify-center gap-2 text-dim">
                    <Terminal className="h-4 w-4" />
                    <span className="text-[9px]">No log lines match this filter.</span>
                  </div>
                ) : (
                  visibleLogs.map((entry) => (
                    <div key={entry.id} className="flex gap-3">
                      <span className="shrink-0 text-[#4c5a70]">{entry.timestamp}</span>
                      <span className={cn('w-[34px] shrink-0 font-medium', levelStyle[entry.level])}>{entry.level}</span>
                      {entry.node && <span className="w-[86px] shrink-0 truncate text-[#6b7d99]">{entry.node}</span>}
                      <span className="min-w-0 text-[#9aa9be]">{entry.message}</span>
                    </div>
                  ))
                )}
              </div>
              <div className="flex flex-wrap items-center justify-between gap-2 border-t border-line px-3 py-2">
                <span className="flex items-center gap-1.5 font-mono text-[8.5px] text-dim"><StatusDot status="success" pulse /> Streaming trace</span>
                <Switch checked={autoScroll} onCheckedChange={setAutoScroll} label={<span className="font-mono text-[8.5px] text-dim">Auto-scroll {autoScroll ? 'enabled' : 'disabled'}</span>} />
              </div>
            </section>

            <aside className="space-y-3">
              <section className="rounded-lg border border-line bg-[#0c141f] p-3.5">
                <div className="flex items-center justify-between">
                  <h3 className="text-[11.5px] font-medium text-ink">Runtime metrics</h3>
                  <Gauge className="h-3.5 w-3.5 text-dim" />
                </div>
                <p className="mt-1 font-mono text-[8px] uppercase tracking-[0.13em] text-dim">Latency breakdown</p>
                <div className="mt-2.5 space-y-2">
                  {execution.nodeRuns.map((node) => (
                    <div key={node.nodeId}>
                      <div className="flex items-center justify-between font-mono text-[8.5px]">
                        <span className="text-[#8a98ad]">{node.name}</span>
                        <span className="text-[#b8c4d6]">{node.durationMs}ms</span>
                      </div>
                      <div className="mt-1 h-[3px] overflow-hidden rounded-full bg-[#1a2433]">
                        <div className="h-full rounded-full" style={{ width: `${Math.max(2, (node.durationMs / maxDuration) * 100)}%`, backgroundColor: node.accent }} />
                      </div>
                    </div>
                  ))}
                </div>
                <div className="mt-3 grid grid-cols-2 gap-2 border-t border-line/60 pt-3">
                  <div className="rounded border border-line/70 bg-[#0b111b] px-2 py-2">
                    <p className="font-mono text-[7.5px] uppercase tracking-[0.1em] text-dim">Peak memory</p>
                    <p className="mt-1 font-mono text-[11px] text-[#c5d0df]">428 MB</p>
                  </div>
                  <div className="rounded border border-line/70 bg-[#0b111b] px-2 py-2">
                    <p className="font-mono text-[7.5px] uppercase tracking-[0.1em] text-dim">Tokens / second</p>
                    <p className="mt-1 font-mono text-[11px] text-[#c5d0df]">932</p>
                  </div>
                </div>
              </section>

              <section className="rounded-lg border border-line bg-[#0b121c] px-3.5 py-3">
                <p className="font-mono text-[8px] uppercase tracking-[0.13em] text-dim">Run fingerprint</p>
                <div className="mt-2 space-y-1.5 font-mono text-[8.5px]">
                  <div className="flex justify-between gap-2"><span className="text-dim">Pipeline version</span><span className="text-muted">v2.4</span></div>
                  <div className="flex justify-between gap-2"><span className="text-dim">Graph hash</span><span className="text-muted">8e4c92a1</span></div>
                  <div className="flex justify-between gap-2"><span className="text-dim">Started</span><span className="text-muted">{execution.startedAt}</span></div>
                  <div className="flex justify-between gap-2"><span className="text-dim">Finished</span><span className="text-muted">{execution.finishedAt ?? '—'}</span></div>
                </div>
              </section>

              <Button variant="secondary" className="w-full" onClick={() => navigate(`/runs/${execution.id}/results`)}>
                Inspect intermediate results <ArrowRight className="h-3.5 w-3.5" />
              </Button>
            </aside>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-2 border-t border-line/60 pt-2 font-mono text-[8.5px] text-dim">
            <span className="flex items-center gap-1.5"><Check className="h-3 w-3 text-success" /> All node outputs captured</span>
            <div className="flex items-center gap-3">
              <Link to={`/pipelines/${execution.pipelineId}`} className="flex items-center gap-1 hover:text-ink"><ArrowLeft className="h-2.5 w-2.5" /> Back to graph</Link>
              <Link to={`/runs/${execution.id}/results`} className="flex items-center gap-1 text-[#7f95cf] hover:text-[#b5c6ff]">Inspect intermediate results <ArrowRight className="h-2.5 w-2.5" /></Link>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
