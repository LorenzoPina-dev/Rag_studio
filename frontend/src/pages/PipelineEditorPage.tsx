import * as React from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Background,
  BackgroundVariant,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  useViewport,
  type NodeChange,
  type NodeProps,
  type NodeTypes,
} from '@xyflow/react'
import {
  Bug,
  Check,
  CheckCircle2,
  ChevronDown,
  Copy,
  Download,
  Link2,
  Loader2,
  Minus,
  Play,
  Plus,
  Redo2,
  Save,
  Share2,
  Square,
  SquareTerminal,
  Trash2,
  Undo2,
  Users,
  Workflow,
} from 'lucide-react'
import { toast } from 'sonner'
import { pipelinesApi } from '@/api/pipelines.api'
import { nodesApi } from '@/api/nodes.api'
import { usePipelineStore, type RagFlowNode } from '@/store/usePipelineStore'
import { activeExecution, useActiveExecution } from '@/lib/activeExecution'
import { bus } from '@/lib/bus'
import { registerRunNavigation } from '@/lib/runNavigation'
import { cn } from '@/lib/utils'
import { connectionIsCompatible } from '@/lib/portCompatibility'
import type { Execution, Pipeline } from '@/types'
import { RAGNode } from '@/components/pipeline/RAGNode'
import { RAGEdge } from '@/components/pipeline/RAGEdge'
import { NodeLibrary } from '@/components/pipeline/NodeLibrary'
import { NodeInspector } from '@/components/pipeline/NodeInspector'
import { OutputPreview } from '@/components/pipeline/OutputPreview'
import { Breadcrumbs } from '@/components/shared/page'
import { Button } from '@/components/ui/button'
import { StatusDot } from '@/components/ui/badge'
import { Select } from '@/components/ui/select'
import { Dialog, DialogBody, DialogContent, DialogFooter, DialogHeader } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { ErrorState } from '@/components/ui/badge'
import { nodeDefById } from '@/api/mock/pipelineSeed'

const nodeTypes = { rag: RAGNode as unknown as React.ComponentType<NodeProps> } as NodeTypes
const edgeTypes = { rag: RAGEdge }

function GroupLabel({ data }: NodeProps) {
  return (
    <div className="pointer-events-none select-none font-mono text-[9px] uppercase tracking-[0.14em] text-[#5f6d83]">
      {(data as { label: string }).label}
    </div>
  )
}

function CalloutNode({ data }: NodeProps) {
  return (
    <div className="pointer-events-none flex w-[268px] select-none items-center gap-2 rounded border border-[#253348] bg-[#0c141f]/95 px-2.5 py-2 text-[9px] text-[#8090a6] shadow-[0_4px_16px_rgba(0,0,0,0.25)] backdrop-blur-sm">
      <span className="text-[#63728a]">↳</span>
      {(data as { text: string }).text}
    </div>
  )
}

const canvasNodeTypes = {
  rag: RAGNode as unknown as React.ComponentType<NodeProps>,
  'group-label': GroupLabel as unknown as React.ComponentType<NodeProps>,
  callout: CalloutNode as unknown as React.ComponentType<NodeProps>,
} as NodeTypes

function ZoomControls() {
  const { zoomIn, zoomOut, fitView } = useReactFlow()
  const { zoom } = useViewport()
  return (
    <div className="absolute bottom-3 left-3 z-10 flex items-center gap-0.5 rounded-md border border-[#27354a] bg-[#0b121c]/95 px-1 py-1 shadow-[0_8px_24px_rgba(0,0,0,0.4)] backdrop-blur">
      <button onClick={() => zoomOut({ duration: 180 })} className="flex h-5 w-5 items-center justify-center rounded text-dim hover:bg-white/5 hover:text-ink" aria-label="Zoom out">
        <Minus className="h-3 w-3" />
      </button>
      <span className="min-w-[34px] text-center font-mono text-[8.5px] text-[#8b98ac]">{Math.round(zoom * 100)}%</span>
      <button onClick={() => zoomIn({ duration: 180 })} className="flex h-5 w-5 items-center justify-center rounded text-dim hover:bg-white/5 hover:text-ink" aria-label="Zoom in">
        <Plus className="h-3 w-3" />
      </button>
      <div className="mx-0.5 h-3 w-px bg-line" />
      <button onClick={() => fitView({ duration: 260, padding: 0.15 })} className="flex h-5 w-5 items-center justify-center rounded text-dim hover:bg-white/5 hover:text-ink" aria-label="Fit view">
        <svg viewBox="0 0 16 16" className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth={1.3}>
          <path d="M2 5V2h3M14 11v3h-3M11 2h3v3M5 14H2v-3" />
        </svg>
      </button>
    </div>
  )
}

