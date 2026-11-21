import * as React from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ArrowUpRight,
  CheckCircle2,
  Copy,
  Download,
  MoreHorizontal,
  Play,
  Plus,
  Search,
  Trash2,
  Workflow,
  XCircle,
} from 'lucide-react'
import { toast } from 'sonner'
import { PageHeader, Pagination } from '@/components/shared/page'
import { Button } from '@/components/ui/button'
import { SearchInput } from '@/components/ui/input'
import { EmptyState, ErrorState, LoadingState, StatusDot } from '@/components/ui/badge'
import { Dialog, DialogBody, DialogContent, DialogFooter, DialogHeader } from '@/components/ui/dialog'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown'
import { Select } from '@/components/ui/select'
import { pipelinesApi } from '@/api/pipelines.api'
import { useAppStore } from '@/store/useAppStore'
import { cn } from '@/lib/utils'
import type { PipelineSummary } from '@/types'

type SortKey = 'updated' | 'name' | 'nodes'
type StatusFilter = 'all' | 'valid' | 'draft' | 'running' | 'failed'

function statusMeta(status: PipelineSummary['status']) {
  if (status === 'running') return { tone: 'text-accent', dot: 'running' as const, label: 'Running' }
  if (status === 'failed') return { tone: 'text-danger', dot: 'danger' as const, label: 'Failed' }
  if (status === 'draft') return { tone: 'text-warn', dot: 'warning' as const, label: 'Draft' }
  return { tone: 'text-success', dot: 'success' as const, label: 'Valid' }
}

