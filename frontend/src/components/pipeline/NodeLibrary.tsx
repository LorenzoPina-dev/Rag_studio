import * as React from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ChevronDown, ChevronRight, GripVertical, Loader2, Plus, Search, Star } from 'lucide-react'
import { nodesApi } from '@/api/nodes.api'
import type { NodeCatalogCategory, NodeDefinition } from '@/types'
import { usePipelineStore } from '@/store/usePipelineStore'
import { cn } from '@/lib/utils'
import { Dialog, DialogBody, DialogContent, DialogFooter, DialogHeader } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { toast } from 'sonner'

const initialOpen: Record<string, boolean> = {
  'Data Sources': true,
  'Document Processing': true,
  Embeddings: false,
  'Vector Databases': false,
  Databases: false,
  Retrieval: true,
  Selection: true,
  Reranking: true,
  'LLM Generation': false,
  'Control Flow': false,
  Evaluation: false,
  'Multimodal Processing': false,
  Preprocessing: false,
  Enrichment: false,
  'Indexing & Storage': false,
  Fusion: false,
  'Selection & Filtering': false,
  'Context Processing': false,
  Validation: false,
  Orchestration: false,
  'Monitoring & Security': false,
}

function NodeChip({ definition }: { definition: NodeDefinition }) {
  const selectedNodeId = usePipelineStore((s) => s.selectedNodeId)
  const nodes = usePipelineStore((s) => s.nodes)
  const addNode = usePipelineStore((s) => s.addNode)
  const favorites = usePipelineStore((s) => s.favorites)
  const toggleFavorite = usePipelineStore((s) => s.toggleFavorite)
  const isActive = nodes.some((n) => n.id === selectedNodeId && n.data.pipelineNode.definitionId === definition.id)
  const isFavorite = favorites.includes(definition.id)

  return (
    <div
      draggable
      onDragStart={(event) => {
        event.dataTransfer.setData('application/rag-node', definition.id)
        event.dataTransfer.effectAllowed = 'move'
      }}
      onClick={() => {
        addNode(definition, { x: 320 + Math.random() * 120, y: 300 + Math.random() * 120 })
        toast.success(`${definition.name} added to canvas`)
      }}
      className={cn(
        'group flex h-[26px] cursor-grab items-center gap-2 rounded-[4px] border px-2 text-left transition-colors active:cursor-grabbing',
        isActive
          ? 'border-[#4c64c9] bg-[#1b2745] text-[#d5deff]'
          : 'border-[#202c3e] bg-[#0d1521] text-[#a6b1c2] hover:border-[#2d3b52] hover:bg-[#111b2a] hover:text-ink',
      )}
      title={definition.description}
    >
      <GripVertical className="h-2.5 w-2.5 shrink-0 text-[#4c5a70] group-hover:text-dim" />
      <span className="min-w-0 flex-1 truncate text-[10.5px]">{definition.name}</span>
      {definition.custom && <span className="font-mono text-[7px] uppercase tracking-wider text-violet">custom</span>}
      <button
        onClick={(e) => {
          e.stopPropagation()
          toggleFavorite(definition.id)
        }}
        className={cn(
          'shrink-0 rounded p-0.5 transition-opacity',
          isFavorite ? 'text-warn opacity-100' : 'text-dim opacity-0 group-hover:opacity-100',
        )}
        aria-label={isFavorite ? 'Remove from favorites' : 'Add to favorites'}
      >
        <Star className={cn('h-2.5 w-2.5', isFavorite && 'fill-warn')} />
      </button>
    </div>
  )
}

