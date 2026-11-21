import { cn } from '@/lib/utils'

export function Sparkline({
  data,
  color = '#7296FF',
  className,
  height = 34,
  width = 104,
  bars = 18,
}: {
  data: number[]
  color?: string
  className?: string
  height?: number
  width?: number
  bars?: number
}) {
  const values = data.slice(-bars)
  const max = Math.max(...values, 1)
  const min = Math.min(...values, 0)
  const gap = 2
  const barWidth = (width - gap * (values.length - 1)) / values.length
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className={cn('overflow-visible', className)} style={{ width, height }} aria-hidden="true">
      <defs>
        <linearGradient id={`spark-${color.replace('#', '')}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.95" />
          <stop offset="100%" stopColor={color} stopOpacity="0.2" />
        </linearGradient>
      </defs>
      {values.map((value, i) => {
        const normalized = (value - min) / (max - min || 1)
        const h = Math.max(3, normalized * height)
        const isRecent = i >= values.length - 4
        return (
          <rect
            key={i}
            x={i * (barWidth + gap)}
            y={height - h}
            width={barWidth}
            height={h}
            rx={0.8}
            fill={`url(#spark-${color.replace('#', '')})`}
            opacity={isRecent ? 1 : 0.34}
          />
        )
      })}
    </svg>
  )
}

export function KpiCard({
  label,
  value,
  delta,
  tone = 'success',
  spark,
  sparkColor = '#7296FF',
  className,
  suffix,
  onClick,
  children,
}: {
  label: string
  value: React.ReactNode
  delta?: React.ReactNode
  tone?: 'success' | 'muted' | 'danger' | 'warning'
  spark?: number[]
  sparkColor?: string
  className?: string
  suffix?: React.ReactNode
  onClick?: () => void
  children?: React.ReactNode
}) {
  const toneClass = {
    success: 'text-success',
    muted: 'text-dim',
    danger: 'text-danger',
    warning: 'text-warn',
  }[tone]
  return (
    <div
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      className={cn(
        'group relative min-w-0 overflow-hidden rounded-lg border border-line bg-gradient-to-b from-[#101927] to-[#0d1622] px-4 pb-3.5 pt-3.5 transition-colors',
        onClick && 'cursor-pointer hover:border-[#30405a]',
        className,
      )}
    >
      <p className="text-[11px] font-medium text-muted">{label}</p>
      <div className="mt-2 flex items-end justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-baseline gap-1">
            <span className="text-[25px] font-semibold leading-none tracking-[-0.03em] text-ink tabular-nums">{value}</span>
            {suffix && <span className="text-[11px] text-dim">{suffix}</span>}
          </div>
          {delta && <div className={cn('mt-2.5 flex items-center gap-1 font-mono text-[9.5px] leading-none', toneClass)}>{delta}</div>}
        </div>
        {spark && <Sparkline data={spark} color={sparkColor} className="mb-0.5 shrink-0 opacity-90" />}
      </div>
      {children}
    </div>
  )
}
