import * as React from 'react'
import * as TabsPrimitive from '@radix-ui/react-tabs'
import * as SwitchPrimitive from '@radix-ui/react-switch'
import * as CheckboxPrimitive from '@radix-ui/react-checkbox'
import { Check } from 'lucide-react'
import { cn } from '@/lib/utils'

export const Tabs = TabsPrimitive.Root

export function TabsList({ children, className }: { children: React.ReactNode; className?: string }) {
  return <TabsPrimitive.List className={cn('flex items-center gap-5 border-b border-line', className)}>{children}</TabsPrimitive.List>
}

export function TabsTrigger({ children, value, className }: { children: React.ReactNode; value: string; className?: string }) {
  return (
    <TabsPrimitive.Trigger
      value={value}
      className={cn(
        'relative -mb-px border-b border-transparent pb-2 pt-1.5 text-[11.5px] font-medium text-muted outline-none transition-colors hover:text-ink data-[state=active]:border-accent data-[state=active]:text-ink',
        className,
      )}
    >
      {children}
    </TabsPrimitive.Trigger>
  )
}

export function TabsContent({ children, value, className }: { children: React.ReactNode; value: string; className?: string }) {
  return (
    <TabsPrimitive.Content value={value} className={cn('outline-none', className)}>
      {children}
    </TabsPrimitive.Content>
  )
}

export function Switch({
  checked,
  onCheckedChange,
  label,
  className,
  disabled,
}: {
  checked: boolean
  onCheckedChange: (checked: boolean) => void
  label?: React.ReactNode
  className?: string
  disabled?: boolean
}) {
  return (
    <div className={cn('flex items-center justify-between gap-3', className)}>
      {label && <span className="text-[11.5px] text-muted">{label}</span>}
      <SwitchPrimitive.Root
        checked={checked}
        onCheckedChange={onCheckedChange}
        disabled={disabled}
        className={cn(
          'peer inline-flex h-[18px] w-[32px] shrink-0 cursor-pointer items-center rounded-full border border-line-strong bg-[#182234] transition-colors data-[state=checked]:border-accent/60 data-[state=checked]:bg-accent/80 disabled:cursor-not-allowed disabled:opacity-40',
        )}
      >
        <SwitchPrimitive.Thumb className="pointer-events-none block h-3 w-3 translate-x-[2px] rounded-full bg-[#8d9ab0] shadow transition-transform data-[state=checked]:translate-x-[16px] data-[state=checked]:bg-white" />
      </SwitchPrimitive.Root>
    </div>
  )
}

export function Checkbox({
  checked,
  onCheckedChange,
  className,
  'aria-label': ariaLabel,
  indeterminate,
}: {
  checked: boolean
  onCheckedChange: (checked: boolean) => void
  className?: string
  'aria-label'?: string
  indeterminate?: boolean
}) {
  return (
    <CheckboxPrimitive.Root
      checked={indeterminate ? 'indeterminate' : checked}
      onCheckedChange={(v) => onCheckedChange(v === true)}
      aria-label={ariaLabel}
      className={cn(
        'flex h-[14px] w-[14px] shrink-0 items-center justify-center rounded-[3px] border border-[#34445c] bg-[#0a1019] outline-none transition-colors hover:border-[#4a5d7a] data-[state=checked]:border-accent data-[state=checked]:bg-accent data-[state=indeterminate]:border-accent data-[state=indeterminate]:bg-accent',
        className,
      )}
    >
      <CheckboxPrimitive.Indicator className="text-white">
        {indeterminate ? <span className="block h-[1.5px] w-2 rounded bg-white" /> : <Check className="h-2.5 w-2.5" strokeWidth={3} />}
      </CheckboxPrimitive.Indicator>
    </CheckboxPrimitive.Root>
  )
}