function Group({
  label,
  open,
  onToggle,
  children,
  count,
}: {
  label: string
  open: boolean
  onToggle: () => void
  children: React.ReactNode
  count?: number
}) {
  return (
    <div>
      <button onClick={onToggle} className="group flex w-full items-center gap-1 rounded px-1 py-1.5 text-left">
        {open ? (
          <ChevronDown className="h-2.5 w-2.5 text-[#5b687e]" />
        ) : (
          <ChevronRight className="h-2.5 w-2.5 text-[#5b687e]" />
        )}
        <span className="text-[10.5px] text-[#8290a5] transition-colors group-hover:text-ink">{label}</span>
        {count !== undefined && <span className="ml-auto font-mono text-[8px] text-[#4f5c70]">{count}</span>}
      </button>
      {open && <div className="space-y-1 pb-1.5 pl-3">{children}</div>}
    </div>
  )
}

export function NodeLibrary({ onClose }: { onClose?: () => void }) {
  const navigate = useNavigate()
  const addNode = usePipelineStore((s) => s.addNode)
  const libraryTab = usePipelineStore((s) => s.libraryTab)
  const setLibraryTab = usePipelineStore((s) => s.setLibraryTab)
  const search = usePipelineStore((s) => s.librarySearch)
  const setSearch = usePipelineStore((s) => s.setLibrarySearch)
  const favorites = usePipelineStore((s) => s.favorites)
  const [openCategories, setOpenCategories] = React.useState(initialOpen)
  const [chunkingOpen, setChunkingOpen] = React.useState(true)
  const [createOpen, setCreateOpen] = React.useState(false)
  const [customName, setCustomName] = React.useState('')
  const [customCategory, setCustomCategory] = React.useState('Selection')

  const { data, isLoading } = useQuery({ queryKey: ['node-catalog'], queryFn: nodesApi.catalog, staleTime: 300_000 })
  const catalog = data ?? []

  const filtered = React.useMemo(() => {
    const q = search.trim().toLowerCase()
    return catalog
      .map((category) => ({
        ...category,
        nodes: category.nodes.filter(
          (node) =>
            (!q || `${node.name} ${node.category} ${node.tags.join(' ')}`.toLowerCase().includes(q)) &&
            (libraryTab === 'all' || favorites.includes(node.id)),
        ),
      }))
      .filter((category) => category.nodes.length > 0)
  }, [catalog, search, libraryTab, favorites])

  const toggleCategory = (category: string) =>
    setOpenCategories((state) => ({ ...state, [category]: !state[category] }))

  const renderCategory = (group: NodeCatalogCategory) => {
    if (group.category === 'Document Processing') {
      const nonChunking = group.nodes.filter((n) => !n.id.includes('chunking'))
      const chunking = group.nodes.filter((n) => n.id.includes('chunking'))
      return (
        <div key={group.category} className="mb-1">
          <Group
            label={group.category}
            open={openCategories[group.category] ?? true}
            onToggle={() => toggleCategory(group.category)}
            count={group.nodes.length}
          >
            {nonChunking.map((node) => (
              <NodeChip key={node.id} definition={node} />
            ))}
            {chunking.length > 0 && (
              <div className="pt-0.5">
                <button onClick={() => setChunkingOpen((v) => !v)} className="flex w-full items-center gap-1 py-1">
                  {chunkingOpen ? <ChevronDown className="h-2.5 w-2.5 text-[#5b687e]" /> : <ChevronRight className="h-2.5 w-2.5 text-[#5b687e]" />}
                  <span className="text-[10px] text-[#76849a]">Chunking</span>
                </button>
                {chunkingOpen && <div className="space-y-1 pl-3">{chunking.map((node) => <NodeChip key={node.id} definition={node} />)}</div>}
              </div>
            )}
          </Group>
        </div>
      )
    }
    return (
      <div key={group.category} className="mb-1">
        <Group
          label={group.category}
          open={openCategories[group.category] ?? false}
          onToggle={() => toggleCategory(group.category)}
          count={group.nodes.length}
        >
          {group.nodes.map((node) => (
            <NodeChip key={node.id} definition={node} />
          ))}
        </Group>
      </div>
    )
  }

  return (
    <aside className="flex h-full w-[218px] shrink-0 flex-col border-r border-line bg-[#0b111b]">
      <div className="flex h-[42px] shrink-0 items-center justify-between border-b border-line px-3">
        <span className="font-mono text-[9px] font-medium uppercase tracking-[0.13em] text-[#a5b0c1]">Node Library</span>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setCreateOpen(true)}
            className="rounded p-1 text-dim transition-colors hover:bg-white/5 hover:text-ink"
            aria-label="Create custom node"
          >
            <Plus className="h-3.5 w-3.5" />
          </button>
          {onClose && (
            <button onClick={onClose} className="rounded p-1 text-dim hover:bg-white/5 hover:text-ink xl:hidden" aria-label="Hide node library">
              <ChevronRight className="h-3.5 w-3.5 rotate-180" />
            </button>
          )}
        </div>
      </div>

      <div className="border-b border-line px-3 pb-2 pt-2.5">
        <div className="relative">
          <Search className="pointer-events-none absolute left-2 top-1/2 h-3 w-3 -translate-y-1/2 text-dim" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search nodes…"
            className="h-[27px] w-full rounded border border-[#283447] bg-[#0b121c] pl-7 pr-2 text-[10.5px] text-ink placeholder:text-dim focus:border-accent/60 focus:outline-none"
          />
        </div>
        <div className="mt-2 flex items-center gap-4">
          {(['all', 'favorites'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setLibraryTab(tab)}
              className={cn(
                'relative -mb-[9px] border-b border-transparent pb-2 text-[10.5px] capitalize transition-colors',
                libraryTab === tab ? 'border-[#5570e8] text-[#b9c8ff]' : 'text-[#7d8a9f] hover:text-ink',
              )}
            >
              {tab === 'all' ? 'All nodes' : 'Favorites'}
            </button>
          ))}
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-2 py-2">
        {isLoading && (
          <div className="flex items-center gap-2 px-2 py-4 font-mono text-[9px] uppercase tracking-wider text-dim">
            <Loader2 className="h-3 w-3 animate-spin" /> Loading catalog
          </div>
        )}
        {!isLoading && filtered.length === 0 && (
          <div className="px-2 py-8 text-center">
            <Search className="mx-auto mb-2 h-4 w-4 text-dim" />
            <p className="text-[10.5px] text-muted">No nodes match “{search}”</p>
            <button onClick={() => setSearch('')} className="mt-2 text-[10px] text-accent hover:underline">Clear search</button>
          </div>
        )}
        {filtered.map(renderCategory)}
      </div>

      <button
        onClick={() => navigate('/custom-nodes')}
        className="flex h-9 shrink-0 items-center gap-1.5 border-t border-line px-3 text-[10px] text-[#7f8ea5] transition-colors hover:bg-white/[0.025] hover:text-ink"
      >
        <Plus className="h-3 w-3" /> Create custom Python node
      </button>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent size="sm">
          <DialogHeader eyebrow="Custom node" title="Create a component" description="Start a new Python node and register its typed ports." />
          <DialogBody className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-[11.5px] text-muted">Node name</label>
              <Input value={customName} onChange={(e) => setCustomName(e.target.value)} placeholder="e.g. Keyword booster" autoFocus />
            </div>
            <div className="space-y-1.5">
              <label className="text-[11.5px] text-muted">Category</label>
              <Select
                value={customCategory}
                onValueChange={setCustomCategory}
                options={['Data Sources', 'Document Processing', 'Embeddings', 'Retrieval', 'Selection', 'Reranking', 'LLM Generation', 'Control Flow', 'Evaluation']}
              />
            </div>
          </DialogBody>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setCreateOpen(false)}>Cancel</Button>
            <Button
              variant="primary"
              disabled={!customName.trim()}
              onClick={() => {
                setCreateOpen(false)
                toast.success('Draft component created', { description: 'Opening the Python component editor…' })
                navigate('/custom-nodes')
              }}
            >
              Continue
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </aside>
  )
}
