import * as React from 'react'
import { executionsApi, subscribeExecution, type ExecutionStreamEvent } from '@/api/executions.api'
import type { Execution, LogEntry } from '@/types'

/**
 * Owning the execution stream at app level keeps a run alive while the user
 * moves between the editor, the monitor and the results page. Page components
 * only read the snapshot; closing a page must not stop the backend execution
 * (the backend drives the DAG from the SSE consumer).
 */
export interface ActiveExecutionSnapshot {
  execution: Execution
  logs: LogEntry[]
  error: string | null
  terminal: boolean
}

type Listener = (snapshot: ActiveExecutionSnapshot | null) => void

const isTerminalStatus = (status: Execution['status']) =>
  status === 'completed' || status === 'failed' || status === 'stopped'

const STORAGE_KEY = 'rag-studio.active-execution'

let snapshot: ActiveExecutionSnapshot | null = null
let unsubscribeStream: (() => void) | null = null
const listeners = new Set<Listener>()

function publish() {
  listeners.forEach((listener) => listener(snapshot))
}

function closeStream() {
  unsubscribeStream?.()
  unsubscribeStream = null
}

function applyEvent(event: ExecutionStreamEvent) {
  if (!snapshot) return

  const current = snapshot
  let execution = current.execution
  let logs = current.logs
  let error = current.error
  let terminal = current.terminal

  if (event.type === 'status' && event.status) {
    execution = { ...execution, status: event.status }
  } else if (event.type === 'node' && event.node) {
    const node = event.node
    const exists = execution.nodeRuns.some((run) => run.nodeId === node.nodeId)
    execution = {
      ...execution,
      nodeRuns: exists
        ? execution.nodeRuns.map((run) => (run.nodeId === node.nodeId ? { ...run, ...node } : run))
        : [...execution.nodeRuns, node],
    }
  } else if (event.type === 'log' && event.log) {
    const log = event.log
    if (!logs.some((entry) => entry.id === log.id)) {
      logs = [...logs, log]
      execution = { ...execution, logs }
    }
  } else if (event.type === 'done' && event.execution) {
    execution = { ...event.execution, logs }
    terminal = true
  } else if (event.type === 'error') {
    execution = { ...execution, status: 'failed' }
    error = event.detail ?? 'Esecuzione interrotta prima del completamento.'
    terminal = true
  }

  snapshot = { execution, logs, error, terminal }
  if (terminal) clearActiveRun()
  publish()
}

function rememberRun(id: string) {
  try {
    sessionStorage.setItem(STORAGE_KEY, id)
  } catch {
    /* storage may be unavailable (private mode) */
  }
}

function clearActiveRun() {
  closeStream()
  try {
    sessionStorage.removeItem(STORAGE_KEY)
  } catch {
    /* ignore */
  }
}

export const activeExecution = {
  /** Start (or re-attach to) a run. Only one stream is ever open. */
  start(execution: Execution) {
    if (snapshot?.execution.id === execution.id && !snapshot.terminal) {
      publish()
      return snapshot
    }
    clearActiveRun()
    snapshot = {
      execution,
      logs: execution.logs ?? [],
      error: null,
      terminal: isTerminalStatus(execution.status),
    }
    publish()
    if (!snapshot.terminal) {
      rememberRun(execution.id)
      unsubscribeStream = subscribeExecution(execution, applyEvent)
    }
    return snapshot
  },

  /** Apply an API-side change (e.g. stop) without waiting for the next frame. */
  update(execution: Execution) {
    if (!snapshot || snapshot.execution.id !== execution.id) return
    snapshot = { ...snapshot, execution }
    publish()
  },

  clear() {
    clearActiveRun()
    snapshot = null
    publish()
  },

  get: () => snapshot,

  subscribe(listener: Listener) {
    listeners.add(listener)
    listener(snapshot)
    return () => {
      listeners.delete(listener)
    }
  },
}

/** Re-attach to the active run after a full page reload. */
export async function restoreActiveExecution() {
  if (snapshot) return
  let id: string | null = null
  try {
    id = sessionStorage.getItem(STORAGE_KEY)
  } catch {
    return
  }
  if (!id) return
  try {
    const execution = await executionsApi.get(id)
    if (isTerminalStatus(execution.status)) activeExecution.clear()
    else activeExecution.start(execution)
  } catch {
    activeExecution.clear()
  }
}

export function useActiveExecution() {
  const [value, setValue] = React.useState<ActiveExecutionSnapshot | null>(activeExecution.get())
  React.useEffect(() => activeExecution.subscribe(setValue), [])
  return value
}
