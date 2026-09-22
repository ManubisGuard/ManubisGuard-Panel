import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import type { SystemUsersStats, SystemResourceStats } from '@/service/api'
import { formatBytes } from '@/utils/formatByte'
import { Activity, HardDrive, MemoryStick, Users, Wifi } from 'lucide-react'

type Props = {
  usersData?: SystemUsersStats
  resourceData?: SystemResourceStats
}

export default function DashboardOverview({ usersData, resourceData }: Props) {
  const totalUsers = Number(usersData?.total_user) || 0
  const activeUsers = Number(usersData?.active_users) || 0
  const onlineUsers = Number(usersData?.online_users) || 0
  const traffic = (Number(usersData?.incoming_bandwidth) || 0) + (Number(usersData?.outgoing_bandwidth) || 0)
  const memory = resourceData?.mem_total ? (Number(resourceData.mem_used) / Number(resourceData.mem_total)) * 100 : 0
  const disk = resourceData?.disk_total ? (Number(resourceData.disk_used) / Number(resourceData.disk_total)) * 100 : 0

  const items = [
    { label: 'Online Users', value: onlineUsers, meta: `${activeUsers} active`, icon: Wifi, accent: true },
    { label: 'Total Users', value: totalUsers, meta: `${activeUsers} active`, icon: Users },
    { label: 'Traffic', value: formatBytes(traffic, 2), meta: 'Inbound + outbound', icon: Activity },
    { label: 'System Load', value: `${Math.round(Number(resourceData?.cpu_usage) || 0)}%`, meta: `RAM ${Math.round(memory)}% · Disk ${Math.round(disk)}%`, icon: HardDrive },
  ]

  if (!usersData && !resourceData) {
    return <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">{items.map((_, i) => <Card key={i} className="border-border/60 bg-card/55"><CardContent className="p-4"><Skeleton className="h-4 w-24" /><Skeleton className="mt-3 h-8 w-28" /></CardContent></Card>)}</div>
  }

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {items.map(({ label, value, meta, icon: Icon, accent }) => (
        <Card key={label} className="group overflow-hidden border-border/60 bg-card/55 transition-colors hover:border-primary/25 hover:bg-card/70">
          <CardContent className="relative p-4 sm:p-5">
            <div className="pointer-events-none absolute -right-10 -top-10 h-24 w-24 rounded-full bg-primary/5 blur-2xl transition-opacity group-hover:opacity-100" />
            <div className="relative flex items-start justify-between gap-3">
              <div>
                <p className="text-xs font-medium text-muted-foreground">{label}</p>
                <p dir="ltr" className={`mt-2 text-2xl font-semibold tracking-tight ${accent ? 'text-primary' : 'text-foreground'}`}>{value}</p>
                <p className="mt-1 text-[11px] text-muted-foreground/80">{meta}</p>
              </div>
              <div className={`rounded-lg border p-2 ${accent ? 'border-primary/20 bg-primary/10 text-primary' : 'border-border/60 bg-background/40 text-muted-foreground'}`}>
                <Icon className="h-4 w-4" />
              </div>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
