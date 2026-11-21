import * as React from 'react'
import { ArrowUpRight, ChevronDown, ChevronUp, CircleCheck, Loader2, Terminal, X } from 'lucide-react'
import type { LogEntry, Pipeline } from '@/types'
import { cn } from '@/lib/utils'
import { StatusDot } from '@/components/ui/badge'

export function OutputPreview({
  pipeline,
  running,
  logs,
  showLogs,
  onToggleLogs,
  onInspect,
  onOpenRun,
}: {
  pipeline: Pipeline
  running: boolean
  logs: LogEntry[]
  showLogs: boolean
  onToggleLogs: (value: boolean) => void
  onInspect: () => void
  onOpenRun: () => void
}) {
  const [collapsed, setCollapsed] = React.useState(false)
  const logRef = React.useRef<HTMLDivElement>(null)
  const lastRun = pipeline.lastRun

  React.useEffect(() => {
    if (showLogs && logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [logs, showLogs])

  return (
    <div className={cn('relative shrink-0 border-t border-line bg-[#0a1019] transition-[height] duration-200', collapsed ? 'h-[34px]' : 'h-[142px]')}>
      <div className="flex h-[34px] items-center justify-between border-b border-line/70 px-4">
        <div className="flex items-center gap-3">
          <span className="font-mono text-[8.5px] font-medium uppercase tracking-[0.14em] text-[#7f8da3]">Output Preview</span>
          {running ? (
            <span className="flex items-center gap-1.5 font-mono text-[8.5px] text-accent">
              <Loader2 className="h-2.5 w-2.5 animate-spin" /> Running
            </span>
          ) : lastRun ? (
            <span className="flex items-center gap-1.5 font-mono text-[8.5px] text-[#7f907f]">
              <StatusDot status={lastRun.status === 'completed' ? 'success' : 'danger'} />
              {lastRun.status === 'completed' ? 'Last run succeeded' : 'Last run failed'}
            </span>
          ) : (
            <span className="font-mono text-[8.5px] text-dim">No runs yet</span>
          )}
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-3">
            <button
              onClick={() => onToggleLogs(false)}
              className={cn('font-mono text-[8.5px] uppercase tracking-wider transition-colors', !showLogs ? 'text-ink' : 'text-dim hover:text-muted')}
            >
              Preview
            </button>
            <button
              onClick={() => onToggleLogs(true)}
              className={cn('flex items-center gap-1 font-mono text-[8.5px] uppercase tracking-wider transition-colors', showLogs ? 'text-ink' : 'text-dim hover:text-muted')}
            >
              <Terminal className="h-2.5 w-2.5" /> Logs {logs.length > 0 && <span className="text-[8px] text-dim">({logs.length})</span>}
            </button>
          </div>
          <div className="h-3 w-px bg-line" />
          <button onClick={onOpenRun} className="font-mono text-[8.5px] uppercase tracking-wider text-dim transition-colors hover:text-ink">
            Open run
          </button>
          <button onClick={onInspect} className="flex items-center gap-0.5 font-mono text-[8.5px] uppercase tracking-wider text-[#89a1ff] transition-colors hover:text-[#b3c3ff]">
            Inspect results <ArrowUpRight className="h-3 w-3" />
          </button>
          <button onClick={() => setCollapsed((v) => !v)} className="rounded p-0.5 text-dim hover:text-ink" aria-label={collapsed ? 'Expand output preview' : 'Collapse output preview'}>
            {collapsed ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
          </button>
        </div>
      </div>

      {!collapsed && (
        <div className="h-[calc(100%-34px)] overflow-hidden">
          {showLogs ? (
            <div ref={logRef} className="h-full overflow-y-auto bg-[#080e16] px-4 py-2 font-mono">
              {logs.length === 0 ? (
                <div className="flex h-full items-center justify-center gap-2 text-[9.5px] text-dim">
                  <Terminal className="h-3 w-3" /> Run the pipeline to stream execution logs.
                </div>
              ) : (
                logs.map((log) => (
                  <div key={log.id} className="flex items-start gap-3 border-b border-[#111a26] py-[3px] text-[9px] leading-relaxed last:border-0">
                    <span className="shrink-0 text-[#536177]">{log.timestamp}</span>
                    <span
                      className={cn(
                        'w-8 shrink-0 font-medium',
                        log.level === 'WARN' && 'text-warn',
                        log.level === 'ERROR' && 'text-danger',
                        log.level === 'DONE' && 'text-success',
                        log.level === 'INFO' && 'text-[#7186a3]',
                        log.level === 'DEBUG' && 'text-dim',
                      )}
                    >
                      {log.level}
                    </span>
                    <span className="text-[#aeb9c9]">{log.message}</span>
                  </div>
                ))
              )}
              {running && (
                <div className="flex items-center gap-2 py-1 text-[9px] text-accent">
                  <span className="h-1 w-1 animate-pulse rounded-full bg-accent" />
                  streaming trace…
                </div>
              )}
            </div>
          ) : (
            <div className="flex h-full flex-col justify-between px-4 py-2.5">
              {running ? (
                <div className="flex flex-1 items-center gap-2">
                  <div className="flex items-end gap-1">
                    {[0, 1, 2, 3, 4].map((i) => (
                      <span key={i} className="w-1 animate-pulse rounded-full bg-accent/70" style={{ height: 6 + ((i * 5) % 15), animationDelay: `${i * 120}ms` }} />
                    ))}
                  </div>
                  <p className="text-[11px] text-muted">
                    {logs.length > 0 ? logs[logs.length - 1].message : 'Starting pipeline execution…'}
                  </p>
                </div>
              ) : lastRun ? (
                <p className="line-clamp-2 max-w-4xl text-[11px] leading-[1.65] text-[#c3cddb]">{lastRun.output}</p>
              ) : (
                <p className="text-[11px] text-dim">Run the pipeline to preview grounded output and token usage.</p>
              )}
              <div className="flex items-end justify-between gap-4">
                <div className="flex flex-wrap items-center gap-x-5 gap-y-1 font-mono text-[8.5px] text-[#617087]">
                  {lastRun ? (
                    <>
                      <span><span className="text-[#94a2b5]">{lastRun.sources}</span> sources cited</span>
                      <span><span className="text-[#94a2b5]">{(lastRun.latencyMs / 1000).toFixed(2)}s</span> latency</span>
                      <span><span className="text-[#94a2b5]">{lastRun.tokens.toLocaleString()}</span> tokens</span>
                      <span><span className="text-[#94a2b5]">${lastRun.cost.toFixed(4)}</span></span>
                    </>
                  ) : (
                    <span>Outputs are persisted after each run.</span>
                  )}
                </div>
                {lastRun && (
                  <button onClick={onOpenRun} className="flex items-center gap-1 font-mono text-[8.5px] text-dim hover:text-ink">
                    <CircleCheck className="h-3 w-3 text-success" /> trace captured
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
