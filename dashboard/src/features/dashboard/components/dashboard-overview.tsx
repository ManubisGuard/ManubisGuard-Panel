import type { ReactNode } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import type { SystemUsersStats, SystemResourceStats } from '@/service/api'
import { formatBytes } from '@/utils/formatByte'
import { useTranslation } from 'react-i18next'
import { Activity, Cpu, HardDrive, MemoryStick, Server, Users, Wifi, Clock3, ShieldCheck, Gauge } from 'lucide-react'

type Props = { usersData?: SystemUsersStats; resourceData?: SystemResourceStats }
const clamp = (value: number) => Math.max(0, Math.min(100, value))

function formatUptime(seconds = 0) {
  const total = Math.max(0, Math.floor(seconds))
  const days = Math.floor(total / 86400)
  const hours = Math.floor((total % 86400) / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  if (days) return `${days}d ${hours}h ${minutes}m`
  if (hours) return `${hours}h ${minutes}m`
  return `${minutes}m`
}

function SectionTitle({ icon: Icon, title, subtitle, right }: { icon: typeof Cpu; title: string; subtitle?: string; right?: ReactNode }) {
  return <div className="mg-section-heading"><span className="mg-section-icon"><Icon className="h-4 w-4" /></span><div className="min-w-0 flex-1"><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div>{right}</div>
}

function ResourceCard({ label, value, detail, icon: Icon, used, total }: { label: string; value: number; detail: string; icon: typeof Cpu; used?: number; total?: number }) {
  const { t } = useTranslation()
  const percentage = clamp(value)
  return <div className="mg-resource-card"><div className="mg-resource-card-top"><span className="mg-metric-icon"><Icon className="h-4 w-4" /><i /></span><div className="min-w-0 flex-1"><p className="mg-metric-label">{label}</p><p className="mg-metric-detail">{detail}</p></div><strong className="mg-resource-percent" dir="ltr">{Math.round(percentage)}<small>%</small></strong></div><div className="mg-resource-meter" role="progressbar" aria-label={t('mgUi.resourceUtilization', { label })} aria-valuenow={Math.round(percentage)} aria-valuemin={0} aria-valuemax={100}><div className="mg-resource-meter-fill" style={{ width: `${percentage}%` }} /><span className="mg-resource-meter-ticks" /></div>{used != null && total != null && <div className="mg-resource-foot" dir="ltr"><span>{t('mgUi.used')} {formatBytes(used, 1)}</span><span>{t('mgUi.capacity')} {formatBytes(total, 1)}</span></div>}<div className="mg-resource-card-index"><span>{t('mgUi.monitorNode')}</span><b>{label === "CPU" ? "01" : label === "Memory" ? "02" : "03"}</b></div></div>
}

export default function DashboardOverview({ usersData, resourceData }: Props) {
  const { t } = useTranslation()
  const totalUsers = Number(usersData?.total_user) || 0
  const activeUsers = Number(usersData?.active_users) || 0
  const onlineUsers = Number(usersData?.online_users) || 0
  const expiredUsers = Number(usersData?.expired_users) || 0
  const disabledUsers = Number(usersData?.disabled_users) || 0
  const limitedUsers = Number(usersData?.limited_users) || 0
  const onHoldUsers = Number(usersData?.on_hold_users) || 0
  const traffic = (Number(usersData?.incoming_bandwidth) || 0) + (Number(usersData?.outgoing_bandwidth) || 0)
  const memory = resourceData?.mem_total ? (Number(resourceData.mem_used) / Number(resourceData.mem_total)) * 100 : 0
  const disk = resourceData?.disk_total ? (Number(resourceData.disk_used) / Number(resourceData.disk_total)) * 100 : 0
  const cpu = Number(resourceData?.cpu_usage) || 0

  if (!usersData && !resourceData) return <div className="grid grid-cols-2 gap-2 xl:grid-cols-4">{Array.from({ length: 4 }).map((_, i) => <Card key={i} className="mg-cyber-card"><CardContent className="p-4"><Skeleton className="h-4 w-24" /><Skeleton className="mt-3 h-8 w-28" /></CardContent></Card>)}</div>

  const cards = [
    { label: t('mgUi.onlineUsers'), value: onlineUsers.toLocaleString(), meta: t('mgUi.activeNow', { count: activeUsers.toLocaleString() }), icon: Wifi, accent: true },
    { label: t('mgUi.totalUsers'), value: totalUsers.toLocaleString(), meta: t('mgUi.disabledExpired', { disabled: disabledUsers.toLocaleString(), expired: expiredUsers.toLocaleString() }), icon: Users },
    { label: t('mgUi.networkTraffic'), value: formatBytes(traffic, 2), meta: t('mgUi.inboundOutbound'), icon: Activity },
    { label: t('mgUi.cpuLoad'), value: `${Math.round(cpu)}%`, meta: t('mgUi.cpuCores', { count: resourceData?.cpu_cores ?? '—' }), icon: Cpu },
  ]
  const states = [
    { label: t('mgUi.active'), value: activeUsers, tone: 'green' }, { label: t('mgUi.online'), value: onlineUsers, tone: 'cyan' },
    { label: t('mgUi.onHold'), value: onHoldUsers, tone: 'amber' }, { label: t('mgUi.limited'), value: limitedUsers, tone: 'orange' },
    { label: t('mgUi.expired'), value: expiredUsers, tone: 'red' }, { label: t('mgUi.disabled'), value: disabledUsers, tone: 'slate' },
  ]

  return <div className="mg-dashboard-content space-y-3 sm:space-y-4">
    <div className="grid grid-cols-2 gap-2.5 xl:grid-cols-4 xl:gap-3">
      {cards.map(({ label, value, meta, icon: Icon, accent }) => <Card key={label} className={`mg-cyber-card mg-kpi-card ${accent ? 'mg-kpi-primary' : ''}`}><CardContent className="p-3.5 sm:p-4"><div className="flex items-start justify-between gap-2.5"><div className="min-w-0"><p className="mg-eyebrow">{label}</p><p dir="ltr" className="mg-kpi-value">{value}</p><p className="mg-kpi-meta">{meta}</p></div><span className="mg-kpi-icon"><Icon className="h-4 w-4" /></span></div></CardContent></Card>)}
    </div>

    <div className="grid gap-3 xl:grid-cols-[1.45fr_1fr]">
      <Card className="mg-cyber-card mg-resource-console overflow-hidden"><CardContent className="relative p-3.5 sm:p-4"><div className="mg-resource-console-grid" aria-hidden="true" /><div className="mg-resource-console-head"><div className="mg-resource-console-title"><span className="mg-resource-console-emblem"><Gauge className="h-4 w-4" /><i /></span><div className="min-w-0"><div className="mg-resource-kicker"><span>SYS.MON / 01</span><span className="mg-resource-kicker-line" /></div><h2>{t('mgUi.systemResources')}</h2><p>{t('mgUi.liveResourceUtilization')} <span>·</span> {t('mgUi.telemetryStream')}</p></div></div><div className="mg-resource-console-status"><span className="mg-resource-status-dot" /><span>{t('mgUi.liveStatus')}</span><strong>{t('mgUi.active')}</strong></div></div><div className="mg-resource-terminal-strip"><span><i /> {t('mgUi.resourceMonitor')}</span><span>CPU / MEM / DISK</span><span>{t('mgUi.telemetryStream')}: <b>{t('mgUi.connected')}</b></span></div><div className="relative mt-3 grid grid-cols-1 gap-2.5 sm:grid-cols-3"><ResourceCard label="CPU" value={cpu} detail={t('mgUi.coresCount', { count: resourceData?.cpu_cores ?? '—' })} icon={Cpu} /><ResourceCard label="Memory" value={memory} detail={t('mgUi.ramUtilization')} used={Number(resourceData?.mem_used) || 0} total={Number(resourceData?.mem_total) || 0} icon={MemoryStick} /><ResourceCard label="Disk" value={disk} detail={t('mgUi.storageUtilization')} used={Number(resourceData?.disk_used) || 0} total={Number(resourceData?.disk_total) || 0} icon={HardDrive} /></div><div className="mg-resource-console-foot"><span>MANUBIS // {t('mgUi.resourceMonitor')}</span><span><i /> {t('mgUi.connected')}</span></div></CardContent></Card>
      <Card className="mg-cyber-card overflow-hidden"><CardContent className="p-3.5 sm:p-4"><SectionTitle icon={Server} title={t('mgUi.platformStatus')} subtitle={t('mgUi.coreRuntime')} right={<span className="mg-live-pill"><span /> {t('mgUi.liveStatus')}</span>} /><div className="mt-4 grid grid-cols-2 gap-2"><div className="mg-platform-stat"><span>{t('mgUi.version')}</span><strong dir="ltr">{resourceData?.version || '—'}</strong></div><div className="mg-platform-stat"><span>{t('mgUi.uptime')}</span><strong dir="ltr"><Clock3 className="h-3.5 w-3.5" />{formatUptime(resourceData?.uptime_seconds)}</strong></div><div className="mg-platform-capacity"><div className="flex items-center justify-between gap-2 text-xs"><span>{t('mgUi.userCapacity')}</span><strong>{t('mgUi.total', { count: totalUsers.toLocaleString() })}</strong></div><div className="mg-progress-track mt-2"><div className="mg-progress-fill" style={{ width: `${totalUsers ? clamp((activeUsers / totalUsers) * 100) : 0}%` }} /></div></div></div></CardContent></Card>
    </div>

    <Card className="mg-cyber-card"><CardContent className="p-3.5 sm:p-4"><SectionTitle icon={ShieldCheck} title={t('mgUi.userStateOverview')} subtitle={t('mgUi.currentAccountDistribution')} right={<span className="mg-muted-total">{t('mgUi.total', { count: totalUsers.toLocaleString() })}</span>} /><div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-6">{states.map(({ label, value, tone }) => <div key={label} className="mg-state-card"><span className={`mg-state-dot mg-tone-${tone}`} /><div className="min-w-0"><p>{label}</p><strong>{value.toLocaleString()}</strong></div></div>)}</div></CardContent></Card>
  </div>
}
