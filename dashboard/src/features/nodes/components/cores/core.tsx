import { Card } from '@/components/ui/card'
import { CoreResponse } from '@/service/api'
import CoreActionsMenu from './core-actions-menu'
import { cn } from '@/lib/utils'
import type { ReactNode } from 'react'

interface CoreProps {
  core: CoreResponse
  onEdit: (core: CoreResponse) => void
  onToggleStatus: (core: CoreResponse) => Promise<void>
  onDuplicate?: () => void
  onDelete?: () => void
  canUpdate?: boolean
  canCreate?: boolean
  canDelete?: boolean
  selectionControl?: ReactNode
  selected?: boolean
}

export default function Core({ core, onEdit, onDuplicate, onDelete, canUpdate = true, canCreate = true, canDelete = true, selectionControl, selected = false }: CoreProps) {
  return (
    <Card
      className={cn('group relative h-full overflow-hidden rounded-xl border-border/60 bg-card/45 px-4 py-4 shadow-none transition-all duration-200', canUpdate && 'cursor-pointer hover:border-primary/25 hover:bg-card/70', selected && 'border-primary/45 bg-primary/5')}
      onClick={() => {
        if (canUpdate) onEdit(core)
      }}
    >
      <div className="flex items-start gap-3">
        {selectionControl ? <div className="pt-1">{selectionControl}</div> : null}
        <div className="flex min-w-0 flex-1 items-start gap-3">
          <div className="min-w-0 flex-1">
            <div className="flex items-center justify-between gap-2">
              <div className="flex min-w-0 items-center gap-2">
                <div className={cn('min-h-2 min-w-2 rounded-full bg-primary shadow-[0_0_10px_hsl(var(--primary)/.45)]')} />
                <div className="truncate text-sm font-medium tracking-tight">{core.name}</div>
              </div>
            </div>
          </div>
          <CoreActionsMenu core={core} onEdit={onEdit} onDuplicate={onDuplicate} onDelete={onDelete} canUpdate={canUpdate} canCreate={canCreate} canDelete={canDelete} />
        </div>
      </div>
    </Card>
  )
}
