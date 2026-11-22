import * as React from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ArrowRight,
  ArrowUpRight,
  CheckCircle2,
  Copy,
  Cpu,
  Database,
  FolderKanban,
  HardDrive,
  MemoryStick,
  MoreHorizontal,
  Pencil,
  Plus,
  Search,
  Trash2,
  Workflow,
} from 'lucide-react'
import { toast } from 'sonner'
import { PageHeader, HealthPill, InlineMeta, MiniDag, Pagination } from '@/components/shared/page'
import { KpiCard } from '@/components/shared/sparkline'
import { Button } from '@/components/ui/button'
import { SearchInput } from '@/components/ui/input'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/controls'
import { StatusDot, EmptyState, ErrorState, LoadingState } from '@/components/ui/badge'
import { RunsTab } from '@/components/runs/RunsTab'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown'
import { Dialog, DialogBody, DialogContent, DialogFooter, DialogHeader } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { projectsApi } from '@/api/projects.api'
import { useAppStore } from '@/store/useAppStore'
import { cn, formatCompact, formatNumber } from '@/lib/utils'
import type { Project, PipelineSummary } from '@/types'

function SkeletonDashboard() {
  return (
    <div className="space-y-5 p-6">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-[116px] animate-pulse rounded-lg border border-line bg-surface" />
        ))}
      </div>
      <div className="h-5 w-32 animate-pulse rounded bg-white/5" />
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-[240px] animate-pulse rounded-lg border border-line bg-surface" />
        ))}
      </div>
    </div>
  )
}

function ProjectCard({ project, onRename, onArchive }: { project: Project; onRename: (p: Project) => void; onArchive: (p: Project) => void }) {
  const navigate = useNavigate()
  const setCreatePipelineOpen = useAppStore((s) => s.setCreatePipelineOpen)
  return (
    <div className="group relative flex flex-col rounded-lg border border-line bg-gradient-to-b from-[#0f1825] to-[#0c141f] p-4 transition-colors hover:border-[#2c3b53]">
      <div className="flex items-start justify-between gap-2">
        <button onClick={() => navigate('/pipelines')} className="min-w-0 flex-1 text-left">
          <h3 className="truncate text-[13px] font-medium tracking-[-0.01em] text-ink group-hover:text-white">{project.name}</h3>
          <p className="mt-1 truncate text-[10.5px] text-dim">{project.description}</p>
        </button>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button className="rounded p-1 text-dim opacity-60 transition-colors hover:bg-white/5 hover:text-ink group-hover:opacity-100" aria-label={`Actions for ${project.name}`}>
              <MoreHorizontal className="h-4 w-4" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent className="w-48">
            <DropdownMenuItem icon={<ArrowUpRight className="h-3.5 w-3.5" />} onSelect={() => navigate('/pipelines')}>
              Open project
            </DropdownMenuItem>
            <DropdownMenuItem icon={<Workflow className="h-3.5 w-3.5" />} onSelect={() => setCreatePipelineOpen(true)}>
              New pipeline
            </DropdownMenuItem>
            <DropdownMenuItem icon={<Pencil className="h-3.5 w-3.5" />} onSelect={() => onRename(project)}>
              Rename project
            </DropdownMenuItem>
            <DropdownMenuItem icon={<Copy className="h-3.5 w-3.5" />} onSelect={() => toast.success('Project duplicated', { description: `${project.name} copy created as a draft.` })}>
              Duplicate
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem danger icon={<Trash2 className="h-3.5 w-3.5" />} onSelect={() => onArchive(project)}>
              Archive project
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <div className="mt-3.5 flex h-[82px] items-center justify-center rounded-md border border-[#1c2737] bg-[#0a111a] px-3">
        <MiniDag accent={project.accent} />
      </div>

      <div className="mt-3.5 flex items-center justify-between gap-2 border-t border-line/50 pt-3">
        <div className="flex items-center gap-2.5 font-mono text-[9.5px] text-dim">
          <span>{project.pipelineCount} pipelines</span>
          <span className="text-[#344158]">·</span>
          <span>{formatCompact(project.chunkCount)} chunks</span>
        </div>
        <HealthPill health={project.health} />
      </div>
      <div className="mt-2 flex items-center justify-between">
        <span className="font-mono text-[8.5px] text-[#5a677b]">Edited {project.editedAt}</span>
        <button onClick={() => navigate('/pipelines')} className="flex items-center gap-0.5 font-mono text-[8.5px] text-[#7f95cf] opacity-0 transition-opacity hover:text-[#aabfff] group-hover:opacity-100">
          Open <ArrowRight className="h-2.5 w-2.5" />
        </button>
      </div>
    </div>
  )
}

