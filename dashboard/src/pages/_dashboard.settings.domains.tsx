import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { useGetGeneralSettings, useGetNodesSimple, useInspectDomainCertificate, useInspectDomainIntelligence, type ManagedServerAddress as ApiManagedServerAddress } from '@/service/api'
import { useDeployManagedCertificates, useInstallExistingCertificate, useIssueManagedCertificate, type ManagedDomainLifecycle as ApiManagedDomain } from '@/service/domainCertificates'
import { CheckCircle2, Clock3, Globe2, Plus, RefreshCcw, ShieldCheck, Trash2, UploadCloud } from 'lucide-react'
import { toast } from 'sonner'
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useSettingsContext } from './_dashboard.settings'

const protocolOptions = ['Xray', 'Reality', 'AmneziaWG', 'Shadowsocks', 'TUIC', 'Hysteria2', 'NaiveProxy', 'sing-box']

const newId = () => crypto.randomUUID()

const normalizeDomain = (value: string) => value.trim().toLowerCase()

type CertificateJob = {
  domainId: string
  domain: string
  status: 'running' | 'succeeded' | 'failed'
  startedAt: string
  lastAttemptAt: string
  error?: string
}

const emptyDomain = (): ApiManagedDomain => ({
  id: newId(),
  domain: '',
  node_id: null,
  certificate_method: 'letsencrypt',
  address_mode: 'additional',
  protocols: ['Xray', 'Reality'],
  email: '',
  auto_renew: true,
  serve_tls: true,
  status: 'pending',
  certificate_expires_at: null,
  last_checked_at: null,
})

