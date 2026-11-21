import * as React from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  ArrowRight,
  Boxes,
  Braces,
  Check,
  Code2,
  Copy,
  Database,
  FileText,
  GitBranch,
  Layers,
  ListFilter,
  Play,
  Search,
  Sparkles,
  Star,
  Wand2,
  Workflow,
} from 'lucide-react'
import { toast } from 'sonner'
import { PageHeader } from '@/components/shared/page'
import { Button } from '@/components/ui/button'
import { SearchInput } from '@/components/ui/input'
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { nodesApi } from '@/api/nodes.api'
import type { NodeCategory, NodeDefinition } from '@/types'

const categoryIcons: Record<NodeCategory, React.ElementType> = {
  'Data Sources': Database,
  'Document Processing': FileText,
  Embeddings: Layers,
  'Vector Databases': Boxes,
  Retrieval: Search,
  Selection: ListFilter,
  Reranking: Wand2,
  'LLM Generation': Sparkles,
  'Control Flow': GitBranch,
  Evaluation: Workflow,
  'Multimodal Processing': Braces,
}

function NodeGlyph({ category, accent, size = 'md' }: { category: NodeCategory; accent: string; size?: 'sm' | 'md' }) {
  const Icon = categoryIcons[category] ?? Boxes
  return (
    <span
      className={cn(
        'flex shrink-0 items-center justify-center rounded-md border bg-[#0b111b]',
        size === 'md' ? 'h-8 w-8' : 'h-6 w-6',
      )}
      style={{ borderColor: `${accent}44`, color: accent, boxShadow: `inset 0 0 18px ${accent}12` }}
    >
      <Icon className={size === 'md' ? 'h-3.5 w-3.5' : 'h-3 w-3'} />
    </span>
  )
}

function PortRow({ port, direction }: { port: NodeDefinition['inputs'][number]; direction: 'in' | 'out' }) {
  return (
    <div className="flex items-center justify-between gap-3 py-1.5">
      <div className="flex min-w-0 items-center gap-2">
        <span className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ backgroundColor: port.color }} />
        <span className="truncate font-mono text-[10px] text-[#b5c2d5]">{port.label}</span>
        {port.required && <span className="font-mono text-[8px] uppercase tracking-wide text-warn">req</span>}
      </div>
      <span className="shrink-0 font-mono text-[9px] text-dim">{direction === 'in' ? '←' : '→'} {port.typeLabel}</span>
    </div>
  )
}