function PipelineTable({ pipelines }: { pipelines: PipelineSummary[] }) {
  const navigate = useNavigate()
  return (
    <div className="overflow-hidden rounded-lg border border-line bg-[#0c141f]">
      <table className="w-full border-collapse">
        <thead>
          <tr className="border-b border-line">
            {['Pipeline', 'Project', 'Last run', 'Status', ''].map((header) => (
              <th key={header} className={cn('table-head h-8 px-3 text-left text-[8.5px] first:pl-4 last:pr-4', header === '' && 'sr-only')}>
                {header || 'Action'}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {pipelines.map((pipeline) => (
            <tr key={pipeline.id} className="table-row cursor-pointer last:border-0" onClick={() => navigate(`/pipelines/${pipeline.id}`)}>
              <td className="px-3 py-2.5 pl-4">
                <span className="text-[11px] text-[#c5d0df]">{pipeline.name}</span>
                <span className="ml-2 font-mono text-[8.5px] text-dim">{pipeline.environment}</span>
              </td>
              <td className="px-3 py-2.5 font-mono text-[9.5px] text-dim">{pipeline.projectName}</td>
              <td className="px-3 py-2.5 font-mono text-[9.5px] text-dim">{pipeline.lastRunAt ?? '—'}</td>
              <td className="px-3 py-2.5">
                {pipeline.lastRunStatus === 'passed' ? (
                  <span className="flex items-center gap-1.5 font-mono text-[9.5px] text-success"><StatusDot status="success" /> Passed</span>
                ) : pipeline.lastRunStatus === 'failed' ? (
                  <span className="flex items-center gap-1.5 font-mono text-[9.5px] text-danger"><StatusDot status="danger" /> Failed</span>
                ) : (
                  <span className="flex items-center gap-1.5 font-mono text-[9.5px] text-warn"><StatusDot status="warning" /> Draft</span>
                )}
              </td>
              <td className="px-3 py-2.5 pr-4 text-right">
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    navigate(`/pipelines/${pipeline.id}`)
                  }}
                  className="flex items-center gap-1 font-mono text-[8.5px] text-[#7f95cf] hover:text-[#b5c6ff]"
                >
                  Open <ArrowUpRight className="h-2.5 w-2.5" />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function DashboardPage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const tab = searchParams.get('tab') === 'runs' ? 'runs' : 'overview'
  const setTab = (value: string) => {
    const next = new URLSearchParams(searchParams)
    if (value === 'runs') next.set('tab', 'runs')
    else next.delete('tab')
    setSearchParams(next, { replace: true })
  }
  const queryClient = useQueryClient()
  const setCreateProjectOpen = useAppStore((s) => s.setCreateProjectOpen)
  const pushNotification = useAppStore((s) => s.pushNotification)
  const [search, setSearch] = React.useState('')
  const [page, setPage] = React.useState(1)
  const [renameProject, setRenameProject] = React.useState<Project | null>(null)
  const [renameValue, setRenameValue] = React.useState('')
  const [hiddenProjects, setHiddenProjects] = React.useState<string[]>([])

  const { data, isLoading, isError, error, refetch } = useQuery({ queryKey: ['dashboard'], queryFn: projectsApi.dashboard })

  const renameMutation = useMutation({
    mutationFn: () => projectsApi.update(renameProject!.id, { name: renameValue.trim() }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      toast.success('Project renamed')
      setRenameProject(null)
    },
    onError: (err: Error) => toast.error('Rename failed', { description: err.message }),
  })

  const pageSize = 4
  const filteredPipelines = (data?.pipelines ?? []).filter((p) => `${p.name} ${p.projectName}`.toLowerCase().includes(search.toLowerCase()))
  const pagedPipelines = filteredPipelines.slice((page - 1) * pageSize, page * pageSize)
  const pages = Math.max(1, Math.ceil(filteredPipelines.length / pageSize))
  const visibleProjects = (data?.projects ?? []).filter((p) => !hiddenProjects.includes(p.id))

  if (isLoading) {
    return (
      <>
        <PageHeader eyebrow="Workspace overview" title="Project dashboard" description="Build, test and ship better retrieval pipelines." actions={<Button variant="primary" disabled><Plus className="h-3.5 w-3.5" /> New project</Button>} />
        <div className="min-h-0 flex-1 overflow-y-auto"><SkeletonDashboard /></div>
      </>
    )
  }

  if (isError || !data) {
    return (
      <>
        <PageHeader eyebrow="Workspace overview" title="Project dashboard" description="Build, test and ship better retrieval pipelines." />
        <div className="flex-1 overflow-y-auto"><ErrorState message={(error as Error)?.message} onRetry={() => void refetch()} /></div>
      </>
    )
  }

  return (
    <>
      <Tabs value={tab} onValueChange={setTab}>
        <PageHeader
          eyebrow="Workspace overview"
          title="Project dashboard"
          description="Build, test and ship better retrieval pipelines."
          actions={
            <Button variant="primary" size="lg" onClick={() => setCreateProjectOpen(true)}>
              <Plus className="h-3.5 w-3.5" /> New project
            </Button>
          }
          tabs={
            <TabsList>
              <TabsTrigger value="overview">Panoramica</TabsTrigger>
              <TabsTrigger value="runs">Run <span className="ml-1.5 rounded bg-white/[0.05] px-1 font-mono text-[8.5px] text-dim">{formatNumber(data.metrics.executions)}</span></TabsTrigger>
            </TabsList>
          }
        />

        <div className="min-h-0 flex-1 overflow-y-auto">
          <TabsContent value="overview">
            <div className="space-y-6 px-6 py-5">
            <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4" aria-label="Workspace metrics">
              <KpiCard label="Active projects" value={data.metrics.activeProjects} delta={data.metrics.activeProjectsDelta} tone="success" spark={data.metrics.sparks.projects} sparkColor="#6F8FFF" />
              <KpiCard label="Pipelines" value={data.metrics.pipelines} delta={data.metrics.pipelinesDelta} tone="success" spark={data.metrics.sparks.pipelines} sparkColor="#7296FF" />
              <KpiCard label="Total executions" value={formatNumber(data.metrics.executions)} delta={data.metrics.executionsDelta} tone="success" spark={data.metrics.sparks.executions} sparkColor="#557BF2" />
              <KpiCard label="Average faithfulness" value={data.metrics.faithfulness.toFixed(2)} delta={data.metrics.faithfulnessDelta} tone="success" spark={data.metrics.sparks.faithfulness} sparkColor="#7C8FFF" />
            </section>

            <section>
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-[15px] font-semibold tracking-[-0.015em] text-ink">Your projects</h2>
                <Link to="/projects" className="flex items-center gap-1 font-mono text-[9px] text-dim transition-colors hover:text-ink">
                  View all projects <ArrowRight className="h-3 w-3" />
                </Link>
              </div>
              {visibleProjects.length === 0 ? (
                <div className="rounded-lg border border-line bg-surface">
                  <EmptyState
                    icon={<FolderKanban className="h-4 w-4" />}
                    title="No projects in this workspace"
                    description="Create your first project to start building retrieval pipelines."
                    action={<Button variant="primary" onClick={() => setCreateProjectOpen(true)}><Plus className="h-3.5 w-3.5" /> New project</Button>}
                  />
                </div>
              ) : (
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                  {visibleProjects.map((project) => (
                    <ProjectCard
                      key={project.id}
                      project={project}
                      onRename={(p) => {
                        setRenameProject(p)
                        setRenameValue(p.name)
                      }}
                      onArchive={(p) => {
                        setHiddenProjects((prev) => [...prev, p.id])
                        pushNotification({ title: 'Project archived', body: `${p.name} was moved to the archive.`, type: 'info' })
                        toast.success('Project archived', { description: `${p.name} can be restored from Settings.` })
                      }}
                    />
                  ))}
                </div>
              )}
            </section>

            <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_310px]">
              <div>
                <div className="mb-2.5 flex flex-wrap items-center justify-between gap-2">
                  <h2 className="text-[15px] font-semibold tracking-[-0.015em] text-ink">Recent pipelines</h2>
                  <SearchInput value={search} onChange={(v) => { setSearch(v); setPage(1) }} placeholder="Search pipelines…" className="w-[210px]" />
                </div>
                {pagedPipelines.length === 0 ? (
                  <div className="rounded-lg border border-line bg-surface">
                    <EmptyState
                      icon={<Search className="h-4 w-4" />}
                      title="No pipelines match your search"
                      description="Try a different pipeline or project name."
                      action={<Button variant="secondary" size="sm" onClick={() => setSearch('')}>Clear search</Button>}
                    />
                  </div>
                ) : (
                  <PipelineTable pipelines={pagedPipelines} />
                )}
                {filteredPipelines.length > 0 && (
                  <div className="rounded-b-lg border-x border-b border-line bg-[#0b111b]">
                    <Pagination page={page} pages={pages} onChange={setPage} total={filteredPipelines.length} pageSize={pageSize} />
                  </div>
                )}
              </div>

              <aside>
                <h2 className="mb-2.5 text-[15px] font-semibold tracking-[-0.015em] text-ink">Workspace activity</h2>
                <div className="rounded-lg border border-line bg-[#0c141f]">
                  {data.activity.map((item, index) => (
                    <div key={item.id} className={cn('flex gap-3 px-4 py-3', index > 0 && 'border-t border-line/60')}>
                      <span className="mt-1">
                        <StatusDot
                          status={item.type === 'pipeline' ? 'success' : item.type === 'evaluation' ? 'accent' : item.type === 'dataset' ? 'accent' : 'warning'}
                        />
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-start justify-between gap-2">
                          <p className="text-[10.5px] font-medium text-[#c3cfe0]">{item.title}</p>
                          <span className="shrink-0 font-mono text-[8.5px] text-[#5b687d]">{item.time}</span>
                        </div>
                        <p className="mt-1 truncate font-mono text-[8.5px] text-dim">{item.detail}</p>
                      </div>
                    </div>
                  ))}
                  <button
                    onClick={() => navigate('/experiments')}
                    className="flex w-full items-center justify-center gap-1 border-t border-line py-2.5 font-mono text-[8.5px] text-dim transition-colors hover:bg-white/[0.02] hover:text-ink"
                  >
                    View full activity <ArrowUpRight className="h-2.5 w-2.5" />
                  </button>
                </div>
              </aside>
            </section>

            <section className="flex flex-wrap items-center gap-x-6 gap-y-2 rounded-lg border border-line bg-[#0b121c] px-4 py-2.5">
              <span className="font-mono text-[8px] uppercase tracking-[0.16em] text-[#4e5c71]">Local resources</span>
              <InlineMeta items={[
                <span className="flex items-center gap-1.5"><MemoryStick className="h-3 w-3" /> Memory <span className="text-[#92a0b4]">{data.metrics.resources.memory}</span></span>,
                <span className="flex items-center gap-1.5"><Cpu className="h-3 w-3" /> GPU <span className="text-[#92a0b4]">{data.metrics.resources.gpu}</span></span>,
                <span className="flex items-center gap-1.5"><HardDrive className="h-3 w-3" /> Storage <span className="text-[#92a0b4]">{data.metrics.resources.storage}</span></span>,
              ]} />
              <span className="ml-auto flex items-center gap-1.5 font-mono text-[8.5px] text-dim"><Database className="h-3 w-3" /> 4 services connected</span>
            </section>
            </div>
          </TabsContent>

          <TabsContent value="runs">
            <div className="px-6 py-5">
              <RunsTab />
            </div>
          </TabsContent>
        </div>
      </Tabs>

      <Dialog open={Boolean(renameProject)} onOpenChange={(open) => !open && setRenameProject(null)}>
        <DialogContent size="sm">
          <DialogHeader eyebrow="Project" title="Rename project" description="The project name appears across pipelines, datasets and reports." />
          <DialogBody>
            <Input value={renameValue} onChange={(e) => setRenameValue(e.target.value)} autoFocus />
          </DialogBody>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setRenameProject(null)}>Cancel</Button>
            <Button variant="primary" disabled={!renameValue.trim() || renameMutation.isPending} onClick={() => renameMutation.mutate()}>
              Save name
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