export default function DomainsSettings() {
  const { data: generalSettings, isLoading } = useGetGeneralSettings()
  const { data: nodesResponse } = useGetNodesSimple()
  const inspectMutation = useInspectDomainIntelligence()
  const certificateMutation = useInspectDomainCertificate()
  const [intelligence, setIntelligence] = useState<Record<string, any>>({})
  const [certificates, setCertificates] = useState<Record<string, any>>({})
  const [certificateJobs, setCertificateJobs] = useState<Record<string, CertificateJob>>({})
  const nodes = ((nodesResponse as any)?.data?.nodes ?? (nodesResponse as any)?.nodes ?? []) as Array<{ id: number; name: string }>

  const general = ((generalSettings as any)?.data ?? generalSettings ?? {}) as {
    default_method?: unknown
    custom_variables?: unknown
    reality_sni_pool?: string[]
    domains?: ApiManagedDomain[]
    primary_domain?: ApiManagedDomain | null
    server_addresses?: ApiManagedServerAddress[]
  }
  const storedDomains = general.domains ?? []
  const storedPrimary = general.primary_domain ?? null
  const storedAddresses = general.server_addresses ?? []

  const { updateSettings } = useSettingsContext()
  const syncingRef = useRef(false)
  const dirtyRef = useRef(false)
  const [primary, setPrimary] = useState<ApiManagedDomain | null>(storedPrimary)
  const [domains, setDomains] = useState<ApiManagedDomain[]>(storedDomains)
  const [addresses, setAddresses] = useState<ApiManagedServerAddress[]>(storedAddresses)

  useEffect(() => {
    syncingRef.current = true
    dirtyRef.current = false
    setPrimary(storedPrimary)
    setDomains(storedDomains)
    setAddresses(storedAddresses)
  }, [
    (generalSettings as any)?.data?.domains,
    (generalSettings as any)?.data?.primary_domain,
    (generalSettings as any)?.data?.server_addresses,
    (generalSettings as any)?.domains,
    (generalSettings as any)?.primary_domain,
    (generalSettings as any)?.server_addresses,
  ])

  const nodeName = useMemo(() => new Map(nodes.map(node => [node.id, node.name])), [nodes])
  useEffect(() => {
    if (syncingRef.current) {
      syncingRef.current = false
      return
    }
    if (!dirtyRef.current) return
    const timer = window.setTimeout(() => {
      const cleanDomains = domains.map(item => ({ ...item, domain: normalizeDomain(item.domain) })).filter(item => item.domain)
      const cleanPrimary = primary?.domain ? { ...primary, domain: normalizeDomain(primary.domain) } : null
      updateSettings({
        default_method: general.default_method,
        custom_variables: general.custom_variables,
        reality_sni_pool: general.reality_sni_pool,
        domains: cleanDomains,
        primary_domain: cleanPrimary,
        server_addresses: addresses.filter(item => item.address.trim()).map(item => ({ ...item, address: item.address.trim() })),
      }).then(() => {
        dirtyRef.current = false
      }).catch(() => {
        dirtyRef.current = true
      })
    }, 500)
    return () => window.clearTimeout(timer)
  }, [addresses, domains, general.custom_variables, general.default_method, general.reality_sni_pool, primary, updateSettings])

  const markDirty = () => {
    dirtyRef.current = true
  }
  const addDomain = () => setDomains(current => [...current, emptyDomain()])
  const updateDomain = (id: string, patch: Partial<ApiManagedDomain>) => {
    markDirty()
    setDomains(current => current.map(item => (item.id === id ? { ...item, ...patch } : item)))
  }
  const removeDomain = (id: string) => {
    markDirty()
    setDomains(current => current.filter(item => item.id !== id))
  }
  const addAddress = () => {
    markDirty()
    setAddresses(current => [...current, { id: newId(), node_id: null, address: '', enabled: true }])
  }

  if (isLoading) return <div className="text-muted-foreground w-full p-6 text-sm">Loading Domains & SSL…</div>

  return (
    <div className="w-full space-y-6 p-4 sm:p-6 lg:p-8">
      <section className="border-border/60 bg-card/40 rounded-2xl border p-5 shadow-sm">
        <div className="mb-5 flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-lg font-semibold">
              <ShieldCheck className="text-primary size-5" />
              Primary domain
            </div>
            <p className="text-muted-foreground mt-1 text-sm">The main public domain used by your panel and subscriptions.</p>
          </div>
          <Button variant="outline" size="sm" onClick={() => {
            if (primary) {
              markDirty()
              setPrimary(null)
            } else {
              setPrimary(emptyDomain())
            }
          }}>
            {primary ? 'Remove' : 'Add primary domain'}
          </Button>
        </div>
        {primary && (
          <>
            <div className="grid gap-4 md:grid-cols-2">
              <Field label="Domain">
                <Input value={primary.domain} onChange={e => {
                  markDirty()
                  setPrimary({ ...primary, domain: e.target.value })
                }} placeholder="panel.example.com" />
              </Field>
              <Field label="Node">
                <NodeSelect value={primary.node_id} nodes={nodes} onChange={node_id => {
                  markDirty()
                  setPrimary({ ...primary, node_id })
                }} />
              </Field>
              <Field label="Certificate method">
                <CertSelect value={primary.certificate_method} onChange={certificate_method => {
                  markDirty()
                  setPrimary({ ...primary, certificate_method })
                }} />
              </Field>
              <Field label="Certificate email (optional)">
                <Input value={primary.email ?? ''} onChange={e => {
                  markDirty()
                  setPrimary({ ...primary, email: e.target.value })
                }} placeholder="you@example.com" />
              </Field>
            </div>
            <div className="border-border/50 mt-5 border-t pt-5">
              <CertificateLifecycleActions domain={primary} primary onDomainUpdate={updated => {
                syncingRef.current = true
                dirtyRef.current = false
                setPrimary(updated)
              }} onJobUpdate={job => setCertificateJobs(current => ({ ...current, [job.domainId]: job }))} />
            </div>
          </>
        )}
      </section>

      <section className="border-border/60 bg-card/40 rounded-2xl border p-5 shadow-sm">
        <div className="mb-5 flex items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-lg font-semibold">
              <Globe2 className="text-primary size-5" />
              Additional domains
            </div>
            <p className="text-muted-foreground mt-1 text-sm">Attach domains to nodes, choose certificate handling, and control where each domain is published.</p>
          </div>
          <Button onClick={addDomain}>
            <Plus className="mr-2 size-4" />
            Add domain
          </Button>
        </div>

        <div className="space-y-4">
          {domains.length === 0 && <div className="border-border/70 text-muted-foreground rounded-xl border border-dashed p-8 text-center text-sm">No managed domains yet.</div>}
          {domains.map(domain => (
            <div key={domain.id} className="border-border/60 bg-background/40 rounded-xl border p-4">
              <div className="mb-4 flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="truncate font-medium">{domain.domain || 'New domain'}</div>
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-xs">
                    <StatusBadge status={domain.status} />
                    <span className="border-border/60 text-muted-foreground rounded-full border px-2 py-1">
                      {domain.certificate_method === 'letsencrypt' ? "Let's Encrypt" : 'Existing certificate'}
                    </span>
                    {domain.node_id && <span className="text-muted-foreground">Node: {nodeName.get(domain.node_id) ?? domain.node_id}</span>}
                  </div>
                </div>
                <Button variant="ghost" size="icon" className="text-destructive" onClick={() => removeDomain(domain.id)}>
                  <Trash2 className="size-4" />
                </Button>
              </div>

              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                <Field label="Domain / subdomain">
                  <Input value={domain.domain} onChange={e => updateDomain(domain.id, { domain: e.target.value })} placeholder="edge.example.com" />
                </Field>
                <Field label="Node">
                  <NodeSelect value={domain.node_id} nodes={nodes} onChange={node_id => updateDomain(domain.id, { node_id })} />
                </Field>
                <Field label="Certificate method">
                  <CertSelect value={domain.certificate_method} onChange={certificate_method => updateDomain(domain.id, { certificate_method })} />
                </Field>
                <Field label="How to use this address">
                  <Select value={domain.address_mode} onValueChange={address_mode => updateDomain(domain.id, { address_mode: address_mode as NonNullable<ApiManagedDomain['address_mode']> })}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="additional">As additional address</SelectItem>
                      <SelectItem value="alias">As alias</SelectItem>
                      <SelectItem value="both">Both</SelectItem>
                    </SelectContent>
                  </Select>
                </Field>
                <Field label="Certificate email (optional)">
                  <Input value={domain.email ?? ''} onChange={e => updateDomain(domain.id, { email: e.target.value })} placeholder="you@example.com" />
                </Field>
                <Field label="Auto renewal">
                  <div className="border-border/60 flex h-10 items-center gap-3 rounded-md border px-3">
                    <Switch checked={domain.auto_renew} onCheckedChange={auto_renew => updateDomain(domain.id, { auto_renew })} />
                    <span className="text-sm">{domain.auto_renew ? 'Enabled' : 'Disabled'}</span>
                  </div>
                </Field>
                <Field label="Serve TLS">
                  <div className="border-border/60 flex h-10 items-center gap-3 rounded-md border px-3">
                    <Switch checked={domain.serve_tls !== false} onCheckedChange={serve_tls => updateDomain(domain.id, { serve_tls })} />
                    <span className="text-sm">{domain.serve_tls === false ? 'Disabled' : 'Enabled'}</span>
                  </div>
                </Field>
              </div>

              <div className="mt-4">
                <div className="mb-2 text-sm font-medium">Use in configurations</div>
                <div className="flex flex-wrap gap-2">
                  {protocolOptions.map(protocol => {
                    const active = domain.protocols.includes(protocol)
                    return (
                      <button
                        type="button"
                        key={protocol}
                        onClick={() => updateDomain(domain.id, { protocols: active ? domain.protocols.filter(item => item !== protocol) : [...domain.protocols, protocol] })}
                        className={`rounded-full border px-3 py-1.5 text-xs transition-colors ${active ? 'border-primary bg-primary/10 text-primary' : 'border-border/60 text-muted-foreground hover:text-foreground'}`}
                      >
                        {protocol}
                      </button>
                    )
                  })}
                </div>
                <p className="text-muted-foreground mt-2 text-xs">This is the publishing policy for the managed address. Certificate installation is handled by the node/core layer.</p>
              </div>

              <div className="mt-4 flex flex-wrap items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={!domain.domain.trim() || inspectMutation.isPending || certificateMutation.isPending}
                  onClick={async () => {
                    try {
                      const response = await inspectMutation.mutateAsync({ data: { domain: domain.domain.trim() } })
                      setIntelligence(current => ({ ...current, [domain.id]: (response as any)?.data ?? response }))
                      updateDomain(domain.id, { last_checked_at: new Date().toISOString() })
                    } catch {
                      setIntelligence(current => ({ ...current, [domain.id]: null }))
                    }
                  }}
                >
                  <RefreshCcw className="mr-2 size-4" />
                  {inspectMutation.isPending ? 'Checking…' : 'Inspect domain'}
                </Button>
                {intelligence[domain.id] && (
                  <span className="text-muted-foreground text-xs">
                    {intelligence[domain.id].status} · DNS {intelligence[domain.id].dns?.a?.length ?? 0} A / {intelligence[domain.id].dns?.aaaa?.length ?? 0} AAAA · HTTPS{' '}
                    {intelligence[domain.id].https?.status_code ?? '—'}
                  </span>
                )}
                <Button
                  variant="outline"
                  size="sm"
                  disabled={!domain.domain.trim() || inspectMutation.isPending || certificateMutation.isPending}
                  onClick={async () => {
                    try {
                      const response = await certificateMutation.mutateAsync({ data: { domain: domain.domain.trim() } })
                      const certificate = (response as any)?.data ?? response
                      setCertificates(current => ({ ...current, [domain.id]: certificate }))
                      updateDomain(domain.id, {
                        last_checked_at: certificate.checked_at ?? new Date().toISOString(),
                        certificate_expires_at: certificate.expires_at ?? null,
                        status: certificate.status === 'valid' ? 'active' : certificate.status === 'expiring' ? 'expiring' : certificate.status === 'unreachable' ? 'pending' : 'failed',
                      })
                    } catch {
                      setCertificates(current => ({ ...current, [domain.id]: null }))
                    }
                  }}
                >
                  <ShieldCheck className="mr-2 size-4" />
                  {certificateMutation.isPending ? 'Checking TLS…' : 'Inspect certificate'}
                </Button>
                {certificates[domain.id] && (
                  <span className="text-muted-foreground text-xs">
                    TLS {certificates[domain.id].tls_version ?? '—'} · {certificates[domain.id].status} · {certificates[domain.id].days_remaining ?? '—'}d left
                  </span>
                )}
              </div>

              <div className="border-border/50 text-muted-foreground mt-4 flex flex-wrap items-center gap-2 border-t pt-4 text-xs">
                <span>Last check: {domain.last_checked_at ?? 'not checked'}</span>
                <span>•</span>
                <span>Certificate: {domain.certificate_expires_at ?? 'not issued'}</span>
              </div>
              <div className="border-border/50 mt-4 border-t pt-4">
                <CertificateLifecycleActions domain={domain} onDomainUpdate={updated => {
                  syncingRef.current = true
                  dirtyRef.current = false
                  setDomains(current => current.map(item => (item.id === domain.id ? updated : item)))
                }} onJobUpdate={job => setCertificateJobs(current => ({ ...current, [job.domainId]: job }))} />
              </div>
            </div>
          ))}
        </div>
      </section>

      <CertificateJobsList jobs={Object.values(certificateJobs)} />

      <section className="border-border/60 bg-card/40 rounded-2xl border p-5 shadow-sm">
        <div className="mb-5 flex items-center justify-between gap-4">
          <div>
            <div className="text-lg font-semibold">Server IPs & addresses</div>
            <p className="text-muted-foreground mt-1 text-sm">Keep stable server addresses available for protocols that need an IP fallback or direct endpoint.</p>
          </div>
          <Button variant="outline" onClick={addAddress}>
            <Plus className="mr-2 size-4" />
            Add address
          </Button>
        </div>
        <div className="space-y-3">
          {addresses.map(address => (
            <div key={address.id} className="border-border/60 bg-background/40 grid gap-3 rounded-xl border p-3 md:grid-cols-[1fr_220px_auto] md:items-center">
              <Input
                value={address.address}
                onChange={e => setAddresses(current => current.map(item => (item.id === address.id ? { ...item, address: e.target.value } : item)))}
                placeholder="203.0.113.10 or server.example.com"
              />
              <NodeSelect value={address.node_id} nodes={nodes} onChange={node_id => setAddresses(current => current.map(item => (item.id === address.id ? { ...item, node_id } : item)))} />
              <div className="flex items-center gap-2">
                <Switch checked={address.enabled} onCheckedChange={enabled => setAddresses(current => current.map(item => (item.id === address.id ? { ...item, enabled } : item)))} />
                <Button variant="ghost" size="icon" className="text-destructive" onClick={() => setAddresses(current => current.filter(item => item.id !== address.id))}>
                  <Trash2 className="size-4" />
                </Button>
              </div>
            </div>
          ))}
          {addresses.length === 0 && <div className="border-border/70 text-muted-foreground rounded-xl border border-dashed p-8 text-center text-sm">No server addresses configured.</div>}
        </div>
      </section>

    </div>
  )
}

