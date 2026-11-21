import * as React from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ArrowRight,
  ArrowUpRight,
  CheckCircle2,
  Download,
  Filter,
  Gauge,
  Play,
  Search,
  Settings2,
  SlidersHorizontal,
  Target,
  TriangleAlert,
} from 'lucide-react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { toast } from 'sonner'
import { PageHeader } from '@/components/shared/page'
import { Button } from '@/components/ui/button'
import { SearchInput, Input, Field } from '@/components/ui/input'
import { ErrorState, LoadingState, StatusDot } from '@/components/ui/badge'
import { Dialog, DialogBody, DialogContent, DialogFooter, DialogHeader } from '@/components/ui/dialog'
import { Select } from '@/components/ui/select'
import { Switch } from '@/components/ui/controls'
import { evaluationsApi } from '@/api/evaluations.api'
import { useAppStore } from '@/store/useAppStore'
import { cn, formatNumber } from '@/lib/utils'
import type { EvaluationData, QuestionResult } from '@/types'

const tooltipStyle = {
  contentStyle: { background: '#0f1724', border: '1px solid #283549', borderRadius: 6, fontSize: 10, color: '#e5ebf4' },
  labelStyle: { color: '#8995a8', fontSize: 9 },
  itemStyle: { color: '#c5d0df', fontSize: 10 },
}

function MetricCard({ metric, index }: { metric: EvaluationData['metrics'][number]; index: number }) {
  return (
    <div className="rounded-lg border border-line bg-gradient-to-b from-[#101927] to-[#0d1622] px-4 py-3.5">
      <div className="flex items-start justify-between">
        <p className="text-[11px] font-medium text-muted">{metric.label}</p>
        <ArrowUpRight className="h-3.5 w-3.5 text-[#6f7f98]" />
      </div>
      <div className="mt-2 flex items-end justify-between gap-2">
        <span className="text-[27px] font-semibold leading-none tracking-[-0.035em] text-ink tabular-nums">{metric.value.toFixed(2)}</span>
        <span className="mb-0.5 font-mono text-[8.5px] text-success">{metric.delta}</span>
      </div>
      <div className="mt-2.5 h-[2px] overflow-hidden rounded-full bg-[#1a2433]">
        <div className="h-full rounded-full" style={{ width: `${metric.value * 100}%`, backgroundColor: ['#7296FF', '#35D99B', '#A78BFA', '#39D6D0'][index % 4] }} />
      </div>
    </div>
  )
}

function ResultBadge({ question }: { question: QuestionResult }) {
  if (question.reviewStatus === 'passed') return <span className="flex items-center gap-1 font-mono text-[8.5px] text-success"><CheckCircle2 className="h-2.5 w-2.5" /> Passed</span>
  if (question.reviewStatus === 'review') return <span className="flex items-center gap-1 font-mono text-[8.5px] text-warn"><TriangleAlert className="h-2.5 w-2.5" /> Review</span>
  return <span className="flex items-center gap-1 font-mono text-[8.5px] text-danger"><TriangleAlert className="h-2.5 w-2.5" /> Failed</span>
}

