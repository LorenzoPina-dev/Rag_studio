import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const toastInfo = vi.hoisted(() => vi.fn())

vi.mock('sonner', () => ({ toast: { info: toastInfo } }))

import { bus } from './bus'
import { registerRunNavigation } from './runNavigation'

describe('registerRunNavigation', () => {
  let off: () => void = () => {}
  let activeRunId: string | null = null
  const navigate = vi.fn()

  beforeEach(() => {
    activeRunId = null
    navigate.mockClear()
    toastInfo.mockClear()
  })

  afterEach(() => off())

  it('navigates to the current run and its results', () => {
    activeRunId = 'run_42'
    off = registerRunNavigation(() => activeRunId, navigate)

    bus.emit('pipeline:open-run')
    bus.emit('pipeline:inspect-results')

    expect(navigate).toHaveBeenNthCalledWith(1, '/runs/run_42')
    expect(navigate).toHaveBeenNthCalledWith(2, '/runs/run_42/results')
    expect(toastInfo).not.toHaveBeenCalled()
  })

  it('reads the latest run id instead of a stale closure value', () => {
    off = registerRunNavigation(() => activeRunId, navigate)
    activeRunId = 'run_99'

    bus.emit('pipeline:inspect-results')

    expect(navigate).toHaveBeenCalledWith('/runs/run_99/results')
  })

  it('does not navigate when no run is active', () => {
    off = registerRunNavigation(() => activeRunId, navigate)

    bus.emit('pipeline:open-run')
    bus.emit('pipeline:inspect-results')

    expect(navigate).not.toHaveBeenCalled()
    expect(toastInfo).toHaveBeenCalledTimes(2)
    expect(toastInfo).toHaveBeenNthCalledWith(1, 'No run yet', { description: 'Run the pipeline first.' })
    expect(toastInfo).toHaveBeenNthCalledWith(2, 'No results yet', { description: 'Run the pipeline first.' })
  })
})
