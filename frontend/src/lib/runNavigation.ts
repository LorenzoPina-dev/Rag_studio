import { toast } from 'sonner'
import { bus } from './bus'

export const RUN_NAVIGATION_EVENTS = ['pipeline:open-run', 'pipeline:inspect-results'] as const

export type RunNavigationEvent = (typeof RUN_NAVIGATION_EVENTS)[number]

/**
 * Wire the top-bar run actions to the run currently owned by the pipeline editor.
 * Keeping the lookup in a callback avoids stale closures over `activeRunId`.
 */
export function registerRunNavigation(
  getActiveRunId: () => string | null,
  navigate: (path: string) => void,
): () => void {
  const handle = (event: RunNavigationEvent) => {
    const runId = getActiveRunId()
    const isResults = event === 'pipeline:inspect-results'
    if (!runId) {
      toast.info(isResults ? 'No results yet' : 'No run yet', {
        description: 'Run the pipeline first.',
      })
      return
    }
    navigate(isResults ? `/runs/${runId}/results` : `/runs/${runId}`)
  }

  const offs = RUN_NAVIGATION_EVENTS.map((event) => bus.on(event, () => handle(event)))
  return () => offs.forEach((off) => off())
}