export function NodeLibraryPage() {
  const navigate = useNavigate()
  const [search, setSearch] = React.useState('')
  const [category, setCategory] = React.useState<NodeCategory | 'All'>('All')
  const [favorites, setFavorites] = React.useState<string[]>(['hybrid-retrieval', 'bge-reranker'])
  const [selectedId, setSelectedId] = React.useState<string | null>(null)
  const [onlyFavorites, setOnlyFavorites] = React.useState(false)

  const { data, isLoading, isError, error, refetch } = useQuery({ queryKey: ['node-catalog'], queryFn: nodesApi.catalog })

  const allNodes = React.useMemo(() => (data ?? []).flatMap((group) => group.nodes), [data])
  const selected = allNodes.find((node) => node.id === selectedId) ?? allNodes[0]

  const filtered = allNodes
    .filter((node) => (category === 'All' ? true : node.category === category))
    .filter((node) => (onlyFavorites ? favorites.includes(node.id) : true))
    .filter((node) => `${node.name} ${node.description} ${node.tags.join(' ')}`.toLowerCase().includes(search.toLowerCase()))

  React.useEffect(() => {
    if (selected && !selectedId) setSelectedId(selected.id)
  }, [selected, selectedId])

  const toggleFavorite = (id: string) => {
    setFavorites((prev) => (prev.includes(id) ? prev.filter((value) => value !== id) : [...prev, id]))
  }

  return (
    <>
      <PageHeader
        eyebrow="Builder resources"
        title="Node library"
        description="Composable building blocks for ingestion, retrieval, generation and evaluation."
        breadcrumbs={[{ label: 'Workspace', to: '/' }, { label: 'Node library' }]}
        actions={
          <>
            <Button variant="secondary" onClick={() => navigate('/custom-nodes')}>
              <Code2 className="h-3.5 w-3.5" /> Custom node SDK
            </Button>
            <Button variant="primary" size="lg" onClick={() => navigate('/pipelines/pl_hybrid_rag')}>
              <Workflow className="h-3.5 w-3.5" /> Open editor
            </Button>
          </>
        }
      />

      <div className="flex min-h-0 flex-1 overflow-hidden">
        <aside className="hidden w-[214px] shrink-0 flex-col overflow-y-auto border-r border-line bg-[#0a1019] py-3 md:flex">
          <div className="px-3 pb-2">
            <SearchInput value={search} onChange={setSearch} placeholder="Find a node…" />
          </div>
          <div className="px-2">
            <p className="px-2 pb-1.5 pt-2 font-mono text-[8.5px] uppercase tracking-[0.16em] text-[#4e5b70]">Categories</p>
            <button
              onClick={() => setCategory('All')}
              className={cn(
                'flex w-full items-center justify-between rounded px-2 py-[6px] text-[11px] transition-colors',
                category === 'All' ? 'bg-[#16213a] text-ink' : 'text-[#8c97aa] hover:bg-white/[0.035] hover:text-ink',
              )}
            >
              <span className="flex items-center gap-2"><Boxes className="h-3.5 w-3.5 text-[#7b8ba4]" /> All nodes</span>
              <span className="font-mono text-[8.5px] text-dim">{allNodes.length}</span>
            </button>
            {(data ?? []).map((group) => {
              const Icon = categoryIcons[group.category] ?? Boxes
              return (
                <button
                  key={group.category}
                  onClick={() => setCategory(group.category)}
                  className={cn(
                    'flex w-full items-center justify-between rounded px-2 py-[6px] text-left text-[11px] transition-colors',
                    category === group.category ? 'bg-[#16213a] text-ink' : 'text-[#8c97aa] hover:bg-white/[0.035] hover:text-ink',
                  )}
                >
                  <span className="flex min-w-0 items-center gap-2"><Icon className="h-3.5 w-3.5 shrink-0 text-[#7b8ba4]" /> <span className="truncate">{group.category}</span></span>
                  <span className="font-mono text-[8.5px] text-dim">{group.nodes.length}</span>
                </button>
              )
            })}
          </div>
          <div className="mt-4 border-t border-line/60 px-2 pt-3">
            <button
              onClick={() => setOnlyFavorites((value) => !value)}
              className={cn(
                'flex w-full items-center gap-2 rounded px-2 py-[6px] text-[11px] transition-colors',
                onlyFavorites ? 'bg-[#16213a] text-ink' : 'text-[#8c97aa] hover:bg-white/[0.035] hover:text-ink',
              )}
            >
              <Star className={cn('h-3.5 w-3.5', onlyFavorites ? 'fill-warn text-warn' : 'text-[#7b8ba4]')} />
              Favorites
              <span className="ml-auto font-mono text-[8.5px] text-dim">{favorites.length}</span>
            </button>
            <button
              onClick={() => navigate('/custom-nodes')}
              className="flex w-full items-center gap-2 rounded px-2 py-[6px] text-[11px] text-[#8c97aa] transition-colors hover:bg-white/[0.035] hover:text-ink"
            >
              <Code2 className="h-3.5 w-3.5 text-[#7b8ba4]" /> Create custom node
            </button>
          </div>
          <div className="mt-auto px-3 pt-4">
            <div className="rounded-md border border-line/80 bg-[#0d1622] p-2.5">
              <p className="font-mono text-[8.5px] uppercase tracking-[0.12em] text-dim">SDK version</p>
              <p className="mt-1 font-mono text-[10px] text-muted">rag-studio 0.8.2</p>
              <button onClick={() => toast.info('Documentation opens in the IDE panel')} className="mt-2 flex items-center gap-1 font-mono text-[8.5px] text-[#7f95cf] hover:text-[#b5c6ff]">
                Read docs <ArrowRight className="h-2.5 w-2.5" />
              </button>
            </div>
          </div>
        </aside>

        <div className="min-w-0 flex-1 overflow-y-auto">
          <div className="flex flex-wrap items-center gap-2 border-b border-line/70 px-5 py-3">
            <SearchInput value={search} onChange={setSearch} placeholder="Search 38 nodes…" className="w-[240px] md:hidden" />
            <span className="font-mono text-[9px] uppercase tracking-[0.12em] text-dim">
              {category === 'All' ? 'All nodes' : category}
            </span>
            <span className="rounded border border-line bg-white/[0.03] px-1.5 py-0.5 font-mono text-[8.5px] text-dim">{filtered.length}</span>
            {onlyFavorites && (
              <span className="flex items-center gap-1 rounded border border-warn/20 bg-warn/[0.06] px-1.5 py-0.5 font-mono text-[8.5px] text-warn">
                <Star className="h-2.5 w-2.5 fill-current" /> Favorites only
              </span>
            )}
            <span className="ml-auto font-mono text-[8.5px] text-dim">Drag nodes into the canvas to build a graph</span>
          </div>

          {isLoading && <LoadingState label="Loading node catalog…" rows={6} />}
          {isError && <ErrorState message={(error as Error)?.message} onRetry={() => void refetch()} />}

          {!isLoading && !isError && filtered.length === 0 && (
            <EmptyState
              icon={<Search className="h-4 w-4" />}
              title="No nodes match these filters"
              description="Try another category or clear the search and favorites filter."
              action={
                <Button variant="secondary" size="sm" onClick={() => { setSearch(''); setCategory('All'); setOnlyFavorites(false) }}>
                  Reset filters
                </Button>
              }
            />
          )}

          {!isLoading && !isError && filtered.length > 0 && (
            <div className="grid gap-2.5 p-5 sm:grid-cols-2 xl:grid-cols-3">
              {filtered.map((node) => {
                const active = selected?.id === node.id
                const favorite = favorites.includes(node.id)
                return (
                  <button
                    key={node.id}
                    onClick={() => setSelectedId(node.id)}
                    className={cn(
                      'group relative flex flex-col rounded-lg border p-3 text-left transition-colors',
                      active
                        ? 'border-accent/60 bg-[#111c2e] shadow-[0_0_0_1px_rgba(91,124,250,0.16)]'
                        : 'border-line bg-gradient-to-b from-[#0e1724] to-[#0b1320] hover:border-[#30405a]',
                    )}
                  >
                    <div className="flex items-start gap-2.5">
                      <NodeGlyph category={node.category} accent={node.accent} />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-[11.5px] font-medium text-[#d4deeb]">{node.name}</p>
                        <p className="mt-0.5 truncate font-mono text-[8.5px] text-dim">{node.category} · {node.kind}</p>
                      </div>
                      <span className="flex h-5 w-5 items-center justify-center rounded text-dim opacity-0 transition-opacity hover:bg-white/5 hover:text-warn group-hover:opacity-100" onClick={(event) => { event.stopPropagation(); toggleFavorite(node.id) }}>
                        <Star className={cn('h-3 w-3', favorite && 'fill-warn text-warn opacity-100')} />
                      </span>
                    </div>
                    <p className="mt-2.5 line-clamp-2 min-h-[26px] text-[10px] leading-[1.4] text-[#7f8da2]">{node.description}</p>
                    <div className="mt-2.5 flex items-center gap-1.5">
                      {node.tags.slice(0, 2).map((tag) => (
                        <span key={tag} className="rounded border border-line/80 bg-white/[0.025] px-1 py-0.5 font-mono text-[8px] text-dim">{tag}</span>
                      ))}
                      <span className="ml-auto font-mono text-[8px] text-[#4c5a70]">{node.inputs.length} in · {node.outputs.length} out</span>
                    </div>
                  </button>
                )
              })}
            </div>
          )}
        </div>

        <aside className="hidden w-[330px] shrink-0 overflow-y-auto border-l border-line bg-[#0a1019] xl:block">
          {selected ? (
            <>
              <div className="border-b border-line px-4 py-3.5">
                <div className="flex items-start gap-2.5">
                  <NodeGlyph category={selected.category} accent={selected.accent} />
                  <div className="min-w-0 flex-1">
                    <h2 className="truncate text-[13px] font-semibold text-ink">{selected.name}</h2>
                    <p className="mt-0.5 font-mono text-[8.5px] text-dim">{selected.category} / {selected.kind}</p>
                  </div>
                  <button
                    onClick={() => toggleFavorite(selected.id)}
                    className="rounded p-1 text-dim transition-colors hover:bg-white/5 hover:text-warn"
                    aria-label="Toggle favorite"
                  >
                    <Star className={cn('h-3.5 w-3.5', favorites.includes(selected.id) && 'fill-warn text-warn')} />
                  </button>
                </div>
                <p className="mt-3 text-[10.5px] leading-relaxed text-muted">{selected.description}</p>
                <div className="mt-2.5 flex flex-wrap gap-1">
                  {selected.tags.map((tag) => (
                    <span key={tag} className="rounded border border-line bg-white/[0.03] px-1.5 py-0.5 font-mono text-[8px] text-dim">{tag}</span>
                  ))}
                </div>
              </div>

              <div className="border-b border-line px-4 py-3">
                <p className="mb-1 font-mono text-[8.5px] uppercase tracking-[0.13em] text-dim">Inputs</p>
                {selected.inputs.length === 0 && <p className="py-1 font-mono text-[9px] text-[#4c5a70]">No inputs</p>}
                {selected.inputs.map((port) => <PortRow key={port.id} port={port} direction="in" />)}
                <p className="mb-1 mt-3 font-mono text-[8.5px] uppercase tracking-[0.13em] text-dim">Outputs</p>
                {selected.outputs.length === 0 && <p className="py-1 font-mono text-[9px] text-[#4c5a70]">No outputs</p>}
                {selected.outputs.map((port) => <PortRow key={port.id} port={port} direction="out" />)}
              </div>

              <div className="border-b border-line px-4 py-3">
                <p className="mb-2 font-mono text-[8.5px] uppercase tracking-[0.13em] text-dim">Parameters</p>
                {selected.params.length === 0 && <p className="font-mono text-[9px] text-[#4c5a70]">No configurable parameters</p>}
                <div className="space-y-1.5">
                  {selected.params.map((param) => (
                    <div key={param.key} className="flex items-start justify-between gap-3 rounded border border-line/70 bg-[#0c141f] px-2 py-1.5">
                      <div className="min-w-0">
                        <p className="truncate font-mono text-[9.5px] text-[#b5c2d5]">{param.key}</p>
                        <p className="mt-0.5 truncate text-[8.5px] text-dim">{param.label}</p>
                      </div>
                      <span className="shrink-0 rounded bg-white/[0.04] px-1 py-0.5 font-mono text-[8.5px] text-muted">
                        {String(param.defaultValue)}{param.unit ? ` ${param.unit}` : ''}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="border-b border-line px-4 py-3">
                <p className="mb-2 font-mono text-[8.5px] uppercase tracking-[0.13em] text-dim">Documentation</p>
                <p className="text-[10px] leading-relaxed text-[#8e9cb0]">
                  {selected.documentation ??
                    `${selected.name} is a ${selected.kind} node. Connect compatible ports to pass ${selected.inputs[0]?.typeLabel ?? 'data'} through this stage, then tune the parameters above to match your corpus and latency budget.`}
                </p>
              </div>

              <div className="space-y-2 px-4 py-3">
                <Button variant="primary" className="w-full" onClick={() => navigate('/pipelines/pl_hybrid_rag')}>
                  <Play className="h-3.5 w-3.5" /> Use in pipeline
                </Button>
                <div className="grid grid-cols-2 gap-2">
                  <Button variant="secondary" size="sm" onClick={() => { navigator.clipboard?.writeText(selected.id); toast.success('Node ID copied') }}>
                    <Copy className="h-3 w-3" /> Copy ID
                  </Button>
                  <Button variant="secondary" size="sm" onClick={() => navigate('/custom-nodes')}>
                    <Code2 className="h-3 w-3" /> Extend
                  </Button>
                </div>
              </div>
            </>
          ) : (
            <EmptyState icon={<Boxes className="h-4 w-4" />} title="Select a node" description="Choose a node to inspect its ports and parameters." />
          )}
        </aside>
      </div>
    </>
  )
}
