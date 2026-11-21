import * as React from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Bell,
  BookOpen,
  ChevronDown,
  CircleHelp,
  Download,
  FilePlus2,
  Keyboard,
  LayoutDashboard,
  PanelLeft,
  Play,
  Plus,
  Redo2,
  Save,
  Search,
  ShieldCheck,
  SquareTerminal,
  Undo2,
  Workflow,
  X,
  Zap,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Kbd, StatusDot } from '@/components/ui/badge'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown'
import { projectsApi } from '@/api/projects.api'
import { useAppStore } from '@/store/useAppStore'
import { usePipelineStore } from '@/store/usePipelineStore'
import { bus } from '@/lib/bus'
import { cn } from '@/lib/utils'

function Logo() {
  return (
    <div className="flex items-center gap-2.5">
      <div className="relative flex h-[21px] w-[21px] items-center justify-center overflow-hidden rounded-[5px] bg-gradient-to-br from-[#7296FF] to-[#4A6BE0] shadow-[0_0_14px_rgba(90,120,250,0.3)]">
        <span className="relative z-10 font-mono text-[12px] font-bold leading-none text-white">R</span>
        <div className="absolute inset-x-0 top-0 h-1/2 bg-white/15" />
      </div>
      <span className="text-[12.5px] font-semibold tracking-[0.065em] text-ink">RAG STUDIO</span>
    </div>
  )
}

