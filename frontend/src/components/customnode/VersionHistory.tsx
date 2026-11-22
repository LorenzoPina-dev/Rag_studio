import * as React from 'react'
import { GitCompareArrows, History, RotateCcw, Send } from 'lucide-react'
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
