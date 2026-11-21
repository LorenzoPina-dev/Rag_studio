import * as React from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Activity,
  BarChart3,
  Box,
  Boxes,
  ChevronRight,
  Code2,
  Database,
  FilePlus2,
  FileText,
  FlaskConical,
  Folder,
  Keyboard,
  LayoutGrid,
  Loader2,
  Plus,
  Search,
  Settings,
  Sparkles,
  Terminal,
  Workflow,
  X,
  Zap,
} from 'lucide-react'
import { toast } from 'sonner'
import { Dialog, DialogBody, DialogClose, DialogContent, DialogFooter, DialogHeader } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input, SearchInput, Textarea } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { Checkbox, Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/controls'
import { StatusDot, Kbd, Badge } from '@/components/ui/badge'
import { useAppStore } from '@/store/useAppStore'
import { projectsApi } from '@/api/projects.api'
import { pipelinesApi } from '@/api/pipelines.api'
import { cn } from '@/lib/utils'
import type { SearchResult } from '@/types'

const pages: Array<{ title: string; subtitle: string; href: string; icon: React.ComponentType<{ className?: string }>; keywords: string }> = [
  { title: 'Dashboard', subtitle: 'Workspace overview', href: '/', icon: LayoutGrid, keywords: 'home overview stats' },
  { title: 'Projects', subtitle: 'All projects', href: '/projects', icon: Folder, keywords: 'workspaces' },
  { title: 'Pipelines', subtitle: 'Pipeline library', href: '/pipelines', icon: Workflow, keywords: 'flows dag' },
  { title: 'Hybrid RAG pipeline', subtitle: 'Pipeline editor', href: '/pipelines/pl_hybrid_rag', icon: Workflow, keywords: 'editor graph nodes' },
  { title: 'Node Library', subtitle: 'Browse node definitions', href: '/nodes', icon: Boxes, keywords: 'components catalog' },
  { title: 'Custom Nodes', subtitle: 'Python component editor', href: '/custom-nodes', icon: Code2, keywords: 'python code ide' },
  { title: 'Datasets & data sources', subtitle: 'Documents and ingestion', href: '/datasets', icon: Database, keywords: 'data knowledge chunks' },
  { title: 'Model manager', subtitle: 'LLMs, embeddings, rerankers', href: '/models', icon: Box, keywords: 'openai ollama huggingface' },
  { title: 'Execution monitor', subtitle: 'Run #2,486 trace and logs', href: '/runs/run_2486', icon: Activity, keywords: 'logs trace runtime' },
  { title: 'Intermediate results', subtitle: 'Retrieved chunks and lineage', href: '/runs/run_2486/results', icon: FileText, keywords: 'documents retrieval lineage' },
  { title: 'Experiments', subtitle: 'Compare configurations', href: '/experiments', icon: FlaskConical, keywords: 'trials compare scores' },
  { title: 'Evaluation dashboard', subtitle: 'RAGAS quality metrics', href: '/evaluation', icon: BarChart3, keywords: 'faithfulness relevance precision recall' },
  { title: 'Settings', subtitle: 'Workspace and runtime', href: '/settings', icon: Settings, keywords: 'preferences environment' },
]

const typeIcon: Record<SearchResult['type'], React.ComponentType<{ className?: string }>> = {
  pipeline: Workflow,
  project: Folder,
  dataset: Database,
  model: Box,
  experiment: FlaskConical,
  node: Boxes,
  page: FileText,
}

export function GlobalOverlays() {
  const commandOpen = useAppStore((s) => s.commandOpen)
  const setCommandOpen = useAppStore((s) => s.setCommandOpen)
  const createProjectOpen = useAppStore((s) => s.createProjectOpen)
  const setCreateProjectOpen = useAppStore((s) => s.setCreateProjectOpen)
  const createPipelineOpen = useAppStore((s) => s.createPipelineOpen)
  const setCreatePipelineOpen = useAppStore((s) => s.setCreatePipelineOpen)
  const notificationsOpen = useAppStore((s) => s.notificationsOpen)
  const setNotificationsOpen = useAppStore((s) => s.setNotificationsOpen)
  const shortcutsOpen = useAppStore((s) => s.shortcutsOpen)
  const setShortcutsOpen = useAppStore((s) => s.setShortcutsOpen)
  const aboutOpen = useAppStore((s) => s.aboutOpen)
  const setAboutOpen = useAppStore((s) => s.setAboutOpen)

  React.useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'j') {
        event.preventDefault()
        setCommandOpen(true)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [setCommandOpen])

  return (
    <>
      <CommandPalette open={commandOpen} onOpenChange={setCommandOpen} />
      <NewProjectDialog open={createProjectOpen} onOpenChange={setCreateProjectOpen} />
      <NewPipelineDialog open={createPipelineOpen} onOpenChange={setCreatePipelineOpen} />
      <NotificationsPanel open={notificationsOpen} onOpenChange={setNotificationsOpen} />
      <ShortcutsDialog open={shortcutsOpen} onOpenChange={setShortcutsOpen} />
      <AboutDialog open={aboutOpen} onOpenChange={setAboutOpen} />
    </>
  )
}

