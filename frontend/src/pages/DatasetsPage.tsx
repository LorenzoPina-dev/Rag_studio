import * as React from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ArrowUpRight,
  CheckCircle2,
  Cloud,
  Database,
  Download,
  FileStack,
  FolderOpen,
  HardDrive,
  Link2,
  MoreHorizontal,
  Plus,
  RefreshCcw,
  Search,
  Server,
  Settings2,
  Trash2,
} from 'lucide-react'
import { toast } from 'sonner'
import { PageHeader } from '@/components/shared/page'
import { KpiCard } from '@/components/shared/sparkline'
import { Button } from '@/components/ui/button'
import { SearchInput, Input, Field } from '@/components/ui/input'
import { EmptyState, ErrorState, LoadingState, ProgressBar, StatusDot } from '@/components/ui/badge'
import { Dialog, DialogBody, DialogContent, DialogFooter, DialogHeader } from '@/components/ui/dialog'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/controls'
import { Select } from '@/components/ui/select'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown'
import { datasetsApi } from '@/api/datasets.api'
import { dataSourcesApi } from '@/api/datasources.api'
import { cn, formatNumber } from '@/lib/utils'
import type { Dataset, DatasetFile, DatasetStatus } from '@/types'

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function fileStats(files: DatasetFile[] = []) {
  const grouped = new Map<string, { count: number; bytes: number }>()
  for (const file of files) {
    const entry = grouped.get(file.fileType) ?? { count: 0, bytes: 0 }
    entry.count += 1
    entry.bytes += file.size
    grouped.set(file.fileType, entry)
  }
  return {
    total: files.length,
    indexed: files.filter((file) => file.indexed).length,
    bytes: files.reduce((sum, file) => sum + file.size, 0),
    types: Array.from(grouped, ([fileType, value]) => ({ fileType, ...value })).sort((a, b) => b.count - a.count),
  }
}

function connectionHint(connector: string): string {
  if (connector === 'S3') return '{ "endpoint": "play.min.io", "accessKey": "…", "secretKey": "…", "bucket": "docs", "prefix": "", "secure": true }'
  if (connector === 'PostgreSQL') return '{ "dsn": "postgresql+psycopg://user:pass@host/db", "query": "SELECT id, title, source, content FROM documents LIMIT 200" }'
  return '{ "headers": { "Authorization": "Bearer …" } }'
}

const statusTone: Record<DatasetStatus, { label: string; dot: 'success' | 'running' | 'warning' | 'danger'; className: string }> = {
  indexed: { label: 'Indexed', dot: 'success', className: 'text-success' },
  ingesting: { label: 'Ingesting', dot: 'running', className: 'text-accent' },
  syncing: { label: 'Syncing', dot: 'warning', className: 'text-warn' },
  error: { label: 'Error', dot: 'danger', className: 'text-danger' },
}

const sourceGlyph: Record<string, React.ElementType> = {
  'Local files': FolderOpen,
  S3: Cloud,
  Notion: FileStack,
  'Google Drive': Cloud,
  'Web crawl': Link2,
  PostgreSQL: Database,
  'REST API': Server,
}

function DatasetStatusCell({ status }: { status: DatasetStatus }) {
  const tone = statusTone[status]
  return (
    <span className={cn('flex items-center gap-1.5 font-mono text-[9px]', tone.className)}>
      <StatusDot status={tone.dot} pulse={tone.dot === 'running'} /> {tone.label}
    </span>
  )
}

function DetailRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[104px_minmax(0,1fr)] items-baseline gap-2 py-[5px]">
      <span className="font-mono text-[8.5px] uppercase tracking-[0.09em] text-dim">{label}</span>
      <span className="min-w-0 break-words font-mono text-[9.5px] text-[#b8c4d6]">{value}</span>
    </div>
  )
}

