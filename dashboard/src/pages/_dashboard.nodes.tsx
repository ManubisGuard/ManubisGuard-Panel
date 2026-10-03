import PageHeader from '@/components/layout/page-header'
import { cn } from '@/lib/utils'
import { Cpu, Logs, Network, Share2Icon } from 'lucide-react'
import { useAdmin } from '@/hooks/use-admin'
import { hasPermission, canReadResourcePage } from '@/utils/rbac'
import { useLocation, useNavigate, Outlet } from 'react-router'
import { useTranslation } from 'react-i18next'

export default function NodesLayout() {
  const { admin } = useAdmin()
  const { t } = useTranslation()
  const location = useLocation()
  const navigate = useNavigate()
  const canReadNodes = canReadResourcePage(admin, 'nodes')
  const canReadCores = canReadResourcePage(admin, 'cores')
  const canReadNodeLogs = hasPermission(admin, 'nodes', 'logs')
  const canReadWireGuard = canReadCores
  const canCreateNodes = hasPermission(admin, 'nodes', 'create')
  const canCreateCores = hasPermission(admin, 'cores', 'create')

  const tabs = [
    ...(canReadNodes ? [{ id: 'nodes', label: t('navigation.nodeCore'), icon: Share2Icon, url: '/nodes' }] : []),
    ...(canReadCores ? [{ id: 'cores', label: t('settings.cores.title'), icon: Cpu, url: '/nodes/cores' }] : []),
    ...(canReadWireGuard ? [{ id: 'wireguard', label: t('nodes.wireguard.title'), icon: Network, url: '/nodes/wireguard' }] : []),
    ...(canReadNodeLogs ? [{ id: 'logs', label: t('nodes.logs.title'), icon: Logs, url: '/nodes/logs' }] : []),
  ]

  const activeTab = tabs.find(tab => location.pathname === tab.url || (tab.id === 'cores' && location.pathname.startsWith('/nodes/cores/')))?.id || 'nodes'
  const activeLabel = tabs.find(tab => tab.id === activeTab)?.label || t('nodes.title')
  const canCreateActiveResource = activeTab === 'nodes' ? canCreateNodes : activeTab === 'cores' ? canCreateCores : false

  return (
    <div className="flex w-full min-w-0 flex-col gap-0">
      <PageHeader
        title={activeLabel}
        description="manageNodes"
        buttonIcon={activeTab === 'nodes' && canCreateNodes ? Share2Icon : activeTab === 'cores' && canCreateCores ? Cpu : undefined}
        buttonText={activeTab === 'nodes' && canCreateNodes ? 'nodes.addNode' : activeTab === 'cores' && canCreateCores ? 'navigation.addCore' : undefined}
        onButtonClick={
          canCreateActiveResource
            ? () => window.dispatchEvent(new Event(activeTab === 'nodes' ? 'openNodeDialog' : 'openCoreDialog'))
            : undefined
        }
      />
      <div className="scrollbar-hide flex w-full overflow-x-auto border-b px-4 lg:flex-wrap">
        {tabs.map(tab => {
          const isActive = activeTab === tab.id
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => navigate(tab.url)}
              className={cn(
                'relative flex shrink-0 items-center gap-2 px-3 py-2.5 text-sm font-medium whitespace-nowrap transition-colors',
                isActive ? 'border-primary text-foreground border-b-2' : 'text-muted-foreground hover:text-foreground',
              )}
            >
              <tab.icon className="h-4 w-4" />
              <span>{tab.label}</span>
            </button>
          )
        })}
      </div>
      <div className="min-w-0 p-1 sm:p-2">
        <Outlet />
      </div>
    </div>
  )
}
