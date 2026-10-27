import { Language } from '@/components/common/language'
import { ThemeToggle } from '@/components/common/theme-toggle'
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
    <header className="mg-topbar sticky top-0 z-30 flex h-14 min-w-0 items-center gap-3 border-b px-3 sm:px-5 lg:px-6">
      <SidebarTriggerWithBadge />

      <button
        type="button"
        onClick={() => setCommandPaletteOpen(true)}
        aria-label={t('search', { defaultValue: 'Search' })}
        className="mg-search-trigger group flex h-9 min-w-0 flex-1 items-center gap-2 rounded-lg border px-3 text-sm text-muted-foreground transition-colors sm:max-w-xl"
      >
        <Search className="h-4 w-4 shrink-0" />
        <span className="truncate">{t('search', { defaultValue: 'Search' })}</span>
        <kbd className="ms-auto hidden rounded border border-border/60 bg-background/60 px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground md:inline-flex">Ctrl K</kbd>
      </button>

      <div className="ms-auto flex shrink-0 items-center gap-2">
        <div className="hidden sm:block"><Language /></div>
        <div className="hidden sm:block"><ThemeToggle /></div>
        <div className="mg-topbar-user flex h-9 items-center gap-2 rounded-lg border px-2.5">
          <ShieldCheck className="h-4 w-4 text-primary" />
          <span className="hidden max-w-32 truncate text-xs font-medium sm:block">{admin?.username || 'Admin'}</span>
        </div>
      </div>
    </header>
  )
}
