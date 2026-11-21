import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent/60 disabled:pointer-events-none disabled:opacity-45 select-none',
  {
    variants: {
      variant: {
        primary:
          'bg-[#5277EC] text-white shadow-[0_1px_0_rgba(255,255,255,0.14)_inset] hover:bg-[#6184f4] active:bg-[#4a6ddb]',
        secondary:
          'border border-line-strong bg-[#0e1622] text-ink/90 hover:border-[#3b4a61] hover:bg-[#121c2b]',
        ghost: 'text-muted hover:bg-white/[0.045] hover:text-ink',
        outline: 'border border-accent/45 bg-accent/5 text-[#94acff] hover:bg-accent/10',
        danger: 'border border-danger/35 bg-danger/10 text-[#ff9494] hover:bg-danger/15',
        subtle: 'bg-white/[0.04] text-ink/85 hover:bg-white/[0.07]',
      },
      size: {
        xs: 'h-6 px-2 text-[10.5px] rounded',
        sm: 'h-7 px-2.5 text-[11.5px] rounded',
        md: 'h-8 px-3 text-[12px]',
        lg: 'h-9 px-4 text-[12.5px]',
        icon: 'h-8 w-8',
        'icon-sm': 'h-6 w-6 rounded',
      },
    },
    defaultVariants: {
      variant: 'secondary',
      size: 'md',
    },
  },
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button'
    return <Comp className={cn(buttonVariants({ variant, size }), className)} ref={ref} {...props} />
  },
)
Button.displayName = 'Button'

export { buttonVariants }
