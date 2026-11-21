import { API_BASE, http, isMockMode } from './client'
import type { Execution, ExecutionResult, LogEntry, NodeRun } from '@/types'

export interface ExecutionStreamEvent {
  type: 'status' | 'node' | 'log' | 'done' | 'error'
  status?: Execution['status']
  node?: NodeRun
  log?: LogEntry
  execution?: Execution
  /** Human-readable reason for `type: 'error'` frames, when the backend provides one. */
  detail?: string
}

export type StreamHandler = (event: ExecutionStreamEvent) => void

function normalizeStreamEvent(raw: unknown): ExecutionStreamEvent {
  const event = raw as ExecutionStreamEvent & { error?: unknown; message?: unknown }
  if (event.type !== 'error' || event.detail) return event

  const logs = event.execution?.logs ?? []
  const errorLogs = logs.filter((log) => log.level === 'ERROR')
  const lastError = errorLogs[errorLogs.length - 1]?.message
  const errors = event.execution?.errors ?? 0
  const reason = event.error ?? event.message ?? lastError ?? (errors > 0 ? `Execution failed with ${errors} error(s)` : undefined)
  return reason === undefined ? event : { ...event, detail: typeof reason === 'string' ? reason : String(reason) }
}

export const executionsApi = {
  list: (): Promise<Execution[]> => http.get('/executions'),
  get: (id: string): Promise<Execution> => http.get(`/executions/${id}`),
  start: (): Promise<Execution> => http.post('/executions'),
  stop: (id: string): Promise<{ ok: boolean; status: string }> => http.post(`/executions/${id}/stop`),
  logs: (id: string): Promise<LogEntry[]> => http.get(`/executions/${id}/logs`),
  results: (id: string): Promise<ExecutionResult> => http.get(`/executions/${id}/results`),
  artifact: (executionId: string, artifactId: string): Promise<{ id: string; url: string }> =>
    http.get(`/executions/${executionId}/artifacts/${artifactId}`),
}

/**
 * Subscribe to real-time execution progress.
 * Real mode uses Server-Sent Events; mock mode replays a deterministic trace
 * with the same event shape so the UI needs no special casing.
 */
export function subscribeExecution(execution: Execution, onEvent: StreamHandler): () => void {
  if (!isMockMode) {
    const source = new EventSource(`${API_BASE}/executions/${encodeURIComponent(execution.id)}/stream`)
    source.onmessage = (message) => {
      try {
        onEvent(normalizeStreamEvent(JSON.parse(message.data)))
      } catch {
        /* ignore malformed frames */
      }
    }
    source.addEventListener('error', (message) => {
      try {
        onEvent(normalizeStreamEvent(JSON.parse((message as MessageEvent<string>).data)))
      } catch {
        /* transport errors are handled by source.onerror */
      }
    })
    source.onerror = () => onEvent({
      type: 'error',
      status: 'failed',
      detail: 'Connessione allo stream interrotta prima del completamento.',
    })
    return () => source.close()
  }

  const timeouts: number[] = []
  let cancelled = false
  const schedule = (fn: () => void, ms: number) => {
    timeouts.push(window.setTimeout(() => {
      if (!cancelled) fn()
    }, ms))
  }

  const nodes = execution.nodeRuns
  let elapsed = 0
  onEvent({ type: 'status', status: 'running' })

  nodes.forEach((node, index) => {
    elapsed += 550 + index * 120
    schedule(() => {
      onEvent({ type: 'node', node: { ...node, status: 'running', durationMs: 0 } })
      onEvent({
        type: 'log',
        log: {
          id: `stream_${node.nodeId}_${index}`,
          timestamp: new Date().toLocaleTimeString('en-GB', { hour12: false }) + '.000',
          level: 'INFO',
          message: `${node.name} started`,
          node: node.name,
        },
      })
    }, elapsed)

    schedule(() => {
      onEvent({ type: 'node', node: { ...node, status: 'completed' } })
      onEvent({
        type: 'log',
        log: {
          id: `stream_${node.nodeId}_done_${index}`,
          timestamp: new Date().toLocaleTimeString('en-GB', { hour12: false }) + '.000',
          level: node.kind === 'reranking' ? 'WARN' : 'INFO',
          message:
            node.kind === 'reranking'
              ? 'Connection restored after 22ms · 5 documents selected'
              : `${node.name} completed · ${node.outputCount.toLocaleString()} outputs`,
          node: node.name,
        },
      })
    }, elapsed + 320)
  })

  schedule(() => {
    onEvent({
      type: 'log',
      log: {
        id: 'stream_done',
        timestamp: new Date().toLocaleTimeString('en-GB', { hour12: false }) + '.000',
        level: 'DONE',
        message: 'Pipeline completed successfully in 1.24s',
      },
    })
    onEvent({
      type: 'done',
      status: 'completed',
      execution: {
        ...execution,
        status: 'completed',
        durationMs: 1240,
        tokens: 1842,
        cost: 0.0062,
        warnings: 1,
        nodeRuns: nodes.map((n) => ({ ...n, status: 'completed' as const })),
      },
    })
  }, elapsed + 1200)

  return () => {
    cancelled = true
    timeouts.forEach((t) => window.clearTimeout(t))
  }
}
