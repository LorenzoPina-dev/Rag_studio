import * as React from 'react'
import { cn } from '@/lib/utils'

export function Badge({
  children,
  tone = 'neutral',
  className,
  dot,
}: {
  children: React.ReactNode
  tone?: 'neutral' | 'success' | 'warning' | 'danger' | 'accent' | 'violet' | 'outline'
  className?: string
  dot?: boolean
}) {
  const tones = {
    neutral: 'border-line-strong/80 bg-white/[0.035] text-muted',
    success: 'border-success/20 bg-success/[0.08] text-success',
    warning: 'border-warn/20 bg-warn/[0.08] text-warn',
    danger: 'border-danger/25 bg-danger/[0.08] text-danger',
    accent: 'border-accent/25 bg-accent/[0.09] text-[#9db1ff]',
    violet: 'border-violet/25 bg-violet/[0.09] text-[#c4b1ff]',
    outline: 'border-line-strong bg-transparent text-muted',
  }
  return (
    <span
      className={cn(
        'inline-flex h-5 items-center gap-1.5 rounded border px-1.5 font-mono text-[9.5px] font-medium uppercase tracking-[0.06em]',
        tones[tone],
        className,
      )}
    >
      {dot && <span className={cn('h-1 w-1 rounded-full', tone === 'success' ? 'bg-success' : tone === 'warning' ? 'bg-warn' : tone === 'danger' ? 'bg-danger' : 'bg-current')} />}
      {children}
    </span>
  )
}

export function StatusDot({
  status,
  className,
  pulse,
}: {
  status: 'success' | 'warning' | 'danger' | 'idle' | 'running' | 'accent'
  className?: string
  pulse?: boolean
}) {
  const color = {
    success: 'bg-success shadow-[0_0_7px_rgba(53,217,155,0.55)]',
    warning: 'bg-warn shadow-[0_0_7px_rgba(240,180,92,0.4)]',
    danger: 'bg-danger shadow-[0_0_7px_rgba(240,106,106,0.45)]',
    idle: 'bg-[#68758b]',
    running: 'bg-accent shadow-[0_0_7px_rgba(91,124,250,0.5)]',
    accent: 'bg-accent',
  }[status]
  return <span className={cn('inline-block h-1.5 w-1.5 shrink-0 rounded-full', color, pulse && 'animate-pulse-dot', className)} />
}

export function Kbd({ children }: { children: React.ReactNode }) {
  return (
    <kbd className="rounded border border-line-strong bg-[#101823] px-1 py-0.5 font-mono text-[9px] leading-none text-muted">{children}</kbd>
  )
}

export function SectionLabel({ children, className, action }: { children: React.ReactNode; className?: string; action?: React.ReactNode }) {
  return (
    <div className={cn('flex h-8 items-center justify-between border-b border-line/80 px-4', className)}>
      <span className="font-mono text-[9.5px] font-medium uppercase tracking-[0.13em] text-dim">{children}</span>
      {action}
    </div>
  )
}

export function Divider({ className }: { className?: string }) {
  return <div className={cn('h-px w-full bg-line/80', className)} />
}

export function ProgressBar({
  value,
  max = 100,
  color = '#5277EC',
  className,
  trackClassName,
  height = 4,
}: {
  value: number
  max?: number
  color?: string
  className?: string
  trackClassName?: string
  height?: number
}) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100))
  return (
    <div className={cn('w-full overflow-hidden rounded-full bg-[#1a2433]', trackClassName)} style={{ height }}>
      <div
        className={cn('h-full rounded-full transition-[width] duration-500', className)}
        style={{ width: `${pct}%`, backgroundColor: color }}
      />
    </div>
  )
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: {
  icon?: React.ReactNode
  title: string
  description?: string
  action?: React.ReactNode
  className?: string
}) {
  return (
    <div className={cn('flex flex-col items-center justify-center px-6 py-14 text-center', className)}>
      {icon && <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg border border-line bg-surface2 text-muted">{icon}</div>}
      <h3 className="text-[13px] font-medium text-ink">{title}</h3>
      {description && <p className="mt-1 max-w-sm text-[11.5px] leading-relaxed text-dim">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

export function LoadingState({ label = 'Loading workspace…', rows = 3 }: { label?: string; rows?: number }) {
  return (
    <div className="space-y-3 p-5" aria-busy="true" aria-label={label}>
      <div className="flex items-center gap-2">
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
        <span className="font-mono text-[10px] uppercase tracking-wider text-dim">{label}</span>
      </div>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-9 animate-pulse rounded-md border border-line/60 bg-white/[0.02]" />
      ))}
    </div>
  )
}

export function ErrorState({ message, onRetry }: { message?: string; onRetry?: () => void }) {
  return (
    <div className="m-5 rounded-lg border border-danger/25 bg-danger/[0.05] p-4">
      <p className="text-[12px] font-medium text-[#ff9c9c]">Couldn’t load this view</p>
      <p className="mt-1 text-[11px] text-muted">{message ?? 'The request failed. Check the API connection and try again.'}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-3 rounded border border-danger/30 px-2.5 py-1 text-[11px] text-[#ffb0b0] hover:bg-danger/10"
        >
          Retry
        </button>
      )}
    </div>
  )
}

export function Tooltip({ label, children, side = 'top' }: { label: string; children: React.ReactNode; side?: 'top' | 'bottom' | 'left' | 'right' }) {
  return (
    <span className="group/tt relative inline-flex">
      {children}
      <span
        className={cn(
          'pointer-events-none absolute z-50 whitespace-nowrap rounded border border-line-strong bg-[#111a27] px-2 py-1 text-[10px] text-ink opacity-0 shadow-pop transition-opacity group-hover/tt:opacity-100',
          side === 'top' && 'bottom-full left-1/2 mb-1.5 -translate-x-1/2',
          side === 'bottom' && 'top-full left-1/2 mt-1.5 -translate-x-1/2',
          side === 'left' && 'right-full top-1/2 mr-1.5 -translate-y-1/2',
          side === 'right' && 'left-full top-1/2 ml-1.5 -translate-y-1/2',
        )}
        role="tooltip"
      >
        {label}
      </span>
    </span>
  )
}
