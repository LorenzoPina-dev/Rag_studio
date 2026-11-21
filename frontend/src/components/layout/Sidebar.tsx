import * as React from 'react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  BarChart3,
  BookOpen,
  Box,
  Boxes,
  ChevronDown,
  Code2,
  Database,
  FlaskConical,
  Folder,
  LayoutGrid,
  Settings,
  Sparkles,
  Workflow,
  X,
  Check,
  Plus,
  LifeBuoy,
  Loader2,
  ScrollText,
} from 'lucide-react'
import { checkApiHealth } from '@/api/client'
import { projectsApi } from '@/api/projects.api'
import { providersApi } from '@/api/providers.api'
import { useAppStore } from '@/store/useAppStore'
import { cn } from '@/lib/utils'
import { StatusDot } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogBody, DialogContent, DialogFooter, DialogHeader } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown'
import { toast } from 'sonner'

const navItems = [
  { to: '/', label: 'Dashboard', icon: LayoutGrid, end: true },
  { to: '/projects', label: 'Projects', icon: Folder },
  { to: '/pipelines', label: 'Pipelines', icon: Workflow },
  { to: '/nodes', label: 'Node Library', icon: Boxes },
  { to: '/custom-nodes', label: 'Custom Nodes', icon: Code2 },
  { to: '/datasets', label: 'Datasets', icon: Database },
  { to: '/models', label: 'Models', icon: Box },
  { to: '/experiments', label: 'Experiments', icon: FlaskConical },
  { to: '/evaluation', label: 'Evaluation', icon: BarChart3 },
  { to: '/settings', label: 'Settings', icon: Settings },
]

