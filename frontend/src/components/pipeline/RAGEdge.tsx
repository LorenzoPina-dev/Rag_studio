import { memo } from 'react'
import { BaseEdge, EdgeLabelRenderer, getBezierPath, type EdgeProps } from '@xyflow/react'
import { X } from 'lucide-react'
import { usePipelineStore } from '@/store/usePipelineStore'

const colorByType: Record<string, [string, string]> = {
  documents: ['#2FC9C3', '#2FC9C3'],
  chunks: ['#B27CFF', '#7296FF'],
  embedding: ['#B27CFF', '#6F93FF'],
  query: ['#4A8CFF', '#7AA2FF'],
  any: ['#4E6B8F', '#6C88AB'],
  json: ['#F0B45C', '#F0B45C'],
  text: ['#6C88AB', '#8AA0C0'],
}

export const RAGEdge = memo(({ id, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, data, selected, markerEnd }: EdgeProps) => {
  const removeEdges = usePipelineStore((s) => s.removeEdges)
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
    curvature: 0.32,
  })
  const dataType = (data as { dataType?: string } | undefined)?.dataType ?? 'any'
  const [from, to] = colorByType[dataType] ?? colorByType.any
  const gradientId = `edge-gradient-${id}`
  return (
    <>
      <defs>
        <linearGradient id={gradientId} gradientUnits="userSpaceOnUse" x1={sourceX} y1={sourceY} x2={targetX} y2={targetY}>
          <stop offset="0%" stopColor={from} stopOpacity="0.85" />
          <stop offset="100%" stopColor={to} stopOpacity="0.9" />
        </linearGradient>
        <filter id={`edge-glow-${id}`} x="-30%" y="-30%" width="160%" height="160%">
          <feGaussianBlur stdDeviation="2.2" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>
      <BaseEdge
        id={id}
        path={edgePath}
        markerEnd={markerEnd}
        style={{
          stroke: `url(#${gradientId})`,
          strokeWidth: selected ? 2.2 : 1.25,
          filter: selected ? `url(#edge-glow-${id})` : undefined,
          opacity: 0.88,
          strokeLinecap: 'round',
        }}
      />
      {selected && (
        <EdgeLabelRenderer>
          <button
            type="button"
            title="Rimuovi collegamento"
            aria-label="Rimuovi collegamento"
            className="nodrag nopan absolute flex h-[18px] w-[18px] items-center justify-center rounded-full border border-[#3a4a66] bg-[#0b121c] text-[#9fb0c8] shadow-[0_2px_10px_rgba(0,0,0,0.45)] transition-colors hover:border-danger hover:text-danger"
            style={{ transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`, pointerEvents: 'all' }}
            onClick={(event) => {
              event.stopPropagation()
              removeEdges([id])
            }}
          >
            <X className="h-2.5 w-2.5" strokeWidth={2.4} />
          </button>
        </EdgeLabelRenderer>
      )}
    </>
  )
})

RAGEdge.displayName = 'RAGEdge'
