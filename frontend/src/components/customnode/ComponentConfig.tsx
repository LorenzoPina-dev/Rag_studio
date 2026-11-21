import * as React from 'react'
import { Check, Plus, Trash2, FileCode2, Package, ChevronRight } from 'lucide-react'
import type { CustomNode, CustomNodeParameter } from '@/types'
import { cn } from '@/lib/utils'
import { Select } from '@/components/ui/select'
import { Button } from '@/components/ui/button'
import { PORT_COLORS } from '@/api/mock/pipelineSeed'
import { Dialog, DialogBody, DialogContent, DialogFooter, DialogHeader } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'

export type ConfigTab = 'configuration' | 'io' | 'docs'

export function ComponentConfig({
  node,
  tab,
  onTabChange,
  onUpdate,
  onAddDependency,
  onRemoveDependency,
}: {
  node: CustomNode
  tab: ConfigTab
  onTabChange: (tab: ConfigTab) => void
  onUpdate: (patch: Partial<CustomNode>) => void
  onAddDependency: (name: string, version: string) => void
  onRemoveDependency: (name: string) => void
}) {
  const [dependencyOpen, setDependencyOpen] = React.useState(false)
  const [dependencyName, setDependencyName] = React.useState('')
  const [dependencyVersion, setDependencyVersion] = React.useState('>= 1.0.0')

  const updateParameter = (key: string, value: string | number | boolean) => {
    onUpdate({
      parameters: node.parameters.map((p) => (p.key === key ? { ...p, value } : p)),
    })
  }

  return (
    <aside className="flex h-full w-[286px] shrink-0 flex-col border-l border-line bg-[#0b111b]">
      <div className="flex h-[34px] shrink-0 items-center border-b border-line px-3.5">
        <span className="font-mono text-[8.5px] font-medium uppercase tracking-[0.12em] text-[#7f8da2]">Component Configuration</span>
      </div>
      <div className="flex h-[42px] shrink-0 items-center gap-5 border-b border-line px-3.5">
        {([
          ['configuration', 'Configuration'],
          ['io', 'I/O'],
          ['docs', 'Docs'],
        ] as const).map(([id, label]) => (
          <button
            key={id}
            onClick={() => onTabChange(id)}
            className={cn(
              'relative h-full border-b border-transparent pt-1 text-[10.5px] transition-colors',
              tab === id ? 'border-[#5570e8] text-[#bccaff]' : 'text-[#7d8a9f] hover:text-ink',
            )}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-3.5 py-3">
        {tab === 'configuration' && (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-[10.5px] text-[#8c99ad]">Node name</label>
              <input
                value={node.name}
                onChange={(e) => onUpdate({ name: e.target.value })}
                className="h-8 w-full rounded border border-[#233044] bg-[#0a1019] px-2.5 font-mono text-[10.5px] text-ink focus:border-accent/60 focus:outline-none"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-[10.5px] text-[#8c99ad]">Category</label>
              <Select
                value={node.category}
                onValueChange={(value) => onUpdate({ category: value })}
                options={['Data Sources', 'Document Processing', 'Embeddings', 'Retrieval', 'Selection', 'Reranking', 'LLM Generation', 'Control Flow', 'Evaluation']}
                className="h-8 text-[10.5px]"
              />
            </div>

            <div className="border-t border-line/60 pt-3">
              <p className="mb-2 font-mono text-[8px] uppercase tracking-[0.13em] text-[#5e6b80]">Input Definitions</p>
              <div className="space-y-2">
                {node.inputDefinitions.map((input) => (
                  <div key={input.id} className="flex items-center justify-between gap-2">
                    <span className="flex min-w-0 items-center gap-1.5">
                      <span className="h-[5px] w-[5px] shrink-0 rounded-full" style={{ background: input.color }} />
                      <span className="truncate font-mono text-[9.5px] text-[#a9b5c7]">{input.label}</span>
                    </span>
                    <span className="shrink-0 font-mono text-[8.5px] text-[#68768c]">{input.typeLabel}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="border-t border-line/60 pt-3">
              <p className="mb-2 font-mono text-[8px] uppercase tracking-[0.13em] text-[#5e6b80]">Output Definitions</p>
              <div className="space-y-2">
                {node.outputDefinitions.map((output) => (
                  <div key={output.id} className="flex items-center justify-between gap-2">
                    <span className="flex min-w-0 items-center gap-1.5">
                      <span className="h-[5px] w-[5px] shrink-0 rounded-full" style={{ background: output.color }} />
                      <span className="truncate font-mono text-[9.5px] text-[#a9b5c7]">{output.label}</span>
                    </span>
                    <span className="shrink-0 font-mono text-[8.5px] text-[#68768c]">{output.typeLabel}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="border-t border-line/60 pt-3">
              <p className="mb-2 font-mono text-[8px] uppercase tracking-[0.13em] text-[#5e6b80]">Parameters</p>
              <div className="space-y-3">
                {node.parameters.map((parameter) => (
                  <div key={parameter.key} className="space-y-1">
                    <label className="text-[9.5px] text-[#78879d]">{parameter.label}</label>
                    <div className="flex h-8 items-center overflow-hidden rounded border border-[#233044] bg-[#0a1019] focus-within:border-accent/60">
                      <input
                        value={String(parameter.value)}
                        onChange={(e) =>
                          updateParameter(parameter.key, parameter.type === 'int' || parameter.type === 'float' ? Number(e.target.value) || 0 : e.target.value)
                        }
                        className="h-full min-w-0 flex-1 bg-transparent px-2.5 font-mono text-[10.5px] text-ink focus:outline-none"
                      />
                      <span className="border-l border-[#1e2a3c] px-2 font-mono text-[8.5px] text-[#5f6d83]">{parameter.type}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="border-t border-line/60 pt-3">
              <p className="mb-2 font-mono text-[8px] uppercase tracking-[0.13em] text-[#5e6b80]">Dependencies</p>
              <div className="space-y-1.5">
                {node.dependencies.map((dep) => (
                  <div key={dep.name} className="group flex h-8 items-center gap-2 rounded border border-[#233044] bg-[#0a1019] px-2.5">
                    <Package className="h-3 w-3 text-[#7d8ca2]" />
                    <span className="font-mono text-[9.5px] text-[#b6c2d3]">{dep.name}</span>
                    <span className="ml-auto font-mono text-[8.5px] text-[#647187]">{dep.version}</span>
                    {dep.installed && <Check className="h-3 w-3 text-success" />}
                    <button
                      onClick={() => onRemoveDependency(dep.name)}
                      className="rounded p-0.5 text-dim opacity-0 hover:text-danger group-hover:opacity-100"
                      aria-label={`Remove ${dep.name}`}
                    >
                      <Trash2 className="h-2.5 w-2.5" />
                    </button>
                  </div>
                ))}
                <button onClick={() => setDependencyOpen(true)} className="flex items-center gap-1.5 px-1 py-1 font-mono text-[8.5px] text-[#7d8df0] transition-colors hover:text-[#a8b8ff]">
                  <Plus className="h-2.5 w-2.5" /> Add dependency
                </button>
              </div>
            </div>
          </div>
        )}

        {tab === 'io' && (
          <div className="space-y-4">
            {[
              { label: 'Inputs', ports: node.inputDefinitions },
              { label: 'Outputs', ports: node.outputDefinitions },
            ].map((section) => (
              <div key={section.label}>
                <p className="mb-2 font-mono text-[8px] uppercase tracking-[0.13em] text-[#5e6b80]">{section.label}</p>
                <div className="space-y-2">
                  {section.ports.map((port) => (
                    <div key={port.id} className="rounded border border-[#223047] bg-[#0c141f] px-2.5 py-2">
                      <div className="flex items-center justify-between">
                        <span className="flex items-center gap-1.5 font-mono text-[10px] text-[#c6d0de]">
                          <span className="h-[5px] w-[5px] rounded-full" style={{ background: port.color }} />
                          {port.label}
                        </span>
                        <span className="font-mono text-[8.5px] text-[#647187]">{port.dataType}</span>
                      </div>
                      <p className="mt-1 font-mono text-[8.5px] text-[#5f6d83]">{port.typeLabel}</p>
                    </div>
                  ))}
                </div>
              </div>
            ))}
            <div className="rounded border border-[#223047] bg-[#0c141f] p-2.5">
              <p className="font-mono text-[8px] uppercase tracking-wider text-dim">Type contract</p>
              <p className="mt-1 text-[9px] leading-relaxed text-[#728198]">Ports are matched against the pipeline graph by data type. Changing an output requires publishing a new component version.</p>
            </div>
          </div>
        )}

        {tab === 'docs' && (
          <div className="space-y-4">
            <div>
              <p className="eyebrow mb-1.5">Description</p>
              <p className="text-[10.5px] leading-relaxed text-[#a9b5c7]">{node.description}</p>
            </div>
            <div>
              <p className="eyebrow mb-1.5">Component</p>
              <div className="space-y-2 rounded border border-line/70 bg-[#0c141f] p-2.5 font-mono text-[9px]">
                <div className="flex justify-between"><span className="text-dim">slug</span><span className="text-[#aab6c7]">{node.slug}</span></div>
                <div className="flex justify-between"><span className="text-dim">category</span><span className="text-[#aab6c7]">{node.category}</span></div>
                <div className="flex justify-between"><span className="text-dim">language</span><span className="text-[#aab6c7]">{node.language}</span></div>
                <div className="flex justify-between"><span className="text-dim">version</span><span className="text-[#aab6c7]">{node.draftVersion}</span></div>
              </div>
            </div>
            <div>
              <p className="eyebrow mb-1.5">Usage</p>
              <p className="text-[9.5px] leading-relaxed text-[#728198]">
                Drop the component into a pipeline from the Node Library. Its parameters are exposed in the node inspector,
                and outputs are persisted with every run for reproducibility.
              </p>
            </div>
            <div className="rounded border border-[#223047] bg-[#0c141f] p-2.5">
              <p className="flex items-center gap-1.5 font-mono text-[8px] uppercase tracking-wider text-dim"><FileCode2 className="h-2.5 w-2.5" /> Source</p>
              <p className="mt-1 font-mono text-[9px] text-[#8fa0b8]">{node.files.find((f) => f.language === 'python')?.name}</p>
              <button className="mt-1.5 flex items-center gap-0.5 font-mono text-[8.5px] text-[#8fa6ff] hover:underline" onClick={() => onTabChange('configuration')}>
                View parameters <ChevronRight className="h-2.5 w-2.5" />
              </button>
            </div>
          </div>
        )}
      </div>

      <Dialog open={dependencyOpen} onOpenChange={setDependencyOpen}>
        <DialogContent size="sm">
          <DialogHeader eyebrow="Dependency" title="Add a Python dependency" description="Dependencies are installed in the isolated component runtime." />
          <DialogBody className="space-y-3">
            <div className="space-y-1.5">
              <label className="text-[11.5px] text-muted">Package</label>
              <Input value={dependencyName} onChange={(e) => setDependencyName(e.target.value)} placeholder="e.g. scikit-learn" autoFocus />
            </div>
            <div className="space-y-1.5">
              <label className="text-[11.5px] text-muted">Version constraint</label>
              <Input value={dependencyVersion} onChange={(e) => setDependencyVersion(e.target.value)} placeholder=">= 1.0.0" />
            </div>
          </DialogBody>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setDependencyOpen(false)}>Cancel</Button>
            <Button
              variant="primary"
              disabled={!dependencyName.trim()}
              onClick={() => {
                onAddDependency(dependencyName.trim(), dependencyVersion.trim())
                setDependencyOpen(false)
                setDependencyName('')
              }}
            >
              Add dependency
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </aside>
  )
}
