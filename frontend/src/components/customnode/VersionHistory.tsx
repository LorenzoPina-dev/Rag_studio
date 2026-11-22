import * as React from 'react'
import { Check, GitCompareArrows, History, RotateCcw, Send, Sparkles } from 'lucide-react'
import type { CustomNode, CustomNodeVersion } from '@/types'
import { Dialog, DialogBody, DialogContent, DialogFooter, DialogHeader } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { toast } from 'sonner'

export function VersionHistoryDialog({
  open,
  onOpenChange,
  node,
  versions,
  onRestore,
  onPublish,
  publishing,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  node: CustomNode
  versions: CustomNodeVersion[]
  onRestore: (version: CustomNodeVersion) => void
  onPublish: () => void
  publishing: boolean
}) {
  const [compare, setCompare] = React.useState<string | null>(null)
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="lg">
        <DialogHeader eyebrow="Component history" title={node.name} description="Every saved version is immutable and pinned to its dependency lockfile." />
        <DialogBody>
          {compare && (
            <div className="mb-4 rounded-md border border-[#2a3a51] bg-[#0b131f] p-3 font-mono text-[9px]">
              <div className="flex items-center justify-between pb-2 text-[8.5px] uppercase tracking-wider text-dim">
                <span>Diff · {compare} → {node.draftVersion}</span>
                <button onClick={() => setCompare(null)} className="text-[#8fa6ff] hover:underline">close</button>
              </div>
              <p className="text-[#8a99ae]">Diff non disponibile finché il backend non fornisce il confronto tra versioni.</p>
            </div>
          )}
          <div className="relative space-y-2 pl-5">
            <div className="absolute bottom-3 left-[7px] top-3 w-px bg-line" />
            {versions.map((version) => (
              <div
                key={version.id}
                className={cn(
                  'relative rounded-md border px-3.5 py-3',
                  version.current ? 'border-accent/40 bg-accent/[0.05]' : 'border-line/70 bg-[#0b111b]',
                )}
              >
                <span className={cn('absolute -left-[18px] top-4 h-2 w-2 rounded-full border-2 border-[#0b111b]', version.current ? 'bg-accent' : 'bg-[#3f4e65]')} />
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-[11px] text-ink">{version.version}</span>
                  <span className={cn('rounded border px-1.5 py-0.5 font-mono text-[7.5px] uppercase tracking-wider', version.current ? 'border-accent/30 bg-accent/10 text-[#a8b9ff]' : 'border-line bg-white/[0.02] text-dim')}>
                    {version.current ? 'Working draft' : version.label}
                  </span>
                  {version.date && <span className="font-mono text-[8.5px] text-dim">{version.date}</span>}
                  {version.author && <span className="font-mono text-[8.5px] text-[#4f5d72]">· {version.author}</span>}
                  <div className="ml-auto flex items-center gap-1">
                    <button onClick={() => setCompare(version.version)} className="flex items-center gap-1 rounded px-1.5 py-1 font-mono text-[8.5px] text-dim hover:bg-white/5 hover:text-ink">
                      <GitCompareArrows className="h-2.5 w-2.5" /> Compare
                    </button>
                    {!version.current && (
                      <button
                        onClick={() => {
                          onRestore(version)
                          toast.success(`Restored ${version.version}`, { description: 'The editor now reflects this version as a new draft.' })
                        }}
                        className="flex items-center gap-1 rounded px-1.5 py-1 font-mono text-[8.5px] text-[#8fa6ff] hover:bg-accent/10"
                      >
                        <RotateCcw className="h-2.5 w-2.5" /> Restore
                      </button>
                    )}
                  </div>
                </div>
                <p className="mt-1.5 text-[10px] leading-relaxed text-muted">{version.changes}</p>
              </div>
            ))}
          </div>
        </DialogBody>
        <DialogFooter className="justify-between">
          <span className="flex items-center gap-1.5 font-mono text-[8.5px] text-dim">
            <History className="h-3 w-3" /> {versions.length} versions · draft {node.draftVersion}
          </span>
          <div className="flex items-center gap-2">
            <Button variant="secondary" onClick={() => onOpenChange(false)}>Close</Button>
            <Button variant="primary" onClick={onPublish} disabled={publishing}>
              <Send className="h-3 w-3" /> {publishing ? 'Publishing…' : `Publish ${node.draftVersion}`}
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export function TestNodeDialog({
  open,
  onOpenChange,
  node,
  onRun,
  running,
  output,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  node: CustomNode
  onRun: (input: { alpha: number; top_n: number; query: string; limit: number }) => void
  running: boolean
  output: import('@/types').CustomNodeTestOutput | null
}) {
  const [alpha, setAlpha] = React.useState(0.7)
  const [topN, setTopN] = React.useState(5)
  const [limit, setLimit] = React.useState(20)
  const [query, setQuery] = React.useState('How does hybrid retrieval work?')

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="lg">
        <DialogHeader eyebrow="Component test" title="Test node" description="Run this component in an isolated runtime against a sample of the retrieval corpus." />
        <DialogBody className="space-y-4">
          <div className="grid grid-cols-3 gap-3">
            <div className="space-y-1.5">
              <label className="text-[10.5px] text-muted">alpha · Relevance</label>
              <input type="number" step="0.05" value={alpha} onChange={(e) => setAlpha(Number(e.target.value))} className="input-base h-8 font-mono text-[11px]" />
            </div>
            <div className="space-y-1.5">
              <label className="text-[10.5px] text-muted">top_n · Results</label>
              <input type="number" value={topN} onChange={(e) => setTopN(Number(e.target.value))} className="input-base h-8 font-mono text-[11px]" />
            </div>
            <div className="space-y-1.5">
              <label className="text-[10.5px] text-muted">Candidate limit</label>
              <input type="number" value={limit} onChange={(e) => setLimit(Number(e.target.value))} className="input-base h-8 font-mono text-[11px]" />
            </div>
          </div>
          <div className="space-y-1.5">
            <label className="text-[10.5px] text-muted">Test query</label>
            <input value={query} onChange={(e) => setQuery(e.target.value)} className="input-base h-8 text-[11px]" />
          </div>
          <div className="rounded-md border border-line bg-[#0a1019]">
            <div className="flex items-center justify-between border-b border-line px-3 py-2">
              <span className="font-mono text-[8.5px] uppercase tracking-wider text-dim">Output preview</span>
              {output && (
                <div className="flex items-center gap-3 font-mono text-[8.5px]">
                  <span className="flex items-center gap-1 text-success"><Check className="h-2.5 w-2.5" /> completed</span>
                  <span className="text-dim">{output.durationMs}ms</span>
                  <span className="text-[#a8b9ff]">diversity {output.diversityScore}</span>
                </div>
              )}
            </div>
            <div className="max-h-[230px] min-h-[120px] overflow-y-auto">
              {running && (
                <div className="flex h-[120px] items-center justify-center gap-2 font-mono text-[9.5px] text-accent">
                  <Sparkles className="h-3.5 w-3.5 animate-pulse" /> Executing component in isolated runtime…
                </div>
              )}
              {!running && !output && (
                <div className="flex h-[120px] flex-col items-center justify-center text-center">
                  <Sparkles className="mb-2 h-4 w-4 text-dim" />
                  <p className="text-[11px] text-muted">Run the component to inspect ranked documents.</p>
                  <p className="mt-1 font-mono text-[8.5px] text-dim">Outputs are not persisted until the node is saved.</p>
                </div>
              )}
              {!running && output && (
                <div className="divide-y divide-line/60">
                  {output.documents.map((document) => (
                    <div key={document.id} className="flex items-start gap-3 px-3 py-2">
                      <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border border-line bg-white/[0.03] font-mono text-[7.5px] text-dim">{String(document.rank).padStart(2, '0')}</span>
                      <div className="min-w-0 flex-1">
                        <p className="text-[10.5px] text-[#c6d2e2]">{document.title}</p>
                        <p className="mt-0.5 truncate font-mono text-[8px] text-dim">{document.source} · {document.chunkId}</p>
                      </div>
                      <span className="rounded bg-success/10 px-1.5 py-0.5 font-mono text-[8.5px] text-success">{document.score.toFixed(3)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
          {output && (
            <div className="flex items-center justify-between font-mono text-[8.5px] text-dim">
              <span>{output.documents.length} documenti restituiti · {output.durationMs}ms</span>
              <button onClick={() => navigator.clipboard?.writeText(JSON.stringify(output, null, 2)).then(() => toast.success('Output copied'))} className="text-[#8fa6ff] hover:underline">
                Copy JSON
              </button>
            </div>
          )}
        </DialogBody>
        <DialogFooter>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>Close</Button>
          <Button variant="primary" onClick={() => onRun({ alpha, top_n: topN, query, limit })} disabled={running}>
            <Sparkles className="h-3 w-3" /> {running ? 'Testing…' : 'Run test'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
