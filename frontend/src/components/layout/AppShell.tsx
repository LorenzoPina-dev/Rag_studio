import { Outlet, useLocation } from 'react-router-dom'
import { TopBar } from './TopBar'
import { Sidebar } from './Sidebar'
import { StatusBar } from './StatusBar'
import { GlobalOverlays } from '@/components/overlays/GlobalOverlays'

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
    </div>
  )
}
