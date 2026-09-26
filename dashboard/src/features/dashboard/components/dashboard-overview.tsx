import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import type { SystemUsersStats, SystemResourceStats } from '@/service/api'
import { formatBytes } from '@/utils/formatByte'
import { Activity, Cpu, HardDrive, MemoryStick, Server, Users, Wifi, Clock3 } from 'lucide-react'

type Props = {
  usersData?: SystemUsersStats
  resourceData?: SystemResourceStats
}

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

function ResourceBar({ label, value, detail, icon: Icon }: { label: string; value: number; detail: string; icon: typeof Cpu }) {
  const percentage = clamp(value)
  return (
    <div className="rounded-2xl border border-border/50 bg-background/30 p-4 backdrop-blur-md">
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2.5">
          <span className="flex h-8 w-8 items-center justify-center rounded-xl border border-border/50 bg-card/70 text-primary"><Icon className="h-4 w-4" /></span>
          <div className="min-w-0"><p className="truncate text-xs font-medium">{label}</p><p className="text-[10px] text-muted-foreground">{detail}</p></div>
        </div>
        <span className="text-sm font-semibold tabular-nums">{Math.round(percentage)}%</span>
      </div>
      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-muted/70"><div className="h-full rounded-full bg-primary shadow-[0_0_14px_hsl(var(--primary)/.45)] transition-all duration-700" style={{ width: `${percentage}%` }} /></div>
    </div>
  )
}

