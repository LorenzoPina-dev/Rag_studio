import * as React from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Code2, Copy, ExternalLink, Info, SlidersHorizontal, Trash2, Boxes } from 'lucide-react'
import { usePipelineStore } from '@/store/usePipelineStore'
import { datasetsApi } from '@/api/datasets.api'
import { nodesApi } from '@/api/nodes.api'
import { nodeDefById, PORT_COLORS } from '@/api/mock/pipelineSeed'
import { Switch } from '@/components/ui/controls'
import { Select } from '@/components/ui/select'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { toast } from 'sonner'

function ParamField({
  label,
  type,
  value,
  unit,
  options,
  help,
  onChange,
}: {
  label: string
  type: 'text' | 'number' | 'select' | 'boolean' | 'textarea'
  value: string | number | boolean
  unit?: string
  options?: Array<string | { value: string; label: string; description?: string }>
  help?: string
  onChange: (value: string | number | boolean) => void
}) {
  return (
    <div className="space-y-1.5">
      <label className="flex items-center gap-1 text-[10.5px] text-[#8c99ad]">
        {type === 'boolean' && <span className="h-1 w-1 rounded-full bg-success" />}
        {label}
      </label>
      {type === 'select' ? (
        <Select value={String(value)} onValueChange={onChange} options={options ?? []} mono />
      ) : type === 'boolean' ? (
        <div className="flex h-8 items-center justify-between rounded-md border border-[#233044] bg-[#0a1019] px-2.5">
          <span className="font-mono text-[10px] text-[#aab5c6]">{value ? 'Enabled' : 'Disabled'}</span>
          <Switch checked={Boolean(value)} onCheckedChange={onChange} />
        </div>
      ) : type === 'number' ? (
        <div className="relative">
          <input
            type="number"
            value={Number(value)}
            onChange={(e) => onChange(e.target.value === '' ? 0 : Number(e.target.value))}
            className="h-8 w-full rounded-md border border-[#233044] bg-[#0a1019] px-2.5 font-mono text-[11px] text-ink transition-colors focus:border-accent/60 focus:outline-none"
          />
          {unit && <span className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 font-mono text-[9px] text-dim">{unit}</span>}
        </div>
      ) : (
        <input
          value={String(value)}
          onChange={(e) => onChange(e.target.value)}
          className="h-8 w-full rounded-md border border-[#233044] bg-[#0a1019] px-2.5 font-mono text-[11px] text-ink transition-colors focus:border-accent/60 focus:outline-none"
        />
      )}
      {help && <p className="text-[9.5px] leading-relaxed text-[#5e6b80]">{help}</p>}
    </div>
  )
}

export function NodeInspector({ onClose }: { onClose?: () => void }) {
  const navigate = useNavigate()
  const selectedNodeId = usePipelineStore((s) => s.selectedNodeId)
  const nodes = usePipelineStore((s) => s.nodes)
  const inspectorTab = usePipelineStore((s) => s.inspectorTab)
  const setInspectorTab = usePipelineStore((s) => s.setInspectorTab)
  const updateNodeConfig = usePipelineStore((s) => s.updateNodeConfig)
  const duplicateNode = usePipelineStore((s) => s.duplicateNode)
  const removeNode = usePipelineStore((s) => s.removeNode)
  const edges = usePipelineStore((s) => s.edges)

  const selected = nodes.find((n) => n.id === selectedNodeId)?.data.pipelineNode
  const definitionId = selected?.definitionId
  const isDocumentSource = definitionId === 'document-source'
  const datasetsQuery = useQuery({
    queryKey: ['datasets', 'options'],
    queryFn: datasetsApi.options,
    enabled: isDocumentSource,
  })
  const definitionsQuery = useQuery({
    queryKey: ['nodes'],
    queryFn: nodesApi.list,
    staleTime: 300_000,
  })
  const implementationQuery = useQuery({
    queryKey: ['node-implementation', definitionId],
    queryFn: () => nodesApi.implementation(definitionId ?? ''),
    enabled: Boolean(definitionId) && inspectorTab === 'docs',
  })
  const hidden = !selected

  if (hidden) {
    return (
      <aside className="flex h-full w-[286px] shrink-0 flex-col border-l border-line bg-[#0b111b]">
        <div className="flex h-[42px] items-center justify-between border-b border-line px-3.5">
          <span className="font-mono text-[9px] font-medium uppercase tracking-[0.13em] text-[#a5b0c1]">Node Inspector</span>
          {onClose && (
            <button onClick={onClose} className="rounded p-1 text-dim hover:bg-white/5 hover:text-ink xl:hidden" aria-label="Hide inspector">
              <SlidersHorizontal className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
        <div className="flex flex-1 flex-col items-center justify-center px-8 text-center">
          <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg border border-line bg-surface2 text-dim">
            <Boxes className="h-4 w-4" />
          </div>
          <p className="text-[11.5px] font-medium text-muted">No node selected</p>
          <p className="mt-1.5 text-[10px] leading-relaxed text-dim">Select a node on the canvas to inspect its configuration, typed ports and documentation.</p>
        </div>
      </aside>
    )
  }

  const node = selected
  const definition = definitionsQuery.data?.find((item) => item.id === node.definitionId) ?? nodeDefById[node.definitionId]
  const connectedInputs = new Set(edges.filter((e) => e.target === node.id).map((e) => e.targetHandle))
  const connectedOutputs = new Set(edges.filter((e) => e.source === node.id).map((e) => e.sourceHandle))

  return (
    <aside className="flex h-full w-[286px] shrink-0 flex-col border-l border-line bg-[#0b111b]">
      <div className="flex h-[42px] shrink-0 items-center justify-between border-b border-line px-3.5">
        <span className="font-mono text-[9px] font-medium uppercase tracking-[0.13em] text-[#a5b0c1]">Node Inspector</span>
        <div className="flex items-center gap-1">
          <span className="h-1.5 w-1.5 rounded-full" style={{ background: node.accent }} />
          {onClose && (
            <button onClick={onClose} className="rounded p-1 text-dim hover:bg-white/5 hover:text-ink xl:hidden" aria-label="Hide inspector">
              <SlidersHorizontal className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="border-b border-line px-3.5 pb-3 pt-3.5">
          <h2 className="text-[16px] font-semibold tracking-[-0.015em] text-ink">{node.name}</h2>
          <p className="mt-1 font-mono text-[9.5px]" style={{ color: node.accent }}>
            {node.kind.charAt(0).toUpperCase() + node.kind.slice(1)} / {node.category}
          </p>
          <div className="mt-3 flex items-center gap-4">
            {(['params', 'io', 'docs'] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setInspectorTab(tab)}
                className={cn(
                  'relative border-b border-transparent pb-1.5 text-[10.5px] transition-colors',
                  inspectorTab === tab ? 'border-[#5570e8] text-[#bccaff]' : 'text-[#7d8a9f] hover:text-ink',
                )}
              >
                {tab === 'params' ? 'Parameters' : tab === 'io' ? 'I/O' : 'Docs'}
              </button>
            ))}
          </div>
        </div>

        {inspectorTab === 'params' && (
          <div className="px-3.5 py-3.5">
            <p className="mb-3 font-mono text-[8.5px] uppercase tracking-[0.14em] text-[#5e6b80]">Configuration</p>
            <div className="space-y-3">
              {definition?.params.map((param) => {
                const isDatasetParam = param.key === 'dataset' && isDocumentSource
                const datasets = datasetsQuery.data ?? []
                const datasetOptions = isDatasetParam ? datasets : param.options
                const rawValue = String(node.config[param.key] ?? param.defaultValue)
                const matchedDataset = datasets.find(
                  (dataset) => dataset.value === rawValue || dataset.label === rawValue,
                )
                const value = isDatasetParam ? (matchedDataset?.value ?? '') : rawValue
                return (
                  <ParamField
                    key={param.key}
                    label={param.label}
                    type={param.type}
                    value={value}
                    unit={param.unit}
                    options={datasetOptions}
                    help={isDatasetParam ? 'Dataset definiti nella pagina Datasets.' : param.help}
                    onChange={(next) => updateNodeConfig(node.id, param.key, next)}
                  />
                )
              })}
            </div>

            <div className="my-4 h-px bg-line/70" />
            <p className="mb-2.5 font-mono text-[8.5px] uppercase tracking-[0.14em] text-[#5e6b80]">Input / Output</p>
            <div className="space-y-2">
              {node.inputs.map((input) => (
                <div key={input.id} className="flex items-center justify-between gap-2">
                  <span className="flex min-w-0 items-center gap-1.5">
                    <span className="h-[5px] w-[5px] shrink-0 rounded-full" style={{ background: PORT_COLORS[input.dataType] }} />
                    <span className="truncate font-mono text-[9.5px] text-[#a5b2c6]">{input.label}</span>
                  </span>
                  <span className="shrink-0 font-mono text-[8.5px] text-[#66748b]">{input.typeLabel}</span>
                </div>
              ))}
              {node.outputs.map((output) => (
                <div key={output.id} className="flex items-center justify-between gap-2">
                  <span className="flex min-w-0 items-center gap-1.5">
                    <span className="h-[5px] w-[5px] shrink-0 rounded-full" style={{ background: PORT_COLORS[output.dataType] }} />
                    <span className="truncate font-mono text-[9.5px] text-[#a5b2c6]">{output.label}</span>
                  </span>
                  <span className="shrink-0 font-mono text-[8.5px] text-[#66748b]">{output.typeLabel}</span>
                </div>
              ))}
            </div>

            <div className="mt-4 rounded-md border border-[#223047] bg-[#0d1521] p-3">
              <div className="flex items-start gap-2">
                <Info className="mt-0.5 h-3 w-3 shrink-0 text-[#6f7f98]" />
                <div>
                  <p className="text-[10.5px] font-medium text-[#d3dbe7]">{definition?.summary ?? node.name}</p>
                  <p className="mt-1 text-[9.5px] leading-relaxed text-[#728198]">{definition?.documentation ?? definition?.description}</p>
                  <button onClick={() => setInspectorTab('docs')} className="mt-2 flex items-center gap-1 font-mono text-[9px] text-[#8fa6ff] hover:underline">
                    View implementation <ExternalLink className="h-2.5 w-2.5" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {inspectorTab === 'io' && (
          <div className="space-y-4 px-3.5 py-3.5">
            <div>
              <p className="mb-2 font-mono text-[8.5px] uppercase tracking-[0.14em] text-[#5e6b80]">Inputs · {node.inputs.length}</p>
              {node.inputs.length === 0 ? (
                <p className="rounded border border-line/60 bg-[#0c141f] px-2.5 py-2 text-[10px] text-dim">This node has no inputs. It starts a pipeline branch.</p>
              ) : (
                <div className="space-y-2">
                  {node.inputs.map((input) => (
                    <div key={input.id} className="rounded-md border border-[#223047] bg-[#0c141f] px-2.5 py-2">
                      <div className="flex items-center justify-between">
                        <span className="flex items-center gap-1.5 font-mono text-[10px] text-[#c6d0de]">
                          <span className="h-[5px] w-[5px] rounded-full" style={{ background: PORT_COLORS[input.dataType] }} />
                          {input.label}
                        </span>
                        <span className={cn('font-mono text-[8px] uppercase tracking-wider', connectedInputs.has(input.id) ? 'text-success' : 'text-dim')}>
                          {connectedInputs.has(input.id) ? 'connected' : 'unbound'}
                        </span>
                      </div>
                      <div className="mt-1 flex items-center justify-between font-mono text-[8.5px] text-[#66748b]">
                        <span>{input.typeLabel}</span>
                        <span>{input.dataType}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div>
              <p className="mb-2 font-mono text-[8.5px] uppercase tracking-[0.14em] text-[#5e6b80]">Outputs · {node.outputs.length}</p>
              <div className="space-y-2">
                {node.outputs.map((output) => (
                  <div key={output.id} className="rounded-md border border-[#223047] bg-[#0c141f] px-2.5 py-2">
                    <div className="flex items-center justify-between">
                      <span className="flex items-center gap-1.5 font-mono text-[10px] text-[#c6d0de]">
                        <span className="h-[5px] w-[5px] rounded-full" style={{ background: PORT_COLORS[output.dataType] }} />
                        {output.label}
                      </span>
                      <span className={cn('font-mono text-[8px] uppercase tracking-wider', connectedOutputs.has(output.id) ? 'text-success' : 'text-dim')}>
                        {connectedOutputs.has(output.id) ? 'connected' : 'unbound'}
                      </span>
                    </div>
                    <div className="mt-1 flex items-center justify-between font-mono text-[8.5px] text-[#66748b]">
                      <span>{output.typeLabel}</span>
                      <span>{output.dataType}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
            <div className="rounded-md border border-[#223047] bg-[#0c141f] p-2.5">
              <p className="font-mono text-[8.5px] uppercase tracking-wider text-dim">Schema contract</p>
              <p className="mt-1 text-[9.5px] leading-relaxed text-[#728198]">Ports are typed at the graph boundary. Connections are validated by data type before execution.</p>
            </div>
          </div>
        )}

        {inspectorTab === 'docs' && (
          <div className="space-y-4 px-3.5 py-3.5">
            <div>
              <p className="eyebrow mb-1.5">Description</p>
              <p className="text-[11px] leading-relaxed text-[#aab6c7]">{definition?.description}</p>
            </div>
            <div>
              <p className="eyebrow mb-1.5">Behavior</p>
              <p className="text-[10.5px] leading-relaxed text-[#7f8ca1]">{definition?.documentation ?? definition?.summary}</p>
            </div>
            <div>
              <p className="eyebrow mb-1.5">Implementation</p>
              <div className="overflow-hidden rounded-md border border-[#223047] bg-[#0c141f]">
                <div className="flex items-center justify-between gap-2 border-b border-line/70 px-2.5 py-2">
                  <span className="min-w-0 truncate font-mono text-[9px] text-[#bcc8db]">
                    {implementationQuery.data?.implementation ?? definition?.id ?? node.definitionId}
                  </span>
                  <span className="shrink-0 font-mono text-[8px] uppercase tracking-wider text-[#6f7f98]">
                    {implementationQuery.data?.reference ? 'reference' : 'built-in'}
                  </span>
                </div>
                {implementationQuery.isLoading ? (
                  <p className="px-2.5 py-3 font-mono text-[9px] text-dim">Loading implementation…</p>
                ) : implementationQuery.isError ? (
                  <p className="px-2.5 py-3 text-[9.5px] text-[#c78f8f]">Implementation source unavailable.</p>
                ) : (
                  <pre className="max-h-44 overflow-auto px-2.5 py-2 font-mono text-[8.5px] leading-[1.5] text-[#9fb0c8]">
                    {implementationQuery.data?.source ?? ''}
                  </pre>
                )}
              </div>
              <Button
                variant="secondary"
                size="sm"
                className="mt-2 w-full"
                onClick={() => navigate(`/custom-nodes?from=${encodeURIComponent(node.definitionId)}`)}
              >
                <Code2 className="h-3 w-3" /> Create custom from this block
              </Button>
            </div>
            <div>
              <p className="eyebrow mb-1.5">Tags</p>
              <div className="flex flex-wrap gap-1.5">
                {definition?.tags.map((tag) => (
                  <span key={tag} className="rounded border border-line bg-white/[0.025] px-1.5 py-0.5 font-mono text-[8.5px] text-[#7f8ca1]">{tag}</span>
                ))}
              </div>
            </div>
            <div className="space-y-2 rounded-md border border-line/70 bg-[#0c141f] p-3 font-mono text-[9px]">
              <div className="flex justify-between"><span className="text-dim">definition</span><span className="text-[#aab6c7]">{definition?.id}</span></div>
              <div className="flex justify-between"><span className="text-dim">category</span><span className="text-[#aab6c7]">{definition?.category}</span></div>
              <div className="flex justify-between"><span className="text-dim">version</span><span className="text-[#aab6c7]">{definition?.version ?? 'builtin'}</span></div>
              <div className="flex justify-between"><span className="text-dim">kind</span><span className="text-[#aab6c7]">{definition?.kind}</span></div>
            </div>
            <Button variant="secondary" size="sm" className="w-full" onClick={() => toast.info('Node documentation', { description: `${definition?.name} · ${definition?.category}` })}>
              <ExternalLink className="h-3 w-3" /> Open full documentation
            </Button>
          </div>
        )}
      </div>

      <div className="shrink-0 border-t border-line px-3 pt-2">
        <Button
          variant="secondary"
          size="sm"
          className="w-full"
          onClick={() => navigate(`/custom-nodes?from=${encodeURIComponent(node.definitionId)}`)}
        >
          <Code2 className="h-3 w-3" /> Create custom from selected block
        </Button>
      </div>
      <div className="flex shrink-0 items-center gap-2 px-3 py-2.5">
        <Button variant="secondary" size="sm" className="flex-1" onClick={() => duplicateNode(node.id)}>
          <Copy className="h-3 w-3" /> Duplicate
        </Button>
        <Button variant="ghost" size="sm" className="text-[#c78f8f] hover:text-danger" onClick={() => { removeNode(node.id); toast.success('Node removed') }}>
          <Trash2 className="h-3 w-3" /> Delete
        </Button>
      </div>
    </aside>
  )
}
