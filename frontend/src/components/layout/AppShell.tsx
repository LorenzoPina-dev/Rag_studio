import * as React from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { TopBar } from './TopBar'
import { Sidebar } from './Sidebar'
import { StatusBar } from './StatusBar'
import { GlobalOverlays } from '@/components/overlays/GlobalOverlays'
import { restoreActiveExecution, useActiveExecution } from '@/lib/activeExecution'

/** Refresh run caches when a run ends, even if no page is watching it. */
function ActiveExecutionSync() {
  const queryClient = useQueryClient()
  const active = useActiveExecution()
  const handled = React.useRef<string | null>(null)

  React.useEffect(() => {
    void restoreActiveExecution()
  }, [])

  React.useEffect(() => {
    if (!active?.terminal || handled.current === active.execution.id) return
    handled.current = active.execution.id
    queryClient.setQueryData(['execution', active.execution.id], active.execution)
    queryClient.invalidateQueries({ queryKey: ['execution', active.execution.id] })
    queryClient.invalidateQueries({ queryKey: ['executions'] })
  }, [active, queryClient])

  return null
}

export function AppShell() {
  const location = useLocation()
  return (
    <div className="flex h-screen min-h-0 flex-col overflow-hidden bg-bg">
      <TopBar />
      <div className="flex min-h-0 flex-1">
        <Sidebar />
        <main className="relative flex min-w-0 flex-1 flex-col overflow-hidden" key={location.pathname.includes('/pipelines/') ? 'editor' : location.pathname}>
          <Outlet />
        </main>
      </div>
      <StatusBar />
      <GlobalOverlays />
      <ActiveExecutionSync />
    </div>
  )
}
