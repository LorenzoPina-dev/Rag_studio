import * as React from 'react'
import * as SelectPrimitive from '@radix-ui/react-select'
import { Check, ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'

export interface SelectOption {
  value: string
  label: string
  description?: string
}

export function Select({
  value,
  onValueChange,
  options,
  placeholder = 'Select…',
  className,
  contentClassName,
  mono,
  'aria-label': ariaLabel,
}: {
  value?: string
  onValueChange: (value: string) => void
  options: Array<SelectOption | string>
  placeholder?: string
  className?: string
  contentClassName?: string
  mono?: boolean
  'aria-label'?: string
}) {
  const normalized = options.map((o) => (typeof o === 'string' ? { value: o, label: o } : o))
  return (
    <SelectPrimitive.Root value={value} onValueChange={onValueChange}>
      <SelectPrimitive.Trigger className={cn('select-trigger', mono && 'font-mono text-[11px]', className)} aria-label={ariaLabel}>
        <SelectPrimitive.Value placeholder={<span className="text-dim">{placeholder}</span>} />
        <SelectPrimitive.Icon>
          <ChevronDown className="h-3.5 w-3.5 text-dim" />
        </SelectPrimitive.Icon>
      </SelectPrimitive.Trigger>
      <SelectPrimitive.Portal>
        <SelectPrimitive.Content
          position="popper"
          sideOffset={4}
          className={cn(
            'z-[110] min-w-[var(--radix-select-trigger-width)] overflow-hidden rounded-md border border-line-strong bg-[#0f1724] p-1 shadow-pop animate-fade-in',
            contentClassName,
          )}
        >
          <SelectPrimitive.Viewport>
            {normalized.map((option) => (
              <SelectPrimitive.Item
                key={option.value}
                value={option.value}
                className="relative flex cursor-pointer select-none items-center rounded px-2 py-1.5 pr-7 text-[11.5px] text-muted outline-none data-[highlighted]:bg-white/[0.055] data-[highlighted]:text-ink data-[state=checked]:text-ink"
              >
                <SelectPrimitive.ItemText>
                  <span className={cn(mono && 'font-mono text-[11px]')}>{option.label}</span>
                  {option.description && <span className="ml-2 text-[10px] text-dim">{option.description}</span>}
                </SelectPrimitive.ItemText>
                <SelectPrimitive.ItemIndicator className="absolute right-2">
                  <Check className="h-3 w-3 text-accent" />
                </SelectPrimitive.ItemIndicator>
              </SelectPrimitive.Item>
            ))}
          </SelectPrimitive.Viewport>
        </SelectPrimitive.Content>
      </SelectPrimitive.Portal>
    </SelectPrimitive.Root>
  )
}