function CertificateLifecycleActions({ domain, primary = false, onDomainUpdate, onJobUpdate }: { domain: ApiManagedDomain; primary?: boolean; onDomainUpdate: (domain: ApiManagedDomain) => void; onJobUpdate?: (job: CertificateJob) => void }) {
  const issueMutation = useIssueManagedCertificate()
  const installMutation = useInstallExistingCertificate()
  const deployMutation = useDeployManagedCertificates()
  const [showExisting, setShowExisting] = useState(false)
  const [certificatePem, setCertificatePem] = useState('')
  const [privateKeyPem, setPrivateKeyPem] = useState('')
  const method = domain.certificate_method ?? 'letsencrypt'
  const busy = issueMutation.isPending || installMutation.isPending || deployMutation.isPending
  const expiry = formatCertificateDate(domain.certificate_expires_at)
  const days = daysUntil(domain.certificate_expires_at)

  const updateFromResponse = (response: any) => {
    const payload = response?.data ?? response
    if (payload?.domain) onDomainUpdate(payload.domain as ApiManagedDomain)
    return payload
  }

  const issue = async () => {
    const startedAt = new Date().toISOString()
    onJobUpdate?.({ domainId: domain.id, domain: domain.domain, status: 'running', startedAt, lastAttemptAt: startedAt })
    try {
      const payload = updateFromResponse(await issueMutation.mutateAsync({ data: { domain_id: domain.id, force: true, domain, primary } }))
      const succeeded = payload?.domain?.status === 'active' || payload?.domain?.status === 'expiring'
      const lastAttemptAt = new Date().toISOString()
      onJobUpdate?.({
        domainId: domain.id,
        domain: payload?.domain?.domain ?? domain.domain,
        status: succeeded ? 'succeeded' : 'failed',
        startedAt,
        lastAttemptAt,
        error: succeeded ? undefined : 'Certificate issuance failed.',
      })
      toast.success(succeeded ? 'Certificate request completed.' : 'Certificate issuance failed.')
    } catch {
      const lastAttemptAt = new Date().toISOString()
      onJobUpdate?.({ domainId: domain.id, domain: domain.domain, status: 'failed', startedAt, lastAttemptAt, error: 'Certificate issuance failed.' })
      toast.error('Certificate issuance failed.')
    }
  }

  const install = async () => {
    if (!certificatePem.trim() || !privateKeyPem.trim()) {
      toast.error('Certificate and private key are required.')
      return
    }
    try {
      updateFromResponse(
        await installMutation.mutateAsync({
          data: {
            domain_id: domain.id,
            certificate_pem: certificatePem,
            private_key_pem: privateKeyPem,
            domain,
            primary,
          },
        }),
      )
      setCertificatePem('')
      setPrivateKeyPem('')
      setShowExisting(false)
      toast.success('Existing certificate installed; deployment requested.')
    } catch (error: any) {
      toast.error(error?.message ?? 'Certificate installation failed.')
    }
  }

  const deploy = async () => {
    try {
      const payload = updateFromResponse(await deployMutation.mutateAsync({ data: { domain_id: domain.id } }))
      toast.success((payload?.domain?.deployment_status ?? 'not_deployed') === 'deployed' ? 'Managed certificates deployed to the node.' : 'Certificate deployment did not complete.')
    } catch (error: any) {
      toast.error(error?.message ?? 'Certificate deployment failed.')
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-muted-foreground text-xs font-medium">Certificate lifecycle</span>
        <StatusBadge status={domain.status ?? 'pending'} />
        <span className="border-border/60 text-muted-foreground rounded-full border px-2 py-1 text-xs">
          {domain.deployment_status === 'deployed' ? 'Node deployed' : domain.deployment_status === 'failed' ? 'Deployment failed' : 'Not deployed'}
        </span>
      </div>

      <div className="text-muted-foreground grid gap-3 text-xs sm:grid-cols-2 lg:grid-cols-4">
        <span>
          <Clock3 className="mr-1 inline size-3.5" />
          Expires: {expiry}
        </span>
        <span>Days remaining: {days ?? '—'}</span>
        <span>Renewal attempts: {domain.renewal_attempts ?? 0}</span>
        <span>Next renewal: {formatCertificateDate(domain.next_renewal_at)}</span>
      </div>

      {(domain.certificate_error || domain.deployment_error) && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/5 px-3 py-2 text-xs text-red-400">{domain.certificate_error ?? domain.deployment_error}</div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        {method !== 'existing' && (
          <Button size="sm" disabled={busy || !domain.domain.trim()} onClick={issue}>
            <RefreshCcw className="mr-2 size-4" />
            {issueMutation.isPending ? 'Issuing…' : domain.certificate_expires_at ? 'Renew certificate' : 'Issue certificate'}
          </Button>
        )}
        {method === 'existing' && (
          <Button variant="outline" size="sm" disabled={busy || !domain.domain.trim()} onClick={() => setShowExisting(value => !value)}>
            <UploadCloud className="mr-2 size-4" />
            {showExisting ? 'Hide certificate form' : 'Install existing certificate'}
          </Button>
        )}
        {domain.node_id != null && domain.certificate_expires_at && (
          <Button variant="outline" size="sm" disabled={busy} onClick={deploy}>
            <CheckCircle2 className="mr-2 size-4" />
            {deployMutation.isPending ? 'Deploying…' : domain.deployment_status === 'deployed' ? 'Re-deploy to node' : 'Deploy to node'}
          </Button>
        )}
      </div>

      {showExisting && method === 'existing' && (
        <div className="border-border/60 bg-background/30 space-y-3 rounded-xl border p-3">
          <p className="text-muted-foreground text-xs">The private key is submitted only for validation/storage and is never returned by the API.</p>
          <Field label="Full certificate chain">
            <Textarea value={certificatePem} onChange={event => setCertificatePem(event.target.value)} rows={7} placeholder="-----BEGIN CERTIFICATE-----" />
          </Field>
          <Field label="Private key">
            <Textarea value={privateKeyPem} onChange={event => setPrivateKeyPem(event.target.value)} rows={7} placeholder="-----BEGIN PRIVATE KEY-----" />
          </Field>
          <Button size="sm" disabled={busy} onClick={install}>
            {installMutation.isPending ? 'Installing…' : 'Validate & install certificate'}
          </Button>
        </div>
      )}

      {domain.certificate_deployed_at && <span className="text-muted-foreground text-xs">Last deployed: {formatCertificateDate(domain.certificate_deployed_at)}</span>}
    </div>
  )
}

