import { UserCheck, UsersIcon } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { SystemUsersStats } from '@/service/api'

const UserStatisticsCard = ({ data }: { data: SystemUsersStats | undefined }) => {
  const { t } = useTranslation()
  const totalUsers = data?.total_user ?? 0
  const activeUsers = data?.active_users ?? 0
  const percentOfTotal = (value: number | undefined) => {
    if (!totalUsers || value === undefined || value <= 0) return null
    return Math.round((value / totalUsers) * 100)
  }
  const percentOfActive = (value: number | undefined) => {
    if (!activeUsers || value === undefined || value <= 0) return null
    return Math.round((value / activeUsers) * 100)
  }

  return (
    <Card className="mg-cyber-card mg-users-statistics overflow-hidden rounded-xl">
      <CardHeader className="p-3.5 pb-2 sm:p-4 sm:pb-2">
        <CardTitle className="truncate text-sm font-semibold">{t('statistics.users')}</CardTitle>
        <CardDescription className="truncate text-xs">{t('monitorUsers')}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-2 p-3.5 pt-1 sm:p-4 sm:pt-1">
        <div className="mg-user-stat-row flex min-w-0 flex-row items-center gap-2 rounded-lg border px-3 py-2.5 md:gap-3">
          <UsersIcon className="mg-user-stat-icon size-4 shrink-0 md:size-4" />
          <span className="truncate text-sm md:text-base">{t('statistics.users')}</span>
          <span className="ms-auto text-sm font-bold md:text-base">{totalUsers}</span>
        </div>
        <div className="mg-user-stat-row flex min-w-0 flex-row items-center gap-2 rounded-lg border px-3 py-2.5 md:gap-3">
          <UserCheck className="mg-user-stat-icon size-4 shrink-0 md:size-4" />
          <span className="truncate text-sm md:text-base">{t('statistics.activeUsers')}</span>
          <div className="ms-auto flex items-center gap-2">
            {percentOfTotal(data?.active_users) !== null && (
              <Badge variant="secondary" className="mg-user-stat-percent text-[10px]">
                {percentOfTotal(data?.active_users)}%
              </Badge>
            )}
            <span className="mg-user-stat-value text-sm font-semibold">{data?.active_users || 0}</span>
          </div>
        </div>
        <div className="mg-user-stat-row flex min-w-0 flex-row items-center gap-2 rounded-lg border px-3 py-2.5 md:gap-3">
          <div className="mg-user-status-dot mg-tone-green size-2 shrink-0 md:size-2" />
          <span className="truncate text-sm md:text-base">{t('statistics.onlineUsers')}</span>
          <div className="ms-auto flex items-center gap-2">
            {percentOfActive(data?.online_users) !== null && (
              <Badge variant="secondary" className="mg-user-stat-percent text-[10px]">
                {percentOfActive(data?.online_users)}%
              </Badge>
            )}
            <span className="mg-user-stat-value text-sm font-semibold">{data?.online_users || 0}</span>
          </div>
        </div>
        <div className="mg-user-stat-row flex min-w-0 flex-row items-center gap-2 rounded-lg border px-3 py-2.5 md:gap-3">
          <div className="mg-user-status-dot mg-tone-orange size-2 shrink-0 md:size-2" />
          <span className="truncate text-sm md:text-base">{t('statistics.expiredUsers')}</span>
          <div className="ms-auto flex items-center gap-2">
            {percentOfTotal(data?.expired_users) !== null && (
              <Badge variant="secondary" className="mg-user-stat-percent text-[10px]">
                {percentOfTotal(data?.expired_users)}%
              </Badge>
            )}
            <span className="mg-user-stat-value text-sm font-semibold">{data?.expired_users || 0}</span>
          </div>
        </div>
        <div className="mg-user-stat-row flex min-w-0 flex-row items-center gap-2 rounded-lg border px-3 py-2.5 md:gap-3">
          <div className="mg-user-status-dot mg-tone-red size-2 shrink-0 md:size-2" />
          <span className="truncate text-sm md:text-base">{t('statistics.limitedUsers')}</span>
          <div className="ms-auto flex items-center gap-2">
            {percentOfTotal(data?.limited_users) !== null && (
              <Badge variant="secondary" className="mg-user-stat-percent text-[10px]">
                {percentOfTotal(data?.limited_users)}%
              </Badge>
            )}
            <span className="mg-user-stat-value text-sm font-semibold">{data?.limited_users || 0}</span>
          </div>
        </div>
        <div className="mg-user-stat-row flex min-w-0 flex-row items-center gap-2 rounded-lg border px-3 py-2.5 md:gap-3">
          <div className="mg-user-status-dot mg-tone-purple size-2 shrink-0 md:size-2" />
          <span className="truncate text-sm md:text-base">{t('statistics.onHoldUsers')}</span>
          <div className="ms-auto flex items-center gap-2">
            {percentOfTotal(data?.on_hold_users) !== null && (
              <Badge variant="secondary" className="mg-user-stat-percent text-[10px]">
                {percentOfTotal(data?.on_hold_users)}%
              </Badge>
            )}
            <span className="mg-user-stat-value text-sm font-semibold">{data?.on_hold_users || 0}</span>
          </div>
        </div>
        <div className="mg-user-stat-row flex min-w-0 flex-row items-center gap-2 rounded-lg border px-3 py-2.5 md:gap-3">
          <div className="mg-user-status-dot mg-tone-slate size-2 shrink-0 md:size-2" />
          <span className="truncate text-sm md:text-base">{t('statistics.disabledUsers')}</span>
          <div className="ms-auto flex items-center gap-2">
            {percentOfTotal(data?.disabled_users) !== null && (
              <Badge variant="secondary" className="mg-user-stat-percent text-[10px]">
                {percentOfTotal(data?.disabled_users)}%
              </Badge>
            )}
            <span className="mg-user-stat-value text-sm font-semibold">{data?.disabled_users || 0}</span>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

export default UserStatisticsCard
