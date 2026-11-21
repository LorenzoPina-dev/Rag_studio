import * as React from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ArrowRight,
  CheckCircle2,
  ChevronDown,
  FlaskConical,
  GitCompareArrows,
  Play,
  Plus,
  Search,
  Sparkles,
  Target,
  TrendingUp,
  XCircle,
} from 'lucide-react'
import {
  CartesianGrid,
  Cell,
  LabelList,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from 'recharts'
import { toast } from 'sonner'
import { PageHeader } from '@/components/shared/page'
import { Button } from '@/components/ui/button'
import { SearchInput, Input, Field } from '@/components/ui/input'
import { EmptyState, ErrorState, LoadingState, StatusDot } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/controls'
import { Dialog, DialogBody, DialogContent, DialogFooter, DialogHeader } from '@/components/ui/dialog'
import { Select } from '@/components/ui/select'
import { experimentsApi } from '@/api/experiments.api'
import { datasetsApi } from '@/api/datasets.api'
import { comparisonApi, type ComparisonResponse, type ComparisonVariantInput } from '@/api/comparison.api'
import { isMockMode } from '@/api/client'
import { cn, formatCurrency, formatMs } from '@/lib/utils'
import type { Experiment, ExperimentData } from '@/types'

const RAG_PRESETS: ComparisonVariantInput[] = [
  {
    id: 'hybrid-extractive',
    label: 'Hybrid + extractive',
    config: { retrievalAlgorithm: 'hybrid', generationStrategy: 'extractive' },
  },
  {
    id: 'bm25-concise',
    label: 'BM25 + concise',
    config: { retrievalAlgorithm: 'bm25', generationStrategy: 'concise' },
  },
  {
    id: 'dense-diversity',
    label: 'Dense + diversity',
    config: { retrievalAlgorithm: 'dense', rerankStrategy: 'diversity' },
  },
]

const statusMeta: Record<Experiment['status'], { label: string; dot: 'success' | 'running' | 'warning' | 'danger'; className: string }> = {
  complete: { label: 'Complete', dot: 'success', className: 'text-success' },
  running: { label: 'Running', dot: 'running', className: 'text-accent' },
  failed: { label: 'Failed', dot: 'danger', className: 'text-danger' },
  draft: { label: 'Draft', dot: 'warning', className: 'text-warn' },
}

const tooltipStyle = {
  contentStyle: { background: '#0f1724', border: '1px solid #283549', borderRadius: 6, fontSize: 10, color: '#e5ebf4' },
  labelStyle: { color: '#8995a8', fontSize: 9 },
  itemStyle: { color: '#c5d0df', fontSize: 10 },
}

export function ExperimentsPage() {
  const queryClient = useQueryClient()
  const [search, setSearch] = React.useState('')
  const [status, setStatus] = React.useState('all')
  const [tag, setTag] = React.useState('all')
  const [selected, setSelected] = React.useState<string[]>(['exp_024', 'exp_023', 'exp_022'])
  const [comparison, setComparison] = React.useState<ExperimentData['comparison'] | null>(null)
  const [createOpen, setCreateOpen] = React.useState(false)
  const [newName, setNewName] = React.useState('')
  const [newChunking, setNewChunking] = React.useState('Semantic · 512')
  const [newRetrieval, setNewRetrieval] = React.useState('Hybrid α0.7')
  const [lifted, setLifted] = React.useState(false)
  const [ragQuery, setRagQuery] = React.useState('What is BM25?')
  const [ragDataset, setRagDataset] = React.useState('')
  const [activePresets, setActivePresets] = React.useState<string[]>(RAG_PRESETS.map((preset) => preset.id))
  const [ragResult, setRagResult] = React.useState<ComparisonResponse | null>(null)

  const { data, isLoading, isError, error, refetch } = useQuery({ queryKey: ['experiments'], queryFn: experimentsApi.get })
  const { data: datasetData } = useQuery({ queryKey: ['datasets', 'options'], queryFn: datasetsApi.options })

  const createMutation = useMutation({
    mutationFn: () => experimentsApi.create({ name: newName }),
    onSuccess: (experiment) => {
      queryClient.invalidateQueries({ queryKey: ['experiments'] })
      toast.success('Experiment created', { description: `${experiment.name} is queued and will start shortly.` })
      setCreateOpen(false)
      setNewName('')
      setSelected((prev) => [experiment.id, ...prev].slice(0, 3))
    },
    onError: (err: Error) => toast.error('Could not create experiment', { description: err.message }),
  })

  const compareMutation = useMutation({
    mutationFn: (ids: string[]) => experimentsApi.compare(ids),
    onSuccess: (result) => {
      setComparison(result)
      setLifted(true)
      toast.success('Comparison updated', { description: `${result.ids.length} experiments compared.` })
    },
    onError: (err: Error) => toast.error('Comparison failed', { description: err.message }),
  })

  const ragMutation = useMutation({
    mutationFn: () =>
      comparisonApi.run(
        ragQuery,
        RAG_PRESETS.filter((preset) => activePresets.includes(preset.id)),
        ragDataset || undefined,
      ),
    onSuccess: (result) => {
      setRagResult(result)
      toast.success('Confronto completato', { description: `${result.variants.length} varianti eseguite sulla stessa query.` })
    },
    onError: (err: Error) => toast.error('Confronto non riuscito', { description: err.message }),
  })

  const promoteMutation = useMutation({
    mutationFn: (id: string) => experimentsApi.promote(id),
    onSuccess: () => toast.success('Experiment promoted', { description: 'Its configuration is now the pipeline default.' }),
    onError: (err: Error) => toast.error('Could not promote', { description: err.message }),
  })

  const experiments = data?.experiments ?? []
  const tags = Array.from(new Set(experiments.flatMap((experiment) => experiment.tags))).slice(0, 8)
  const filtered = experiments
    .filter((experiment) => (status === 'all' ? true : experiment.status === status))
    .filter((experiment) => (tag === 'all' ? true : experiment.tags.includes(tag)))
    .filter((experiment) => `${experiment.name} ${experiment.chunking} ${experiment.retrieval} ${experiment.selection}`.toLowerCase().includes(search.toLowerCase()))

  const activeComparison = comparison ?? data?.comparison ?? null
  const comparisonIds = activeComparison?.ids ?? []

  const togglePreset = (id: string) => {
    setActivePresets((prev) =>
      prev.includes(id) ? prev.filter((value) => value !== id) : [...prev, id],
    )
  }

  const toggle = (id: string) => {
    setSelected((prev) => {
      if (prev.includes(id)) return prev.filter((value) => value !== id)
      if (prev.length >= 3) {
        toast.info('Up to three experiments can be compared at once')
        return prev
      }
      return [...prev, id]
    })
  }

  if (isLoading) {
    return (
      <>
        <PageHeader eyebrow="Experimentation workspace" title="Experiment manager" description="Compare pipeline configurations. Find the best trade-off for your use case." />
        <div className="flex-1 overflow-y-auto"><LoadingState label="Loading experiments…" rows={7} /></div>
      </>
    )
  }

  if (isError || !data) {
    return (
      <>
        <PageHeader eyebrow="Experimentation workspace" title="Experiment manager" description="Compare pipeline configurations. Find the best trade-off for your use case." />
        <div className="flex-1 overflow-y-auto"><ErrorState message={(error as Error)?.message} onRetry={() => void refetch()} /></div>
      </>
    )
  }

  return (
    <>
      <PageHeader
        eyebrow="Experimentation workspace"
        title="Experiment manager"
        description="Compare pipeline configurations. Find the best trade-off for your use case."
        breadcrumbs={[{ label: 'Research lab', to: '/' }, { label: 'Experiments' }]}
        actions={
          <Button variant="primary" size="lg" onClick={() => setCreateOpen(true)}>
            <Plus className="h-3.5 w-3.5" /> New experiment
          </Button>
        }
      />

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="space-y-4 px-6 py-4">
          <section className="rounded-lg border border-line bg-[#0c141f] px-4 py-3.5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="font-mono text-[8px] uppercase tracking-[0.14em] text-dim">Real algorithm run</p>
                <h2 className="mt-1 text-[13px] font-semibold tracking-[-0.01em] text-ink">Confronta varianti RAG</h2>
                <p className="mt-0.5 text-[9.5px] text-dim">
                  Stessa query, algoritmi diversi.{' '}
                  {isMockMode
                    ? 'Mock attivo: avvia il backend con VITE_USE_MOCKS=false per risultati reali.'
                    : 'Backend reale connesso.'}
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                {RAG_PRESETS.map((preset) => (
                  <label key={preset.id} className="flex items-center gap-1.5 font-mono text-[8.5px] text-[#aebacc]">
                    <Checkbox
                      checked={activePresets.includes(preset.id)}
                      onCheckedChange={() => togglePreset(preset.id)}
                      aria-label={`Usa variante ${preset.label}`}
                    />
                    {preset.label}
                  </label>
                ))}
              </div>
            </div>

            <div className="mt-3 flex flex-wrap items-end gap-2">
              <Field label="Query" className="min-w-[260px] flex-1">
                <Input
                  value={ragQuery}
                  onChange={(event) => setRagQuery(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' && !ragMutation.isPending) ragMutation.mutate()
                  }}
                  placeholder="What is BM25?"
                />
              </Field>
              <Field label="Dataset" className="min-w-[190px]">
                <Select
                  value={ragDataset}
                  onValueChange={setRagDataset}
                  placeholder="Dataset predefinito"
                  options={[
                    { value: '', label: 'Dataset predefinito' },
                    ...(datasetData ?? []).map((dataset) => ({
                      value: dataset.value,
                      label: dataset.label,
                      description: dataset.description,
                    })),
                  ]}
                  className="w-full"
                />
              </Field>
              <Button
                variant="primary"
                size="sm"
                disabled={ragMutation.isPending || !ragQuery.trim() || activePresets.length < 2}
                onClick={() => ragMutation.mutate()}
              >
                <Play className="h-3 w-3" /> {ragMutation.isPending ? 'Running…' : 'Run comparison'}
              </Button>
            </div>

            {ragResult && (
              <div className="mt-3 grid gap-3 lg:grid-cols-3">
                {ragResult.variants.map((variant) => (
                  <div key={variant.id} className="rounded-md border border-line-strong bg-[#0a1019] px-3 py-2.5">
                    <div className="flex items-start justify-between gap-2">
                      <h3 className="text-[10.5px] font-medium text-ink">{variant.label}</h3>
                      <span className="shrink-0 font-mono text-[8px] text-dim">{formatMs(variant.durationMs)}</span>
                    </div>
                    <div className="mt-1 flex flex-wrap gap-1 font-mono text-[7.5px] text-dim">
                      {['retrieval_algorithm', 'rerank_strategy', 'generation_strategy'].map((key) => (
                        <span key={key} className="rounded border border-line bg-[#0b111b] px-1 py-0.5">
                          {String(variant.config[key] ?? key)}
                        </span>
                      ))}
                    </div>
                    <p className="mt-2 max-h-[92px] overflow-y-auto text-[10px] leading-relaxed text-[#c5d0df]">
                      {variant.answer}
                    </p>
                    <div className="mt-2 border-t border-line/60 pt-2">
                      <p className="font-mono text-[8px] uppercase tracking-[0.1em] text-dim">Top sources</p>
                      {variant.documents.slice(0, 3).map((doc) => (
                        <p key={doc.chunkId ?? doc.rank} className="mt-1 truncate font-mono text-[8px] text-[#8fa0b8]">
                          [{doc.rank}] {doc.title ?? doc.source ?? doc.chunkId} · {Number(doc.score).toFixed(2)}
                        </p>
                      ))}
                    </div>
                    <div className="mt-2 flex flex-wrap gap-2 border-t border-line/60 pt-2 font-mono text-[8px] text-dim">
                      <span>chunks {variant.metrics.chunks}</span>
                      <span>retrieved {variant.metrics.retrieved}</span>
                      <span>selected {variant.metrics.selected}</span>
                      <span>tokens {variant.metrics.tokens}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          <section className="rounded-lg border border-line bg-gradient-to-r from-[#101a2b] to-[#0d1622] px-4 py-3.5">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <p className="font-mono text-[8px] uppercase tracking-[0.14em] text-dim">Active project</p>
                <h2 className="mt-1 text-[15px] font-semibold tracking-[-0.015em] text-ink">{data.project.name}</h2>
                <p className="mt-1 font-mono text-[8.5px] text-dim">{data.project.name === 'Retrieval optimization' ? 'Knowledge assistant' : data.project.name} / {data.project.dataset} / {data.project.questions} questions</p>
              </div>
              <div className="flex flex-wrap items-center gap-6">
                {[
                  ['Experiments', data.summary.experiments, ''],
                  ['Completed', data.summary.completed, 'text-success'],
                  ['Running', data.summary.running, 'text-accent'],
                  ['Best score', data.summary.bestScore.toFixed(2), 'text-success'],
                ].map(([label, value, tone]) => (
                  <div key={String(label)} className="min-w-[66px] text-right">
                    <p className="font-mono text-[8px] uppercase tracking-[0.12em] text-dim">{label}</p>
                    <p className={cn('mt-1 text-[20px] font-semibold leading-none tracking-[-0.02em] text-ink', tone)}>{value}</p>
                  </div>
                ))}
              </div>
            </div>
          </section>

          <div className="flex flex-wrap items-center gap-2">
            <SearchInput value={search} onChange={setSearch} placeholder="Search experiments…" className="w-[250px]" />
            <Select
              value={status}
              onValueChange={setStatus}
              options={[
                { value: 'all', label: 'All statuses' },
                { value: 'complete', label: 'Complete' },
                { value: 'running', label: 'Running' },
                { value: 'failed', label: 'Failed' },
                { value: 'draft', label: 'Draft' },
              ]}
              className="w-[145px]"
              aria-label="Filter by status"
            />
            <Select
              value={tag}
              onValueChange={setTag}
              options={[{ value: 'all', label: 'Tags' }, ...tags.map((value) => ({ value, label: value }))]}
              className="w-[135px]"
              aria-label="Filter by tag"
            />
            <span className="ml-auto font-mono text-[8.5px] text-dim">{selected.length} selected</span>
            <Button
              variant="primary"
              size="sm"
              disabled={selected.length < 2 || compareMutation.isPending}
              onClick={() => compareMutation.mutate(selected)}
            >
              <GitCompareArrows className="h-3.5 w-3.5" /> {compareMutation.isPending ? 'Comparing…' : 'Compare selected'}
            </Button>
          </div>

          <div className="overflow-hidden rounded-lg border border-line bg-[#0c141f]">
            <table className="w-full border-collapse">
              <thead>
                <tr className="border-b border-line">
                  <th className="table-head h-8 w-8 px-3 pl-4">
                    <Checkbox
                      checked={filtered.length > 0 && filtered.every((experiment) => selected.includes(experiment.id))}
                      indeterminate={filtered.some((experiment) => selected.includes(experiment.id)) && !filtered.every((experiment) => selected.includes(experiment.id))}
                      onCheckedChange={(checked) => setSelected(checked ? filtered.slice(0, 3).map((experiment) => experiment.id) : [])}
                      aria-label="Select all experiments"
                    />
                  </th>
                  {['Experiment', 'Chunking', 'Retrieval', 'Selection', 'Faithfulness ↓', 'Latency', 'Cost / query', 'Status'].map((header) => (
                    <th key={header} className={cn('table-head h-8 px-3 text-left last:pr-4', ['Latency', 'Cost / query'].includes(header) && 'hidden lg:table-cell')}>{header}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 ? (
                  <tr><td colSpan={9} className="px-4 py-10 text-center font-mono text-[9.5px] text-dim">No experiments match these filters.</td></tr>
                ) : filtered.map((experiment) => {
                  const isSelected = selected.includes(experiment.id)
                  const meta = statusMeta[experiment.status]
                  return (
                    <tr key={experiment.id} onClick={() => toggle(experiment.id)} className={cn('table-row cursor-pointer last:border-0', isSelected && 'bg-accent/[0.06] hover:bg-accent/[0.08]')}>
                      <td className="px-3 py-2.5 pl-4" onClick={(event) => event.stopPropagation()}>
                        <Checkbox checked={isSelected} onCheckedChange={() => toggle(experiment.id)} aria-label={`Compare ${experiment.name}`} />
                      </td>
                      <td className="px-3 py-2.5">
                        <p className="text-[10.5px] text-[#c5d0df]">{experiment.name}</p>
                        <p className="mt-0.5 font-mono text-[8px] text-dim">{experiment.createdAt}</p>
                      </td>
                      <td className="px-3 py-2.5 font-mono text-[9px] text-[#8fa0b8]">{experiment.chunking}</td>
                      <td className="px-3 py-2.5 font-mono text-[9px] text-[#8fa0b8]">{experiment.retrieval}</td>
                      <td className="px-3 py-2.5 font-mono text-[9px] text-[#8fa0b8]">{experiment.selection}</td>
                      <td className="px-3 py-2.5 font-mono text-[9.5px]">
                        <span className={experiment.faithfulness === null ? 'text-dim' : experiment.faithfulness >= 0.9 ? 'text-success' : 'text-[#b8c4d6]'}>
                          {experiment.faithfulness?.toFixed(2) ?? '—'}
                        </span>
                      </td>
                      <td className="hidden px-3 py-2.5 font-mono text-[9px] text-[#8fa0b8] lg:table-cell">{experiment.latency ? `${experiment.latency.toFixed(2)}s` : '—'}</td>
                      <td className="hidden px-3 py-2.5 font-mono text-[9px] text-[#8fa0b8] lg:table-cell">{experiment.cost ? formatCurrency(experiment.cost) : '—'}</td>
                      <td className="px-3 py-2.5 pr-4">
                        <span className={cn('flex items-center gap-1.5 font-mono text-[8.5px]', meta.className)}>
                          <StatusDot status={meta.dot} pulse={meta.dot === 'running'} /> {meta.label}
                        </span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          <section>
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-[13px] font-semibold tracking-[-0.01em] text-ink">Comparison workspace</h2>
              <div className="flex items-center gap-2 font-mono text-[8.5px] text-dim">
                {comparisonIds.map((id, index) => (
                  <React.Fragment key={id}>
                    {index > 0 && <span className="uppercase text-[#3c4a60]">vs</span>}
                    <span className="rounded border border-line-strong bg-[#0b111b] px-1.5 py-0.5 text-[#aebacc]">{id.replace('_', '-').toUpperCase()}</span>
                  </React.Fragment>
                ))}
                {lifted && <span className="flex items-center gap-1 text-success"><CheckCircle2 className="h-2.5 w-2.5" /> live</span>}
              </div>
            </div>

            {selected.length < 2 ? (
              <div className="rounded-lg border border-line bg-surface">
                <EmptyState
                  icon={<GitCompareArrows className="h-4 w-4" />}
                  title="Select at least two experiments"
                  description="Use the checkboxes above to compare configurations side by side."
                  action={<Button variant="secondary" size="sm" onClick={() => setSelected(experiments.slice(0, 3).map((experiment) => experiment.id))}>Select top 3</Button>}
                />
              </div>
            ) : activeComparison ? (
              <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
                <div className="rounded-lg border border-line bg-[#0c141f] px-4 py-3">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <h3 className="text-[12px] font-medium text-ink">Quality vs. latency</h3>
                      <p className="mt-0.5 text-[9.5px] text-dim">Higher quality, lower latency is better</p>
                    </div>
                    <TrendingUp className="h-3.5 w-3.5 text-dim" />
                  </div>
                  <div className="mt-2 h-[196px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <ScatterChart margin={{ top: 18, right: 16, bottom: 2, left: -16 }}>
                        <CartesianGrid strokeDasharray="2 4" />
                        <XAxis type="number" dataKey="latency" name="Latency" unit="s" domain={[0.5, 1.8]} tickLine={false} axisLine={false} tick={{ fontSize: 8.5 }} />
                        <YAxis type="number" dataKey="faithfulness" name="Faithfulness" domain={[0.84, 0.94]} tickLine={false} axisLine={false} tick={{ fontSize: 8.5 }} />
                        <ZAxis range={[46, 46]} />
                        <Tooltip {...tooltipStyle} cursor={{ strokeDasharray: '3 3', stroke: '#3c4a60' }} formatter={(value: number, name: string) => [name === 'Latency' ? `${value.toFixed(2)}s` : value.toFixed(2), name]} />
                        <Scatter data={activeComparison.scatter} name="Experiments" isAnimationActive={false}>
                          {activeComparison.scatter.map((point) => <Cell key={point.id} fill={point.accent} stroke="#0c141f" strokeWidth={1} />)}
                          <LabelList dataKey="name" position="top" style={{ fill: '#8995a8', fontSize: 8.5 }} />
                        </Scatter>
                      </ScatterChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                <div className="overflow-hidden rounded-lg border border-line bg-[#0c141f]">
                  <div className="flex items-center justify-between px-4 py-2.5">
                    <h3 className="text-[12px] font-medium text-ink">Configuration diff</h3>
                    <GitCompareArrows className="h-3.5 w-3.5 text-dim" />
                  </div>
                  <table className="w-full border-collapse">
                    <thead>
                      <tr className="border-y border-line">
                        <th className="table-head h-7 px-3 pl-4 text-left">Parameter</th>
                        {comparisonIds.map((id) => <th key={id} className="table-head h-7 px-3 text-left last:pr-4">{id.replace('_', '-').toUpperCase()}</th>)}
                      </tr>
                    </thead>
                    <tbody>
                      {activeComparison.parameters.map((parameter) => (
                        <tr key={parameter.key} className="border-b border-line/50 last:border-0">
                          <td className="px-3 py-2 pl-4 font-mono text-[8.5px] text-dim">{parameter.key}</td>
                          {parameter.values.map((value, index) => (
                            <td key={index} className={cn('px-3 py-2 font-mono text-[9px] last:pr-4', parameter.key === 'Faithfulness' && index === 0 ? 'text-success' : 'text-[#aebacc]')}>{value}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <div className="mx-3 mb-3 mt-2 rounded border border-success/20 bg-success/[0.05] px-2.5 py-2">
                    <p className="flex items-start gap-1.5 font-mono text-[8.5px] leading-relaxed text-[#8edcbc]">
                      <Sparkles className="mt-0.5 h-2.5 w-2.5 shrink-0" /> {activeComparison.insight}
                    </p>
                  </div>
                </div>
              </div>
            ) : null}
          </section>

          <div className="flex flex-wrap items-center justify-between gap-2 border-t border-line/60 pt-2 font-mono text-[8.5px] text-dim">
            <span className="flex items-center gap-1.5"><FlaskConical className="h-3 w-3" /> Experiments are reproducible from pinned configuration hashes</span>
            <button
              onClick={() => {
                const best = selected[0] ?? experiments[0]?.id
                if (best) promoteMutation.mutate(best)
              }}
              disabled={!selected.length || promoteMutation.isPending}
              className="flex items-center gap-1 text-[#7f95cf] hover:text-[#b5c6ff] disabled:opacity-40"
            >
              Promote to pipeline <ArrowRight className="h-2.5 w-2.5" />
            </button>
          </div>
        </div>
      </div>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent size="md">
          <DialogHeader eyebrow="Experimentation" title="New experiment" description="Create a configuration to compare against your current pipeline." />
          <DialogBody className="space-y-4">
            <Field label="Experiment name"><Input value={newName} onChange={(event) => setNewName(event.target.value)} placeholder="e.g. EXP-026 Wider recall" autoFocus /></Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Chunking">
                <Select value={newChunking} onValueChange={setNewChunking} options={['Semantic · 512', 'Semantic · 768', 'Recursive · 512', 'Recursive · 256']} />
              </Field>
              <Field label="Retrieval">
                <Select value={newRetrieval} onValueChange={setNewRetrieval} options={['Hybrid α0.7', 'Hybrid α0.5', 'Dense only', 'BM25']} />
              </Field>
            </div>
            <div className="rounded-md border border-line bg-[#0b111b] px-3 py-2.5">
              <p className="font-mono text-[8px] uppercase tracking-[0.12em] text-dim">Evaluation plan</p>
              <p className="mt-1 text-[10.5px] text-muted">{data.project.dataset} · {data.project.questions} questions · judged by GPT-4o</p>
              <p className="mt-1 flex items-center gap-1.5 font-mono text-[8.5px] text-dim"><Target className="h-2.5 w-2.5" /> The run will use the current pipeline graph with the overrides above.</p>
            </div>
          </DialogBody>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setCreateOpen(false)}>Cancel</Button>
            <Button variant="primary" disabled={!newName.trim() || createMutation.isPending} onClick={() => createMutation.mutate()}>
              <Play className="h-3.5 w-3.5" /> {createMutation.isPending ? 'Creating…' : 'Create & run'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
