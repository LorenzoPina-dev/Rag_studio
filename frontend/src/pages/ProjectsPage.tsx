import * as React from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ArrowRight,
  ArrowUpRight,
  Copy,
  FolderKanban,
  Grid2X2,
  List,
  MoreHorizontal,
  Pencil,
  Plus,
  Search,
  Trash2,
  Workflow,
} from 'lucide-react'
import { toast } from 'sonner'
import { PageHeader, HealthPill, MiniDag } from '@/components/shared/page'
import { Button } from '@/components/ui/button'
import { SearchInput, Input, Textarea, Field } from '@/components/ui/input'
import { EmptyState, ErrorState, LoadingState, StatusDot } from '@/components/ui/badge'
import { Dialog, DialogBody, DialogContent, DialogFooter, DialogHeader } from '@/components/ui/dialog'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown'
import { Select } from '@/components/ui/select'
import { projectsApi } from '@/api/projects.api'
import { useAppStore } from '@/store/useAppStore'
import { cn, formatCompact, formatNumber } from '@/lib/utils'
import type { Project } from '@/types'

type SortKey = 'name' | 'pipelines' | 'chunks' | 'updated'

function ProjectActions({
  project,
  onRename,
  onDelete,
}: {
  project: Project
  onRename: (project: Project) => void
  onDelete: (project: Project) => void
}) {
  const navigate = useNavigate()
  const setCreatePipelineOpen = useAppStore((s) => s.setCreatePipelineOpen)
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          onClick={(event) => event.stopPropagation()}
          className="rounded p-1 text-dim opacity-70 transition-colors hover:bg-white/5 hover:text-ink group-hover:opacity-100"
          aria-label={`Actions for ${project.name}`}
        >
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
        <DropdownMenuItem
          icon={<Copy className="h-3.5 w-3.5" />}
          onSelect={() => toast.success('Project duplicated', { description: `${project.name} copy created as a draft.` })}
        >
          Duplicate
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem danger icon={<Trash2 className="h-3.5 w-3.5" />} onSelect={() => onDelete(project)}>
          Archive project
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

function ProjectCard({
  project,
  onRename,
  onDelete,
  onArchived,
}: {
  project: Project
  onRename: (project: Project) => void
  onDelete: (project: Project) => void
  onArchived: (id: string) => void
}) {
  const navigate = useNavigate()
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => navigate('/pipelines')}
      onKeyDown={(event) => event.key === 'Enter' && navigate('/pipelines')}
      className="group relative flex cursor-pointer flex-col rounded-lg border border-line bg-gradient-to-b from-[#0f1825] to-[#0c141f] p-4 text-left transition-colors hover:border-[#2c3b53]"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-[13.5px] font-medium tracking-[-0.01em] text-ink group-hover:text-white">{project.name}</h3>
          <p className="mt-1 truncate text-[10.5px] text-dim">{project.description}</p>
        </div>
        <div onClick={(event) => event.stopPropagation()}>
          <ProjectActions
            project={project}
            onRename={onRename}
            onDelete={(value) => {
              onArchived(value.id)
              onDelete(value)
            }}
          />
        </div>
      </div>

      <div className="mt-3.5 flex h-[84px] items-center justify-center rounded-md border border-[#1c2737] bg-[#0a111a] px-3">
        <MiniDag accent={project.accent} />
      </div>

      <div className="mt-3.5 grid grid-cols-2 gap-2 border-t border-line/50 pt-3 font-mono text-[9.5px]">
        <span className="text-dim">{project.pipelineCount} pipelines</span>
        <span className="text-right text-dim">{formatCompact(project.chunkCount)} chunks</span>
      </div>
      <div className="mt-3 flex items-center justify-between">
        <HealthPill health={project.health} />
        <span className="font-mono text-[8.5px] text-[#5a677b]">Edited {project.editedAt}</span>
      </div>
    </div>
  )
}

