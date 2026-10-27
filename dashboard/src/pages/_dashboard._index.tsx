import AdminStatisticsCard from '@/features/dashboard/components/admin-statistics-card'
import DashboardOverview from '@/features/dashboard/components/dashboard-overview'
import WorkersHealthCard from '@/features/dashboard/components/workers-health-card'
import AdminFilterCombobox from '@/components/common/admin-filter-combobox'
import { useCommandPaletteStore } from '@/hooks/use-command-palette-store'
import { useAdmin } from '@/hooks/use-admin'
import { useClipboard } from '@/hooks/use-clipboard'
import type { AdminDetails, UserResponse } from '@/service/api'
import { useGetSystemResourceStats, useGetSystemUsersStats } from '@/service/api'
import { ArrowUpRight, Bookmark, Plus, Server, Users, Layers, ShieldCheck, Activity } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Link } from 'react-router'
import { lazy, Suspense, useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import PageHeader from '@/components/layout/page-header'
import { type UseEditFormValues, type UseFormValues, getDefaultUserForm } from '@/features/users/forms/user-form'
import { hasPermission, hasScopeAll } from '@/utils/rbac'
import { useQueryClient } from '@tanstack/react-query'

type DashboardAdmin = Pick<AdminDetails, 'id' | 'username'>

// The user editor pulls in advanced usage charts and editors. Load it only when requested.
const UserModal = lazy(() => import('@/features/users/dialogs/user-modal'))

const totalAdmin: DashboardAdmin = {
  username: 'Total',
}

const Dashboard = () => {
  const [isUserModalOpen, setUserModalOpen] = useState(false)
  const setCommandPaletteOpen = useCommandPaletteStore(s => s.setOpen)
  const { admin: currentAdmin } = useAdmin()
  const canReadAllUsers = hasScopeAll(currentAdmin, 'users', 'read')
  const canCreateUsers = hasPermission(currentAdmin, 'users', 'create')
  const canReadNodeStats = hasPermission(currentAdmin, 'nodes', 'stats')
  const { t } = useTranslation()

  const [selectedAdmin, setSelectedAdmin] = useState<DashboardAdmin | undefined>(totalAdmin)

  const userForm = useForm<UseFormValues | UseEditFormValues>({
    defaultValues: getDefaultUserForm,
  })

  const queryClient = useQueryClient()
  const { copy } = useClipboard()

  const refreshAllUserData = () => {
    queryClient.invalidateQueries({ queryKey: ['getUsers'] })
    queryClient.invalidateQueries({ queryKey: ['getUsersUsage'] })
    queryClient.invalidateQueries({ queryKey: ['/api/users/'] })
  }

  const handleCreateUserSuccess = async (user: UserResponse) => {
    if (user.subscription_url) {
      const subURL = user.subscription_url.startsWith('/') ? window.location.origin + user.subscription_url : user.subscription_url
      await copy(subURL)
      toast.success(t('userSettings.subscriptionUrlCopied'))
    }
    refreshAllUserData()
  }

  const handleCreateUser = () => {
    if (!canCreateUsers) return
    userForm.reset()
    setUserModalOpen(true)
  }

  const handleOpenQuickActions = () => {
    setCommandPaletteOpen(true)
  }

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'n' && (event.metaKey || event.ctrlKey)) {
        event.preventDefault()
        handleCreateUser()
      }
      if (event.key === 'r' && (event.metaKey || event.ctrlKey)) {
        event.preventDefault()
        refreshAllUserData()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  const systemUsersStatsParams = canReadAllUsers && selectedAdmin && selectedAdmin.username !== 'Total' ? { admin_username: selectedAdmin.username } : undefined

  const { data: systemResourceStatsData } = useGetSystemResourceStats({
    query: {
      refetchInterval: 15_000,
    },
  })

  const { data: systemUsersStatsData } = useGetSystemUsersStats(systemUsersStatsParams, {
    query: {
      refetchInterval: 15_000,
    },
  })

  return (
    <div className="flex w-full flex-col items-start">
      <div className="mg-dashboard-hero w-full">
        <div className="mg-dashboard-heading-wrap">
          <PageHeader title="dashboard" description="dashboardDescription" buttonIcon={Bookmark} buttonText="quickActions.title" onButtonClick={handleOpenQuickActions} className="mg-dashboard-page-header" />
          <div className="mg-network-banner" aria-label={t('mgUi.networkConsole')}>
            <div className="mg-network-art" aria-hidden="true"><span /><span /><span /><span /><i /><i /><i /></div>
            <div className="mg-network-copy"><span className="mg-eyebrow">{t('mgUi.yourNetwork')}</span><strong>{t('mgUi.brandTagline')}</strong><span className="mg-network-sub"><Activity className="h-3.5 w-3.5" /> {t('mgUi.securityConsole')}</span></div>
            <div className="mg-network-mark"><ShieldCheck className="h-5 w-5" /></div>
          </div>
        </div>
        <div className="mg-command-row">
          <div className="mr-auto flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground"><span className="mg-command-dot" /> {t('mgUi.commandCenter')}</div>
          {canCreateUsers && <Button asChild size="sm" className="mg-primary-action h-8 rounded-lg px-3"><Link to="/users"><Plus className="mr-1.5 h-3.5 w-3.5" />{t('mgUi.createUser')}<ArrowUpRight className="ml-1.5 h-3 w-3" /></Link></Button>}
          {canReadNodeStats && <Button asChild variant="outline" size="sm" className="mg-secondary-action h-8 rounded-lg px-3"><Link to="/nodes"><Server className="mr-1.5 h-3.5 w-3.5" />{t('mgUi.nodes')}</Link></Button>}
          {hasPermission(currentAdmin, 'users', 'read') && <Button asChild variant="outline" size="sm" className="mg-secondary-action h-8 rounded-lg px-3"><Link to="/users"><Users className="mr-1.5 h-3.5 w-3.5" />{t('mgUi.users')}</Link></Button>}
          {hasPermission(currentAdmin, 'groups', 'read') && <Button asChild variant="outline" size="sm" className="mg-secondary-action h-8 rounded-lg px-3"><Link to="/groups"><Layers className="mr-1.5 h-3.5 w-3.5" />{t('mgUi.groups')}</Link></Button>}
        </div>
      </div>

      <div className="mg-dashboard-main relative w-full px-3 py-4 sm:px-5 lg:px-6 lg:py-5">
        <div className="mx-auto flex max-w-[1680px] flex-col gap-4">
          <DashboardOverview resourceData={systemResourceStatsData} usersData={systemUsersStatsData} />
          {canReadNodeStats && <WorkersHealthCard />}
          <div className="h-px bg-border/50" />
          {canReadAllUsers ? (
            <>
              <AdminFilterCombobox
                value={selectedAdmin?.username === 'Total' ? 'all' : (selectedAdmin?.username ?? 'all')}
                onValueChange={username => {
                  if (username === 'all') {
                    setSelectedAdmin(totalAdmin)
                    return
                  }
                  if (currentAdmin?.username === username) {
                    setSelectedAdmin(currentAdmin)
                    return
                  }
                  setSelectedAdmin(prev => (prev?.username === username ? prev : { username }))
                }}
                onAdminSelect={admin => {
                  if (!admin) return
                  setSelectedAdmin(admin)
                }}
                className="relative mb-3 w-full max-w-xs sm:mb-4 sm:max-w-sm lg:max-w-md"
              />
              <div className="flex flex-col gap-3 sm:gap-4">
                {selectedAdmin && <AdminStatisticsCard key={selectedAdmin.username} admin={selectedAdmin} systemStats={systemUsersStatsData} currentAdmin={currentAdmin} skipStatsFetch />}
              </div>
            </>
          ) : (
            <AdminStatisticsCard showAdminInfo={false} admin={currentAdmin} systemStats={systemUsersStatsData} currentAdmin={currentAdmin} skipStatsFetch />
          )}
        </div>
      </div>

      {isUserModalOpen && (
        <Suspense fallback={null}>
          <UserModal isDialogOpen={isUserModalOpen} onOpenChange={setUserModalOpen} form={userForm} editingUser={false} onSuccessCallback={handleCreateUserSuccess} />
        </Suspense>
      )}
    </div>
  )
}

export default Dashboard