export function PipelinesPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const setCreatePipelineOpen = useAppStore((s) => s.setCreatePipelineOpen)
  const [search, setSearch] = React.useState('')
  const [environment, setEnvironment] = React.useState('all')
  const [status, setStatus] = React.useState<StatusFilter>('all')
  const [sort, setSort] = React.useState<SortKey>('updated')
  const [page, setPage] = React.useState(1)
  const [deleteTarget, setDeleteTarget] = React.useState<PipelineSummary | null>(null)
  const [runningId, setRunningId] = React.useState<string | null>(null)

  const { data, isLoading, isError, error, refetch } = useQuery({ queryKey: ['pipelines'], queryFn: pipelinesApi.list })

  const runMutation = useMutation({
    mutationFn: (pipeline: PipelineSummary) => pipelinesApi.run(pipeline.id),
    onMutate: (pipeline) => setRunningId(pipeline.id),
    onSuccess: (run) => {
      queryClient.invalidateQueries({ queryKey: ['pipelines'] })
      toast.success(`Run #${run.runNumber.toLocaleString()} started`, { description: 'Streaming execution progress.' })
      navigate(`/runs/${run.id}`)
    },
    onError: (err: Error) => toast.error('Could not start run', { description: err.message }),
    onSettled: () => setRunningId(null),
  })

  const duplicateMutation = useMutation({
    mutationFn: (id: string) => pipelinesApi.duplicate(id),
    onSuccess: (pipeline) => {
      queryClient.invalidateQueries({ queryKey: ['pipelines'] })
      toast.success('Pipeline duplicated', { description: `${pipeline.name} created as a draft.` })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => pipelinesApi.remove(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pipelines'] })
      toast.success('Pipeline deleted')
      setDeleteTarget(null)
    },
    onError: (err: Error) => toast.error('Delete failed', { description: err.message }),
  })

  const all = data ?? []
  const filtered = all
    .filter((pipeline) => (environment === 'all' ? true : pipeline.environment === environment))
    .filter((pipeline) => (status === 'all' ? true : pipeline.status === status))
    .filter((pipeline) => `${pipeline.name} ${pipeline.projectName}`.toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => {
      if (sort === 'name') return a.name.localeCompare(b.name)
      if (sort === 'nodes') return b.nodeCount - a.nodeCount
      return new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
    })

  const pageSize = 8
  const pages = Math.max(1, Math.ceil(filtered.length / pageSize))
  const paged = filtered.slice((page - 1) * pageSize, page * pageSize)
  const production = all.filter((pipeline) => pipeline.environment === 'Production').length
  const passing = all.filter((pipeline) => pipeline.lastRunStatus === 'passed').length

  React.useEffect(() => {
    setPage(1)
  }, [search, environment, status, sort])

  const action = (pipeline: PipelineSummary) => (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          onClick={(event) => event.stopPropagation()}
          className="rounded p-1 text-dim transition-colors hover:bg-white/[0.06] hover:text-ink"
          aria-label={`Actions for ${pipeline.name}`}
        >
          <MoreHorizontal className="h-4 w-4" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-48" align="end">
        <DropdownMenuItem icon={<ArrowUpRight className="h-3.5 w-3.5" />} onSelect={() => navigate(`/pipelines/${pipeline.id}`)}>
          Open editor
        </DropdownMenuItem>
        <DropdownMenuItem icon={<Play className="h-3.5 w-3.5" />} disabled={runningId === pipeline.id} onSelect={() => runMutation.mutate(pipeline)}>
          {runningId === pipeline.id ? 'Starting…' : 'Run pipeline'}
        </DropdownMenuItem>
        <DropdownMenuItem icon={<Workflow className="h-3.5 w-3.5" />} onSelect={() => navigate(`/runs/run_2486`)}>
          Inspect last run
        </DropdownMenuItem>
        <DropdownMenuItem icon={<Download className="h-3.5 w-3.5" />} onSelect={() => void pipelinesApi.export(pipeline.id).then(() => toast.success('Pipeline exported'))}>
          Export JSON
        </DropdownMenuItem>
        <DropdownMenuItem icon={<Copy className="h-3.5 w-3.5" />} onSelect={() => duplicateMutation.mutate(pipeline.id)}>
          Duplicate
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem danger icon={<Trash2 className="h-3.5 w-3.5" />} onSelect={() => setDeleteTarget(pipeline)}>
          Delete pipeline
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )

  return (
    <>
      <PageHeader
        eyebrow="Workspace"
        title="Pipelines"
        description="Build, version and run retrieval-augmented generation graphs."
        breadcrumbs={[{ label: 'Research lab', to: '/' }, { label: 'Pipelines' }]}
        actions={
          <>
            <Button variant="secondary" onClick={() => navigate('/runs/run_2486')}>
              <Play className="h-3.5 w-3.5" /> Execution monitor
            </Button>
            <Button variant="primary" size="lg" onClick={() => setCreatePipelineOpen(true)}>
              <Plus className="h-3.5 w-3.5" /> New pipeline
            </Button>
          </>
        }
      />

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="space-y-4 px-6 py-5">
          <div className="flex flex-wrap items-center gap-x-5 gap-y-2 rounded-lg border border-line bg-[#0c141f] px-4 py-2.5 font-mono text-[9.5px] text-dim">
            <span className="text-muted">{all.length} pipelines</span>
            <span className="text-[#344158]">·</span>
            <span>{production} in production</span>
            <span className="text-[#344158]">·</span>
            <span className="flex items-center gap-1.5"><StatusDot status="success" /> {passing} passing</span>
            <span className="ml-auto flex items-center gap-1.5 text-[#7f95cf]">
              <CheckCircle2 className="h-3 w-3" /> Graph validation enabled
            </span>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <SearchInput value={search} onChange={setSearch} placeholder="Search pipelines…" className="w-[250px]" />
            <Select
              value={environment}
              onValueChange={setEnvironment}
              options={[
                { value: 'all', label: 'All environments' },
                { value: 'Development', label: 'Development' },
                { value: 'Staging', label: 'Staging' },
                { value: 'Production', label: 'Production' },
              ]}
              className="w-[165px]"
              aria-label="Filter by environment"
            />
            <Select
              value={status}
              onValueChange={(value) => setStatus(value as StatusFilter)}
              options={[
                { value: 'all', label: 'All statuses' },
                { value: 'valid', label: 'Valid' },
                { value: 'draft', label: 'Draft' },
                { value: 'running', label: 'Running' },
                { value: 'failed', label: 'Failed' },
              ]}
              className="w-[145px]"
              aria-label="Filter by status"
            />
            <Select
              value={sort}
              onValueChange={(value) => setSort(value as SortKey)}
              options={[
                { value: 'updated', label: 'Last updated' },
                { value: 'name', label: 'Name' },
                { value: 'nodes', label: 'Node count' },
              ]}
              className="w-[145px]"
              aria-label="Sort pipelines"
            />
            <span className="ml-auto font-mono text-[9px] text-dim">{filtered.length} matching</span>
          </div>

          {isLoading && <LoadingState label="Loading pipelines…" rows={6} />}
          {isError && <ErrorState message={(error as Error)?.message} onRetry={() => void refetch()} />}

          {!isLoading && !isError && filtered.length === 0 && (
            <div className="rounded-lg border border-line bg-surface">
              <EmptyState
                icon={search ? <Search className="h-4 w-4" /> : <Workflow className="h-4 w-4" />}
                title={search ? 'No pipelines match your search' : 'No pipelines yet'}
                description={search ? 'Try another name or adjust the filters.' : 'Create your first retrieval pipeline and start with a tested template.'}
                action={
                  search ? (
                    <Button variant="secondary" size="sm" onClick={() => { setSearch(''); setEnvironment('all'); setStatus('all') }}>
                      Clear filters
                    </Button>
                  ) : (
                    <Button variant="primary" onClick={() => setCreatePipelineOpen(true)}>
                      <Plus className="h-3.5 w-3.5" /> New pipeline
                    </Button>
                  )
                }
              />
            </div>
          )}

          {!isLoading && !isError && paged.length > 0 && (
            <div className="overflow-hidden rounded-lg border border-line bg-[#0c141f]">
              <table className="w-full border-collapse">
                <thead>
                  <tr className="border-b border-line">
                    {['Pipeline', 'Project', 'Graph', 'Environment', 'Last run', 'Status', ''].map((header) => (
                      <th key={header} className={cn('table-head h-8 px-3 text-left first:pl-4 last:pr-4', header === '' && 'sr-only')}>
                        {header || 'Actions'}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {paged.map((pipeline) => {
                    const meta = statusMeta(pipeline.status)
                    return (
                      <tr
                        key={pipeline.id}
                        onClick={() => navigate(`/pipelines/${pipeline.id}`)}
                        className="table-row cursor-pointer last:border-0"
                      >
                        <td className="px-3 py-3 pl-4">
                          <div className="flex items-center gap-2.5">
                            <span className="flex h-6 w-6 items-center justify-center rounded border border-line-strong bg-[#111a28] text-[#8ea6db]">
                              <Workflow className="h-3 w-3" />
                            </span>
                            <div>
                              <p className="text-[11.5px] font-medium text-[#c5d0df]">{pipeline.name}</p>
                              <p className="mt-0.5 font-mono text-[8.5px] text-dim">{pipeline.id}</p>
                            </div>
                          </div>
                        </td>
                        <td className="px-3 py-3 font-mono text-[9.5px] text-dim">{pipeline.projectName}</td>
                        <td className="px-3 py-3 font-mono text-[9.5px] text-muted">
                          {pipeline.nodeCount} nodes <span className="text-[#3c4a60]">·</span> {pipeline.connectionCount} links
                        </td>
                        <td className="px-3 py-3">
                          <span className={cn('rounded border px-1.5 py-0.5 font-mono text-[8.5px]', pipeline.environment === 'Production' ? 'border-success/20 bg-success/[0.06] text-success' : 'border-line-strong bg-white/[0.03] text-muted')}>
                            {pipeline.environment}
                          </span>
                        </td>
                        <td className="px-3 py-3 font-mono text-[9px] text-dim">{pipeline.lastRunAt ?? '—'}</td>
                        <td className="px-3 py-3">
                          <span className={cn('flex items-center gap-1.5 font-mono text-[9px]', meta.tone)}>
                            <StatusDot status={meta.dot} pulse={meta.dot === 'running'} /> {meta.label}
                          </span>
                        </td>
                        <td className="px-3 py-3 pr-4">
                          <div className="flex items-center justify-end gap-1">
                            <button
                              onClick={(event) => {
                                event.stopPropagation()
                                runMutation.mutate(pipeline)
                              }}
                              disabled={runMutation.isPending}
                              className="flex h-6 items-center gap-1 rounded border border-line-strong px-1.5 font-mono text-[8.5px] text-muted transition-colors hover:border-accent/50 hover:text-ink disabled:opacity-40"
                            >
                              {runningId === pipeline.id ? <span className="h-2.5 w-2.5 animate-spin rounded-full border border-accent border-t-transparent" /> : <Play className="h-2.5 w-2.5" />}
                              Run
                            </button>
                            {action(pipeline)}
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
              {filtered.length > pageSize && (
                <Pagination page={page} pages={pages} onChange={setPage} total={filtered.length} pageSize={pageSize} />
              )}
            </div>
          )}
        </div>
      </div>

      <Dialog open={Boolean(deleteTarget)} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <DialogContent size="sm">
          <DialogHeader eyebrow="Delete" title={`Delete “${deleteTarget?.name}”?`} description="This removes the graph and its run history from the workspace." />
          <DialogBody>
            <div className="flex items-start gap-2 rounded-md border border-danger/20 bg-danger/[0.05] px-3 py-2.5 text-[11px] text-[#e8a0a0]">
              <XCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              Deployments referencing this pipeline will fail until they are re-pointed.
            </div>
          </DialogBody>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setDeleteTarget(null)}>Cancel</Button>
            <Button variant="danger" disabled={deleteMutation.isPending} onClick={() => deleteTarget && deleteMutation.mutate(deleteTarget.id)}>
              <Trash2 className="h-3.5 w-3.5" /> Delete pipeline
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
