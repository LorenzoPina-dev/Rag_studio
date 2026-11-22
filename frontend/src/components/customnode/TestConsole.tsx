import * as React from 'react'
import { Check, ChevronRight, FlaskConical, Loader2, Play, X } from 'lucide-react'
import type { CustomNode, TestRun } from '@/types'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { StatusDot } from '@/components/ui/badge'

export function TestConsole({
  node,
  testRun,
  running,
  onRun,
  onOpenTest,
}: {
  node: CustomNode
  testRun: TestRun | null
  running: boolean
  onRun: () => void
  onOpenTest: () => void
}) {
  const [tab, setTab] = React.useState<'console' | 'results'>('console')
  const passed = testRun?.tests.filter((t) => t.status === 'passed').length ?? 0

  return (
    <div className="flex h-[236px] shrink-0 flex-col border-t border-line bg-[#0a111b]">
      <div className="flex h-[34px] shrink-0 items-center justify-between border-b border-line/70 px-4">
        <div className="flex h-full items-center gap-5">
          <button
            onClick={() => setTab('console')}
            className={cn(
              'relative flex h-full items-center text-[10.5px] transition-colors',
              tab === 'console' ? 'text-ink' : 'text-dim hover:text-muted',
            )}
          >
            Test console
            {tab === 'console' && <span className="absolute inset-x-0 bottom-0 h-px bg-accent" />}
          </button>
          <button
            onClick={() => setTab('results')}
            className={cn(
              'relative flex h-full items-center text-[10.5px] transition-colors',
              tab === 'results' ? 'text-ink' : 'text-dim hover:text-muted',
            )}
          >
            Execution results
            {tab === 'results' && <span className="absolute inset-x-0 bottom-0 h-px bg-accent" />}
          </button>
        </div>
        <div className="flex items-center gap-3">
          {testRun && (
            <span className={cn('flex items-center gap-1.5 font-mono text-[8.5px]', testRun.status === 'passed' ? 'text-success' : 'text-danger')}>
              <StatusDot status={testRun.status === 'passed' ? 'success' : 'danger'} />
              {passed}/{testRun.tests.length} tests passed
            </span>
          )}
          <Button variant="secondary" size="sm" className="h-6 text-[10px]" onClick={onRun} disabled={running}>
            {running ? <Loader2 className="h-2.5 w-2.5 animate-spin" /> : <Play className="h-2.5 w-2.5" />}
            {running ? 'Running' : 'Run tests'}
          </Button>
        </div>
      </div>

      {tab === 'console' ? (
        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-2.5 font-mono">
          <p className="text-[9.5px] text-[#6f7e94]">
            <span className="mr-2 text-[#4f5c70]">$</span> {testRun?.logs[0] ?? 'Output non disponibile'}
          </p>
          {running && (
            <div className="mt-3 flex items-center gap-2 text-[9px] text-accent">
              <Loader2 className="h-3 w-3 animate-spin" /> Collecting tests and executing node…
            </div>
          )}
          {testRun && !running && (
            <>
              <div className="mt-2 space-y-1">
                {testRun.tests.map((test) => (
                  <div key={test.name} className="flex items-center gap-2 text-[9px]">
                    {test.status === 'passed' ? (
                      <Check className="h-2.5 w-2.5 shrink-0 text-success" strokeWidth={3} />
                    ) : (
                      <X className="h-2.5 w-2.5 shrink-0 text-danger" strokeWidth={3} />
                    )}
                    <span className={test.status === 'passed' ? 'text-[#b6c4d6]' : 'text-[#ff9d9d]'}>{test.name}</span>
                    <span className={cn('ml-auto text-[8.5px] uppercase', test.status === 'passed' ? 'text-success' : 'text-danger')}>
                      {test.status}
                    </span>
                    <span className="w-10 text-right text-[8.5px] text-[#5f6d82]">{test.durationMs}ms</span>
                  </div>
                ))}
              </div>
              <div className="mt-3 rounded border border-[#22503f] bg-[#0c1e18] px-3 py-2">
                <div className="flex items-center gap-2">
                  <Check className="h-3 w-3 text-success" />
                  <span className="text-[9.5px] font-medium text-[#9fe4c9]">
                    {testRun.status === 'passed' ? 'All tests passed. Your node is ready to use.' : 'Tests failed. Review the output before publishing.'}
                  </span>
                </div>
                <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-[8.5px] text-[#6d9f8b]">
                  {testRun.metrics.length > 0 ? (
                    testRun.metrics.map((metric, index) => (
                      <React.Fragment key={`${metric.label}-${index}`}>
                        {index > 0 && <span>·</span>}
                        <span>{metric.label}: {metric.value}</span>
                      </React.Fragment>
                    ))
                  ) : (
                    <span>Output non disponibile</span>
                  )}
                </div>
              </div>
            </>
          )}
          {!testRun && !running && (
            <p className="mt-3 text-[9px] text-dim">No tests have been run yet. Execute the test suite to validate this component.</p>
          )}
        </div>
      ) : (
        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="font-mono text-[8.5px] uppercase tracking-[0.12em] text-dim">Last component execution</p>
              <div className="mt-1.5 flex items-center gap-2">
                <StatusDot status={testRun?.status === 'passed' ? 'success' : 'idle'} />
                <span className="text-[11px] text-ink">{node.name}</span>
                <span className="font-mono text-[9px] text-dim">{node.draftVersion}</span>
              </div>
              <p className="mt-1.5 font-mono text-[9px] text-dim">
                {testRun ? `${testRun.summary} · finished ${new Date(testRun.finishedAt).toLocaleTimeString()}` : 'No execution results yet.'}
              </p>
            </div>
            <Button variant="secondary" size="sm" onClick={onOpenTest}>
              <FlaskConical className="h-3 w-3" /> Test node
            </Button>
          </div>
          <div className="mt-3 grid grid-cols-3 gap-2">
            {testRun && testRun.metrics.length > 0 ? (
              testRun.metrics.map((metric) => (
                <div key={metric.label} className="rounded border border-line/70 bg-[#0c141f] px-2.5 py-2">
                  <p className="font-mono text-[8px] uppercase tracking-wider text-dim">{metric.label}</p>
                  <p className="mt-1 font-mono text-[11px] text-ink">{metric.value}</p>
                </div>
              ))
            ) : (
              <div className="col-span-3 rounded border border-line/70 bg-[#0c141f] px-2.5 py-2 font-mono text-[9px] text-dim">Output non disponibile</div>
            )}
          </div>
          <button onClick={onOpenTest} className="mt-3 flex items-center gap-1 font-mono text-[8.5px] text-[#8fa6ff] hover:underline">
            Inspect intermediate outputs <ChevronRight className="h-2.5 w-2.5" />
          </button>
        </div>
      )}
    </div>
  )
}