function CommandPalette({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const navigate = useNavigate()
  const [query, setQuery] = React.useState('')
  const [selectedIndex, setSelectedIndex] = React.useState(0)
  const inputRef = React.useRef<HTMLInputElement>(null)
  const setCreateProjectOpen = useAppStore((s) => s.setCreateProjectOpen)
  const setCreatePipelineOpen = useAppStore((s) => s.setCreatePipelineOpen)
  const setShortcutsOpen = useAppStore((s) => s.setShortcutsOpen)

  const { data: results, isFetching } = useQuery({
    queryKey: ['search', query],
    queryFn: () => projectsApi.search(query),
    enabled: open && query.trim().length > 0,
    staleTime: 5_000,
  })

  React.useEffect(() => {
    if (open) {
      setQuery('')
      setSelectedIndex(0)
      setTimeout(() => inputRef.current?.focus(), 30)
    }
  }, [open])

  const q = query.trim().toLowerCase()
  const pageMatches = q ? pages.filter((p) => `${p.title} ${p.subtitle} ${p.keywords}`.toLowerCase().includes(q)) : pages.slice(0, 7)
  const actionMatches = q
    ? [
        { title: 'New project', subtitle: 'Create a retrieval workspace', icon: FilePlus2, action: () => setCreateProjectOpen(true) },
        { title: 'New pipeline', subtitle: 'Start from a template or blank canvas', icon: Plus, action: () => setCreatePipelineOpen(true) },
        { title: 'Open pipeline editor', subtitle: 'Edit Hybrid RAG pipeline', icon: Workflow, action: () => navigate('/pipelines/pl_hybrid_rag') },
        { title: 'Keyboard shortcuts', subtitle: 'View all shortcuts', icon: Keyboard, action: () => setShortcutsOpen(true) },
      ].filter((a) => `${a.title} ${a.subtitle}`.toLowerCase().includes(q))
    : []

  const entityMatches = (results ?? []).filter((r) => r.type !== 'page').slice(0, 8)
  const items = [
    ...actionMatches.map((a) => ({ kind: 'action' as const, title: a.title, subtitle: a.subtitle, icon: a.icon, href: undefined, action: a.action })),
    ...pageMatches.map((p) => ({ kind: 'page' as const, title: p.title, subtitle: p.subtitle, icon: p.icon, href: p.href, action: undefined })),
    ...entityMatches.map((r) => ({ kind: 'entity' as const, title: r.title, subtitle: r.subtitle, icon: typeIcon[r.type], href: r.href, action: undefined, badge: r.type })),
  ]

  const runItem = React.useCallback(
    (index: number) => {
      const item = items[index]
      if (!item) return
      onOpenChange(false)
      if (item.action) {
        setTimeout(() => item.action!(), 50)
      } else if (item.href) {
        navigate(item.href)
      }
    },
    [items, navigate, onOpenChange],
  )

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="lg" hideClose className="top-[12%] max-w-[620px] overflow-hidden p-0">
        <div className="flex items-center gap-2.5 border-b border-line px-4">
          <Search className="h-4 w-4 text-dim" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value)
              setSelectedIndex(0)
            }}
            onKeyDown={(e) => {
              if (e.key === 'ArrowDown') {
                e.preventDefault()
                setSelectedIndex((i) => Math.min(items.length - 1, i + 1))
              }
              if (e.key === 'ArrowUp') {
                e.preventDefault()
                setSelectedIndex((i) => Math.max(0, i - 1))
              }
              if (e.key === 'Enter') {
                e.preventDefault()
                runItem(selectedIndex)
              }
            }}
            placeholder="Search projects, pipelines, datasets, models…"
            className="h-[52px] flex-1 bg-transparent text-[13px] text-ink placeholder:text-dim focus:outline-none"
          />
          {isFetching && <Loader2 className="h-3.5 w-3.5 animate-spin text-dim" />}
          <Kbd>Esc</Kbd>
        </div>
        <div className="max-h-[420px] overflow-y-auto p-1.5">
          {items.length === 0 && (
            <div className="px-4 py-10 text-center">
              <Search className="mx-auto mb-2 h-5 w-5 text-dim" />
              <p className="text-[12px] text-muted">No results for “{query}”</p>
              <p className="mt-1 text-[10.5px] text-dim">Try a project, dataset or node name.</p>
            </div>
          )}
          {items.map((item, index) => {
            const Icon = item.icon
            const showHeading =
              index === 0 ||
              (items[index - 1].kind !== item.kind && item.kind !== 'entity') ||
              (item.kind === 'entity' &&
                (index === 0 || items[index - 1].kind !== 'entity'))
            return (
              <React.Fragment key={`${item.kind}-${item.title}-${index}`}>
                {showHeading && (
                  <p className="px-2.5 pb-1 pt-2.5 font-mono text-[8.5px] uppercase tracking-[0.14em] text-dim">
                    {item.kind === 'action' ? 'Actions' : item.kind === 'page' ? 'Navigate' : 'Results'}
                  </p>
                )}
                <button
                  onMouseEnter={() => setSelectedIndex(index)}
                  onClick={() => runItem(index)}
                  className={cn(
                    'flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-left transition-colors',
                    selectedIndex === index ? 'bg-[#1a2440]' : 'hover:bg-white/[0.035]',
                  )}
                >
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded border border-line bg-[#101a28] text-muted">
                    <Icon className="h-3.5 w-3.5" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[11.5px] text-ink">{item.title}</span>
                    <span className="block truncate text-[10px] text-dim">{item.subtitle}</span>
                  </span>
                  {item.kind === 'entity' && item.badge && <Badge className="shrink-0">{item.badge}</Badge>}
                  <ChevronRight className={cn('h-3.5 w-3.5 shrink-0', selectedIndex === index ? 'text-muted' : 'text-transparent')} />
                </button>
              </React.Fragment>
            )
          })}
        </div>
        <div className="flex items-center gap-4 border-t border-line bg-[#0b111b] px-4 py-2 font-mono text-[8.5px] uppercase tracking-wider text-dim">
          <span className="flex items-center gap-1"><Kbd>↑</Kbd><Kbd>↓</Kbd> navigate</span>
          <span className="flex items-center gap-1"><Kbd>↵</Kbd> open</span>
          <span className="flex items-center gap-1"><Kbd>⌘</Kbd><Kbd>K</Kbd> toggle</span>
          <span className="ml-auto flex items-center gap-1.5"><StatusDot status="success" /> Local workspace</span>
        </div>
      </DialogContent>
    </Dialog>
  )
}

function NewProjectDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [name, setName] = React.useState('')
  const [description, setDescription] = React.useState('')
  const [template, setTemplate] = React.useState<'starter' | 'blank'>('starter')

  const mutation = useMutation({
    mutationFn: () => projectsApi.create({ name: name.trim(), description: description.trim() }),
    onSuccess: (project) => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      toast.success('Project created', { description: `${project.name} is ready to configure.` })
      onOpenChange(false)
      setName('')
      setDescription('')
      navigate('/projects')
    },
    onError: (error: Error) => toast.error('Could not create project', { description: error.message }),
  })

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader eyebrow="New project" title="Create a project" description="Projects group pipelines, datasets and evaluation suites around one retrieval use case." />
        <DialogBody className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-[11.5px] font-medium text-muted">Project name</label>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Contract intelligence" autoFocus />
          </div>
          <div className="space-y-1.5">
            <label className="text-[11.5px] font-medium text-muted">Description</label>
            <Textarea value={description} onChange={(e) => setDescription(e.target.value)} placeholder="What knowledge does this project serve?" rows={2} />
          </div>
          <div className="space-y-2">
            <label className="text-[11.5px] font-medium text-muted">Starting point</label>
            <div className="grid grid-cols-2 gap-2">
              {[
                { id: 'starter', title: 'Hybrid retrieval', description: 'Source → chunk → hybrid retrieval → rerank → generate.', icon: Zap },
                { id: 'blank', title: 'Blank project', description: 'Start with an empty canvas and compose your own graph.', icon: Plus },
              ].map((option) => (
                <button
                  key={option.id}
                  type="button"
                  onClick={() => setTemplate(option.id as 'starter' | 'blank')}
                  className={cn(
                    'rounded-lg border p-3 text-left transition-colors',
                    template === option.id ? 'border-accent/60 bg-accent/[0.07]' : 'border-line bg-[#0b111b] hover:border-line-strong',
                  )}
                >
                  <option.icon className={cn('mb-2 h-4 w-4', template === option.id ? 'text-[#a6b8ff]' : 'text-dim')} />
                  <p className="text-[11.5px] font-medium text-ink">{option.title}</p>
                  <p className="mt-1 text-[10px] leading-relaxed text-dim">{option.description}</p>
                </button>
              ))}
            </div>
          </div>
        </DialogBody>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button variant="primary" disabled={!name.trim() || mutation.isPending} onClick={() => mutation.mutate()}>
            {mutation.isPending && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            Create project
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function NewPipelineDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [name, setName] = React.useState('')
  const [project, setProject] = React.useState('pr_knowledge')
  const [template, setTemplate] = React.useState<'starter' | 'blank'>('starter')
  const { data: projects } = useQuery({ queryKey: ['projects'], queryFn: projectsApi.list, enabled: open })

  const mutation = useMutation({
    mutationFn: () => pipelinesApi.create({ name: name.trim(), projectId: project, template }),
    onSuccess: (pipeline) => {
      queryClient.invalidateQueries({ queryKey: ['pipelines'] })
      toast.success('Pipeline created', { description: 'Opening the visual editor…' })
      onOpenChange(false)
      setName('')
      navigate(`/pipelines/${pipeline.id}`)
    },
    onError: (error: Error) => toast.error('Could not create pipeline', { description: error.message }),
  })

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader eyebrow="New pipeline" title="Create a pipeline" description="Compose source, retrieval and generation nodes in the visual editor." />
        <DialogBody className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-[11.5px] font-medium text-muted">Pipeline name</label>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Contract QA pipeline" autoFocus />
          </div>
          <div className="space-y-1.5">
            <label className="text-[11.5px] font-medium text-muted">Project</label>
            <Select
              value={project}
              onValueChange={setProject}
              options={(projects ?? []).map((p) => ({ value: p.id, label: p.name }))}
            />
          </div>
          <div className="space-y-2">
            <label className="text-[11.5px] font-medium text-muted">Template</label>
            <div className="grid grid-cols-2 gap-2">
              {[
                { id: 'starter', title: 'Starter graph', description: 'Document source node preconfigured.' },
                { id: 'blank', title: 'Blank canvas', description: 'Build entirely from scratch.' },
              ].map((option) => (
                <button
                  key={option.id}
                  type="button"
                  onClick={() => setTemplate(option.id as 'starter' | 'blank')}
                  className={cn(
                    'rounded-lg border p-3 text-left transition-colors',
                    template === option.id ? 'border-accent/60 bg-accent/[0.07]' : 'border-line bg-[#0b111b] hover:border-line-strong',
                  )}
                >
                  <p className="text-[11.5px] font-medium text-ink">{option.title}</p>
                  <p className="mt-1 text-[10px] leading-relaxed text-dim">{option.description}</p>
                </button>
              ))}
            </div>
          </div>
        </DialogBody>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button variant="primary" disabled={!name.trim() || mutation.isPending} onClick={() => mutation.mutate()}>
            {mutation.isPending && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            Create pipeline
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function NotificationsPanel({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const navigate = useNavigate()
  const notifications = useAppStore((s) => s.notifications)
  const markAllRead = useAppStore((s) => s.markAllRead)
  if (!open) return null
  return (
    <div className="fixed inset-0 z-[90]">
      <div className="absolute inset-0 bg-black/35" onClick={() => onOpenChange(false)} />
      <aside className="absolute inset-y-0 right-0 flex w-[360px] flex-col border-l border-line-strong bg-[#0c131e] shadow-pop animate-slide-up">
        <div className="flex items-center justify-between border-b border-line px-4 py-3.5">
          <div>
            <p className="text-[12.5px] font-medium text-ink">Notifications</p>
            <p className="mt-0.5 font-mono text-[9px] uppercase tracking-wider text-dim">{notifications.filter((n) => !n.read).length} unread</p>
          </div>
          <div className="flex items-center gap-1">
            <button onClick={markAllRead} className="rounded px-2 py-1 text-[10px] text-muted hover:bg-white/5 hover:text-ink">Mark all read</button>
            <button onClick={() => onOpenChange(false)} className="rounded p-1.5 text-dim hover:bg-white/5 hover:text-ink" aria-label="Close notifications">
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto">
          {notifications.map((notification) => (
            <button
              key={notification.id}
              onClick={() => {
                markAllRead()
                onOpenChange(false)
                if (notification.id === 'n1') navigate('/evaluation')
                else if (notification.id === 'n2') navigate('/datasets')
                else if (notification.id === 'n3') navigate('/custom-nodes')
                else navigate('/runs/run_2485')
              }}
              className={cn(
                'flex w-full gap-3 border-b border-line/60 px-4 py-3.5 text-left transition-colors hover:bg-white/[0.025]',
                !notification.read && 'bg-accent/[0.025]',
              )}
            >
              <span className="mt-1 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-line bg-[#101a28]">
                <StatusDot status={notification.type === 'success' ? 'success' : notification.type === 'warning' ? 'warning' : 'accent'} />
              </span>
              <span className="min-w-0 flex-1">
                <span className="flex items-center gap-2">
                  <span className="truncate text-[11.5px] font-medium text-ink">{notification.title}</span>
                  {!notification.read && <span className="h-1 w-1 shrink-0 rounded-full bg-accent" />}
                </span>
                <span className="mt-1 block text-[10.5px] leading-relaxed text-muted">{notification.body}</span>
                <span className="mt-1.5 block font-mono text-[8.5px] text-dim">{notification.time}</span>
              </span>
            </button>
          ))}
        </div>
        <div className="border-t border-line p-3">
          <Button variant="secondary" className="w-full" onClick={() => { markAllRead(); toast.success('All notifications marked as read') }}>
            Clear notification center
          </Button>
        </div>
      </aside>
    </div>
  )
}

interface ShortcutGroup {
  label: string
  shortcuts: Array<[string, string]>
}

const shortcutGroups: ShortcutGroup[] = [
  {
    label: 'Global',
    shortcuts: [
      ['⌘ K', 'Search anything'],
      ['⌘ J', 'Open command menu'],
      ['⌘ ,', 'Open settings'],
      ['Esc', 'Close dialog or palette'],
    ],
  },
  {
    label: 'Pipeline editor',
    shortcuts: [
      ['⌘ S', 'Save pipeline'],
      ['⇧ ⌘ R', 'Run pipeline'],
      ['⌘ Z', 'Undo'],
      ['⇧ ⌘ Z', 'Redo'],
      ['Del', 'Delete selected node'],
      ['Drag', 'Move node on canvas'],
      ['Scroll', 'Zoom canvas'],
    ],
  },
  {
    label: 'Code editor',
    shortcuts: [
      ['⌘ /', 'Toggle comment'],
      ['⌥ ↑ / ↓', 'Move line'],
      ['⇧ ⌥ F', 'Format document'],
      ['F5', 'Run node tests'],
    ],
  },
]

function ShortcutsDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="lg">
        <DialogHeader eyebrow="Help" title="Keyboard shortcuts" description="Work faster across the studio. Shortcuts adapt to the active editor." />
        <DialogBody className="space-y-5">
          {shortcutGroups.map((group) => (
            <div key={group.label}>
              <p className="eyebrow mb-2">{group.label}</p>
              <div className="overflow-hidden rounded-md border border-line">
                {group.shortcuts.map(([keys, action], i) => (
                  <div key={action} className={cn('flex items-center justify-between px-3 py-2', i > 0 && 'border-t border-line/60')}>
                    <span className="text-[11px] text-muted">{action}</span>
                    <span className="flex items-center gap-1">
                      {keys.split(' ').map((key) => (
                        <Kbd key={key}>{key}</Kbd>
                      ))}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </DialogBody>
        <DialogFooter>
          <Button variant="primary" onClick={() => onOpenChange(false)}>Done</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function AboutDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="md">
        <DialogHeader eyebrow="About" title="RAG Studio" description="A local-first studio for retrieval-augmented generation." />
        <DialogBody className="space-y-4">
          <div className="rounded-lg border border-line bg-[#0b111b] p-4">
            <div className="flex items-center gap-2">
              <span className="flex h-8 w-8 items-center justify-center rounded-md bg-gradient-to-br from-[#7296FF] to-[#4A6BE0] font-mono text-[14px] font-bold text-white">R</span>
              <div>
                <p className="text-[12px] font-medium text-ink">RAG STUDIO <span className="ml-1 font-mono text-[9px] text-dim">v0.8.2</span></p>
                <p className="font-mono text-[9px] text-dim">Python 3.11 · local workspace</p>
              </div>
            </div>
            <p className="mt-3 text-[11px] leading-relaxed text-muted">
              Design retrieval pipelines, write custom Python components, evaluate quality with RAGAS and ship grounded
              answers — all from one workspace.
            </p>
          </div>
          <div className="grid grid-cols-3 gap-2">
            {[
              ['Pipelines', '38'],
              ['Evaluations', '1,248'],
              ['Datasets', '8'],
            ].map(([label, value]) => (
              <div key={label} className="rounded border border-line/70 bg-[#0b111b] px-3 py-2 text-center">
                <p className="text-[16px] font-semibold text-ink">{value}</p>
                <p className="font-mono text-[8.5px] uppercase tracking-wider text-dim">{label}</p>
              </div>
            ))}
          </div>
        </DialogBody>
        <DialogFooter>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>Close</Button>
          <Button variant="primary" onClick={() => { onOpenChange(false); window.open('https://ragstudio.dev', '_blank', 'noopener') }}>
            Documentation
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