function CertificateJobsList({ jobs }: { jobs: CertificateJob[] }) {
  if (jobs.length === 0) return null
  return (
    <section className="border-border/60 bg-card/40 rounded-2xl border p-5 shadow-sm">
      <div className="mb-4">
        <div className="text-lg font-semibold">Certificate Jobs</div>
        <p className="text-muted-foreground mt-1 text-sm">Certificate issuance activity for the managed domains.</p>
      </div>
      <div className="space-y-2">
        {jobs.map(job => {
          const running = job.status === 'running'
          const failed = job.status === 'failed'
          const succeeded = job.status === 'succeeded'
          return (
            <div key={job.domainId} className="border-border/60 bg-background/30 grid gap-2 rounded-xl border p-3 md:grid-cols-[1fr_auto_auto] md:items-center">
              <div className="min-w-0">
                <div className="truncate font-medium">{job.domain || 'New domain'}</div>
                <div className="text-muted-foreground mt-1 text-xs">
                  Started: {formatCertificateDate(job.startedAt)} · Last attempt: {formatCertificateDate(job.lastAttemptAt)}
                </div>
              </div>
              <div className={
                `rounded-full border px-2.5 py-1 text-xs ${running ? 'border-amber-500/30 bg-amber-500/10 text-amber-400' : failed ? 'border-red-500/30 bg-red-500/10 text-red-400' : succeeded ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400' : 'border-border/60 text-muted-foreground'}`
              }>
                {running ? '🟠 در حال دریافت گواهی' : succeeded ? '🟢 گواهی دریافت شد' : failed ? '🔴 دریافت گواهی ناموفق بود' : '—'}
              </div>
              {failed && job.error && <div className="text-xs text-red-400 md:max-w-xs md:text-right">{job.error}</div>}
            </div>
          )
        })}
      </div>
    </section>
  )
}

