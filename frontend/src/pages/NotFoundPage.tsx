import { Link } from 'react-router-dom'
import { ArrowLeft, Compass, LayoutGrid, Search } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Breadcrumbs } from '@/components/shared/page'
import { useAppStore } from '@/store/useAppStore'

export function NotFoundPage() {
  const setCommandOpen = useAppStore((state) => state.setCommandOpen)
  return (
    <>
      <div className="flex shrink-0 items-center border-b border-line/80 bg-bg/60 px-6 py-3">
        <Breadcrumbs items={[{ label: 'Research lab', to: '/' }, { label: 'Not found' }]} />
      </div>
      <div className="relative flex min-h-0 flex-1 items-center justify-center overflow-hidden dotted-canvas px-6">
        <div className="absolute inset-0 vignette" />
        <div className="relative z-10 w-full max-w-md rounded-xl border border-line-strong bg-[#0c141f]/95 p-8 text-center shadow-pop">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-lg border border-accent/30 bg-accent/[0.08] text-[#9db1ff] shadow-glow">
            <Compass className="h-5 w-5" />
          </div>
          <p className="mt-4 font-mono text-[9px] uppercase tracking-[0.18em] text-dim">Error 404 · Route not found</p>
          <h1 className="mt-2 text-[24px] font-semibold tracking-[-0.03em] text-ink">This page drifted off the graph</h1>
          <p className="mx-auto mt-2 max-w-sm text-[11.5px] leading-relaxed text-muted">
            The screen you requested doesn’t exist, or the pipeline, run or experiment it pointed to has been removed.
          </p>
          <div className="mt-5 flex flex-wrap items-center justify-center gap-2">
            <Button variant="primary" asChild>
              <Link to="/"><LayoutGrid className="h-3.5 w-3.5" /> Back to dashboard</Link>
            </Button>
            <Button variant="secondary" onClick={() => setCommandOpen(true)}>
              <Search className="h-3.5 w-3.5" /> Search workspace
            </Button>
          </div>
          <div className="mt-5 border-t border-line/60 pt-3 font-mono text-[8.5px] text-dim">
            <Link to="/pipelines" className="inline-flex items-center gap-1 text-[#7f95cf] hover:text-[#b5c6ff]">
              <ArrowLeft className="h-2.5 w-2.5" /> Return to pipelines
            </Link>
          </div>
        </div>
      </div>
    </>
  )
}
