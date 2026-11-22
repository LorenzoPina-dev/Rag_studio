import * as React from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowUpRight, FileText, RefreshCw, Search } from 'lucide-react'
import { executionsApi } from '@/api/executions.api'
import { Pagination } from '@/components/shared/page'
import { Badge, EmptyState, ErrorState, LoadingState, StatusDot } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogBody, DialogContent, DialogFooter, DialogHeader } from '@/components/ui/dialog'
import { SearchInput } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { cn, formatMs, formatNumber } from '@/lib/utils'
import type { Execution, ExecutionResult } from '@/types'

const PAGE_SIZE = 8

type StatusFilter = 'all' | Execution['status']

export function runStatusTone(status: Execution['status']): 'success' | 'danger' | 'running' | 'warning' | 'idle' {
  switch (status) {
    case 'completed': return 'success'
    case 'failed': return 'danger'
    case 'running': return 'running'
    case 'queued': return 'warning'
    case 'stopped': return 'idle'
  }
}

function runBadgeTone(status: Execution['status']) {
  const tone = runStatusTone(status)
  if (tone === 'idle') return 'neutral'
  if (tone === 'running') return 'accent'
  return tone
}

export function filterRuns(runs: Execution[], search: string, status: StatusFilter): Execution[] {
  const term = search.trim().toLowerCase()
  return runs.filter((run) => {
    if (status !== 'all' && run.status !== status) return false
    if (!term) return true
    return [
      run.id, run.pipelineId, run.pipelineName, run.trigger, run.environment, `#${run.runNumber}`,
    ].some((value) => value.toLowerCase().includes(term))
  })
}

function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-md border border-line bg-[#0a111a] px-3 py-2">
      <p className="font-mono text-[8.5px] uppercase tracking-[0.12em] text-dim">{label}</p>
      <p className="mt-1 text-[12px] text-ink">{value}</p>
    </div>
  )
}