function formatCertificateDate(value?: string | null) {
  if (!value) return 'not set'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

function daysUntil(value?: string | null) {
  if (!value) return null
  const time = new Date(value).getTime()
  if (Number.isNaN(time)) return null
  return Math.ceil((time - Date.now()) / 86400000)
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="space-y-1.5">
      <div className="text-sm font-medium">{label}</div>
      {children}
    </div>
  )
}

function NodeSelect({ value, nodes, onChange }: { value?: number | null; nodes: Array<{ id: number; name: string }>; onChange: (value: number | null) => void }) {
  return (
    <Select value={value ? String(value) : 'none'} onValueChange={next => onChange(next === 'none' ? null : Number(next))}>
      <SelectTrigger>
        <SelectValue placeholder="Select node" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="none">No node</SelectItem>
        {nodes.map(node => (
          <SelectItem key={node.id} value={String(node.id)}>
            {node.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

function CertSelect({ value, onChange }: { value: NonNullable<ApiManagedDomain['certificate_method']>; onChange: (value: ApiManagedDomain['certificate_method']) => void }) {
  return (
    <Select value={value} onValueChange={value => onChange(value as ApiManagedDomain['certificate_method'])}>
      <SelectTrigger>
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="letsencrypt">Auto with Let's Encrypt</SelectItem>
        <SelectItem value="existing">Use existing certificate</SelectItem>
      </SelectContent>
    </Select>
  )
}

function StatusBadge({ status }: { status: NonNullable<ApiManagedDomain['status']> }) {
  const label = status === 'active' ? 'Active' : status === 'expiring' ? 'Expiring' : status === 'expired' ? 'Expired' : status === 'failed' ? 'Failed' : 'Pending'
  const cls =
    status === 'active'
      ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400'
      : status === 'failed' || status === 'expired'
        ? 'border-red-500/30 bg-red-500/10 text-red-400'
        : 'border-amber-500/30 bg-amber-500/10 text-amber-400'
  return <span className={`rounded-full border px-2 py-1 ${cls}`}>{label}</span>
}