function ShareDialog({ open, onOpenChange, pipeline }: { open: boolean; onOpenChange: (open: boolean) => void; pipeline: Pipeline }) {
  const [copied, setCopied] = React.useState(false)
  const [permission, setPermission] = React.useState('Can edit')
  const link = `${window.location.origin}/pipelines/${pipeline.id}`
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="md">
        <DialogHeader eyebrow="Share pipeline" title={pipeline.name} description="Invite teammates to inspect, edit or run this pipeline." />
        <DialogBody className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-[11.5px] text-muted">Invite by email</label>
            <div className="flex gap-2">
              <Input placeholder="name@company.com" />
              <Select value={permission} onValueChange={setPermission} options={['Can edit', 'Can run', 'Can view']} className="w-[110px]" />
              <Button variant="primary" title="Non ancora implementato" onClick={() => toast.info('Azione non ancora disponibile: invito via email')}>Invite</Button>
            </div>
          </div>
          <div className="space-y-1.5">
            <label className="text-[11.5px] text-muted">Workspace link</label>
            <div className="flex items-center gap-1.5">
              <div className="flex h-8 flex-1 items-center gap-2 overflow-hidden rounded-md border border-line bg-[#0a1019] px-2.5">
                <Link2 className="h-3 w-3 shrink-0 text-dim" />
                <span className="truncate font-mono text-[9.5px] text-[#8d9bb0]">{link}</span>
              </div>
              <Button
                variant="secondary"
                onClick={() => {
                  navigator.clipboard?.writeText(link)
                  setCopied(true)
                  setTimeout(() => setCopied(false), 1500)
                  toast.success('Link copied to clipboard')
                }}
              >
                {copied ? <Check className="h-3 w-3 text-success" /> : <Copy className="h-3 w-3" />} {copied ? 'Copied' : 'Copy'}
              </Button>
            </div>
          </div>
          <div>
            <p className="mb-2 flex items-center gap-1.5 font-mono text-[8.5px] uppercase tracking-wider text-dim"><Users className="h-3 w-3" /> People with access</p>
            <p className="rounded-md border border-line bg-[#0b111b] px-3 py-2.5 font-mono text-[9px] text-dim">
              Elenco non disponibile: il backend non espone ancora un endpoint per i membri del workspace.
            </p>
          </div>
        </DialogBody>
        <DialogFooter>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>Done</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function PipelineEditorInner({ pipeline }: { pipeline: Pipeline }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [showLibrary, setShowLibrary] = React.useState(() => window.innerWidth >= 1150)
  const [showInspector, setShowInspector] = React.useState(() => window.innerWidth >= 1280)
  const [shareOpen, setShareOpen] = React.useState(false)
  const [showLogs, setShowLogs] = React.useState(false)
  const [debugMode, setDebugMode] = React.useState(false)
  const handledRunRef = React.useRef<string | null>(null)

  // The stream is owned by the app-level runtime, so the run survives
  // navigating to the results page and back.
  const active = useActiveExecution()
  const activeRun = active?.execution.pipelineId === pipeline.id ? active : null
  const running = Boolean(activeRun && !activeRun.terminal && ['queued', 'running'].includes(activeRun.execution.status))
  const activeRunId = activeRun?.execution.id ?? null
  const activeRunIdRef = React.useRef<string | null>(null)
  activeRunIdRef.current = activeRunId
  const logs = activeRun?.logs ?? []
  const { screenToFlowPosition } = useReactFlow()
  const { data: nodeCatalog } = useQuery({ queryKey: ['node-catalog'], queryFn: nodesApi.catalog, staleTime: 300_000 })
  const catalogDefById = React.useMemo(
    () => Object.fromEntries((nodeCatalog ?? []).flatMap((group) => group.nodes.map((node) => [node.id, node]))),
    [nodeCatalog],
  )

  const nodes = usePipelineStore((s) => s.nodes)
  const edges = usePipelineStore((s) => s.edges)
  const dirty = usePipelineStore((s) => s.dirty)
  const validation = usePipelineStore((s) => s.validation)
  const validating = usePipelineStore((s) => s.validating)
  const onNodesChange = usePipelineStore((s) => s.onNodesChange)
  const onEdgesChange = usePipelineStore((s) => s.onEdgesChange)
  const onConnect = usePipelineStore((s) => s.onConnect)
  const removeEdges = usePipelineStore((s) => s.removeEdges)
  const selectNode = usePipelineStore((s) => s.selectNode)
  const addNode = usePipelineStore((s) => s.addNode)
  const undo = usePipelineStore((s) => s.undo)
  const redo = usePipelineStore((s) => s.redo)
  const canUndo = usePipelineStore((s) => s.history.length > 0)
  const canRedo = usePipelineStore((s) => s.future.length > 0)
  const setEnvironment = usePipelineStore((s) => s.setEnvironment)
  const toPipeline = usePipelineStore((s) => s.toPipeline)
  const markSaved = usePipelineStore((s) => s.markSaved)
  const setValidation = usePipelineStore((s) => s.setValidation)
  const setValidating = usePipelineStore((s) => s.setValidating)
  const setNodeStatus = usePipelineStore((s) => s.setNodeStatus)
  const setLastRun = usePipelineStore((s) => s.setLastRun)
  const storedPipeline = usePipelineStore((s) => s.pipeline) ?? pipeline
  const selectedNodeId = usePipelineStore((s) => s.selectedNodeId)

  const deleteSelection = React.useCallback(() => {
    const state = usePipelineStore.getState()
    if (state.selectedNodeId) {
      state.removeNode(state.selectedNodeId)
      toast.success('Node removed')
      return true
    }
    const selectedEdges = state.edges.filter((edge) => edge.selected)
    if (selectedEdges.length > 0) {
      state.removeEdges(selectedEdges.map((edge) => edge.id))
      toast.success('Connection removed')
      return true
    }
    return false
  }, [])

  // Re-apply live node statuses after a remount (loadPipeline clears them).
  const liveNodeRuns = activeRun?.execution.nodeRuns
  React.useEffect(() => {
    if (!liveNodeRuns) return
    setNodeStatus(
      Object.fromEntries(
        liveNodeRuns.map((node) => [
          node.nodeId,
          {
            status: (node.status === 'pending' || node.status === 'skipped' ? 'idle' : node.status) as Pipeline['nodes'][number]['status'],
            durationMs: node.durationMs,
          },
        ]),
      ),
    )
  }, [liveNodeRuns, setNodeStatus])

  React.useEffect(() => {
    if (!activeRun?.terminal || handledRunRef.current === activeRun.execution.id) return
    handledRunRef.current = activeRun.execution.id
    const completed = activeRun.execution
    if (completed.status === 'completed') {
      setLastRun({
        status: 'completed',
        at: new Date().toISOString(),
        latencyMs: completed.durationMs,
        tokens: completed.tokens,
        cost: completed.cost,
        output: pipeline.description,
        sources: 5,
      })
      toast.success('Pipeline completed', {
        description: `${(completed.durationMs / 1000).toFixed(2)}s · ${completed.tokens.toLocaleString()} tokens · $${completed.cost.toFixed(4)}`,
        action: { label: 'Open run', onClick: () => navigate(`/runs/${completed.id}`) },
      })
    } else if (activeRun.error) {
      toast.error('Execution failed', { description: activeRun.error })
    }
  }, [activeRun, navigate, pipeline.description, setLastRun])

  const save = React.useCallback(
    async (notify = true) => {
      const next = toPipeline()
      if (!next) return null
      try {
        const saved = await pipelinesApi.update(next.id, next)
        markSaved(saved)
        queryClient.setQueryData(['pipeline', saved.id], saved)
        queryClient.invalidateQueries({ queryKey: ['pipelines'] })
        if (notify) toast.success('Pipeline saved', { description: `${saved.nodes.length} nodes · ${saved.edges.length} connections` })
        return saved
      } catch (error) {
        toast.error('Could not save pipeline', { description: (error as Error).message })
        return null
      }
    },
    [markSaved, queryClient, toPipeline],
  )

  /** Never validate/run a stale graph: persist it first and abort on failure. */
  const ensureSaved = React.useCallback(async () => {
    if (!dirty) return pipeline.id
    const saved = await save(false)
    return saved?.id ?? null
  }, [dirty, pipeline.id, save])

  const validate = React.useCallback(async () => {
    const pipelineId = await ensureSaved()
    if (!pipelineId) return null
    setValidating(true)
    try {
      const result = await pipelinesApi.validate(pipelineId)
      setValidation(result)
      if (result.valid) {
        toast.success('Pipeline is valid', {
          description: result.warnings.length ? `${result.warnings.length} warning${result.warnings.length === 1 ? '' : 's'} to review` : 'All ports are connected and typed correctly.',
        })
      } else {
        toast.error('Validation failed', { description: `${result.errors.length} connection error${result.errors.length === 1 ? '' : 's'} found.` })
      }
      return result
    } finally {
      setValidating(false)
    }
  }, [ensureSaved, setValidation, setValidating])

  const run = React.useCallback(
    async (debug = false) => {
      if (running) return
      if (active && !active.terminal && active.execution.pipelineId !== pipeline.id) {
        toast.error('Another run is still in progress', { description: 'Wait for it to finish or stop it before starting a new one.' })
        return
      }
      const pipelineId = await ensureSaved()
      if (!pipelineId) return
      try {
        setDebugMode(debug)
        setShowLogs(debug)
        const execution = await pipelinesApi.run(pipelineId)
        queryClient.setQueryData(['execution', execution.id], execution)
        activeExecution.start(execution)
      } catch (error) {
        toast.error('Execution failed', { description: (error as Error).message })
      }
    },
    [active, ensureSaved, pipeline.id, queryClient, running],
  )

  const exportPipeline = React.useCallback(async () => {
    await pipelinesApi.export(pipeline.id)
    toast.success('Pipeline exported', { description: 'JSON graph downloaded.' })
  }, [pipeline.id])

  const exportPython = React.useCallback(async () => {
    await pipelinesApi.exportPython(pipeline.id)
    toast.success('Python script exported', { description: 'Standalone script downloaded.' })
  }, [pipeline.id])

  const actionsRef = React.useRef({ save, validate, run, exportPipeline, exportPython })
  actionsRef.current = { save, validate, run, exportPipeline, exportPython }

  React.useEffect(() => {
    const offs = [
      bus.on('pipeline:save', () => void actionsRef.current.save()),
      bus.on('pipeline:validate', () => void actionsRef.current.validate()),
      bus.on('pipeline:run', () => void actionsRef.current.run(false)),
      bus.on('pipeline:debug', () => void actionsRef.current.run(true)),
      bus.on('pipeline:export', () => void actionsRef.current.exportPipeline()),
      bus.on('pipeline:export-python', () => void actionsRef.current.exportPython()),
      registerRunNavigation(() => activeRunIdRef.current, navigate),
      bus.on('pipeline:delete-selected', () => {
        deleteSelection()
      }),
    ]
    return () => offs.forEach((off) => off())
  }, [deleteSelection, navigate])

  const canvasNodes = React.useMemo(
    () => [
      ...nodes,
      {
        id: '__label_ingestion',
        type: 'group-label',
        position: { x: 12, y: -4 },
        data: { label: 'INGESTION' },
        selectable: false,
        draggable: false,
        connectable: false,
      },
      {
        id: '__label_retrieval',
        type: 'group-label',
        position: { x: 12, y: 344 },
        data: { label: 'RETRIEVAL & GENERATION' },
        selectable: false,
        draggable: false,
        connectable: false,
      },
      {
        id: '__callout',
        type: 'callout',
        position: { x: 10, y: 252 },
        data: { text: 'Semantic boundaries preserve document context' },
        selectable: false,
        draggable: false,
        connectable: false,
      },
    ],
    [nodes],
  )

  const handleDrop = React.useCallback(
    (event: React.DragEvent) => {
      event.preventDefault()
      const definitionId = event.dataTransfer.getData('application/rag-node')
      // Prefer the live backend catalog: mock ids can drift from the real ones (e.g. qdrant).
      const definition = catalogDefById[definitionId] ?? nodeDefById[definitionId]
      if (!definition) return
      const position = screenToFlowPosition({ x: event.clientX, y: event.clientY })
      addNode(definition, { x: position.x - 80, y: position.y - 30 })
      toast.success(`${definition.name} added to canvas`)
    },
    [addNode, catalogDefById, screenToFlowPosition],
  )

  const onKeyDown = (event: React.KeyboardEvent) => {
    const target = event.target as HTMLElement
    if (['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName) || target.isContentEditable) return
    const mod = event.metaKey || event.ctrlKey
    if (mod && event.key.toLowerCase() === 'z') {
      event.preventDefault()
      if (event.shiftKey) redo()
      else undo()
    }
    if (event.key === 'Delete' || event.key === 'Backspace') {
      if (deleteSelection()) event.preventDefault()
    }
  }

  const errorCount = validation?.errors.length ?? 0
  const warningCount = validation?.warnings.length ?? 0
  const statusLabel = running
    ? 'Running pipeline'
    : errorCount > 0
      ? `${errorCount} issue${errorCount === 1 ? '' : 's'}`
      : validation?.valid || storedPipeline.status === 'valid'
        ? 'Valid pipeline'
        : 'Draft pipeline'

  return (
    <div className="flex h-full min-h-0 flex-col" onKeyDown={onKeyDown} tabIndex={-1}>
      <div className="shrink-0 border-b border-line/80 bg-bg px-4 pb-2 pt-2">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <Breadcrumbs items={[{ label: 'Projects', to: '/projects' }, { label: 'Knowledge assistant', to: '/projects' }, { label: pipeline.name }]} />
            <div className="mt-1.5 flex flex-wrap items-center gap-3">
              <h1 className="text-[20px] font-semibold leading-none tracking-[-0.02em] text-ink">{pipeline.name}</h1>
              <span className="flex items-center gap-1.5 font-mono text-[9px] text-dim">
                <StatusDot status={running ? 'running' : dirty ? 'warning' : 'idle'} />
                {running ? 'Running' : dirty ? 'Unsaved changes' : 'All changes saved'}
              </span>
              {storedPipeline.version && <span className="rounded border border-line bg-white/[0.02] px-1.5 py-0.5 font-mono text-[8px] text-dim">{storedPipeline.version}</span>}
            </div>
          </div>
          <div className="flex items-center gap-2 pt-1">
            <Select
              value={storedPipeline.environment}
              onValueChange={(v) => {
                setEnvironment(v as Pipeline['environment'])
                toast.success(`Environment set to ${v}`)
              }}
              options={['Development', 'Staging', 'Production']}
              className="h-7 w-[122px] border-line bg-[#0c131e] text-[10px]"
              aria-label="Environment"
            />
            <Button variant="secondary" size="md" onClick={() => setShareOpen(true)}>
              <Share2 className="h-3 w-3" /> Share
            </Button>
          </div>
        </div>

        <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
          <Button variant="secondary" size="sm" onClick={() => void save()} disabled={!dirty}>
            <Save className="h-3 w-3" /> Save
          </Button>
          <div className="flex items-center">
            <button onClick={undo} disabled={!canUndo} className="flex h-7 w-7 items-center justify-center rounded text-dim hover:bg-white/5 hover:text-ink disabled:opacity-30" aria-label="Undo">
              <Undo2 className="h-3.5 w-3.5" />
            </button>
            <button onClick={redo} disabled={!canRedo} className="flex h-7 w-7 items-center justify-center rounded text-dim hover:bg-white/5 hover:text-ink disabled:opacity-30" aria-label="Redo">
              <Redo2 className="h-3.5 w-3.5" />
            </button>
          </div>
          <div className="mx-0.5 h-4 w-px bg-line" />
          <button
            type="button"
            onClick={deleteSelection}
            disabled={!selectedNodeId && !edges.some((edge) => edge.selected)}
            title="Elimina il nodo o il collegamento selezionato"
            aria-label="Elimina selezione"
            className="flex h-7 items-center gap-1 rounded border border-line-strong px-2 font-mono text-[9px] text-muted transition-colors hover:border-danger hover:text-danger disabled:cursor-not-allowed disabled:opacity-30"
          >
            <Trash2 className="h-3 w-3" /> Delete
          </button>
          <div className="mx-0.5 h-4 w-px bg-line" />
          <Button variant="secondary" size="sm" onClick={() => void validate()} disabled={validating}>
            {validating ? <Loader2 className="h-3 w-3 animate-spin" /> : <CheckCircle2 className="h-3 w-3" />} Validate
          </Button>
          <Button variant="primary" size="sm" className="min-w-[64px]" onClick={() => void run(false)} disabled={running}>
            {running ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3 fill-white" />} {running ? 'Running' : 'Run'}
          </Button>
          <Button variant="secondary" size="sm" onClick={() => { setDebugMode(true); void run(true) }} disabled={running}>
            <Bug className="h-3 w-3" /> Debug
          </Button>
          <Button variant="secondary" size="sm" onClick={() => void exportPipeline()}>
            <Download className="h-3 w-3" /> Export
          </Button>
          <Button variant="secondary" size="sm" onClick={() => void exportPython()}>
            <SquareTerminal className="h-3 w-3" /> Export .py
          </Button>
          <div className="ml-auto flex items-center gap-3 font-mono text-[8.5px] text-dim">
            <span>{nodes.length} nodes</span>
            <span>{edges.length} connections</span>
            <span className={cn('flex items-center gap-1.5', errorCount > 0 ? 'text-danger' : warningCount > 0 ? 'text-warn' : 'text-success')}>
              <StatusDot status={errorCount > 0 ? 'danger' : warningCount > 0 ? 'warning' : 'success'} /> {statusLabel}
            </span>
            <div className="hidden items-center gap-1 lg:flex">
              <button
                onClick={() => setShowLibrary((v) => !v)}
                className={cn('rounded border px-1.5 py-0.5 transition-colors', showLibrary ? 'border-line-strong text-muted' : 'border-line text-dim hover:text-ink')}
                aria-label="Toggle node library"
              >
                Library
              </button>
              <button
                onClick={() => setShowInspector((v) => !v)}
                className={cn('rounded border px-1.5 py-0.5 transition-colors', showInspector ? 'border-line-strong text-muted' : 'border-line text-dim hover:text-ink')}
                aria-label="Toggle inspector"
              >
                Inspector
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="flex min-h-0 flex-1">
        {showLibrary && <NodeLibrary onClose={() => setShowLibrary(false)} />}

        <div className="flex min-w-0 flex-1 flex-col">
          <div className="relative min-h-0 flex-1 dotted-canvas" onDrop={handleDrop} onDragOver={(e) => e.preventDefault()}>
            <ReactFlow
              nodes={canvasNodes}
              edges={edges}
              nodeTypes={canvasNodeTypes}
              edgeTypes={edgeTypes}
              onNodesChange={(changes) => {
                const real = changes.filter((c) => !(c.type === 'remove' && 'id' in c && ['__label_ingestion', '__label_retrieval', '__callout'].includes(c.id)))
                onNodesChange(real as NodeChange<RagFlowNode>[])
              }}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              isValidConnection={(connection) =>
                connectionIsCompatible(
                  connection,
                  usePipelineStore.getState().nodes.map((n) => ({
                    id: n.id,
                    inputs: n.data.pipelineNode.inputs,
                    outputs: n.data.pipelineNode.outputs,
                  })),
                )
              }
              onEdgeDoubleClick={(_, edge) => {
                removeEdges([edge.id])
                toast.success('Connection removed')
              }}
              onNodeClick={(_, node) => {
                if (node.type === 'rag') selectNode(node.id)
              }}
              onPaneClick={() => selectNode(null)}
              fitView
              fitViewOptions={{ padding: 0.14, minZoom: 0.4, maxZoom: 1 }}
              minZoom={0.2}
              maxZoom={1.6}
              proOptions={{ hideAttribution: true }}
              defaultEdgeOptions={{ type: 'rag' }}
              connectionLineStyle={{ stroke: '#6B8AFB', strokeWidth: 1.4 }}
              connectionLineType={'default' as never}
              deleteKeyCode={null}
              panOnScroll
              selectionOnDrag={false}
              zoomOnDoubleClick={false}
            >
              <Background variant={BackgroundVariant.Dots} gap={19} size={1.1} color="#243147" />
              <ZoomControls />
              <MiniMap
                position="bottom-right"
                pannable
                zoomable
                style={{ width: 164, height: 92, margin: 12 }}
                maskColor="rgba(7, 12, 20, 0.72)"
                nodeColor={(node) => (node.type === 'rag' ? (node.data as { pipelineNode: { accent: string } }).pipelineNode.accent : 'transparent')}
                nodeStrokeColor="transparent"
                nodeBorderRadius={2}
              />
            </ReactFlow>
            <div className="pointer-events-none absolute inset-0 vignette" />
            <div className="pointer-events-none absolute left-0 top-0 h-8 w-full bg-gradient-to-b from-[#080d15]/65 to-transparent" />
          </div>

          <OutputPreview
            pipeline={storedPipeline}
            running={running}
            logs={logs}
            showLogs={showLogs}
            onToggleLogs={setShowLogs}
            onInspect={() => { if (activeRunId) navigate(`/runs/${activeRunId}/results`) }}
            onOpenRun={() => { if (activeRunId) navigate(`/runs/${activeRunId}`) }}
          />
        </div>

        {showInspector && <NodeInspector onClose={() => setShowInspector(false)} />}
      </div>

      <ShareDialog open={shareOpen} onOpenChange={setShareOpen} pipeline={pipeline} />
    </div>
  )
}

export function PipelineEditorPage() {
  const { pipelineId = 'pl_hybrid_rag' } = useParams()
  const queryClient = useQueryClient()
  const loadedRef = React.useRef<string | null>(null)
  const { data: pipeline, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['pipeline', pipelineId],
    queryFn: () => pipelinesApi.get(pipelineId),
  })

  React.useEffect(() => {
    if (pipeline && loadedRef.current !== pipeline.id) {
      usePipelineStore.getState().loadPipeline(pipeline)
      loadedRef.current = pipeline.id
    }
  }, [pipeline])

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center bg-bg">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-5 w-5 animate-spin text-accent" />
          <p className="font-mono text-[9px] uppercase tracking-[0.16em] text-dim">Loading pipeline graph</p>
        </div>
      </div>
    )
  }

  if (isError || !pipeline) {
    return (
      <div className="p-6">
        <ErrorState message={(error as Error)?.message} onRetry={() => void refetch()} />
      </div>
    )
  }

  return (
    <ReactFlowProvider>
      <PipelineEditorInner pipeline={pipeline} />
    </ReactFlowProvider>
  )
}
