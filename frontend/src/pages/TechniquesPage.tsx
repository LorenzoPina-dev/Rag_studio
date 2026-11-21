import * as React from 'react'
import { useQuery } from '@tanstack/react-query'
import { BookOpen, Boxes, Layers3, Loader2, RotateCcw, Search, ShieldCheck, Sparkles, Workflow } from 'lucide-react'
import { techniquesApi } from '@/api/techniques.api'
import type { CategorySummary, PhaseSummary, Technique, TechniqueStatus } from '@/types/techniques'
import { TECHNIQUE_STATUSES } from '@/types/techniques'
import { PageHeader } from '@/components/shared/page'
import { Badge, EmptyState, ErrorState, LoadingState } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { SearchInput } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { Dialog, DialogBody, DialogContent, DialogHeader } from '@/components/ui/dialog'
import { cn } from '@/lib/utils'

type BadgeTone = React.ComponentProps<typeof Badge>['tone']

const statusMeta: Record<TechniqueStatus, { label: string; tone: BadgeTone; color: string }> = {
  reference: { label: 'Reference', tone: 'accent', color: '#9db1ff' },
  provider: { label: 'Provider', tone: 'violet', color: '#c4b1ff' },
  integration: { label: 'Integration', tone: 'success', color: '#35d99b' },
  design: { label: 'Design', tone: 'warning', color: '#f0b45c' },
}

function StatusBadge({ status }: { status: TechniqueStatus }) {
  const meta = statusMeta[status] ?? { label: status, tone: 'neutral' as BadgeTone, color: '#8c97aa' }
  return <Badge tone={meta.tone} dot>{meta.label}</Badge>
}

function StatCard({ label, value, detail, icon: Icon, color }: { label: string; value: string | number; detail?: string; icon: React.ElementType; color?: string }) {
  return (
    <div className="rounded-lg border border-line bg-gradient-to-b from-[#0e1724] to-[#0b1320] px-3 py-2.5">
      <div className="flex items-center gap-1.5 font-mono text-[8.5px] uppercase tracking-[0.12em] text-dim">
        <Icon className="h-3 w-3" style={color ? { color } : undefined} />
        {label}
      </div>
      <p className="mt-1.5 text-[19px] font-semibold leading-none tracking-[-0.03em] text-ink">{value}</p>
      {detail && <p className="mt-1 font-mono text-[8.5px] text-dim">{detail}</p>}
    </div>
  )
}

interface NormalizedParameter {
  name: string
  value: string
  description?: string
}

function normalizeParameters(parameters: Technique['parameters']): NormalizedParameter[] {
  if (!parameters) return []
  if (Array.isArray(parameters)) {
    return parameters.map((param, index) => ({
      name: String(param.name ?? param.key ?? param.label ?? `parameter_${index + 1}`),
      value: param.default !== undefined
        ? String(param.default)
        : param.defaultValue !== undefined
          ? String(param.defaultValue)
          : '—',
      description: param.description ?? param.help,
    }))
  }
  return Object.entries(parameters).map(([key, value]) => {
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      const descriptor = value as Record<string, unknown>
      return {
        name: key,
        value: descriptor.default !== undefined
          ? String(descriptor.default)
          : descriptor.defaultValue !== undefined
            ? String(descriptor.defaultValue)
            : '—',
        description: descriptor.description ? String(descriptor.description) : undefined,
      }
    }
    return {
      name: key,
      value: Array.isArray(value) ? value.join(', ') : String(value),
    }
  })
}

function useIsWide() {
  const [wide, setWide] = React.useState(() => typeof window !== 'undefined' && window.matchMedia('(min-width: 1280px)').matches)
  React.useEffect(() => {
    const query = window.matchMedia('(min-width: 1280px)')
    const onChange = (event: MediaQueryListEvent) => setWide(event.matches)
    query.addEventListener('change', onChange)
    return () => query.removeEventListener('change', onChange)
  }, [])
  return wide
}