export function RunsTab() {
  const navigate = useNavigate()
  const [search, setSearch] = React.useState('')
  const [status, setStatus] = React.useState<StatusFilter>('all')
  const [page, setPage] = React.useState(1)
  const [preview, setPreview] = React.useState<Execution | null>(null)
  const [result, setResult] = React.useState<ExecutionResult | null>(null)
  const [resultError, setResultError] = React.useState<string | null>(null)
  const [resultLoading, setResultLoading] = React.useState(false)

  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ['executions'],
    queryFn: executionsApi.list,
    refetchInterval: 8_000,
  })

  const runs = React.useMemo(() => [...(data ?? [])].reverse(), [data])
  const filtered = React.useMemo(() => filterRuns(runs, search, status), [runs, search, status])
  const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const paged = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)
  const runningCount = runs.filter((run) => run.status === 'running' || run.status === 'queued').length

  const openPreview = async (run: Execution) => {
    setPreview(run)
    setResult(null)
    setResultError(null)
    setResultLoading(true)
    try {
      setResult(await executionsApi.results(run.id))
    } catch (err) {
      setResultError((err as Error).message)
    } finally {
      setResultLoading(false)
    }
  }

  return (
    <section aria-label="Runs" className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-[15px] font-semibold tracking-[-0.015em] text-ink">Run ed esecuzioni</h2>
          <p className="mt-0.5 text-[11px] text-dim">
            {runs.length} run totali{runningCount > 0 ? ` · ${runningCount} in corso` : ''} · aggiornamento automatico ogni 8s
          </p>
        </div>
        <Button variant="secondary" size="sm" onClick={() => void refetch()} disabled={isFetching}>
          <RefreshCw className={cn('h-3.5 w-3.5', isFetching && 'animate-spin')} /> Aggiorna
        </Button>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <SearchInput value={search} onChange={(value) => { setSearch(value); setPage(1) }} placeholder="Cerca run o pipeline…" className="w-[250px]" />
        <Select
          value={status}
          onValueChange={(value) => { setStatus(value as StatusFilter); setPage(1) }}
          options={[
            { value: 'all', label: 'Tutti gli stati' },
            { value: 'completed', label: 'Completati' },
            { value: 'running', label: 'In corso' },
            { value: 'queued', label: 'In coda' },
            { value: 'failed', label: 'Falliti' },
            { value: 'stopped', label: 'Fermati' },
          ]}
          className="w-[150px]"
          aria-label="Filtra per stato"
        />
        <span className="ml-auto font-mono text-[9px] text-dim">{filtered.length} risultati</span>
      </div>

      {isLoading ? (
        <div className="rounded-lg border border-line bg-[#0c141f]"><LoadingState label="Caricamento run…" rows={5} /></div>
      ) : isError ? (
        <div className="rounded-lg border border-line bg-[#0c141f]"><ErrorState message={(error as Error)?.message} onRetry={() => void refetch()} /></div>
      ) : filtered.length === 0 ? (
        <div className="rounded-lg border border-line bg-surface">
          <EmptyState
            icon={<Search className="h-4 w-4" />}
            title="Nessun run trovato"
            description="Prova un altro termine o stato, oppure avvia una pipeline."
            action={<Button variant="secondary" size="sm" onClick={() => { setSearch(''); setStatus('all') }}>Azzera filtri</Button>}
          />
        </div>
      ) : (
        <>
          <div className="overflow-hidden rounded-lg border border-line bg-[#0c141f]">
            <table className="w-full border-collapse">
              <thead>
                <tr className="border-b border-line">
                  {['Run', 'Pipeline', 'Stato', 'Avvio', 'Durata', 'Token', ''].map((header) => (
                    <th key={header} className={cn('table-head h-8 px-3 text-left text-[8.5px] first:pl-4 last:pr-4', header === '' && 'sr-only')}>
                      {header || 'Azioni'}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {paged.map((run) => (
                  <tr key={run.id} className="table-row cursor-pointer last:border-0" onClick={() => void openPreview(run)}>
                    <td className="px-3 py-2.5 pl-4">
                      <span className="font-mono text-[10.5px] text-[#c5d0df]">#{run.runNumber}</span>
                      <span className="ml-2 font-mono text-[8.5px] text-dim">{run.id}</span>
                    </td>
                    <td className="px-3 py-2.5">
                      <span className="text-[11px] text-[#c5d0df]">{run.pipelineName}</span>
                      <span className="ml-2 font-mono text-[8.5px] text-dim">{run.environment}</span>
                    </td>
                    <td className="px-3 py-2.5">
                      <Badge tone={runBadgeTone(run.status)} dot>{run.status}</Badge>
                    </td>
                    <td className="px-3 py-2.5 font-mono text-[9.5px] text-dim">{run.startedAt}</td>
                    <td className="px-3 py-2.5 font-mono text-[9.5px] text-dim">{formatMs(run.durationMs)}</td>
                    <td className="px-3 py-2.5 font-mono text-[9.5px] text-dim">{formatNumber(run.tokens)}</td>
                    <td className="px-3 py-2.5 pr-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={(event) => { event.stopPropagation(); navigate(`/runs/${run.id}/results`) }}
                          className="flex items-center gap-1 font-mono text-[8.5px] text-[#7f95cf] hover:text-[#b5c6ff]"
                        >
                          Risultati <ArrowUpRight className="h-2.5 w-2.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="rounded-b-lg border-x border-b border-line bg-[#0b111b]">
            <Pagination page={Math.min(page, pages)} pages={pages} onChange={setPage} total={filtered.length} pageSize={PAGE_SIZE} />
          </div>
        </>
      )}

      <Dialog open={Boolean(preview)} onOpenChange={(open) => { if (!open) setPreview(null) }}>
        <DialogContent size="lg">
          <DialogHeader
            eyebrow={`Run #${preview?.runNumber ?? ''}`}
            title={preview?.pipelineName ?? 'Run'}
            description={`${preview?.id ?? ''} · ${preview?.environment ?? ''} · ${preview?.trigger ?? ''}`}
          />
          <DialogBody>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Stat label="Stato" value={preview ? <span className="flex items-center gap-1.5"><StatusDot status={runStatusTone(preview.status)} /> {preview.status}</span> : '—'} />
              <Stat label="Durata" value={preview ? formatMs(preview.durationMs) : '—'} />
              <Stat label="Token" value={preview ? formatNumber(preview.tokens) : '—'} />
              <Stat label="Nodi" value={preview?.nodeRuns.length ?? '—'} />
            </div>
            <div className="mt-4">
              <p className="mb-1.5 flex items-center gap-1.5 font-mono text-[9px] uppercase tracking-[0.12em] text-dim">
                <FileText className="h-3 w-3" /> Risposta generata
              </p>
              <pre className="max-h-48 overflow-y-auto whitespace-pre-wrap rounded-md border border-line bg-[#0a111a] p-3 font-sans text-[11.5px] leading-relaxed text-[#c5d0df]">
                {resultLoading ? 'Caricamento risultati…' : resultError ? `Risultati non disponibili: ${resultError}` : result?.generatedAnswer || 'Nessun risultato disponibile per questo run.'}
              </pre>
            </div>
            {result && (
              <div className="mt-3 grid gap-3 sm:grid-cols-3">
                <Stat label="Documenti" value={formatNumber(result.retrievedCount)} />
                <Stat label="Chunk selezionati" value={formatNumber(result.selectedCount)} />
                <Stat label="Citazioni" value={formatNumber(result.answerMeta?.citations)} />
              </div>
            )}
            {result?.query && <p className="mt-3 text-[11px] text-muted"><span className="text-dim">Query:</span> {result.query}</p>}
          </DialogBody>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setPreview(null)}>Chiudi</Button>
            <Button variant="secondary" onClick={() => preview && navigate(`/runs/${preview.id}`)}>Dettaglio</Button>
            <Button variant="primary" onClick={() => preview && navigate(`/runs/${preview.id}/results`)}>Risultati completi</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  )
}