export function EvaluationPage() {
  const queryClient = useQueryClient()
  const pushNotification = useAppStore((state) => state.pushNotification)
  const [search, setSearch] = React.useState('')
  const [resultFilter, setResultFilter] = React.useState('all')
  const [range, setRange] = React.useState('30d')
  const [pipeline, setPipeline] = React.useState('Hybrid RAG pipeline')
  const [dataset, setDataset] = React.useState('rag_benchmark_v3')
  const [runOpen, setRunOpen] = React.useState(false)
  const [settingsOpen, setSettingsOpen] = React.useState(false)
  const [runSample, setRunSample] = React.useState(200)
  const [runDataset, setRunDataset] = React.useState('rag_benchmark_v3')
  const [settingsDraft, setSettingsDraft] = React.useState<EvaluationData['settings'] | null>(null)
  const [page, setPage] = React.useState(1)

  const { data, isLoading, isError, error, refetch } = useQuery({ queryKey: ['evaluation'], queryFn: evaluationsApi.get })

  const runMutation = useMutation({
    mutationFn: () => evaluationsApi.run({ pipeline, dataset: runDataset, sampleSize: runSample }),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['evaluation'] })
      pushNotification({ title: 'Evaluation started', body: `${pipeline} is being scored on ${runDataset}.`, type: 'info' })
      toast.success('Evaluation started', { description: `${result.id} · ${runSample} questions queued.` })
      setRunOpen(false)
    },
    onError: (err: Error) => toast.error('Could not start evaluation', { description: err.message }),
  })

  const settingsMutation = useMutation({
    mutationFn: (input: Partial<EvaluationData['settings']>) => evaluationsApi.updateSettings(input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['evaluation'] })
      toast.success('Evaluation settings saved')
      setSettingsOpen(false)
    },
    onError: (err: Error) => toast.error('Could not save settings', { description: err.message }),
  })

  const questions = data?.questions ?? []
  const filteredQuestions = questions
    .filter((question) => (resultFilter === 'all' ? true : resultFilter === 'passed' ? question.passed : resultFilter === 'review' ? question.reviewStatus === 'review' : question.reviewStatus === 'failed'))
    .filter((question) => question.question.toLowerCase().includes(search.toLowerCase()))
  const pageSize = 8
  const pages = Math.max(1, Math.ceil(filteredQuestions.length / pageSize))
  const paged = filteredQuestions.slice((page - 1) * pageSize, page * pageSize)

  React.useEffect(() => setPage(1), [search, resultFilter])

  if (isLoading) {
    return (
      <>
        <PageHeader eyebrow="Quality workspace" title="Evaluation dashboard" description="Measure retrieval quality and answer reliability against your ground truth." />
        <div className="flex-1 overflow-y-auto"><LoadingState label="Loading evaluation results…" rows={8} /></div>
      </>
    )
  }

  if (isError || !data) {
    return (
      <>
        <PageHeader eyebrow="Quality workspace" title="Evaluation dashboard" description="Measure retrieval quality and answer reliability against your ground truth." />
        <div className="flex-1 overflow-y-auto"><ErrorState message={(error as Error)?.message} onRetry={() => void refetch()} /></div>
      </>
    )
  }

  return (
    <>
      <PageHeader
        eyebrow="Quality workspace"
        title="Evaluation dashboard"
        description="Measure retrieval quality and answer reliability against your ground truth."
        breadcrumbs={[{ label: 'Research lab', to: '/' }, { label: 'Quality' }, { label: 'Evaluation' }]}
        actions={
          <>
            <Button variant="secondary" onClick={() => void evaluationsApi.exportReport().then(() => toast.success('Report exported'))}>
              <Download className="h-3.5 w-3.5" /> Export report
            </Button>
            <Button variant="secondary" onClick={() => { setSettingsDraft(data.settings); setSettingsOpen(true) }}><Settings2 className="h-3.5 w-3.5" /> Configure</Button>
            <Button variant="primary" size="lg" onClick={() => setRunOpen(true)}><Play className="h-3.5 w-3.5" /> Run evaluation</Button>
          </>
        }
      />

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="space-y-4 px-6 py-4">
          <div className="flex flex-wrap items-center gap-2">
            <Select
              value={pipeline}
              onValueChange={setPipeline}
              options={['Hybrid RAG pipeline', 'Semantic search v2', 'Support FAQ retrieval']}
              className="w-[210px]"
              aria-label="Evaluation pipeline"
            />
            <Select
              value={dataset}
              onValueChange={setDataset}
              options={['rag_benchmark_v3', 'support_golden_set', 'product_docs']}
              className="w-[210px]"
              aria-label="Evaluation dataset"
            />
            <Select
              value={range}
              onValueChange={setRange}
              options={[
                { value: '7d', label: 'Last 7 days' },
                { value: '30d', label: 'Last 30 days' },
                { value: '90d', label: 'Last 90 days' },
                { value: 'all', label: 'All time' },
              ]}
              className="ml-auto w-[140px]"
              aria-label="Date range"
            />
          </div>

          <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            {data.metrics.map((metric, index) => <MetricCard key={metric.id} metric={metric} index={index} />)}
          </section>

          <section className="grid gap-3 xl:grid-cols-2">
            <div className="rounded-lg border border-line bg-[#0c141f] px-4 py-3">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <h2 className="text-[12px] font-medium text-ink">Answer quality over time</h2>
                  <p className="mt-0.5 text-[9.5px] text-dim">Average score across {data.meta.total} benchmark questions</p>
                </div>
                <div className="flex items-center gap-3 font-mono text-[8px] text-dim">
                  <span className="flex items-center gap-1.5"><span className="h-[2px] w-4 bg-[#7296FF]" /> Current</span>
                  <span className="flex items-center gap-1.5"><span className="h-[2px] w-4 border-t border-dashed border-[#7c8aa0]" /> Baseline</span>
                </div>
              </div>
              <div className="mt-3 h-[188px]">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={data.trend} margin={{ top: 8, right: 6, bottom: 0, left: -18 }}>
                    <CartesianGrid strokeDasharray="2 4" vertical={false} />
                    <XAxis dataKey="date" tickLine={false} axisLine={false} tick={{ fontSize: 8.5 }} interval={1} />
                    <YAxis domain={[0.6, 1]} ticks={[0.6, 0.7, 0.8, 0.9, 1]} tickLine={false} axisLine={false} tick={{ fontSize: 8.5 }} />
                    <Tooltip {...tooltipStyle} formatter={(value: number) => value.toFixed(3)} />
                    <Line type="monotone" dataKey="baseline" stroke="#71809a" strokeWidth={1.2} strokeDasharray="4 4" dot={false} isAnimationActive={false} />
                    <Line type="monotone" dataKey="current" stroke="#7296FF" strokeWidth={1.8} dot={false} activeDot={{ r: 3, fill: '#7296FF' }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="rounded-lg border border-line bg-[#0c141f] px-4 py-3">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <h2 className="text-[12px] font-medium text-ink">Metric comparison</h2>
                  <p className="mt-0.5 text-[9.5px] text-dim">Current pipeline vs. production baseline</p>
                </div>
                <div className="flex items-center gap-3 font-mono text-[8px] text-dim">
                  <span className="flex items-center gap-1.5"><span className="h-2 w-3 rounded-sm bg-[#7296FF]" /> Current</span>
                  <span className="flex items-center gap-1.5"><span className="h-2 w-3 rounded-sm bg-[#A78BFA]" /> Baseline</span>
                </div>
              </div>
              <div className="mt-3 h-[188px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={data.comparison} margin={{ top: 8, right: 6, bottom: 0, left: -18 }} barGap={3}>
                    <CartesianGrid strokeDasharray="2 4" vertical={false} />
                    <XAxis dataKey="metric" tickLine={false} axisLine={false} tick={{ fontSize: 8.5 }} />
                    <YAxis domain={[0, 1]} ticks={[0, 0.25, 0.5, 0.75, 1]} tickLine={false} axisLine={false} tick={{ fontSize: 8.5 }} />
                    <Tooltip {...tooltipStyle} formatter={(value: number) => value.toFixed(3)} cursor={{ fill: 'rgba(255,255,255,0.025)' }} />
                    <Bar dataKey="current" fill="#7296FF" radius={[2, 2, 0, 0]} barSize={17} isAnimationActive={false}>
                      {data.comparison.map((entry) => <Cell key={entry.metric} fill="#7296FF" />)}
                    </Bar>
                    <Bar dataKey="baseline" fill="#A78BFA" radius={[2, 2, 0, 0]} barSize={17} isAnimationActive={false} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </section>

          <section>
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <h2 className="text-[13px] font-semibold tracking-[-0.01em] text-ink">Question-level results</h2>
                <span className="font-mono text-[8.5px] text-dim">{data.meta.total} questions</span>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-[8.5px] text-dim">{data.meta.passed} passed · {data.meta.failed} below threshold</span>
                <SearchInput value={search} onChange={setSearch} placeholder="Search questions…" className="w-[200px]" />
                <Select
                  value={resultFilter}
                  onValueChange={setResultFilter}
                  options={[
                    { value: 'all', label: 'All results' },
                    { value: 'passed', label: 'Passed' },
                    { value: 'review', label: 'Needs review' },
                    { value: 'failed', label: 'Failed' },
                  ]}
                  className="w-[140px]"
                  aria-label="Filter results"
                />
              </div>
            </div>
            <div className="overflow-hidden rounded-lg border border-line bg-[#0c141f]">
              <table className="w-full border-collapse">
                <thead>
                  <tr className="border-b border-line">
                    {['Question', 'Faithfulness', 'Relevance', 'Context precision', 'Context recall', 'Result'].map((header) => (
                      <th key={header} className={cn('table-head h-8 px-3 text-left first:pl-4 last:pr-4', header === 'Context recall' && 'hidden 2xl:table-cell')}>{header}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {paged.length === 0 ? (
                    <tr><td colSpan={6} className="px-4 py-8 text-center font-mono text-[9.5px] text-dim">No questions match this filter.</td></tr>
                  ) : paged.map((question) => (
                    <tr key={question.id} className="table-row last:border-0">
                      <td className="max-w-[360px] px-3 py-2.5 pl-4">
                        <p className="truncate text-[10.5px] text-[#c5d0df]">{question.question}</p>
                      </td>
                      <td className="px-3 py-2.5 font-mono text-[9.5px] text-[#aebacc]">{question.faithfulness.toFixed(2)}</td>
                      <td className="px-3 py-2.5 font-mono text-[9.5px] text-[#aebacc]">{question.relevance.toFixed(2)}</td>
                      <td className="px-3 py-2.5 font-mono text-[9.5px] text-[#aebacc]">{question.contextPrecision.toFixed(2)}</td>
                      <td className="hidden px-3 py-2.5 font-mono text-[9.5px] text-[#aebacc] 2xl:table-cell">{question.contextRecall.toFixed(2)}</td>
                      <td className="px-3 py-2.5 pr-4"><ResultBadge question={question} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {filteredQuestions.length > pageSize && (
                <div className="flex items-center justify-between border-t border-line px-4 py-2.5">
                  <span className="font-mono text-[8.5px] text-dim">Showing {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, filteredQuestions.length)} of {filteredQuestions.length} of {filteredQuestions.length}</span>
                  <div className="flex items-center gap-1">
                    <Button variant="ghost" size="xs" disabled={page <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))}>Prev</Button>
                    <span className="px-1 font-mono text-[9px] text-dim">{page} / {pages}</span>
                    <Button variant="ghost" size="xs" disabled={page >= pages} onClick={() => setPage((value) => Math.min(pages, value + 1))}>Next</Button>
                  </div>
                </div>
              )}
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-[8.5px] text-dim">
              <span>Scored with RAGAS 0.8.2</span>
              <span className="text-[#344158]">·</span>
              <span>Judge: {data.meta.judge}</span>
              <span className="text-[#344158]">·</span>
              <span>Pass threshold: {data.settings.passThreshold.toFixed(2)}</span>
              <span className="text-[#344158]">·</span>
              <span>Last evaluated {data.meta.lastEvaluated}</span>
              <span className="ml-auto flex items-center gap-1.5 text-success"><StatusDot status="success" /> Evaluation healthy</span>
            </div>
          </section>
        </div>
      </div>

      <Dialog open={runOpen} onOpenChange={setRunOpen}>
        <DialogContent size="md">
          <DialogHeader eyebrow="Quality" title="Run evaluation" description="Score a pipeline against a labelled question set." />
          <DialogBody className="space-y-4">
            <Field label="Pipeline"><Select value={pipeline} onValueChange={setPipeline} options={['Hybrid RAG pipeline', 'Semantic search v2', 'Support FAQ retrieval']} /></Field>
            <Field label="Benchmark dataset" hint="Questions include ground-truth answers and reference contexts."><Select value={runDataset} onValueChange={setRunDataset} options={['rag_benchmark_v3', 'support_golden_set', 'product_docs']} /></Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Sample size"><Input type="number" value={runSample} onChange={(event) => setRunSample(Number(event.target.value) || 1)} min={1} max={2000} /></Field>
              <Field label="Judge model"><Select value={data.settings.judge} onValueChange={() => {}} options={['GPT-4o', 'GPT-4o mini', 'Claude 3.5 Sonnet']} /></Field>
            </div>
            <div className="rounded-md border border-line bg-[#0b111b] px-3 py-2.5 font-mono text-[8.5px] text-dim">
              Estimated cost <span className="text-muted">$0.84</span> <span className="text-[#344158]">·</span> estimated time <span className="text-muted">2m 40s</span>
            </div>
          </DialogBody>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setRunOpen(false)}>Cancel</Button>
            <Button variant="primary" disabled={runMutation.isPending} onClick={() => runMutation.mutate()}>
              <Play className="h-3.5 w-3.5" /> {runMutation.isPending ? 'Starting…' : 'Run evaluation'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={settingsOpen} onOpenChange={setSettingsOpen}>
        <DialogContent size="lg">
          <DialogHeader eyebrow="Quality" title="Evaluation settings" description="Thresholds, judge configuration and metric weighting." />
          <DialogBody className="space-y-4">
            {settingsDraft && (
              <>
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Pass threshold" hint="Questions below this score are flagged for review.">
                    <Input type="number" step="0.01" min="0" max="1" value={settingsDraft.passThreshold} onChange={(event) => setSettingsDraft({ ...settingsDraft, passThreshold: Number(event.target.value) })} />
                  </Field>
                  <Field label="Default sample size">
                    <Input type="number" min="1" value={settingsDraft.sampleSize} onChange={(event) => setSettingsDraft({ ...settingsDraft, sampleSize: Number(event.target.value) })} />
                  </Field>
                </div>
                <Field label="Judge model"><Select value={settingsDraft.judge} onValueChange={(value) => setSettingsDraft({ ...settingsDraft, judge: value })} options={['GPT-4o', 'GPT-4o mini', 'Claude 3.5 Sonnet', 'Local Llama 3.1']} /></Field>
                <Switch checked={settingsDraft.autoRun} onCheckedChange={(value) => setSettingsDraft({ ...settingsDraft, autoRun: value })} label="Run evaluation automatically after each production deploy" />
                <div>
                  <p className="mb-2 text-[11.5px] font-medium text-muted">Metric weights</p>
                  <div className="space-y-2.5">
                    {(Object.entries(settingsDraft.metricWeights) as Array<[keyof typeof settingsDraft.metricWeights, number]>).map(([key, value]) => (
                      <div key={key} className="flex items-center gap-3">
                        <span className="w-[92px] font-mono text-[9.5px] capitalize text-[#aebacc]">{key}</span>
                        <input
                          type="range"
                          min="0"
                          max="1"
                          step="0.05"
                          value={value}
                          onChange={(event) => setSettingsDraft({ ...settingsDraft, metricWeights: { ...settingsDraft.metricWeights, [key]: Number(event.target.value) } })}
                          className="h-1 flex-1 accent-[#7296FF]"
                        />
                        <span className="w-[34px] text-right font-mono text-[9px] text-dim">{value.toFixed(2)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </>
            )}
          </DialogBody>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setSettingsOpen(false)}>Cancel</Button>
            <Button variant="primary" disabled={settingsMutation.isPending || !settingsDraft} onClick={() => settingsDraft && settingsMutation.mutate(settingsDraft)}>Save settings</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