function WorkspaceSwitcher({ compact }: { compact?: boolean }) {
  const [open, setOpen] = React.useState(false)
  const [createOpen, setCreateOpen] = React.useState(false)
  const [name, setName] = React.useState('')
  const [active, setActive] = React.useState('Research lab')
  const workspaces = [
    { name: 'Research lab', detail: 'Team workspace' },
    { name: 'Personal sandbox', detail: 'Personal workspace' },
    { name: 'Acme Labs', detail: 'Team workspace' },
  ]

  if (compact) {
    return (
      <div className="flex justify-center py-2">
        <div className="flex h-7 w-7 items-center justify-center rounded border border-line-strong bg-surface2 text-ink">R</div>
      </div>
    )
  }

  return (
    <>
      <DropdownMenu open={open} onOpenChange={setOpen}>
        <DropdownMenuTrigger asChild>
          <button className="group flex w-full items-center gap-2.5 rounded-md border border-line/80 bg-[#0f1723] px-2.5 py-2 text-left transition-colors hover:border-line-strong">
            <span className="flex h-6 w-6 items-center justify-center rounded-[5px] border border-[#2d3d57] bg-[#172236] text-ink/90">
              <Sparkles className="h-3 w-3" />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[11.5px] font-medium leading-tight text-ink">{active}</span>
              <span className="mt-0.5 block text-[9.5px] leading-tight text-dim">Team workspace</span>
            </span>
            <ChevronDown className="h-3 w-3 shrink-0 text-dim transition-transform group-data-[state=open]:rotate-180" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="w-[230px]">
          <DropdownMenuLabel>Workspaces</DropdownMenuLabel>
          {workspaces.map((ws) => (
            <DropdownMenuItem
              key={ws.name}
              onSelect={() => {
                setActive(ws.name)
                toast.success(`Switched to ${ws.name}`)
              }}
              icon={active === ws.name ? <Check className="h-3.5 w-3.5 text-accent" /> : <span className="h-3.5 w-3.5" />}
            >
              <span className="block text-[11.5px]">{ws.name}</span>
              <span className="block text-[9.5px] text-dim">{ws.detail}</span>
            </DropdownMenuItem>
          ))}
          <DropdownMenuSeparator />
          <DropdownMenuItem icon={<Plus className="h-3.5 w-3.5" />} onSelect={() => setCreateOpen(true)}>
            Create workspace
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent size="sm">
          <DialogHeader title="Create workspace" description="Workspaces group projects, datasets and evaluation suites." eyebrow="Workspace" />
          <DialogBody>
            <div className="space-y-1.5">
              <label className="text-[11.5px] text-muted">Workspace name</label>
              <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Retrieval platform" autoFocus />
            </div>
            <div className="mt-3 space-y-1.5">
              <label className="text-[11.5px] text-muted">Plan</label>
              <div className="rounded-md border border-line bg-[#0b111b] px-3 py-2.5 text-[11px] text-muted">Team workspace · unlimited projects</div>
            </div>
          </DialogBody>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setCreateOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              disabled={!name.trim()}
              onClick={() => {
                setActive(name.trim())
                setCreateOpen(false)
                setName('')
                toast.success('Workspace created')
              }}
            >
              Create workspace
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}

function SystemStatusCard() {
  const [open, setOpen] = React.useState(false)
  const [checking, setChecking] = React.useState(false)
  const { data } = useQuery({ queryKey: ['system-status'], queryFn: projectsApi.systemStatus, staleTime: 30_000, refetchInterval: 60_000 })

  const runHealthCheck = React.useCallback(async () => {
    setChecking(true)
    const started = performance.now()
    try {
      const [health, providers] = await Promise.all([checkApiHealth(), providersApi.getStatus()])
      const elapsed = Math.round(performance.now() - started)
      if (health.status !== 'ok') throw new Error(`API health reported "${health.status}"`)
      const available = [
        providers.huggingface_available,
        providers.ollama_running,
        providers.openai_configured,
      ].filter(Boolean).length
      toast.success('Health check completed', {
        description: `API ok · ${available}/3 provider disponibili · ${elapsed}ms`,
      })
    } catch (error) {
      const elapsed = Math.round(performance.now() - started)
      toast.error('Health check failed', { description: `${(error as Error).message} · ${elapsed}ms` })
    } finally {
      setChecking(false)
    }
  }, [])

  const services = [
    { name: 'API gateway', detail: 'api · 12ms', status: 'operational' },
    { name: 'PostgreSQL', detail: 'workspace-db · 4ms', status: 'operational' },
    { name: 'Redis queue', detail: 'celery broker · idle', status: 'operational' },
    { name: 'MinIO storage', detail: 'artifacts · 8.2 GB', status: 'operational' },
    { name: 'Qdrant vector store', detail: '4 collections', status: 'operational' },
    { name: 'GPU worker', detail: 'CUDA:0 · RTX 4090', status: 'operational' },
  ]
  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="w-full rounded-md border border-line/80 bg-[#0e1622] px-3 py-2.5 text-left transition-colors hover:border-line-strong"
      >
        <div className="flex items-center gap-2">
          <StatusDot status="success" pulse />
          <span className="text-[10.5px] font-medium text-[#b9e8d8]">All systems operational</span>
        </div>
        <p className="mt-2 font-mono text-[9.5px] text-dim">{data?.python ?? 'Python 3.11'} · local</p>
        <div className="mt-1 flex items-center gap-2 font-mono text-[9px] text-[#4f5d73]">
          <span>{data?.version ?? 'v0.8.2'}</span>
          <span className="text-[#3a475c]">·</span>
          <span className="underline decoration-[#394659] underline-offset-2 transition-colors hover:text-muted">Release notes</span>
        </div>
      </button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent size="md">
          <DialogHeader eyebrow="Local workspace" title="System status" description="Runtime services connected to this development workspace." />
          <DialogBody className="space-y-1">
            {services.map((service) => (
              <div key={service.name} className="flex items-center justify-between rounded-md border border-line/70 bg-[#0b111b] px-3 py-2.5">
                <div>
                  <p className="text-[11.5px] text-ink">{service.name}</p>
                  <p className="mt-0.5 font-mono text-[9px] text-dim">{service.detail}</p>
                </div>
                <span className="flex items-center gap-1.5 font-mono text-[9px] uppercase tracking-wider text-success">
                  <StatusDot status="success" /> Operational
                </span>
              </div>
            ))}
            <div className="mt-3 flex items-center justify-between rounded-md border border-line/70 bg-[#0b111b] px-3 py-2.5 font-mono text-[9.5px] text-dim">
              <span>RAG STUDIO {data?.version ?? 'v0.8.2'} · {data?.python ?? 'Python 3.11.8'}</span>
              <span className="text-muted">main*</span>
            </div>
          </DialogBody>
          <DialogFooter>
            <Button variant="secondary" onClick={() => setOpen(false)}>
              Close
            </Button>
            <Button
              variant="primary"
              disabled={checking}
              onClick={() => {
                setOpen(false)
                void runHealthCheck()
              }}
            >
              {checking ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null} {checking ? 'Checking…' : 'Run health check'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}

export function Sidebar() {
  const collapsed = useAppStore((s) => s.sidebarCollapsed)
  const mobileNavOpen = useAppStore((s) => s.mobileNavOpen)
  const setMobileNav = useAppStore((s) => s.setMobileNav)
  const location = useLocation()
  const navigate = useNavigate()
  const [aboutOpen, setAboutOpen] = React.useState(false)

  const nav = (
    <>
      <div className={cn('shrink-0 px-3 pb-2 pt-3', collapsed && 'px-2')}>
        <WorkspaceSwitcher compact={collapsed} />
      </div>
      <div className={cn('flex min-h-0 flex-1 flex-col overflow-y-auto pb-2', collapsed ? 'px-2' : 'px-2')}>
        {!collapsed && <p className="px-2.5 pb-1.5 pt-3 font-mono text-[8.5px] uppercase tracking-[0.18em] text-[#4e5b70]">Workspace</p>}
        <nav className="space-y-0.5" aria-label="Primary">
          {navItems.map((item) => {
            const active = item.end ? location.pathname === '/' : location.pathname.startsWith(item.to)
            return (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={() => setMobileNav(false)}
                className={cn(
                  'group relative flex items-center gap-2.5 rounded-[5px] py-[7px] text-[11.5px] transition-colors',
                  collapsed ? 'justify-center px-2' : 'px-2.5',
                  active ? 'bg-[#16213a] text-ink' : 'text-[#8c97aa] hover:bg-white/[0.035] hover:text-ink',
                )}
                title={collapsed ? item.label : undefined}
              >
                {active && <span className="absolute left-0 top-1/2 h-4 w-[2px] -translate-y-1/2 rounded-r bg-accent" />}
                <item.icon className={cn('h-[14px] w-[14px] shrink-0', active ? 'text-[#9db1ff]' : 'text-[#69768c] group-hover:text-muted')} strokeWidth={1.7} />
                {!collapsed && <span className="truncate">{item.label}</span>}
                {!collapsed && active && <span className="ml-auto h-1 w-1 rounded-full bg-accent/80" />}
              </NavLink>
            )
          })}
        </nav>
        {!collapsed && (
          <div className="mt-4 border-t border-line/60 pt-3">
            <p className="px-2.5 pb-1 font-mono text-[8.5px] uppercase tracking-[0.18em] text-[#4e5b70]">Resources</p>
            <button
              onClick={() => setAboutOpen(true)}
              className="flex w-full items-center gap-2.5 rounded px-2.5 py-[7px] text-[11px] text-[#7d899d] transition-colors hover:bg-white/[0.035] hover:text-ink"
            >
              <LifeBuoy className="h-[14px] w-[14px] text-[#69768c]" strokeWidth={1.7} />
              Support & docs
            </button>
            <button
              onClick={() => {
                setAboutOpen(true)
              }}
              className="flex w-full items-center gap-2.5 rounded px-2.5 py-[7px] text-[11px] text-[#7d899d] transition-colors hover:bg-white/[0.035] hover:text-ink"
            >
              <ScrollText className="h-[14px] w-[14px] text-[#69768c]" strokeWidth={1.7} />
              Release notes
              <span className="ml-auto rounded border border-line bg-white/[0.03] px-1 py-0.5 font-mono text-[8px] text-dim">v0.8.2</span>
            </button>
          </div>
        )}
      </div>

      <div className={cn('shrink-0 space-y-2.5 border-t border-line/70 px-3 py-3', collapsed && 'px-2')}>
        {!collapsed && <SystemStatusCard />}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button className={cn('flex w-full items-center gap-2.5 rounded px-1.5 py-1 text-left transition-colors hover:bg-white/[0.035]', collapsed && 'justify-center px-0')}>
              <span className="flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-full border border-[#33415a] bg-gradient-to-br from-[#26344c] to-[#182235] font-mono text-[8.5px] text-ink">
                AM
              </span>
              {!collapsed && (
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[11px] font-medium text-ink/90">Alex Morgan</span>
                  <span className="block truncate font-mono text-[8.5px] text-dim">Owner · Research lab</span>
                </span>
              )}
              {!collapsed && <ChevronDown className="h-3 w-3 text-dim" />}
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-56">
            <DropdownMenuLabel>Alex Morgan</DropdownMenuLabel>
            <DropdownMenuItem onSelect={() => setAboutOpen(true)}>Account & profile</DropdownMenuItem>
            <DropdownMenuItem onSelect={() => navigate('/settings')}>Workspace settings</DropdownMenuItem>
            <DropdownMenuItem onSelect={() => setAboutOpen(true)}>Keyboard shortcuts</DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onSelect={() => toast.info('You are already signed in as Alex Morgan.')}>Sign out</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <Dialog open={aboutOpen} onOpenChange={setAboutOpen}>
        <DialogContent size="md">
          <DialogHeader eyebrow="RAG Studio v0.8.2" title="About this workspace" description="A local-first studio for building retrieval-augmented generation systems." />
          <DialogBody className="space-y-3">
            <div className="grid grid-cols-2 gap-2">
              {[
                ['Workspace', 'Research lab'],
                ['Role', 'Owner'],
                ['Runtime', 'Python 3.11.8'],
                ['Branch', 'main*'],
                ['Storage', 'MinIO · 8.2 GB'],
                ['Region', 'local'],
              ].map(([label, value]) => (
                <div key={label} className="rounded border border-line/70 bg-[#0b111b] px-3 py-2">
                  <p className="font-mono text-[8.5px] uppercase tracking-wider text-dim">{label}</p>
                  <p className="mt-1 text-[11px] text-ink">{value}</p>
                </div>
              ))}
            </div>
            <div className="rounded-md border border-line bg-[#0b111b] p-3">
              <p className="text-[11px] font-medium text-ink">Keyboard shortcuts</p>
              <div className="mt-2 space-y-1.5 font-mono text-[10px] text-muted">
                <div className="flex justify-between"><span>Search anything</span><span className="text-dim">⌘ K</span></div>
                <div className="flex justify-between"><span>Save pipeline</span><span className="text-dim">⌘ S</span></div>
                <div className="flex justify-between"><span>Run pipeline</span><span className="text-dim">⇧ ⌘ R</span></div>
                <div className="flex justify-between"><span>Command menu</span><span className="text-dim">⌘ J</span></div>
              </div>
            </div>
          </DialogBody>
          <DialogFooter>
            <Button variant="secondary" onClick={() => setAboutOpen(false)}>Close</Button>
            <Button variant="primary" onClick={() => { setAboutOpen(false); useAppStore.getState().setShortcutsOpen(true) }}>Open shortcuts</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )

  return (
    <>
      <aside
        className={cn(
          'hidden shrink-0 flex-col border-r border-line bg-[#0b111a] transition-[width] duration-200 lg:flex',
          collapsed ? 'w-[60px]' : 'w-[218px]',
        )}
      >
        {nav}
      </aside>

      {mobileNavOpen && (
        <div className="fixed inset-0 z-[80] lg:hidden">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setMobileNav(false)} />
          <aside className="absolute inset-y-0 left-0 flex w-[248px] flex-col border-r border-line bg-[#0b111a] shadow-pop animate-slide-up">
            <div className="flex h-[46px] shrink-0 items-center justify-between border-b border-line px-4">
              <span className="text-[12px] font-semibold tracking-wide text-ink">RAG STUDIO</span>
              <button onClick={() => setMobileNav(false)} className="rounded p-1 text-dim hover:bg-white/5 hover:text-ink" aria-label="Close navigation">
                <X className="h-4 w-4" />
              </button>
            </div>
            {nav}
          </aside>
        </div>
      )}

    </>
  )
}
