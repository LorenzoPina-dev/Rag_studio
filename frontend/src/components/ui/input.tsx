import * as React from 'react'
import { cn } from '@/lib/utils'

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => <input ref={ref} className={cn('input-base', className)} {...props} />,
)
Input.displayName = 'Input'

export const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, ...props }, ref) => (
    <textarea
      ref={ref}
      className={cn(
        'min-h-[76px] w-full resize-y rounded-md border border-line-strong bg-[#0a1019] px-3 py-2 text-[12.5px] leading-relaxed text-ink placeholder:text-dim transition-colors focus:border-accent/70 focus:outline-none focus:ring-1 focus:ring-accent/25',
        className,
      )}
      {...props}
    />
  ),
)
Textarea.displayName = 'Textarea'

export function Field({
  label,
  hint,
  children,
  className,
  optional,
}: {
  label: React.ReactNode
  hint?: React.ReactNode
  children: React.ReactNode
  className?: string
  optional?: boolean
}) {
  return (
    <div className={cn('space-y-1.5', className)}>
      <div className="flex items-center justify-between gap-2">
        <label className="text-[11.5px] font-medium text-muted">{label}</label>
        {optional && <span className="font-mono text-[9px] uppercase tracking-wider text-dim">optional</span>}
      </div>
      {children}
      {hint && <p className="text-[10.5px] leading-relaxed text-dim">{hint}</p>}
    </div>
  )
}

export function SearchInput({
  value,
  onChange,
  placeholder = 'Search…',
  className,
  onClear,
}: {
  value: string
  onChange: (v: string) => void
  placeholder?: string
  className?: string
  onClear?: () => void
}) {
  return (
    <div className={cn('relative', className)}>
      <svg
        className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-dim"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={1.8}
      >
        <circle cx="11" cy="11" r="7" />
        <path d="m20 20-3.5-3.5" />
      </svg>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className={cn('input-base h-8 pl-8 pr-8 text-[11.5px]', className)}
      />
      {value && (
        <button
          type="button"
          onClick={() => {
            onChange('')
            onClear?.()
          }}
          className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-0.5 text-dim hover:bg-white/5 hover:text-ink"
          aria-label="Clear search"
        >
          <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path d="M18 6 6 18M6 6l12 12" />
          </svg>
        </button>
      )}
    </div>
  )
}