export default function DashboardOverview({ usersData, resourceData }: Props) {
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

  if (!usersData && !resourceData) {
    return <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">{Array.from({ length: 4 }).map((_, i) => <Card key={i} className="border-border/60 bg-card/55"><CardContent className="p-4"><Skeleton className="h-4 w-24" /><Skeleton className="mt-3 h-8 w-28" /></CardContent></Card>)}</div>
  }

  const cards = [
    { label: 'Online Users', value: onlineUsers.toLocaleString(), meta: `${activeUsers.toLocaleString()} active now`, icon: Wifi, accent: true },
    { label: 'Total Users', value: totalUsers.toLocaleString(), meta: `${disabledUsers.toLocaleString()} disabled · ${expiredUsers.toLocaleString()} expired`, icon: Users },
    { label: 'Network Traffic', value: formatBytes(traffic, 2), meta: 'Inbound + outbound', icon: Activity },
    { label: 'CPU Load', value: `${Math.round(cpu)}%`, meta: `${resourceData?.cpu_cores ?? '—'} CPU cores`, icon: Cpu },
  ]

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {cards.map(({ label, value, meta, icon: Icon, accent }) => (
          <Card key={label} className="group relative overflow-hidden border-border/60 bg-card/50 shadow-[0_14px_40px_hsl(0_0%_0%_/_0.16)] backdrop-blur-xl transition-all duration-300 hover:-translate-y-0.5 hover:border-primary/30 hover:bg-card/65">
            <CardContent className="relative p-4 sm:p-5">
              <div className="pointer-events-none absolute -right-12 -top-12 h-28 w-28 rounded-full bg-primary/8 blur-3xl transition-transform duration-500 group-hover:scale-125" />
              <div className="relative flex items-start justify-between gap-3">
                <div className="min-w-0"><p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground/75">{label}</p><p dir="ltr" className={`mt-2 truncate text-2xl font-semibold tracking-tight ${accent ? 'text-primary' : 'text-foreground'}`}>{value}</p><p className="mt-1 truncate text-[11px] text-muted-foreground/80">{meta}</p></div>
                <div className={`rounded-xl border p-2.5 ${accent ? 'border-primary/25 bg-primary/10 text-primary shadow-[0_0_22px_hsl(var(--primary)/.12)]' : 'border-border/60 bg-background/40 text-muted-foreground'}`}><Icon className="h-4 w-4" /></div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.45fr_.9fr]">
        <Card className="overflow-hidden border-border/60 bg-card/45 backdrop-blur-xl">
          <CardContent className="p-4 sm:p-5">
            <div className="mb-4 flex items-center justify-between gap-3"><div><p className="text-sm font-semibold">System Resources</p><p className="mt-0.5 text-xs text-muted-foreground">Live resource utilization</p></div><span className="inline-flex items-center gap-1.5 rounded-full border border-secondary/20 bg-secondary/8 px-2.5 py-1 text-[10px] font-medium text-secondary"><span className="h-1.5 w-1.5 animate-pulse rounded-full bg-secondary" /> Live</span></div>
            <div className="grid gap-3 sm:grid-cols-3">
              <ResourceBar label="CPU" value={cpu} detail={`${resourceData?.cpu_cores ?? '—'} cores`} icon={Cpu} />
              <ResourceBar label="Memory" value={memory} detail={resourceData?.mem_total ? `${formatBytes(Number(resourceData.mem_used), 1)} / ${formatBytes(Number(resourceData.mem_total), 1)}` : 'Unavailable'} icon={MemoryStick} />
              <ResourceBar label="Disk" value={disk} detail={resourceData?.disk_total ? `${formatBytes(Number(resourceData.disk_used), 1)} / ${formatBytes(Number(resourceData.disk_total), 1)}` : 'Unavailable'} icon={HardDrive} />
            </div>
          </CardContent>
        </Card>

        <Card className="border-border/60 bg-card/45 backdrop-blur-xl">
          <CardContent className="p-4 sm:p-5">
            <div className="mb-4 flex items-center gap-3"><span className="flex h-9 w-9 items-center justify-center rounded-xl border border-primary/20 bg-primary/10 text-primary"><Server className="h-4 w-4" /></span><div><p className="text-sm font-semibold">Platform Status</p><p className="text-xs text-muted-foreground">Core runtime information</p></div></div>
            <div className="grid grid-cols-2 gap-2.5">
              <div className="rounded-xl border border-border/50 bg-background/25 p-3"><p className="text-[10px] uppercase tracking-wider text-muted-foreground">Version</p><p dir="ltr" className="mt-1 text-sm font-semibold">{resourceData?.version || '—'}</p></div>
              <div className="rounded-xl border border-border/50 bg-background/25 p-3"><p className="text-[10px] uppercase tracking-wider text-muted-foreground">Uptime</p><p dir="ltr" className="mt-1 flex items-center gap-1.5 text-sm font-semibold"><Clock3 className="h-3.5 w-3.5 text-primary" />{formatUptime(resourceData?.uptime_seconds)}</p></div>
              <div className="col-span-2 rounded-xl border border-border/50 bg-background/25 p-3"><div className="flex items-center justify-between text-xs"><span className="text-muted-foreground">User capacity</span><span className="font-medium">{totalUsers.toLocaleString()} total</span></div><div className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted/60"><div className="h-full rounded-full bg-secondary/80" style={{ width: `${totalUsers ? clamp((activeUsers / totalUsers) * 100) : 0}%` }} /></div></div>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card className="border-border/60 bg-card/40 backdrop-blur-xl">
        <CardContent className="p-4 sm:p-5">
          <div className="mb-4 flex items-center justify-between"><div><p className="text-sm font-semibold">User State Overview</p><p className="text-xs text-muted-foreground">Current account distribution</p></div><span className="text-xs text-muted-foreground">{totalUsers.toLocaleString()} total</span></div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-6">
            {[['Active', activeUsers], ['Online', onlineUsers], ['On hold', onHoldUsers], ['Limited', limitedUsers], ['Expired', expiredUsers], ['Disabled', disabledUsers]].map(([label, value]) => (
              <div key={label as string} className="rounded-xl border border-border/45 bg-background/20 px-3 py-3"><p className="text-[10px] uppercase tracking-wider text-muted-foreground">{label as string}</p><p className="mt-1 text-lg font-semibold tabular-nums">{Number(value).toLocaleString()}</p></div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