export function ProjectsPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const setCreateProjectOpen = useAppStore((s) => s.setCreateProjectOpen)
  const [search, setSearch] = React.useState('')
  const [health, setHealth] = React.useState<'all' | Project['health']>('all')
  const [sort, setSort] = React.useState<SortKey>('updated')
  const [view, setView] = React.useState<'grid' | 'list'>('grid')
  const [renaming, setRenaming] = React.useState<Project | null>(null)
  const [renameValue, setRenameValue] = React.useState('')
  const [deleting, setDeleting] = React.useState<Project | null>(null)
  const [hidden, setHidden] = React.useState<string[]>([])

  const { data, isLoading, isError, error, refetch } = useQuery({ queryKey: ['projects'], queryFn: projectsApi.list })

  const renameMutation = useMutation({
    mutationFn: () => projectsApi.update(renaming!.id, { name: renameValue.trim() }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      toast.success('Project renamed')
      setRenaming(null)
    },
    onError: (err: Error) => toast.error('Rename failed', { description: err.message }),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => projectsApi.remove(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      toast.success('Project archived', { description: 'Restore it any time from Settings → Archive.' })
      setDeleting(null)
    },
    onError: (err: Error) => toast.error('Archive failed', { description: err.message }),
  })

  const projects = (data ?? []).filter((project) => !hidden.includes(project.id))
  const visible = projects
    .filter((project) => (health === 'all' ? true : project.health === health))
    .filter((project) => `${project.name} ${project.description}`.toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => {
      if (sort === 'name') return a.name.localeCompare(b.name)
      if (sort === 'pipelines') return b.pipelineCount - a.pipelineCount
      if (sort === 'chunks') return b.chunkCount - a.chunkCount
      return new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
    })

  const totalPipelines = projects.reduce((sum, project) => sum + project.pipelineCount, 0)
  const totalChunks = projects.reduce((sum, project) => sum + project.chunkCount, 0)
  const healthy = projects.filter((project) => project.health === 'healthy').length

  return (
    <>
      <PageHeader
        eyebrow="Workspace"
        title="Projects"
        description="Organize pipelines, datasets and evaluations into focused workspaces."
        breadcrumbs={[{ label: 'Research lab', to: '/' }, { label: 'Projects' }]}
        actions={
          <>
            <Button variant="secondary" onClick={() => navigate('/pipelines')}>
              <Workflow className="h-3.5 w-3.5" /> All pipelines
            </Button>
            <Button variant="primary" size="lg" onClick={() => setCreateProjectOpen(true)}>
              <Plus className="h-3.5 w-3.5" /> New project
            </Button>
          </>
        }
      />

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="space-y-5 px-6 py-5">
          <div className="flex flex-wrap items-center gap-x-5 gap-y-2 rounded-lg border border-line bg-[#0c141f] px-4 py-2.5 font-mono text-[9.5px] text-dim">
            <span className="flex items-center gap-1.5 text-muted">
              <FolderKanban className="h-3 w-3" /> {projects.length} projects
            </span>
            <span className="text-[#344158]">·</span>
            <span className="flex items-center gap-1.5">
              <StatusDot status="success" /> {healthy} healthy
            </span>
            <span className="text-[#344158]">·</span>
            <span>{totalPipelines} pipelines</span>
            <span className="text-[#344158]">·</span>
            <span>{formatNumber(totalChunks)} indexed chunks</span>
            <span className="ml-auto flex items-center gap-1.5 text-[#7f95cf]">
              <StatusDot status="accent" /> All changes synced
            </span>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <SearchInput value={search} onChange={setSearch} placeholder="Search projects…" className="w-[240px]" />
            <Select
              value={health}
              onValueChange={(value) => setHealth(value as typeof health)}
              options={[
                { value: 'all', label: 'All health' },
                { value: 'healthy', label: 'Healthy' },
                { value: 'warning', label: 'Needs attention' },
                { value: 'draft', label: 'Draft' },
              ]}
              className="w-[150px]"
              aria-label="Filter by health"
            />
            <Select
              value={sort}
              onValueChange={(value) => setSort(value as SortKey)}
              options={[
                { value: 'updated', label: 'Last updated' },
                { value: 'name', label: 'Name' },
                { value: 'pipelines', label: 'Pipelines' },
                { value: 'chunks', label: 'Chunks' },
              ]}
              className="w-[150px]"
              aria-label="Sort projects"
            />
            <div className="ml-auto flex items-center rounded-md border border-line-strong bg-[#0a1019] p-0.5">
              <button
                onClick={() => setView('grid')}
                className={cn('flex h-6 w-6 items-center justify-center rounded transition-colors', view === 'grid' ? 'bg-white/[0.08] text-ink' : 'text-dim hover:text-ink')}
                aria-label="Grid view"
              >
                <Grid2X2 className="h-3.5 w-3.5" />
              </button>
              <button
                onClick={() => setView('list')}
                className={cn('flex h-6 w-6 items-center justify-center rounded transition-colors', view === 'list' ? 'bg-white/[0.08] text-ink' : 'text-dim hover:text-ink')}
                aria-label="List view"
              >
                <List className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>

          {isLoading && <LoadingState label="Loading projects…" rows={5} />}
          {isError && <ErrorState message={(error as Error)?.message} onRetry={() => void refetch()} />}

          {!isLoading && !isError && visible.length === 0 && (
            <div className="rounded-lg border border-line bg-surface">
              <EmptyState
                icon={search ? <Search className="h-4 w-4" /> : <FolderKanban className="h-4 w-4" />}
                title={search ? 'No projects match your search' : 'No projects in this workspace'}
                description={search ? 'Try a different name or clear the health filter.' : 'Create your first project to start building retrieval pipelines.'}
                action={
                  search ? (
                    <Button variant="secondary" size="sm" onClick={() => { setSearch(''); setHealth('all') }}>
                      Clear filters
                    </Button>
                  ) : (
                    <Button variant="primary" onClick={() => setCreateProjectOpen(true)}>
                      <Plus className="h-3.5 w-3.5" /> New project
                    </Button>
                  )
                }
              />
            </div>
          )}

          {!isLoading && !isError && visible.length > 0 && view === 'grid' && (
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
              {visible.map((project) => (
                <ProjectCard
                  key={project.id}
                  project={project}
                  onRename={(value) => {
                    setRenaming(value)
                    setRenameValue(value.name)
                  }}
                  onDelete={(value) => setDeleting(value)}
                  onArchived={(id) => setHidden((prev) => [...prev, id])}
                />
              ))}
            </div>
          )}

          {!isLoading && !isError && visible.length > 0 && view === 'list' && (
            <div className="overflow-hidden rounded-lg border border-line bg-[#0c141f]">
              <table className="w-full border-collapse">
                <thead>
                  <tr className="border-b border-line">
                    {['Project', 'Health', 'Pipelines', 'Chunks', 'Edited', ''].map((header) => (
                      <th key={header} className={cn('table-head h-8 px-3 text-left', header === '' && 'sr-only')}>
                        {header || 'Actions'}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {visible.map((project) => (
                    <tr key={project.id} className="table-row cursor-pointer last:border-0" onClick={() => navigate('/pipelines')}>
                      <td className="px-3 py-2.5 pl-4">
                        <p className="text-[11.5px] text-[#c5d0df]">{project.name}</p>
                        <p className="mt-0.5 font-mono text-[8.5px] text-dim">{project.description}</p>
                      </td>
                      <td className="px-3 py-2.5"><HealthPill health={project.health} /></td>
                      <td className="px-3 py-2.5 font-mono text-[10px] text-muted">{project.pipelineCount}</td>
                      <td className="px-3 py-2.5 font-mono text-[10px] text-muted">{formatCompact(project.chunkCount)}</td>
                      <td className="px-3 py-2.5 font-mono text-[9px] text-dim">{project.editedAt}</td>
                      <td className="px-3 py-2.5 pr-4 text-right" onClick={(event) => event.stopPropagation()}>
                        <div className="flex items-center justify-end gap-2">
                          <button onClick={() => navigate('/pipelines')} className="flex items-center gap-1 font-mono text-[8.5px] text-[#7f95cf] hover:text-[#b5c6ff]">
                            Open <ArrowRight className="h-2.5 w-2.5" />
                          </button>
                          <ProjectActions
                            project={project}
                            onRename={(value) => {
                              setRenaming(value)
                              setRenameValue(value.name)
                            }}
                            onDelete={(value) => {
                              setHidden((prev) => [...prev, value.id])
                              setDeleting(value)
                            }}
                          />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      <Dialog open={Boolean(renaming)} onOpenChange={(open) => !open && setRenaming(null)}>
        <DialogContent size="sm">
          <DialogHeader eyebrow="Project" title="Rename project" description="The name appears across pipelines, datasets and reports." />
          <DialogBody>
            <Input value={renameValue} onChange={(event) => setRenameValue(event.target.value)} autoFocus />
          </DialogBody>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setRenaming(null)}>Cancel</Button>
            <Button variant="primary" disabled={!renameValue.trim() || renameMutation.isPending} onClick={() => renameMutation.mutate()}>
              Save name
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(deleting)} onOpenChange={(open) => !open && setDeleting(null)}>
        <DialogContent size="sm">
          <DialogHeader eyebrow="Archive" title={`Archive “${deleting?.name}”?`} description="Pipelines and datasets in this project are preserved and can be restored later." />
          <DialogBody>
            <div className="rounded-md border border-warn/20 bg-warn/[0.05] px-3 py-2.5 text-[11px] text-[#e6c894]">
              Scheduled runs and evaluations for this project will be paused.
            </div>
          </DialogBody>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setDeleting(null)}>Cancel</Button>
            <Button variant="danger" disabled={deleteMutation.isPending} onClick={() => deleting && deleteMutation.mutate(deleting.id)}>
              <Trash2 className="h-3.5 w-3.5" /> Archive project
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