export function DatasetsPage() {
  const queryClient = useQueryClient()
  const [tab, setTab] = React.useState('datasets')
  const [search, setSearch] = React.useState('')
  const [typeFilter, setTypeFilter] = React.useState('all')
  const [statusFilter, setStatusFilter] = React.useState('all')
  const [page, setPage] = React.useState(1)
  const [selectedId, setSelectedId] = React.useState<string | null>(null)
  const [connectOpen, setConnectOpen] = React.useState(false)
  const [previewOpen, setPreviewOpen] = React.useState(false)
  const [connectorType, setConnectorType] = React.useState('Local files')
  const [datasetName, setDatasetName] = React.useState('')
  const [datasetPath, setDatasetPath] = React.useState('')
  const [datasetConnection, setDatasetConnection] = React.useState('{}')

  const { data, isLoading, isError, error, refetch } = useQuery({ queryKey: ['datasets'], queryFn: datasetsApi.list })

  const syncMutation = useMutation({
    mutationFn: datasetsApi.syncAll,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['datasets'] })
      toast.success('Sources synchronized', { description: 'All pending documents have been queued for indexing.' })
    },
    onError: (err: Error) => toast.error('Sync failed', { description: err.message }),
  })

  const createMutation = useMutation({
    mutationFn: () => {
      let connection: Record<string, unknown> = {}
      try {
        connection = JSON.parse(datasetConnection || '{}') as Record<string, unknown>
      } catch {
        throw new Error('Connection details devono essere JSON valido')
      }
      return datasetsApi.create({
        name: datasetName,
        sourceType: connectorType,
        path: datasetPath,
        connection,
      })
    },
    onSuccess: (dataset) => {
      queryClient.invalidateQueries({ queryKey: ['datasets'] })
      toast.success('Dataset creato', { description: `${dataset.name} è selezionabile nel nodo Document source.` })
      setConnectOpen(false)
      setDatasetName('')
      setDatasetPath('')
      setDatasetConnection('{}')
      setSelectedId(dataset.id)
      setTab('datasets')
    },
    onError: (err: Error) => toast.error('Creazione non riuscita', { description: err.message }),
  })

  const syncOneMutation = useMutation({
    mutationFn: (id: string) => datasetsApi.sync(id),
    onSuccess: (dataset) => {
      queryClient.invalidateQueries({ queryKey: ['datasets'] })
      toast.success('Dataset sincronizzato', { description: `${dataset.documents} documenti da ${dataset.sourceType}.` })
    },
    onError: (err: Error) => toast.error('Sync non riuscita', { description: err.message }),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => datasetsApi.remove(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['datasets'] })
      setSelectedId(null)
      toast.success('Dataset eliminato')
    },
    onError: (err: Error) => toast.error('Eliminazione non riuscita', { description: err.message }),
  })

  const datasets = data?.datasets ?? []
  const healthyDatasets = datasets.filter((dataset) => dataset.health === 'healthy').length
  const sources = data?.sources ?? []
  const jobs = data?.jobs ?? []
  const selected = datasets.find((dataset) => dataset.id === selectedId) ?? datasets[0]
  const globalStats = fileStats(datasets.flatMap((dataset) => dataset.files ?? []))
  const selectedStats = fileStats(selected?.files ?? [])
  const selectedTotal = selected?.documents ?? 0
  const ingestionPercent = selectedTotal > 0
    ? Math.round(((selected?.documentsProcessed ?? selectedTotal) / selectedTotal) * 100)
    : 0

  const filteredDatasets = datasets
    .filter((dataset) => (typeFilter === 'all' ? true : dataset.sourceType === typeFilter))
    .filter((dataset) => (statusFilter === 'all' ? true : dataset.status === statusFilter))
    .filter((dataset) => `${dataset.name} ${dataset.format} ${dataset.sourceType}`.toLowerCase().includes(search.toLowerCase()))
  const pageSize = 5
  const pages = Math.max(1, Math.ceil(filteredDatasets.length / pageSize))
  const paged = filteredDatasets.slice((page - 1) * pageSize, page * pageSize)

  React.useEffect(() => setPage(1), [search, typeFilter, statusFilter])

  const syncMutationAll = () => syncMutation.mutate()

  if (isLoading) {
    return (
      <>
        <PageHeader eyebrow="Data workspace" title="Datasets & data sources" description="Connect, inspect and prepare the knowledge behind your pipelines." />
        <div className="flex-1 overflow-y-auto"><LoadingState label="Loading data sources…" rows={8} /></div>
      </>
    )
  }

  if (isError || !data) {
    return (
      <>
        <PageHeader eyebrow="Data workspace" title="Datasets & data sources" description="Connect, inspect and prepare the knowledge behind your pipelines." />
        <div className="flex-1 overflow-y-auto"><ErrorState message={(error as Error)?.message} onRetry={() => void refetch()} /></div>
      </>
    )
  }

  return (
    <>
      <PageHeader
        eyebrow="Data workspace"
        title="Datasets & data sources"
        description="Connect, inspect and prepare the knowledge behind your pipelines."
        breadcrumbs={[{ label: 'Research lab', to: '/' }, { label: 'Datasets' }]}
        actions={
          <Button variant="primary" size="lg" onClick={() => setConnectOpen(true)}>
            <Plus className="h-3.5 w-3.5" /> New dataset
          </Button>
        }
      />

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="px-6 py-5">
          <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <KpiCard
              label="Connected sources"
              value={data.metrics.connectedSources}
              delta={datasets.length === 0 ? (
                <span className="text-dim">Nessun dato caricato</span>
              ) : (
                <><span className={cn('h-1.5 w-1.5 rounded-full', healthyDatasets === datasets.length ? 'bg-success' : 'bg-warn')} /> {healthyDatasets}/{datasets.length} dataset healthy</>
              )}
              tone={datasets.length > 0 && healthyDatasets === datasets.length ? 'success' : 'warning'}
              spark={data.metrics.sparks.sources}
              sparkColor="#6F8FFF"
            />
            <KpiCard label="Documents" value={formatNumber(data.metrics.documents)} delta={data.metrics.documentsDelta} tone="success" spark={data.metrics.sparks.documents} sparkColor="#7296FF" />
            <KpiCard label="Indexed files" value={formatNumber(globalStats.indexed)} delta={<>{globalStats.total} file found</>} tone="success" />
            <KpiCard label="Files size" value={formatBytes(globalStats.bytes)} delta={<>{globalStats.types.length} file types</>} tone="success" />
          </section>

          <Tabs value={tab} onValueChange={setTab} className="mt-5">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <TabsList>
                <TabsTrigger value="datasets">Datasets <span className="ml-1.5 rounded bg-white/[0.05] px-1 font-mono text-[8.5px] text-dim">{datasets.length}</span></TabsTrigger>
                <TabsTrigger value="sources">Data sources <span className="ml-1.5 rounded bg-white/[0.05] px-1 font-mono text-[8.5px] text-dim">{sources.length}</span></TabsTrigger>
                <TabsTrigger value="jobs">Ingestion jobs <span className="ml-1.5 rounded bg-white/[0.05] px-1 font-mono text-[8.5px] text-dim">{jobs.length}</span></TabsTrigger>
              </TabsList>
              <Button variant="secondary" size="sm" onClick={syncMutationAll} disabled={syncMutation.isPending}>
                <RefreshCcw className={cn('h-3 w-3', syncMutation.isPending && 'animate-spin')} /> {syncMutation.isPending ? 'Syncing…' : 'Sync all'}
              </Button>
            </div>

            <TabsContent value="datasets" className="pt-3">
              <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_300px]">
                <div className="min-w-0">
                  <div className="mb-2.5 flex flex-wrap items-center gap-2">
                    <SearchInput value={search} onChange={setSearch} placeholder="Search datasets…" className="w-[230px]" />
                    <Select
                      value={typeFilter}
                      onValueChange={setTypeFilter}
                      options={[{ value: 'all', label: 'All types' }, ...Array.from(new Set(datasets.map((dataset) => dataset.sourceType))).map((type) => ({ value: type, label: type }))]}
                      className="w-[160px]"
                      aria-label="Filter by source type"
                    />
                    <Select
                      value={statusFilter}
                      onValueChange={setStatusFilter}
                      options={[
                        { value: 'all', label: 'Any status' },
                        { value: 'indexed', label: 'Indexed' },
                        { value: 'ingesting', label: 'Ingesting' },
                        { value: 'syncing', label: 'Syncing' },
                        { value: 'error', label: 'Error' },
                      ]}
                      className="w-[136px]"
                      aria-label="Filter by status"
                    />
                    <span className="ml-auto font-mono text-[8.5px] text-dim">{filteredDatasets.length} datasets</span>
                  </div>

                  {filteredDatasets.length === 0 ? (
                    <div className="rounded-lg border border-line bg-surface">
                      <EmptyState icon={<Search className="h-4 w-4" />} title="No datasets match these filters" description="Try another dataset name or clear the status filter." action={<Button variant="secondary" size="sm" onClick={() => { setSearch(''); setTypeFilter('all'); setStatusFilter('all') }}>Clear filters</Button>} />
                    </div>
                  ) : (
                    <div className="overflow-hidden rounded-lg border border-line bg-[#0c141f]">
                      <table className="w-full border-collapse">
                        <thead>
                          <tr className="border-b border-line">
                            {['Name', 'Documents', 'Files', 'Last sync', 'Status', ''].map((header) => (
                              <th key={header} className={cn('table-head h-8 px-3 text-left first:pl-4 last:pr-4', header === '' && 'sr-only')}>{header || 'Actions'}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {paged.map((dataset) => (
                            <tr
                              key={dataset.id}
                              onClick={() => setSelectedId(dataset.id)}
                              className={cn(
                                'table-row cursor-pointer last:border-0',
                                selected?.id === dataset.id && 'bg-accent/[0.07] hover:bg-accent/[0.09]',
                              )}
                            >
                              <td className="px-3 py-2.5 pl-4">
                                <div className="flex items-center gap-2">
                                  <span className={cn('flex h-5 w-5 items-center justify-center rounded border', selected?.id === dataset.id ? 'border-accent/50 bg-accent/10 text-[#9db1ff]' : 'border-line-strong bg-[#111a28] text-dim')}>
                                    <Database className="h-2.5 w-2.5" />
                                  </span>
                                  <div>
                                    <p className="font-mono text-[10px] text-[#c5d0df]">{dataset.name}</p>
                                    <p className="mt-0.5 font-mono text-[8.5px] text-dim">{dataset.format}</p>
                                  </div>
                                </div>
                              </td>
                              <td className="px-3 py-2.5 font-mono text-[9.5px] text-muted">{formatNumber(dataset.documents)}</td>
                              <td className="px-3 py-2.5 font-mono text-[9.5px] text-muted">{formatNumber(fileStats(dataset.files ?? []).total)}</td>
                              <td className="px-3 py-2.5 font-mono text-[9px] text-dim">{dataset.lastSync}</td>
                              <td className="px-3 py-2.5"><DatasetStatusCell status={dataset.status} /></td>
                              <td className="px-3 py-2.5 pr-4" onClick={(event) => event.stopPropagation()}>
                                <DropdownMenu>
                                  <DropdownMenuTrigger asChild>
                                    <button className="rounded p-1 text-dim hover:bg-white/5 hover:text-ink" aria-label={`Actions for ${dataset.name}`}>
                                      <MoreHorizontal className="h-4 w-4" />
                                    </button>
                                  </DropdownMenuTrigger>
                                  <DropdownMenuContent className="w-48">
                                    <DropdownMenuItem icon={<Search className="h-3.5 w-3.5" />} onSelect={() => { setSelectedId(dataset.id); setPreviewOpen(true) }}>
                                      Preview documents
                                    </DropdownMenuItem>
                                    <DropdownMenuItem icon={<RefreshCcw className="h-3.5 w-3.5" />} onSelect={() => syncOneMutation.mutate(dataset.id)}>
                                      Sync from connector
                                    </DropdownMenuItem>
                                    <DropdownMenuItem icon={<Download className="h-3.5 w-3.5" />} onSelect={() => toast.success('Export queued', { description: `${dataset.name} will be available as JSONL.` })}>
                                      Export metadata
                                    </DropdownMenuItem>
                                    <DropdownMenuSeparator />
                                    <DropdownMenuItem icon={<Trash2 className="h-3.5 w-3.5" />} onSelect={() => deleteMutation.mutate(dataset.id)}>
                                      Delete dataset
                                    </DropdownMenuItem>
                                  </DropdownMenuContent>
                                </DropdownMenu>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      <div className="flex items-center justify-between border-t border-line px-4 py-2.5">
                        <span className="font-mono text-[8.5px] text-dim">Showing {paged.length} of {filteredDatasets.length} datasets</span>
                        <div className="flex items-center gap-1">
                          <button onClick={() => setPage((value) => Math.max(1, value - 1))} disabled={page <= 1} className="flex h-5 w-5 items-center justify-center rounded font-mono text-[9px] text-dim hover:bg-white/5 disabled:opacity-30">‹</button>
                          {Array.from({ length: pages }).map((_, index) => (
                            <button key={index} onClick={() => setPage(index + 1)} className={cn('flex h-5 min-w-5 items-center justify-center rounded px-1 font-mono text-[9px]', page === index + 1 ? 'bg-accent/15 text-[#a6b8ff]' : 'text-dim hover:bg-white/5')}>{index + 1}</button>
                          ))}
                          <button onClick={() => setPage((value) => Math.min(pages, value + 1))} disabled={page >= pages} className="flex h-5 w-5 items-center justify-center rounded font-mono text-[9px] text-dim hover:bg-white/5 disabled:opacity-30">›</button>
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                {selected && (
                  <aside className="rounded-lg border border-line bg-[#0c141f]">
                    <div className="border-b border-line px-4 py-3">
                      <p className="font-mono text-[8px] uppercase tracking-[0.15em] text-dim">Dataset details</p>
                      <h3 className="mt-1.5 font-mono text-[12px] font-medium text-ink">{selected.name}</h3>
                      <div className="mt-1"><DatasetStatusCell status={selected.status} /></div>
                    </div>
                    <div className="px-4 py-2">
                      <DetailRow label="Source" value={selected.sourceType} />
                      <DetailRow label="Path" value={selected.path} />
                      <DetailRow label="File types" value={selectedStats.types.map((type) => type.fileType).join(', ') || selected.format} />
                      <DetailRow label="Files" value={`${selectedStats.total} (${selectedStats.indexed} indicizzabili)`} />
                      <DetailRow label="Size" value={formatBytes(selectedStats.bytes)} />
                      <DetailRow label="Last sync" value={selected.lastSync} />
                      <DetailRow label="Used by" value={`${selected.usedBy} pipelines`} />
                    </div>
                    {selectedStats.types.length > 0 && (
                      <div className="border-t border-line px-4 py-3">
                        <div className="flex items-center justify-between">
                          <p className="font-mono text-[8px] uppercase tracking-[0.15em] text-dim">File types</p>
                          <span className="font-mono text-[8.5px] text-dim">{selectedStats.total} file</span>
                        </div>
                        <div className="mt-2.5 space-y-2">
                          {selectedStats.types.map((type) => (
                            <div key={type.fileType}>
                              <div className="mb-1 flex items-center justify-between font-mono text-[8.5px]">
                                <span className="text-[#b8c4d6]">{type.fileType} <span className="text-dim">×{type.count}</span></span>
                                <span className="text-dim">{formatBytes(type.bytes)}</span>
                              </div>
                              <ProgressBar value={type.count} max={selectedStats.total} height={3} color="#7296FF" />
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    <div className="border-t border-line px-4 py-3">
                      <div className="flex items-center justify-between">
                        <p className="font-mono text-[8px] uppercase tracking-[0.15em] text-dim">Ingestion health</p>
                        <span className="font-mono text-[8.5px] text-success">{ingestionPercent}%</span>
                      </div>
                      <p className="mt-2 font-mono text-[9.5px] text-[#b8c4d6]">{formatNumber(selected.documentsProcessed ?? selected.documents)} / {formatNumber(selected.documents)} documents processed</p>
                      <ProgressBar value={ingestionPercent} color="#35D99B" className="mt-2" height={3} />
                    </div>
                    <div className="flex gap-2 border-t border-line px-4 py-3">
                      <Button variant="secondary" size="sm" className="flex-1" onClick={() => setPreviewOpen(true)}>Preview documents</Button>
                      <Button variant="secondary" size="sm" className="flex-1" disabled={syncOneMutation.isPending} onClick={() => syncOneMutation.mutate(selected.id)}>
                        <RefreshCcw className={cn('h-3 w-3', syncOneMutation.isPending && 'animate-spin')} /> Sync files
                      </Button>
                    </div>
                  </aside>
                )}
              </div>

              <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-line/60 pt-3">
                <span className="font-mono text-[8.5px] text-dim">Supported connectors:</span>
                {data.connectors.map((connector) => (
                  <span key={connector} className="rounded border border-line bg-white/[0.02] px-1.5 py-0.5 font-mono text-[8px] text-[#7f8da2]">{connector}</span>
                ))}
                <button onClick={() => setConnectOpen(true)} className="ml-auto flex items-center gap-1 font-mono text-[8.5px] text-[#7f95cf] hover:text-[#b5c6ff]">
                  Add connector <ArrowUpRight className="h-2.5 w-2.5" />
                </button>
              </div>
            </TabsContent>

            <TabsContent value="sources" className="pt-3">
              <div className="mb-2.5 flex flex-wrap items-center gap-2">
                <span className="font-mono text-[9px] uppercase tracking-[0.12em] text-dim">{sources.length} connected sources</span>
                <Button variant="secondary" size="sm" className="ml-auto" onClick={() => setConnectOpen(true)}><Plus className="h-3 w-3" /> Connect source</Button>
              </div>
              <div className="overflow-hidden rounded-lg border border-line bg-[#0c141f]">
                <table className="w-full border-collapse">
                  <thead>
                    <tr className="border-b border-line">
                      {['Source', 'Connector', 'Documents', 'Datasets', 'Last sync', 'Status', ''].map((header) => (
                        <th key={header} className={cn('table-head h-8 px-3 text-left first:pl-4 last:pr-4', header === '' && 'sr-only')}>{header || 'Actions'}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {sources.map((source) => {
                      const Icon = sourceGlyph[source.type] ?? Database
                      return (
                        <tr key={source.id} className="table-row last:border-0">
                          <td className="px-3 py-3 pl-4">
                            <div className="flex items-center gap-2.5">
                              <span className="flex h-6 w-6 items-center justify-center rounded border border-line-strong bg-[#111a28] text-[#8ea6db]"><Icon className="h-3 w-3" /></span>
                              <div>
                                <p className="text-[11px] text-[#c5d0df]">{source.name}</p>
                                <p className="mt-0.5 font-mono text-[8.5px] text-dim">{source.config}</p>
                              </div>
                            </div>
                          </td>
                          <td className="px-3 py-3 font-mono text-[9px] text-muted">{source.type}</td>
                          <td className="px-3 py-3 font-mono text-[9.5px] text-muted">{formatNumber(source.documents)}</td>
                          <td className="px-3 py-3 font-mono text-[9.5px] text-muted">{source.datasets}</td>
                          <td className="px-3 py-3 font-mono text-[9px] text-dim">{source.lastSync}</td>
                          <td className="px-3 py-3">
                            <span className={cn('flex items-center gap-1.5 font-mono text-[9px]', source.status === 'connected' ? 'text-success' : source.status === 'syncing' ? 'text-accent' : 'text-danger')}>
                              <StatusDot status={source.status === 'connected' ? 'success' : source.status === 'syncing' ? 'running' : 'danger'} pulse={source.status === 'syncing'} />
                              {source.status === 'connected' ? 'Connected' : source.status === 'syncing' ? 'Syncing' : 'Error'}
                            </span>
                          </td>
                          <td className="px-3 py-3 pr-4 text-right">
                            <button
                              onClick={() => { dataSourcesApi.sync(source.id).then(() => { queryClient.invalidateQueries({ queryKey: ['datasets'] }); toast.success(`${source.name} sync started`) }).catch((err: Error) => toast.error(err.message)) }}
                              className="inline-flex items-center gap-1 font-mono text-[8.5px] text-[#7f95cf] hover:text-[#b5c6ff]"
                            >
                              <RefreshCcw className="h-2.5 w-2.5" /> Sync
                            </button>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
              <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-4">
                {(Object.keys(sourceGlyph) as Array<keyof typeof sourceGlyph>).slice(0, 4).map((type) => {
                  const Icon = sourceGlyph[type]
                  return (
                    <button key={type} onClick={() => { setConnectorType(type); setConnectOpen(true) }} className="flex items-center gap-2.5 rounded-lg border border-dashed border-line-strong bg-[#0b121c] px-3 py-2.5 text-left transition-colors hover:border-accent/40 hover:bg-[#0e1724]">
                      <span className="flex h-7 w-7 items-center justify-center rounded border border-line bg-[#111a28] text-[#8ea6db]"><Icon className="h-3.5 w-3.5" /></span>
                      <div>
                        <p className="text-[10.5px] text-muted">{type}</p>
                        <p className="font-mono text-[8px] text-dim">Add connector</p>
                      </div>
                      <Plus className="ml-auto h-3 w-3 text-dim" />
                    </button>
                  )
                })}
              </div>
            </TabsContent>

            <TabsContent value="jobs" className="pt-3">
              <div className="mb-2.5 flex items-center justify-between">
                <span className="font-mono text-[9px] uppercase tracking-[0.12em] text-dim">Ingestion queue</span>
                <Button variant="secondary" size="sm" onClick={syncMutationAll} disabled={syncMutation.isPending}><RefreshCcw className={cn('h-3 w-3', syncMutation.isPending && 'animate-spin')} /> Sync all</Button>
              </div>
              <div className="overflow-hidden rounded-lg border border-line bg-[#0c141f]">
                {jobs.map((job, index) => (
                  <div key={job.id} className={cn('flex flex-wrap items-center gap-4 px-4 py-3', index > 0 && 'border-t border-line/60')}>
                    <span className={cn('flex h-6 w-6 shrink-0 items-center justify-center rounded border', job.status === 'running' ? 'border-accent/30 bg-accent/10 text-[#9db1ff]' : job.status === 'completed' ? 'border-success/20 bg-success/[0.07] text-success' : 'border-danger/25 bg-danger/[0.07] text-danger')}>
                      {job.status === 'running' ? <RefreshCcw className="h-3 w-3 animate-spin" /> : job.status === 'completed' ? <CheckCircle2 className="h-3 w-3" /> : <Search className="h-3 w-3" />}
                    </span>
                    <div className="min-w-[150px] flex-1">
                      <p className="font-mono text-[10px] text-[#c5d0df]">{job.datasetName}</p>
                      <p className="mt-0.5 font-mono text-[8.5px] text-dim">{formatNumber(job.documents)} documents · {job.errors} errors · {job.duration}</p>
                    </div>
                    <div className="w-[180px]">
                      <div className="flex justify-between font-mono text-[8.5px] text-dim"><span>{job.status === 'running' ? 'Indexing' : job.status}</span><span>{job.progress}%</span></div>
                      <ProgressBar value={job.progress} color={job.status === 'failed' ? '#F06A6A' : job.status === 'completed' ? '#35D99B' : '#5277EC'} className="mt-1.5" height={3} />
                    </div>
                    <span className="w-[80px] text-right font-mono text-[8.5px] text-dim">{job.startedAt}</span>
                  </div>
                ))}
              </div>
            </TabsContent>
          </Tabs>
        </div>
      </div>

      <Dialog open={connectOpen} onOpenChange={setConnectOpen}>
        <DialogContent size="lg">
          <DialogHeader eyebrow="Data workspace" title="Crea un dataset" description="Scegli il connettore e indica dove sono i file. Dopo la creazione premi Sync per elencarli: il dataset sarà selezionabile nel nodo Document source." />
          <DialogBody className="space-y-4">
            <div>
              <p className="mb-2 text-[11.5px] font-medium text-muted">Connector</p>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                {data.connectors.map((connector) => {
                  const Icon = sourceGlyph[connector] ?? Database
                  return (
                    <button
                      key={connector}
                      onClick={() => setConnectorType(connector)}
                      className={cn(
                        'flex items-center gap-2 rounded-md border px-2.5 py-2 text-left text-[10.5px] transition-colors',
                        connectorType === connector ? 'border-accent/60 bg-accent/[0.08] text-ink' : 'border-line-strong bg-[#0a1019] text-muted hover:border-[#3b4a61]',
                      )}
                    >
                      <Icon className="h-3.5 w-3.5 text-[#8ea6db]" /> {connector}
                    </button>
                  )
                })}
              </div>
            </div>
            <Field label="Nome dataset" hint="Nome usato anche nel selettore del nodo Document source.">
              <Input value={datasetName} onChange={(event) => setDatasetName(event.target.value)} placeholder={`e.g. ${connectorType} corpus`} autoFocus />
            </Field>
            <Field label={connectorType === 'S3' ? 'Bucket URI' : connectorType === 'PostgreSQL' ? 'Connection string' : connectorType === 'Local files' ? 'Cartella o file locale' : 'Endpoint URL'} hint="Sposta i file in questa cartella (o nel bucket/endpoint) prima di sincronizzare. Sync elenca solo i file: il testo di PDF, txt, md, json, jsonl e csv viene estratto quando esegui la pipeline.">
              <Input value={datasetPath} onChange={(event) => setDatasetPath(event.target.value)} placeholder={connectorType === 'S3' ? 's3://bucket/prefix/' : connectorType === 'PostgreSQL' ? 'postgresql+psycopg://user@host/db' : connectorType === 'REST API' ? 'https://api.example.com/docs' : '/data/corpus/'} />
            </Field>
            <Field label="Dettagli connessione (JSON)" hint={connectionHint(connectorType)}>
              <textarea
                value={datasetConnection}
                onChange={(event) => setDatasetConnection(event.target.value)}
                rows={2}
                className="w-full rounded-md border border-[#233044] bg-[#0a1019] px-2.5 py-2 font-mono text-[10px] text-ink focus:border-accent/60 focus:outline-none"
              />
            </Field>
          </DialogBody>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setConnectOpen(false)}>Cancel</Button>
            <Button variant="primary" disabled={!datasetName.trim() || createMutation.isPending} onClick={() => createMutation.mutate()}>
              {createMutation.isPending ? 'Creazione…' : 'Crea dataset'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={previewOpen} onOpenChange={setPreviewOpen}>
        <DialogContent size="xl">
          <DialogHeader eyebrow={selected?.sourceType} title={selected?.name ?? 'Dataset preview'} description={`${formatNumber(selected?.documents ?? 0)} documenti usati dalla pipeline · ${selected?.sourceType}`} />
          <DialogBody className="space-y-3">
            <div className={cn('grid gap-3', (selected?.items ?? []).length > 0 ? 'md:grid-cols-[220px_minmax(0,1fr)]' : 'md:grid-cols-1')}>
              <div className="space-y-2">
                <div className="rounded-md border border-line bg-[#0b111b] p-3">
                  <p className="font-mono text-[8px] uppercase tracking-[0.12em] text-dim">File e Sync</p>
                  <div className="mt-2 space-y-2">
                    <div><p className="font-mono text-[8px] text-dim">File</p><p className="mt-0.5 font-mono text-[9.5px] text-[#b8c4d6]">{selectedStats.total} · {selectedStats.indexed} indicizzabili</p></div>
                    <div><p className="font-mono text-[8px] text-dim">Dimensione</p><p className="mt-0.5 font-mono text-[9.5px] text-[#b8c4d6]">{formatBytes(selectedStats.bytes)}</p></div>
                    <div><p className="font-mono text-[8px] text-dim">Ultimo Sync</p><p className="mt-0.5 font-mono text-[9.5px] text-[#b8c4d6]">{selected?.lastSync}</p></div>
                    <div><p className="font-mono text-[8px] text-dim">Path</p><p className="mt-0.5 break-all font-mono text-[9px] text-[#b8c4d6]">{selected?.path || '—'}</p></div>
                    <div><p className="font-mono text-[8px] text-dim">ID dataset</p><p className="mt-0.5 break-all font-mono text-[9px] text-[#b8c4d6]">{selected?.id}</p></div>
                  </div>
                </div>
                <Button variant="secondary" size="sm" className="w-full" disabled={!selected || syncOneMutation.isPending} onClick={() => selected && syncOneMutation.mutate(selected.id)}>
                  <RefreshCcw className={cn('h-3 w-3', syncOneMutation.isPending && 'animate-spin')} /> Sync dal connettore
                </Button>
              </div>
              {(selected?.items ?? []).length > 0 && (
                <div className="overflow-hidden rounded-md border border-line">
                  <div className="flex items-center justify-between border-b border-line bg-[#0b111b] px-3 py-2">
                    <span className="font-mono text-[8.5px] uppercase tracking-[0.12em] text-dim">Documenti memorizzati</span>
                    <span className="font-mono text-[8.5px] text-dim">{selected?.items?.length ?? 0} documents</span>
                  </div>
                  <div className="max-h-[260px] overflow-y-auto">
                    {(selected?.items ?? []).map((item, index) => (
                      <div key={`${item.id}-${index}`} className={cn('px-3 py-2.5', index > 0 && 'border-t border-line/60')}>
                        <div className="flex items-center justify-between gap-2">
                          <p className="truncate font-mono text-[9.5px] text-[#c5d0df]">{item.title}</p>
                          <span className="shrink-0 rounded border border-accent/30 bg-accent/[0.08] px-1 py-0.5 font-mono text-[8px] text-[#8fa6ff]">{item.fileType ?? 'text'}</span>
                        </div>
                        <p className="mt-0.5 truncate font-mono text-[8px] text-dim">{item.source}</p>
                        <p className="mt-1 line-clamp-2 font-mono text-[8.5px] leading-relaxed text-[#7f8da2]">{item.content}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
            <div className="overflow-hidden rounded-md border border-line">
              <div className="flex items-center justify-between border-b border-line bg-[#0b111b] px-3 py-2">
                <span className="font-mono text-[8.5px] uppercase tracking-[0.12em] text-dim">File trovati dal connettore</span>
                <span className="font-mono text-[8.5px] text-dim">
                  {selected?.files?.length ?? 0} file · {(selected?.files ?? []).filter((file) => file.indexed).length} indicizzabili
                </span>
              </div>
              {(selected?.files ?? []).length === 0 ? (
                <div className="px-3 py-4 text-center font-mono text-[9.5px] text-dim">
                  Nessun inventario: clicca <span className="text-ink">Sync dal connettore</span> per elencare i file.
                </div>
              ) : (
                <div className="max-h-[180px] overflow-y-auto">
                  {(selected?.files ?? []).map((file) => (
                    <div key={file.id} className="flex items-center gap-2 border-b border-line/50 px-3 py-1.5 last:border-0">
                      <span className="w-10 shrink-0 rounded border border-line bg-white/[0.03] px-1 py-0.5 text-center font-mono text-[8px] text-[#8fa6ff]">{file.fileType}</span>
                      <span className="min-w-0 flex-1 truncate font-mono text-[9px] text-[#c5d0df]" title={file.path}>{file.name}</span>
                      <span className="shrink-0 font-mono text-[8px] text-dim">{formatBytes(file.size)}</span>
                      <span className={cn('shrink-0 font-mono text-[8px]', file.indexed ? 'text-success' : 'text-[#d3976a]')}>
                        {file.indexed ? 'indexed' : 'skip'}
                      </span>
                    </div>
                  ))}
                </div>
              )}
              <p className="border-t border-line bg-[#0b111b] px-3 py-2 font-mono text-[8px] leading-relaxed text-dim">
                Per aggiungere documenti sposta i file nella cartella del connettore e premi <span className="text-ink">Sync</span>: la scansione elenca solo i file, il testo viene estratto dalla pipeline. Nel nodo Document source puoi filtrare per File types (pdf, text, txt, md, json, csv…) o per nome; i file con <span className="text-[#d3976a]">skip</span> non hanno testo estraibile.
              </p>
            </div>
          </DialogBody>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setPreviewOpen(false)}>Close</Button>
            <Button variant="primary" disabled={!selected || syncOneMutation.isPending} onClick={() => selected && syncOneMutation.mutate(selected.id)}>Sync files</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
