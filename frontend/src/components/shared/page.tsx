import * as React from 'react'
import { Link } from 'react-router-dom'
import { ChevronRight, MoreHorizontal } from 'lucide-react'
import { cn } from '@/lib/utils'
import { StatusDot } from '@/components/ui/badge'

export interface Crumb {
  label: string
  to?: string
}

export function Breadcrumbs({ items, className }: { items: Crumb[]; className?: string }) {
  return (
    <nav aria-label="Breadcrumb" className={cn('flex items-center gap-1.5 font-mono text-[10px] text-dim', className)}>
      {items.map((item, i) => (
        <React.Fragment key={`${item.label}-${i}`}>
          {item.to ? (
            <Link to={item.to} className="transition-colors hover:text-muted">
              {item.label}
            </Link>
          ) : (
            <span className={i === items.length - 1 ? 'text-muted' : ''}>{item.label}</span>
          )}
          {i < items.length - 1 && <ChevronRight className="h-2.5 w-2.5 text-[#43506a]" />}
        </React.Fragment>
      ))}
    </nav>
  )
}

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
  breadcrumbs,
  className,
  tabs,
  compact,
}: {
  eyebrow?: string
  title: React.ReactNode
  description?: React.ReactNode
  actions?: React.ReactNode
  breadcrumbs?: Crumb[]
  className?: string
  tabs?: React.ReactNode
  compact?: boolean
}) {
  return (
    <div className={cn('shrink-0 border-b border-line/80 bg-bg/60', className)}>
      <div className={cn('flex flex-wrap items-start justify-between gap-4 px-6', compact ? 'pb-2.5 pt-3' : 'pb-4 pt-5')}>
        <div className="min-w-0">
          {breadcrumbs && <Breadcrumbs items={breadcrumbs} className="mb-2" />}
          {eyebrow && <p className="eyebrow mb-2">{eyebrow}</p>}
          <h1 className={cn('font-semibold tracking-[-0.025em] text-ink', compact ? 'text-[19px]' : 'text-[26px] leading-[1.2]')}>{title}</h1>
          {description && <p className="mt-1.5 max-w-2xl text-[12px] leading-relaxed text-muted">{description}</p>}
        </div>
        {actions && <div className="flex shrink-0 flex-wrap items-center gap-2 pt-1">{actions}</div>}
      </div>
      {tabs && <div className="px-6">{tabs}</div>}
    </div>
  )
}

export function InlineMeta({ items, className }: { items: Array<React.ReactNode>; className?: string }) {
  return (
    <div className={cn('flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[9.5px] text-dim', className)}>
      {items.map((item, i) => (
        <React.Fragment key={i}>
          {i > 0 && <span className="text-[#344158]">·</span>}
          <span>{item}</span>
        </React.Fragment>
      ))}
    </div>
  )
}

export function HealthPill({ health }: { health: 'healthy' | 'warning' | 'draft' }) {
  const map = {
    healthy: { tone: 'text-success', dot: 'success' as const, label: 'Healthy' },
    warning: { tone: 'text-warn', dot: 'warning' as const, label: 'Needs attention' },
    draft: { tone: 'text-muted', dot: 'idle' as const, label: 'Draft' },
  }[health]
  return (
    <span className={cn('flex items-center gap-1.5 font-mono text-[9.5px]', map.tone)}>
      <StatusDot status={map.dot} /> {map.label}
    </span>
  )
}

export function RowActions({ onClick, label = 'Row actions' }: { onClick?: () => void; label?: string }) {
  return (
    <button
      onClick={(e) => {
        e.stopPropagation()
        onClick?.()
      }}
      aria-label={label}
      className="rounded p-1 text-dim transition-colors hover:bg-white/[0.06] hover:text-ink"
    >
      <MoreHorizontal className="h-4 w-4" />
    </button>
  )
}

export function Pagination({
  page,
  pages,
  onChange,
  total,
  pageSize,
}: {
  page: number
  pages: number
  onChange: (page: number) => void
  total?: number
  pageSize?: number
}) {
  return (
    <div className="flex items-center justify-between gap-3 px-4 py-3">
      <span className="font-mono text-[9.5px] text-dim">
        {total !== undefined && pageSize !== undefined
          ? `${(page - 1) * pageSize + 1}–${Math.min(page * pageSize, total)} of ${total}`
          : `${pages} pages`}
      </span>
      <div className="flex items-center gap-1">
        <button
          onClick={() => onChange(Math.max(1, page - 1))}
          disabled={page <= 1}
          className="flex h-6 w-6 items-center justify-center rounded text-dim transition-colors hover:bg-white/5 hover:text-ink disabled:opacity-30"
          aria-label="Previous page"
        >
          <ChevronRight className="h-3.5 w-3.5 rotate-180" />
        </button>
        {Array.from({ length: pages }).map((_, i) => (
          <button
            key={i}
            onClick={() => onChange(i + 1)}
            className={cn(
              'flex h-6 min-w-6 items-center justify-center rounded px-1.5 font-mono text-[10px] transition-colors',
              page === i + 1 ? 'bg-accent/15 text-[#a6b8ff]' : 'text-dim hover:bg-white/5 hover:text-ink',
            )}
            aria-current={page === i + 1 ? 'page' : undefined}
          >
            {i + 1}
          </button>
        ))}
        <button
          onClick={() => onChange(Math.min(pages, page + 1))}
          disabled={page >= pages}
          className="flex h-6 w-6 items-center justify-center rounded text-dim transition-colors hover:bg-white/5 hover:text-ink disabled:opacity-30"
          aria-label="Next page"
        >
          <ChevronRight className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  )
}

export function MiniDag({ accent = '#7296FF', nodes = ['Source', 'Chunk', 'Retrieve', 'LLM'] }: { accent?: string; nodes?: string[] }) {
  return (
    <div className="flex items-center gap-0">
      {nodes.map((node, i) => (
        <div key={node} className="flex items-center">
          <div
            className="rounded border bg-[#0b111b] px-2.5 py-1.5 font-mono text-[9.5px] text-ink/85"
            style={{ borderColor: i === 0 ? `${accent}99` : '#2a3850', boxShadow: i === 0 ? `0 0 12px ${accent}20` : undefined }}
          >
            {node}
          </div>
          {i < nodes.length - 1 && <div className="h-px w-5 bg-gradient-to-r from-[#354864] to-[#354864]" />}
        </div>
      ))}
    </div>
  )
}

export function CopyButton({ value, label = 'Copy' }: { value: string; label?: string }) {
  const [copied, setCopied] = React.useState(false)
  return (
    <button
      onClick={() => {
        navigator.clipboard?.writeText(value)
        setCopied(true)
        setTimeout(() => setCopied(false), 1400)
      }}
      className="flex items-center gap-1 font-mono text-[9.5px] text-dim transition-colors hover:text-ink"
      aria-label={label}
    >
      {copied ? 'Copied' : label}
    </button>
  )
}
