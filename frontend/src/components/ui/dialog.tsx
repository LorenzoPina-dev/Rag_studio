import * as React from 'react'
import * as DialogPrimitive from '@radix-ui/react-dialog'
import { X } from 'lucide-react'
import { cn } from '@/lib/utils'

export const Dialog = DialogPrimitive.Root
export const DialogTrigger = DialogPrimitive.Trigger
export const DialogClose = DialogPrimitive.Close

export function DialogContent({
  children,
  className,
  size = 'md',
  hideClose,
}: {
  children: React.ReactNode
  className?: string
  size?: 'sm' | 'md' | 'lg' | 'xl'
  hideClose?: boolean
}) {
  const sizes = { sm: 'max-w-[400px]', md: 'max-w-[520px]', lg: 'max-w-[680px]', xl: 'max-w-[880px]' }
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="fixed inset-0 z-[100] bg-[#05080d]/75 backdrop-blur-[2px] data-[state=open]:animate-fade-in" />
      <DialogPrimitive.Content
        className={cn(
          'fixed left-1/2 top-[12%] z-[101] w-[calc(100vw-2rem)] -translate-x-1/2 overflow-hidden rounded-xl border border-line-strong bg-[#0d141f] shadow-pop animate-slide-up focus:outline-none',
          sizes[size],
          className,
        )}
      >
        {children}
        {!hideClose && (
          <DialogPrimitive.Close className="absolute right-3.5 top-3.5 rounded p-1 text-dim transition-colors hover:bg-white/5 hover:text-ink focus:outline-none">
            <X className="h-4 w-4" />
            <span className="sr-only">Close</span>
          </DialogPrimitive.Close>
        )}
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  )
}

export function DialogHeader({ title, description, eyebrow, className }: { title: React.ReactNode; description?: React.ReactNode; eyebrow?: string; className?: string }) {
  return (
    <div className={cn('border-b border-line px-5 pb-4 pt-5', className)}>
      {eyebrow && <p className="eyebrow mb-2">{eyebrow}</p>}
      <DialogPrimitive.Title className="pr-8 text-[16px] font-semibold tracking-[-0.01em] text-ink">{title}</DialogPrimitive.Title>
      {description && (
        <DialogPrimitive.Description className="mt-1.5 text-[11.5px] leading-relaxed text-muted">{description}</DialogPrimitive.Description>
      )}
    </div>
  )
}

export function DialogFooter({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn('flex items-center justify-end gap-2 border-t border-line bg-[#0b111b]/60 px-5 py-3', className)}>{children}</div>
}

export function DialogBody({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn('max-h-[62vh] overflow-y-auto px-5 py-4', className)}>{children}</div>
}
