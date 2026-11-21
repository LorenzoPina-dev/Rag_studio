import * as React from 'react'
import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, CheckCircle2, Database, HardDrive, Server, XCircle } from 'lucide-react'
import { projectsApi } from '@/api/projects.api'
import { usePipelineStore } from '@/store/usePipelineStore'
import { isMockMode } from '@/api/client'
import { Dialog, DialogBody, DialogContent, DialogHeader } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { StatusDot } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

export function StatusBar() {
  const { data } = useQuery({ queryKey: ['system-status'], queryFn: projectsApi.systemStatus, staleTime: 30_000 })
  const validation = usePipelineStore((s) => s.validation)
  const [problemsOpen, setProblemsOpen] = React.useState(false)
  const errors = validation ? validation.errors.length : data?.errors ?? 0
  const warnings = validation ? validation.warnings.length : data?.warnings ?? 0
  const issues = validation ? [...validation.errors, ...validation.warnings] : []

  return (
    <>
      <footer className="flex h-[26px] shrink-0 items-center justify-between border-t border-line bg-[#080d15] px-3 font-mono text-[9px] text-dim">
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1.5">
            <StatusDot status={data?.connected === false ? 'danger' : 'success'} />
            {data?.connected === false ? 'Disconnected' : 'Connected'}
          </span>
          <span className="text-[#4d5b70]">{data?.branch ?? 'main*'}</span>
          <span className="hidden sm:inline">{data?.python ?? 'Python 3.11.8'}</span>
          {isMockMode && (
            <span className="hidden items-center gap-1 rounded border border-warn/25 bg-warn/[0.07] px-1.5 py-0.5 text-[8px] uppercase tracking-wider text-warn sm:flex">
              Mock API
            </span>
          )}
        </div>
        <div className="flex items-center gap-4">
          <button
            onClick={() => setProblemsOpen(true)}
            className={cn('flex items-center gap-1 transition-colors hover:text-ink', errors > 0 ? 'text-danger' : 'text-dim')}
          >
            <span className={cn('h-1 w-1 rounded-full', errors > 0 ? 'bg-danger' : 'bg-[#3c4b61]')} />
            {errors} errors
          </button>
          <button
            onClick={() => setProblemsOpen(true)}
            className={cn('flex items-center gap-1 transition-colors hover:text-ink', warnings > 0 ? 'text-warn' : 'text-dim')}
          >
            <span className={cn('h-1 w-1 rounded-full', warnings > 0 ? 'bg-warn' : 'bg-[#3c4b61]')} />
            {warnings} warnings
          </button>
          <span className="hidden text-[#4d5b70] md:inline">RAG STUDIO</span>
          <span className="hidden text-[#728099] md:inline">{data?.version ?? 'v0.8.2'}</span>
        </div>
      </footer>

      <Dialog open={problemsOpen} onOpenChange={setProblemsOpen}>
        <DialogContent size="md">
          <DialogHeader
            eyebrow="Diagnostics"
            title="Workspace problems"
            description="Validation and runtime issues collected from the current pipeline and local services."
          />
          <DialogBody className="space-y-2">
            {issues.length === 0 ? (
              <div className="flex flex-col items-center rounded-lg border border-line/70 bg-[#0b111b] px-4 py-8 text-center">
                <CheckCircle2 className="mb-2 h-6 w-6 text-success" />
                <p className="text-[12px] font-medium text-ink">No problems found</p>
                <p className="mt-1 text-[10.5px] text-dim">The graph is valid and all local services are reachable.</p>
              </div>
            ) : (
              issues.map((issue) => (
                <div key={issue.id} className="flex items-start gap-2.5 rounded-md border border-line/70 bg-[#0b111b] px-3 py-2.5">
                  {issue.severity === 'error' ? <XCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-danger" /> : <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-warn" />}
                  <div>
                    <p className="text-[11px] text-ink">{issue.message}</p>
                    <p className="mt-0.5 font-mono text-[9px] text-dim">{issue.severity.toUpperCase()} · {issue.nodeId ?? 'pipeline'}</p>
                  </div>
                </div>
              ))
            )}
            <div className="grid grid-cols-2 gap-2 pt-2">
              {[
                { icon: Server, label: 'API gateway', value: 'Healthy · 12ms' },
                { icon: Database, label: 'PostgreSQL', value: 'Healthy · 4ms' },
                { icon: HardDrive, label: 'MinIO artifacts', value: '8.2 GB stored' },
                { icon: StatusDotIcon, label: 'GPU worker', value: 'RTX 4090 · idle' },
              ].map((item) => (
                <div key={item.label} className="flex items-center gap-2.5 rounded border border-line/70 bg-[#0b111b] px-2.5 py-2">
                  <item.icon className="h-3.5 w-3.5 text-dim" />
                  <div>
                    <p className="text-[10.5px] text-muted">{item.label}</p>
                    <p className="font-mono text-[8.5px] text-dim">{item.value}</p>
                  </div>
                </div>
              ))}
            </div>
          </DialogBody>
          <div className="flex justify-end border-t border-line px-5 py-3">
            <Button variant="secondary" onClick={() => setProblemsOpen(false)}>Close</Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}

function StatusDotIcon() {
  return <span className="h-1.5 w-1.5 rounded-full bg-success" />
}
