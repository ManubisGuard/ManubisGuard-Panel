import { useQuery } from '@tanstack/react-query'
import { Activity, ArrowDownToLine, ArrowUpFromLine, CircleAlert, Network, Radio, ShieldCheck, Waves } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { orvalFetcher } from '@/service/http'
import type { NodeRealtimeStats, SystemUsersStats } from '@/service/api'

type NetworkMetrics = { collected_at: string; source: string; available: boolean; unavailable_reason?: string | null; tcp_total?: number | null; tcp_established?: number | null; tcp_listen?: number | null; tcp_other?: number | null; udp_sockets?: number | null }
type Props = { selectedServer: string; nodeStats?: NodeRealtimeStats | null; usersStats?: SystemUsersStats }
const number = (value?: number | null) => value == null ? '—' : new Intl.NumberFormat().format(value)
const bytes = (value?: number | null) => { if (value == null) return '—'; const units = ['B/s', 'KB/s', 'MB/s', 'GB/s']; let n = Math.max(0, value), i = 0; while (n >= 1024 && i < units.length - 1) { n /= 1024; i++ } return `${n.toFixed(i ? 1 : 0)} ${units[i]}` }

export default function LiveNetworkIntelligence({ selectedServer, nodeStats, usersStats }: Props) {
  const { t, i18n } = useTranslation()
  const isMaster = selectedServer === 'master'
  const { data, isLoading, isError, dataUpdatedAt } = useQuery({ queryKey: ['system-network-intelligence'], queryFn: () => orvalFetcher<NetworkMetrics>('/api/system/network-intelligence'), enabled: isMaster, refetchInterval: isMaster ? 3000 : false, staleTime: 1000, retry: 1 })
  const time = (value: string | number) => new Date(value).toLocaleTimeString(i18n.resolvedLanguage || i18n.language)
  const updated = dataUpdatedAt ? time(dataUpdatedAt) : null
  const cards = isMaster ? [
    { key: 'tcpEstablished', value: number(data?.tcp_established), detail: t('mgUi.tcpEstablishedDetail'), icon: Network },
    { key: 'tcpListening', value: number(data?.tcp_listen), detail: t('mgUi.tcpTotal', { count: number(data?.tcp_total) }), icon: Radio },
    { key: 'udpSockets', value: number(data?.udp_sockets), detail: t('mgUi.udpDetail'), icon: Waves },
    { key: 'proxyOnline', value: number(usersStats?.online_users), detail: t('mgUi.proxyWindow'), icon: ShieldCheck },
  ] : [
    { key: 'incomingRate', value: bytes(nodeStats?.incoming_bandwidth_speed), detail: t('mgUi.nodeAgentTelemetry'), icon: ArrowDownToLine },
    { key: 'outgoingRate', value: bytes(nodeStats?.outgoing_bandwidth_speed), detail: t('mgUi.nodeAgentTelemetry'), icon: ArrowUpFromLine },
    { key: 'tcpNotExposed', value: t('mgUi.tcpNotExposed'), detail: t('mgUi.tcpNodeUnavailable'), icon: Network },
    { key: 'udpSockets', value: t('mgUi.tcpNotExposed'), detail: t('mgUi.udpNodeUnavailable'), icon: Waves },
  ]
  const status = isMaster && data?.available ? t('mgUi.live3s') : isMaster && isLoading ? t('mgUi.connecting') : isMaster && isError ? t('mgUi.unavailable') : t('mgUi.nodeTelemetry')
  return <section className="mg-live-network" aria-label={t('mgUi.networkIntelligence')}>
    <div className="mg-live-network-head"><div className="mg-live-network-title"><span className="mg-live-network-kicker"><Activity size={13} /> {t('mgUi.telemetry')} / {isMaster ? t('mgUi.networkMaster') : t('mgUi.networkNode', { id: selectedServer })}</span><h3>{t('mgUi.networkIntelligence')}</h3><p>{isMaster ? t('mgUi.networkTelemetry') : t('mgUi.nodeTelemetryDescription')}</p></div><div className="mg-live-network-status">{isMaster && data?.available ? <><i /> {status}</> : isMaster && isError ? <><CircleAlert size={13} /> {status}</> : status}</div></div>
    <div className="mg-live-network-grid">{cards.map(({ key, value, detail, icon: Icon }) => <article className="mg-live-network-card" key={key}><div className="mg-live-network-card-top"><span>{t(`mgUi.${key}`)}</span><Icon size={16} /></div><strong>{isMaster && !data?.available && ['tcpEstablished', 'tcpListening', 'udpSockets'].includes(key) ? t('mgUi.unavailable') : value}</strong><small>{detail}</small></article>)}</div>
    <div className="mg-live-network-foot"><span>{isMaster ? data?.available ? t('mgUi.source', { source: data.source }) : data?.unavailable_reason ? t('mgUi.collectionUnavailable', { reason: data.unavailable_reason }) : t('mgUi.awaitingSockets') : t('mgUi.nodeCountsNotEstimated')}</span><span>{updated ? t('mgUi.updated', { time: updated }) : data?.collected_at ? t('mgUi.collected', { time: time(data.collected_at) }) : t('mgUi.waitingSample')}</span></div>
    {isMaster && data?.available && <p className="mg-live-network-note">{t('mgUi.socketDisclaimer')}</p>}
  </section>
}
