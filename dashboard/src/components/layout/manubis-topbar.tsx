import { SidebarTriggerWithBadge } from '@/components/layout/sidebar-trigger-with-badge'
import { useCommandPaletteStore } from '@/hooks/use-command-palette-store'
import { useAdmin } from '@/hooks/use-admin'
import { Search, ShieldCheck } from 'lucide-react'
import { useTranslation } from 'react-i18next'

export default function ManubisTopbar() {
  const { t } = useTranslation()
  const { admin } = useAdmin()
  const setCommandPaletteOpen = useCommandPaletteStore(s => s.setOpen)

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-border/60 bg-background/85 px-3 backdrop-blur-xl sm:px-5">
      <SidebarTriggerWithBadge showUpdateBadge={Boolean(admin)} />

      <button
        type="button"
        onClick={() => setCommandPaletteOpen(true)}
        className="group flex h-9 min-w-0 flex-1 items-center gap-2 rounded-lg border border-border/60 bg-card/35 px-3 text-sm text-muted-foreground transition-colors hover:border-primary/30 hover:bg-card/60 hover:text-foreground sm:max-w-md"
      >
        <Search className="h-4 w-4 shrink-0" />
        <span className="truncate">{t('search', { defaultValue: 'Search' })}</span>
        <kbd className="ms-auto hidden rounded border border-border/60 bg-background/60 px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground sm:inline-flex">⌘ K</kbd>
      </button>

      <div className="ms-auto flex shrink-0 items-center gap-2">
        <div className="hidden items-center gap-1.5 rounded-full border border-primary/15 bg-primary/5 px-2.5 py-1.5 text-[11px] font-medium text-primary sm:flex">
          <span className="h-1.5 w-1.5 rounded-full bg-primary shadow-[0_0_8px_hsl(var(--primary)/.7)]" />
          <span>{t('online', { defaultValue: 'Online' })}</span>
        </div>
        <div className="flex h-9 items-center gap-2 rounded-lg border border-border/60 bg-card/35 px-2.5">
          <ShieldCheck className="h-4 w-4 text-primary" />
          <span className="hidden max-w-32 truncate text-xs font-medium sm:block">{admin?.username || 'Admin'}</span>
        </div>
      </div>
    </header>
  )
}