function TechniqueDetail({ technique, loading }: { technique: Technique | null; loading: boolean }) {
  if (loading && !technique) return <LoadingState label="Loading technique…" rows={4} />
  if (!technique) {
    return <EmptyState icon={<BookOpen className="h-4 w-4" />} title="Select a technique" description="Choose a technique from the catalog to inspect its implementation and parameters." />
  }

  const parameters = normalizeParameters(technique.parameters)

  return (
    <div>
      <div className="border-b border-line px-4 py-4">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="font-mono text-[8.5px] uppercase tracking-[0.14em] text-dim">{technique.category}</p>
            <h2 className="mt-1.5 text-[14px] font-semibold leading-snug text-ink">{technique.name}</h2>
            <p className="mt-1 font-mono text-[9px] text-dim">{technique.id} · {technique.phase}</p>
          </div>
          <StatusBadge status={technique.status} />
        </div>
        <p className="mt-3 text-[11px] leading-relaxed text-muted">{technique.description}</p>
        {technique.tags.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1">
            {technique.tags.map((tag) => (
              <span key={tag} className="rounded border border-line bg-white/[0.03] px-1.5 py-0.5 font-mono text-[8.5px] text-dim">#{tag}</span>
            ))}
          </div>
        )}
      </div>

      <div className="border-b border-line px-4 py-3.5">
        <p className="mb-2 font-mono text-[8.5px] uppercase tracking-[0.13em] text-dim">Implementation</p>
        <p className="whitespace-pre-wrap text-[10.5px] leading-relaxed text-[#9aa8bc]">{technique.implementation || '—'}</p>
      </div>

      <div className="border-b border-line px-4 py-3.5">
        <p className="mb-2 font-mono text-[8.5px] uppercase tracking-[0.13em] text-dim">Parameters</p>
        {parameters.length === 0 ? (
          <p className="font-mono text-[9px] text-[#4c5a70]">No configurable parameters</p>
        ) : (
          <div className="space-y-1.5">
            {parameters.map((param) => (
              <div key={param.name} className="rounded border border-line/70 bg-[#0c141f] px-2 py-1.5">
                <div className="flex items-start justify-between gap-2">
                  <span className="min-w-0 truncate font-mono text-[9.5px] text-[#b5c2d5]">{param.name}</span>
                  <span className="shrink-0 rounded bg-white/[0.04] px-1 py-0.5 font-mono text-[8.5px] text-muted">{param.value}</span>
                </div>
                {param.description && <p className="mt-1 text-[9px] leading-relaxed text-dim">{param.description}</p>}
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="px-4 py-3.5">
        <p className="mb-2 font-mono text-[8.5px] uppercase tracking-[0.13em] text-dim">Classification</p>
        <div className="grid grid-cols-2 gap-2">
          <div className="rounded border border-line/70 bg-[#0c141f] px-2 py-1.5">
            <p className="font-mono text-[8px] uppercase tracking-wider text-dim">Phase</p>
            <p className="mt-1 text-[10.5px] text-ink">{technique.phase}</p>
          </div>
          <div className="rounded border border-line/70 bg-[#0c141f] px-2 py-1.5">
            <p className="font-mono text-[8px] uppercase tracking-wider text-dim">Status</p>
            <p className="mt-1 text-[10.5px] text-ink">{statusMeta[technique.status]?.label ?? technique.status}</p>
          </div>
        </div>
      </div>
    </div>
  )
}

function categorySummaries(items: Technique[]): CategorySummary[] {
  const categories = Array.from(new Set(items.map((t) => t.category)))
  return categories.map((category) => {
    const members = items.filter((t) => t.category === category)
    return {
      category,
      count: members.length,
      byStatus: Object.fromEntries(TECHNIQUE_STATUSES.map((status) => [status, members.filter((t) => t.status === status).length])),
    }
  })
}

function phaseSummaries(items: Technique[]): PhaseSummary[] {
  const phases = Array.from(new Set(items.map((t) => t.phase)))
  return phases.map((phase) => ({ phase, count: items.filter((t) => t.phase === phase).length }))
}

export function TechniquesPage() {
  const [search, setSearch] = React.useState('')
  const [phase, setPhase] = React.useState('all')
  const [category, setCategory] = React.useState('all')
  const [status, setStatus] = React.useState<TechniqueStatus | 'all'>('all')
  const [selectedId, setSelectedId] = React.useState<string | null>(null)
  const wide = useIsWide()

  const { data, isLoading, isError, error, refetch } = useQuery({ queryKey: ['techniques'], queryFn: techniquesApi.list, staleTime: 300_000 })
  const categoriesQuery = useQuery({ queryKey: ['technique-categories'], queryFn: techniquesApi.categories, staleTime: 300_000 })
  const phasesQuery = useQuery({ queryKey: ['technique-phases'], queryFn: techniquesApi.phases, staleTime: 300_000 })
  const detailQuery = useQuery({
    queryKey: ['technique', selectedId],
    queryFn: () => techniquesApi.get(selectedId!),
    enabled: !!selectedId,
    staleTime: 300_000,
    retry: false,
  })

  const techniques = data ?? []
  const categories = categoriesQuery.data?.length ? categoriesQuery.data : categorySummaries(techniques)
  const phases = phasesQuery.data?.length ? phasesQuery.data : phaseSummaries(techniques)
  const selected = detailQuery.data ?? techniques.find((t) => t.id === selectedId) ?? null

  const filtered = React.useMemo(() => {
    const q = search.trim().toLowerCase()
    return techniques.filter((technique) =>
      (phase === 'all' || technique.phase === phase) &&
      (category === 'all' || technique.category === category) &&
      (status === 'all' || technique.status === status) &&
      (!q || `${technique.name} ${technique.description} ${technique.category} ${technique.phase} ${technique.tags.join(' ')} ${technique.implementation}`.toLowerCase().includes(q)),
    )
  }, [techniques, search, phase, category, status])

  const resetFilters = () => {
    setSearch('')
    setPhase('all')
    setCategory('all')
    setStatus('all')
  }

  const hasFilters = search !== '' || phase !== 'all' || category !== 'all' || status !== 'all'

  return (
    <>
      <PageHeader
        eyebrow="Knowledge base"
        title="RAG techniques"
        description="Explore the catalog of retrieval-augmented generation techniques: preprocessing, indexing, fusion, selection, validation and orchestration."
        breadcrumbs={[{ label: 'Workspace', to: '/' }, { label: 'Techniques' }]}
        actions={
          <Badge tone="outline" className="h-6 normal-case tracking-normal">
            {wide ? 'Click a technique to inspect it' : 'Tap a technique to inspect it'}
          </Badge>
        }
      />

      <div className="flex min-h-0 flex-1 overflow-hidden">
        <div className="min-w-0 flex-1 overflow-y-auto">
          <div className="border-b border-line/70 px-5 py-4">
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-6">
              <StatCard label="Total techniques" value={techniques.length} icon={BookOpen} color="#9db1ff" />
              <StatCard label="Categories" value={categories.length} icon={Boxes} color="#c4b1ff" />
              <StatCard label="Phases" value={phases.length} icon={Workflow} color="#35d99b" />
              {TECHNIQUE_STATUSES.map((item) => (
                <StatCard
                  key={item}
                  label={statusMeta[item].label}
                  value={techniques.filter((t) => t.status === item).length}
                  icon={item === 'design' ? Sparkles : item === 'integration' ? Workflow : item === 'provider' ? ShieldCheck : Layers3}
                  color={statusMeta[item].color}
                />
              ))}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2 border-b border-line/70 px-5 py-3">
            <SearchInput value={search} onChange={setSearch} placeholder="Search techniques…" className="w-full sm:w-[240px]" />
            <Select
              aria-label="Filter by phase"
              value={phase}
              onValueChange={setPhase}
              placeholder="All phases"
              className="min-w-[140px]"
              options={[{ value: 'all', label: 'All phases' }, ...phases.map((item) => ({ value: item.phase, label: `${item.phase} (${item.count})` }))]}
            />
            <Select
              aria-label="Filter by category"
              value={category}
              onValueChange={setCategory}
              placeholder="All categories"
              className="min-w-[180px]"
              options={[{ value: 'all', label: 'All categories' }, ...categories.map((item) => ({ value: item.category, label: `${item.category} (${item.count})` }))]}
            />
            <Select
              aria-label="Filter by status"
              value={status}
              onValueChange={(value) => setStatus(value === 'all' ? 'all' : (value as TechniqueStatus))}
              placeholder="All statuses"
              className="min-w-[140px]"
              options={[{ value: 'all', label: 'All statuses' }, ...TECHNIQUE_STATUSES.map((item) => ({ value: item, label: statusMeta[item].label }))]}
            />
            {hasFilters && (
              <Button variant="ghost" size="sm" onClick={resetFilters}>
                <RotateCcw className="h-3 w-3" /> Reset
              </Button>
            )}
            <span className="ml-auto font-mono text-[9px] uppercase tracking-wider text-dim">{filtered.length} of {techniques.length} shown</span>
          </div>

          {isLoading && <LoadingState label="Loading techniques catalog…" rows={6} />}
          {isError && <ErrorState message={(error as Error)?.message} onRetry={() => void refetch()} />}

          {!isLoading && !isError && filtered.length === 0 && (
            <EmptyState
              icon={<Search className="h-4 w-4" />}
              title="No techniques match these filters"
              description="Try another phase, category or status, or clear the search."
              action={<Button variant="secondary" size="sm" onClick={resetFilters}>Reset filters</Button>}
            />
          )}

          {!isLoading && !isError && filtered.length > 0 && (
            <div className="grid gap-2.5 p-5 sm:grid-cols-2 2xl:grid-cols-3">
              {filtered.map((technique) => (
                <button
                  key={technique.id}
                  onClick={() => setSelectedId(technique.id)}
                  className={cn(
                    'group flex flex-col rounded-lg border p-3 text-left transition-colors',
                    selectedId === technique.id
                      ? 'border-accent/60 bg-[#111c2e] shadow-[0_0_0_1px_rgba(91,124,250,0.16)]'
                      : 'border-line bg-gradient-to-b from-[#0e1724] to-[#0b1320] hover:border-[#30405a]',
                  )}
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="min-w-0 truncate font-mono text-[8.5px] uppercase tracking-[0.1em] text-dim">{technique.category}</span>
                    <StatusBadge status={technique.status} />
                  </div>
                  <p className="mt-2 text-[11.5px] font-medium text-[#d4deeb]">{technique.name}</p>
                  <p className="mt-1.5 line-clamp-2 min-h-[28px] text-[10px] leading-[1.45] text-[#7f8da2]">{technique.description}</p>
                  <div className="mt-3 flex flex-wrap items-center gap-1.5">
                    <span className="rounded border border-line/80 bg-white/[0.025] px-1.5 py-0.5 font-mono text-[8px] text-muted">{technique.phase}</span>
                    {technique.tags.slice(0, 2).map((tag) => (
                      <span key={tag} className="rounded border border-line/80 bg-white/[0.025] px-1 py-0.5 font-mono text-[8px] text-dim">{tag}</span>
                    ))}
                    <span className="ml-auto font-mono text-[8px] text-[#4c5a70]">{technique.id}</span>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        <aside className="hidden w-[340px] shrink-0 overflow-y-auto border-l border-line bg-[#0a1019] xl:block">
          <TechniqueDetail technique={selected} loading={detailQuery.isLoading} />
        </aside>
      </div>

      <Dialog open={!!selectedId && !wide} onOpenChange={(open) => { if (!open) setSelectedId(null) }}>
        <DialogContent size="lg">
          <DialogHeader eyebrow="Technique detail" title={selected?.name ?? 'Technique'} description={selected ? `${selected.category} · ${selected.phase}` : undefined} />
          <DialogBody className="p-0">
            <TechniqueDetail technique={selected} loading={detailQuery.isLoading} />
          </DialogBody>
        </DialogContent>
      </Dialog>
    </>
  )
}
