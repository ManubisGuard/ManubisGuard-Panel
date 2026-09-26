import { cn } from '@/lib/utils'
import * as React from 'react'

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  error?: string
  isError?: boolean
}

const Input = React.forwardRef<HTMLInputElement, InputProps>(({ className, type, error, isError, ...props }, ref) => {
  return (
    <div className="min-w-0 flex-1">
      <input
        type={type}
        dir="ltr"
        className={cn(
          'border-border/70 bg-input/75 file:text-foreground placeholder:text-input-placeholder focus-visible:ring-primary/30 flex h-10 w-full rounded-xl border px-3 py-2 text-sm shadow-[inset_0_1px_0_hsl(0_0%_100%_/_0.025)] transition-all focus-visible:border-primary/50 focus-visible:ring-2 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50',
          className,
          {
            'border-destructive': !!error || isError,
          },
        )}
        ref={ref}
        {...props}
      />
      {error && <span className="text-destructive mt-2 block text-sm">{error}</span>}
    </div>
  )
})
Input.displayName = 'Input'

export { Input }