export function TopBar() {
  const navigate = useNavigate()
  const setCommandOpen = useAppStore((s) => s.setCommandOpen)
  const setCreateProjectOpen = useAppStore((s) => s.setCreateProjectOpen)
  const setCreatePipelineOpen = useAppStore((s) => s.setCreatePipelineOpen)
  const setShortcutsOpen = useAppStore((s) => s.setShortcutsOpen)
  const setAboutOpen = useAppStore((s) => s.setAboutOpen)
  const setNotificationsOpen = useAppStore((s) => s.setNotificationsOpen)
  const setMobileNav = useAppStore((s) => s.setMobileNav)
  const notifications = useAppStore((s) => s.notifications)
  const toggleSidebar = useAppStore((s) => s.toggleSidebar)
  const unread = notifications.filter((n) => !n.read).length
  const { data: workspace } = useQuery({ queryKey: ['workspace'], queryFn: projectsApi.workspace, staleTime: Infinity })

  const undo = usePipelineStore((s) => s.undo)
  const redo = usePipelineStore((s) => s.redo)
  const canUndo = usePipelineStore((s) => s.history.length > 0)
  const canRedo = usePipelineStore((s) => s.future.length > 0)

  React.useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const mod = event.metaKey || event.ctrlKey
      if (mod && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setCommandOpen(true)
      }
      if (mod && event.key === ',') {
        event.preventDefault()
        navigate('/settings')
      }
      if (mod && event.key.toLowerCase() === 's') {
        event.preventDefault()
        bus.emit('pipeline:save')
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [navigate, setCommandOpen])

  return (
    <header className="relative z-40 flex h-[46px] shrink-0 items-center border-b border-line bg-[#0a1019] px-3.5">
      <button
        onClick={() => setMobileNav(true)}
        className="mr-2 rounded p-1.5 text-muted hover:bg-white/5 hover:text-ink lg:hidden"
        aria-label="Open navigation"
      >
        <PanelLeft className="h-4 w-4" />
      </button>
      <Logo />

      <nav className="ml-7 hidden items-center md:flex">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button className="rounded px-2 py-1 text-[11px] text-muted outline-none transition-colors hover:bg-white/[0.04] hover:text-ink data-[state=open]:bg-white/[0.05] data-[state=open]:text-ink">
              File
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-56">
            <DropdownMenuLabel>Create</DropdownMenuLabel>
            <DropdownMenuItem icon={<FilePlus2 className="h-3.5 w-3.5" />} onSelect={() => setCreateProjectOpen(true)}>
              New project
            </DropdownMenuItem>
            <DropdownMenuItem icon={<Workflow className="h-3.5 w-3.5" />} onSelect={() => setCreatePipelineOpen(true)}>
              New pipeline
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem icon={<Save className="h-3.5 w-3.5" />} shortcut="⌘S" onSelect={() => bus.emit('pipeline:save')}>
              Save pipeline
            </DropdownMenuItem>
            <DropdownMenuItem icon={<Download className="h-3.5 w-3.5" />} onSelect={() => bus.emit('pipeline:export')}>
              Export pipeline
            </DropdownMenuItem>
            <DropdownMenuItem icon={<SquareTerminal className="h-3.5 w-3.5" />} onSelect={() => bus.emit('pipeline:export-python')}>
              Export Python script
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem icon={<LayoutDashboard className="h-3.5 w-3.5" />} onSelect={() => navigate('/')}>
              Open dashboard
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button className="rounded px-2 py-1 text-[11px] text-muted outline-none transition-colors hover:bg-white/[0.04] hover:text-ink data-[state=open]:bg-white/[0.05] data-[state=open]:text-ink">
              Edit
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-52">
            <DropdownMenuItem icon={<Undo2 className="h-3.5 w-3.5" />} shortcut="⌘Z" disabled={!canUndo} onSelect={() => undo()}>
              Undo
            </DropdownMenuItem>
            <DropdownMenuItem icon={<Redo2 className="h-3.5 w-3.5" />} shortcut="⇧⌘Z" disabled={!canRedo} onSelect={() => redo()}>
              Redo
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem icon={<Search className="h-3.5 w-3.5" />} shortcut="⌘K" onSelect={() => setCommandOpen(true)}>
              Find anything
            </DropdownMenuItem>
            <DropdownMenuItem icon={<X className="h-3.5 w-3.5" />} shortcut="Del" onSelect={() => bus.emit('pipeline:delete-selected')}>
              Delete selected node
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem icon={<PanelLeft className="h-3.5 w-3.5" />} onSelect={toggleSidebar}>
              Toggle navigation
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button className="rounded px-2 py-1 text-[11px] text-muted outline-none transition-colors hover:bg-white/[0.04] hover:text-ink data-[state=open]:bg-white/[0.05] data-[state=open]:text-ink">
              View
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-52">
            <DropdownMenuLabel>Workspace</DropdownMenuLabel>
            <DropdownMenuItem onSelect={() => navigate('/')}>Dashboard</DropdownMenuItem>
            <DropdownMenuItem onSelect={() => navigate('/projects')}>Projects</DropdownMenuItem>
            <DropdownMenuItem onSelect={() => navigate('/pipelines')}>Pipelines</DropdownMenuItem>
            <DropdownMenuItem onSelect={() => navigate('/runs/run_2486')}>Execution monitor</DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuLabel>Quality</DropdownMenuLabel>
            <DropdownMenuItem onSelect={() => navigate('/evaluation')}>Evaluation dashboard</DropdownMenuItem>
            <DropdownMenuItem onSelect={() => navigate('/experiments')}>Experiments</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button className="rounded px-2 py-1 text-[11px] text-muted outline-none transition-colors hover:bg-white/[0.04] hover:text-ink data-[state=open]:bg-white/[0.05] data-[state=open]:text-ink">
              Pipeline
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-56">
            <DropdownMenuItem icon={<ShieldCheck className="h-3.5 w-3.5" />} onSelect={() => bus.emit('pipeline:validate')}>
              Validate graph
            </DropdownMenuItem>
            <DropdownMenuItem icon={<Play className="h-3.5 w-3.5" />} shortcut="⇧⌘R" onSelect={() => bus.emit('pipeline:run')}>
              Run pipeline
            </DropdownMenuItem>
            <DropdownMenuItem icon={<SquareTerminal className="h-3.5 w-3.5" />} onSelect={() => bus.emit('pipeline:debug')}>
              Debug run
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem icon={<Zap className="h-3.5 w-3.5" />} onSelect={() => navigate('/runs/run_2486/results')}>
              Inspect last results
            </DropdownMenuItem>
            <DropdownMenuItem icon={<Plus className="h-3.5 w-3.5" />} onSelect={() => setCreatePipelineOpen(true)}>
              New pipeline
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button className="rounded px-2 py-1 text-[11px] text-muted outline-none transition-colors hover:bg-white/[0.04] hover:text-ink data-[state=open]:bg-white/[0.05] data-[state=open]:text-ink">
              Help
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-56">
            <DropdownMenuItem icon={<Keyboard className="h-3.5 w-3.5" />} onSelect={() => setShortcutsOpen(true)}>
              Keyboard shortcuts
            </DropdownMenuItem>
            <DropdownMenuItem icon={<BookOpen className="h-3.5 w-3.5" />} onSelect={() => navigate('/nodes')}>
              Node documentation
            </DropdownMenuItem>
            <DropdownMenuItem icon={<CircleHelp className="h-3.5 w-3.5" />} onSelect={() => setAboutOpen(true)}>
              About RAG Studio
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </nav>

      <div className="flex flex-1 justify-center px-4">
        <button
          onClick={() => setCommandOpen(true)}
          className="group flex h-[28px] w-full max-w-[390px] items-center gap-2 rounded-md border border-line/80 bg-[#0c131e] px-2.5 text-left transition-colors hover:border-line-strong hover:bg-[#0e1622]"
        >
          <Search className="h-3.5 w-3.5 text-dim group-hover:text-muted" />
          <span className="flex-1 truncate text-[11px] text-dim">Search anything…</span>
          <Kbd>⌘</Kbd>
          <Kbd>K</Kbd>
        </button>
      </div>

      <div className="flex items-center gap-2">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button className="hidden items-center gap-1.5 rounded px-2 py-1 font-mono text-[9px] uppercase tracking-[0.1em] text-dim transition-colors hover:text-muted sm:flex">
              <StatusDot status="success" />
              Local workspace
              <ChevronDown className="h-3 w-3" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-60">
            <DropdownMenuLabel>Environment</DropdownMenuLabel>
            <DropdownMenuItem icon={<StatusDot status="success" />} onSelect={() => {}}>
              Local workspace
            </DropdownMenuItem>
            <DropdownMenuItem icon={<StatusDot status="accent" />} onSelect={() => navigate('/settings')}>
              Development
            </DropdownMenuItem>
            <DropdownMenuItem icon={<StatusDot status="idle" />} onSelect={() => navigate('/settings')}>
              Production
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem icon={<ShieldCheck className="h-3.5 w-3.5" />} onSelect={() => navigate('/settings')}>
              Manage environments
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>

        <button
          onClick={() => setNotificationsOpen(true)}
          className="relative flex h-7 w-7 items-center justify-center rounded text-muted transition-colors hover:bg-white/[0.05] hover:text-ink"
          aria-label={`Notifications${unread ? `, ${unread} unread` : ''}`}
        >
          <Bell className="h-[15px] w-[15px]" />
          {unread > 0 && <span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full border border-[#0a1019] bg-accent" />}
        </button>

        <div className="hidden items-center gap-2 border-l border-line pl-2 xl:flex">
          <span className="flex h-[21px] w-[21px] items-center justify-center rounded-full border border-[#33415a] bg-[#182235] font-mono text-[8.5px] text-ink">AM</span>
          <span className="max-w-[90px] truncate text-[10.5px] text-muted">{workspace?.role ?? 'Owner'}</span>
        </div>

        <div className="hidden items-center gap-1 pl-1 sm:flex">
          <button aria-label="Toggle navigation" onClick={toggleSidebar} className="flex h-6 w-6 items-center justify-center rounded text-dim hover:bg-white/5 hover:text-muted">
            <PanelLeft className="h-3.5 w-3.5" />
          </button>
          <button aria-label="Keyboard shortcuts" onClick={() => setShortcutsOpen(true)} className="flex h-6 w-6 items-center justify-center rounded text-dim hover:bg-white/5 hover:text-muted">
            <Keyboard className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </header>
  )
}
