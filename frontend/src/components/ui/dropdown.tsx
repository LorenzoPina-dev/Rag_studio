import * as React from 'react'
import * as DropdownPrimitive from '@radix-ui/react-dropdown-menu'
import { Check, ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'

export const DropdownMenu = DropdownPrimitive.Root
export const DropdownMenuTrigger = DropdownPrimitive.Trigger

export function DropdownMenuContent({
  children,
  className,
  align = 'end',
  sideOffset = 5,
}: {
  children: React.ReactNode
  className?: string
  align?: 'start' | 'end' | 'center'
  sideOffset?: number
}) {
  return (
    <DropdownPrimitive.Portal>
      <DropdownPrimitive.Content
        align={align}
        sideOffset={sideOffset}
        className={cn(
          'z-[105] min-w-[190px] overflow-hidden rounded-md border border-line-strong bg-[#0e1622] p-1 shadow-pop animate-fade-in',
          className,
        )}
        onPointerDown={(event) => event.stopPropagation()}
        onClick={(event) => event.stopPropagation()}
      >
        {children}
      </DropdownPrimitive.Content>
    </DropdownPrimitive.Portal>
  )
}

export function DropdownMenuItem({
  children,
  onSelect,
  icon,
  shortcut,
  danger,
  disabled,
  className,
}: {
  children: React.ReactNode
  onSelect?: (event: Event) => void
  icon?: React.ReactNode
  shortcut?: string
  danger?: boolean
  disabled?: boolean
  className?: string
}) {
  return (
    <DropdownPrimitive.Item
      disabled={disabled}
      onSelect={onSelect}
      className={cn(
        'flex cursor-pointer select-none items-center gap-2 rounded px-2 py-1.5 text-[11.5px] text-muted outline-none transition-colors data-[disabled]:pointer-events-none data-[disabled]:opacity-40 data-[highlighted]:bg-white/[0.055] data-[highlighted]:text-ink',
        danger && 'text-[#ff9292] data-[highlighted]:bg-danger/10 data-[highlighted]:text-[#ffb0b0]',
        className,
      )}
    >
      {icon && <span className="flex h-3.5 w-3.5 items-center justify-center text-dim">{icon}</span>}
      <span className="flex-1">{children}</span>
      {shortcut && <span className="font-mono text-[9px] text-dim">{shortcut}</span>}
    </DropdownPrimitive.Item>
  )
}

export function DropdownMenuLabel({ children }: { children: React.ReactNode }) {
  return <div className="px-2 pb-1 pt-1.5 font-mono text-[9px] uppercase tracking-[0.12em] text-dim">{children}</div>
}

export function DropdownMenuSeparator() {
  return <DropdownPrimitive.Separator className="my-1 h-px bg-line" />
}

export function DropdownMenuCheckboxItem({
  children,
  checked,
  onCheckedChange,
}: {
  children: React.ReactNode
  checked: boolean
  onCheckedChange: (checked: boolean) => void
}) {
  return (
    <DropdownPrimitive.CheckboxItem
      checked={checked}
      onCheckedChange={onCheckedChange}
      className="flex cursor-pointer select-none items-center gap-2 rounded px-2 py-1.5 text-[11.5px] text-muted outline-none data-[highlighted]:bg-white/[0.055] data-[highlighted]:text-ink"
    >
      <span className="flex h-3 w-3 items-center justify-center">{checked && <Check className="h-3 w-3 text-accent" />}</span>
      {children}
    </DropdownPrimitive.CheckboxItem>
  )
}

export function DropdownMenuSub({ children }: { children: React.ReactNode }) {
  return <DropdownPrimitive.Sub>{children}</DropdownPrimitive.Sub>
}

export function DropdownMenuSubTrigger({ children, icon }: { children: React.ReactNode; icon?: React.ReactNode }) {
  return (
    <DropdownPrimitive.SubTrigger className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-[11.5px] text-muted outline-none data-[highlighted]:bg-white/[0.055] data-[highlighted]:text-ink">
      {icon && <span className="flex h-3.5 w-3.5 items-center justify-center text-dim">{icon}</span>}
      <span className="flex-1">{children}</span>
      <ChevronRight className="h-3 w-3 text-dim" />
    </DropdownPrimitive.SubTrigger>
  )
}

export function DropdownMenuSubContent({ children }: { children: React.ReactNode }) {
  return (
    <DropdownPrimitive.Portal>
      <DropdownPrimitive.SubContent
        className="z-[106] min-w-[180px] rounded-md border border-line-strong bg-[#0e1622] p-1 shadow-pop"
        onPointerDown={(event) => event.stopPropagation()}
        onClick={(event) => event.stopPropagation()}
      >
        {children}
      </DropdownPrimitive.SubContent>
    </DropdownPrimitive.Portal>
  )
}
