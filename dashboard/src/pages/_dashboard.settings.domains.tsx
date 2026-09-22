import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { useGetGeneralSettings, useGetNodesSimple } from '@/service/api'
import { Globe2, Plus, RefreshCcw, ShieldCheck, Trash2 } from 'lucide-react'
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { useSettingsContext } from './_dashboard.settings'

type ManagedDomain = {
  id: string
  domain: string
  node_id?: number | null
  certificate_method: 'letsencrypt' | 'cloudflare' | 'existing'
  address_mode: 'additional' | 'alias' | 'both'
  protocols: string[]
  email?: string | null
  auto_renew: boolean
  status: 'pending' | 'active' | 'expiring' | 'failed'
  certificate_expires_at?: string | null
  last_checked_at?: string | null
}

type ManagedServerAddress = {
  id: string
  node_id?: number | null
  address: string
  enabled: boolean
}

const protocolOptions = ['Xray', 'Reality', 'AmneziaWG', 'Mieru', 'Shadowsocks', 'TUIC', 'Hysteria2', 'NaiveProxy', 'sing-box']

const newId = () => crypto.randomUUID()

const normalizeDomain = (value: string) => value.trim().toLowerCase()

const emptyDomain = (): ManagedDomain => ({
  id: newId(),
  domain: '',
  node_id: null,
  certificate_method: 'letsencrypt',
  address_mode: 'additional',
  protocols: ['Xray', 'Reality'],
  email: '',
  auto_renew: true,
  status: 'pending',
  certificate_expires_at: null,
  last_checked_at: null,
})

export default function DomainsSettings() {
  const { updateSettings, isSaving } = useSettingsContext()
  const { data: generalSettings, isLoading } = useGetGeneralSettings()
  const { data: nodesResponse } = useGetNodesSimple()
  const nodes = ((nodesResponse as any)?.data?.nodes ?? (nodesResponse as any)?.nodes ?? []) as Array<{ id: number; name: string }>

  const general = ((generalSettings as any)?.data ?? generalSettings ?? {}) as any
  const storedDomains = (general.domains ?? []) as ManagedDomain[]
  const storedPrimary = (general.primary_domain ?? null) as ManagedDomain | null
  const storedAddresses = (general.server_addresses ?? []) as ManagedServerAddress[]

  const [primary, setPrimary] = useState<ManagedDomain | null>(storedPrimary)
  const [domains, setDomains] = useState<ManagedDomain[]>(storedDomains)
  const [addresses, setAddresses] = useState<ManagedServerAddress[]>(storedAddresses)

  useEffect(() => {
    setPrimary(storedPrimary)
    setDomains(storedDomains)
    setAddresses(storedAddresses)
  }, [(generalSettings as any)?.data?.domains, (generalSettings as any)?.data?.primary_domain, (generalSettings as any)?.data?.server_addresses, (generalSettings as any)?.domains, (generalSettings as any)?.primary_domain, (generalSettings as any)?.server_addresses])

  const nodeName = useMemo(() => new Map(nodes.map(node => [node.id, node.name])), [nodes])

  const save = async () => {
    try {
      const cleanDomains = domains
        .map(item => ({ ...item, domain: normalizeDomain(item.domain) }))
        .filter(item => item.domain)
      const cleanPrimary = primary?.domain ? { ...primary, domain: normalizeDomain(primary.domain) } : null

      await updateSettings({
        domains: cleanDomains,
        primary_domain: cleanPrimary,
        server_addresses: addresses.filter(item => item.address.trim()).map(item => ({ ...item, address: item.address.trim() })),
      })
    } catch {
      // Parent settings context reports the API error.
    }
  }

  const addDomain = () => setDomains(current => [...current, emptyDomain()])
  const updateDomain = (id: string, patch: Partial<ManagedDomain>) => setDomains(current => current.map(item => item.id === id ? { ...item, ...patch } : item))
  const removeDomain = (id: string) => setDomains(current => current.filter(item => item.id !== id))
  const addAddress = () => setAddresses(current => [...current, { id: newId(), node_id: null, address: '', enabled: true }])

  if (isLoading) return <div className="w-full p-6 text-sm text-muted-foreground">Loading Domains & SSL…</div>

  return (
    <div className="w-full space-y-6 p-4 sm:p-6 lg:p-8">
      <section className="rounded-2xl border border-border/60 bg-card/40 p-5 shadow-sm">
        <div className="mb-5 flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-lg font-semibold"><ShieldCheck className="size-5 text-primary" />Primary domain</div>
            <p className="mt-1 text-sm text-muted-foreground">The main public domain used by your panel and subscriptions.</p>
          </div>
          <Button variant="outline" size="sm" onClick={() => setPrimary(primary ? null : emptyDomain())}>{primary ? 'Remove' : 'Add primary domain'}</Button>
        </div>
        {primary && (
          <div className="grid gap-4 md:grid-cols-2">
            <Field label="Domain"><Input value={primary.domain} onChange={e => setPrimary({ ...primary, domain: e.target.value })} placeholder="panel.example.com" /></Field>
            <Field label="Node"><NodeSelect value={primary.node_id} nodes={nodes} onChange={node_id => setPrimary({ ...primary, node_id })} /></Field>
            <Field label="Certificate method"><CertSelect value={primary.certificate_method} onChange={certificate_method => setPrimary({ ...primary, certificate_method })} /></Field>
            <Field label="Certificate email (optional)"><Input value={primary.email ?? ''} onChange={e => setPrimary({ ...primary, email: e.target.value })} placeholder="you@example.com" /></Field>
          </div>
        )}
      </section>

      <section className="rounded-2xl border border-border/60 bg-card/40 p-5 shadow-sm">
        <div className="mb-5 flex items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-lg font-semibold"><Globe2 className="size-5 text-primary" />Additional domains</div>
            <p className="mt-1 text-sm text-muted-foreground">Attach domains to nodes, choose certificate handling, and control where each domain is published.</p>
          </div>
          <Button onClick={addDomain}><Plus className="mr-2 size-4" />Add domain</Button>
        </div>

        <div className="space-y-4">
          {domains.length === 0 && <div className="rounded-xl border border-dashed border-border/70 p-8 text-center text-sm text-muted-foreground">No managed domains yet.</div>}
          {domains.map(domain => (
            <div key={domain.id} className="rounded-xl border border-border/60 bg-background/40 p-4">
              <div className="mb-4 flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="truncate font-medium">{domain.domain || 'New domain'}</div>
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-xs">
                    <StatusBadge status={domain.status} />
                    <span className="rounded-full border border-border/60 px-2 py-1 text-muted-foreground">{domain.certificate_method === 'letsencrypt' ? "Let's Encrypt" : domain.certificate_method === 'cloudflare' ? 'Cloudflare DNS' : 'Existing certificate'}</span>
                    {domain.node_id && <span className="text-muted-foreground">Node: {nodeName.get(domain.node_id) ?? domain.node_id}</span>}
                  </div>
                </div>
                <Button variant="ghost" size="icon" className="text-destructive" onClick={() => removeDomain(domain.id)}><Trash2 className="size-4" /></Button>
              </div>

              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                <Field label="Domain / subdomain"><Input value={domain.domain} onChange={e => updateDomain(domain.id, { domain: e.target.value })} placeholder="edge.example.com" /></Field>
                <Field label="Node"><NodeSelect value={domain.node_id} nodes={nodes} onChange={node_id => updateDomain(domain.id, { node_id })} /></Field>
                <Field label="Certificate method"><CertSelect value={domain.certificate_method} onChange={certificate_method => updateDomain(domain.id, { certificate_method })} /></Field>
                <Field label="How to use this address">
                  <Select value={domain.address_mode} onValueChange={address_mode => updateDomain(domain.id, { address_mode: address_mode as ManagedDomain['address_mode'] })}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="additional">As additional address</SelectItem>
                      <SelectItem value="alias">As alias</SelectItem>
                      <SelectItem value="both">Both</SelectItem>
                    </SelectContent>
                  </Select>
                </Field>
                <Field label="Certificate email (optional)"><Input value={domain.email ?? ''} onChange={e => updateDomain(domain.id, { email: e.target.value })} placeholder="you@example.com" /></Field>
                <Field label="Auto renewal">
                  <div className="flex h-10 items-center gap-3 rounded-md border border-border/60 px-3"><Switch checked={domain.auto_renew} onCheckedChange={auto_renew => updateDomain(domain.id, { auto_renew })} /><span className="text-sm">{domain.auto_renew ? 'Enabled' : 'Disabled'}</span></div>
                </Field>
              </div>

              <div className="mt-4">
                <div className="mb-2 text-sm font-medium">Use in configurations</div>
                <div className="flex flex-wrap gap-2">
                  {protocolOptions.map(protocol => {
                    const active = domain.protocols.includes(protocol)
                    return (
                      <button type="button" key={protocol} onClick={() => updateDomain(domain.id, { protocols: active ? domain.protocols.filter(item => item !== protocol) : [...domain.protocols, protocol] })} className={`rounded-full border px-3 py-1.5 text-xs transition-colors ${active ? 'border-primary bg-primary/10 text-primary' : 'border-border/60 text-muted-foreground hover:text-foreground'}`}>
                        {protocol}
                      </button>
                    )
                  })}
                </div>
                <p className="mt-2 text-xs text-muted-foreground">This is the publishing policy for the managed address. Certificate installation is handled by the node/core layer.</p>
              </div>

              <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-border/50 pt-4 text-xs text-muted-foreground">
                <span>Last check: {domain.last_checked_at ?? 'not checked'}</span><span>•</span><span>Certificate: {domain.certificate_expires_at ?? 'not issued'}</span>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-2xl border border-border/60 bg-card/40 p-5 shadow-sm">
        <div className="mb-5 flex items-center justify-between gap-4">
          <div><div className="text-lg font-semibold">Server IPs & addresses</div><p className="mt-1 text-sm text-muted-foreground">Keep stable server addresses available for protocols that need an IP fallback or direct endpoint.</p></div>
          <Button variant="outline" onClick={addAddress}><Plus className="mr-2 size-4" />Add address</Button>
        </div>
        <div className="space-y-3">
          {addresses.map(address => (
            <div key={address.id} className="grid gap-3 rounded-xl border border-border/60 bg-background/40 p-3 md:grid-cols-[1fr_220px_auto] md:items-center">
              <Input value={address.address} onChange={e => setAddresses(current => current.map(item => item.id === address.id ? { ...item, address: e.target.value } : item))} placeholder="203.0.113.10 or server.example.com" />
              <NodeSelect value={address.node_id} nodes={nodes} onChange={node_id => setAddresses(current => current.map(item => item.id === address.id ? { ...item, node_id } : item))} />
              <div className="flex items-center gap-2"><Switch checked={address.enabled} onCheckedChange={enabled => setAddresses(current => current.map(item => item.id === address.id ? { ...item, enabled } : item))} /><Button variant="ghost" size="icon" className="text-destructive" onClick={() => setAddresses(current => current.filter(item => item.id !== address.id))}><Trash2 className="size-4" /></Button></div>
            </div>
          ))}
          {addresses.length === 0 && <div className="rounded-xl border border-dashed border-border/70 p-8 text-center text-sm text-muted-foreground">No server addresses configured.</div>}
        </div>
      </section>

      <div className="sticky bottom-4 z-10 flex justify-end">
        <Button size="lg" onClick={save} disabled={isSaving}><RefreshCcw className="mr-2 size-4" />{isSaving ? 'Saving…' : 'Save domains & SSL'}</Button>
      </div>
    </div>
  )
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return <div className="space-y-1.5"><div className="text-sm font-medium">{label}</div>{children}</div>
}

function NodeSelect({ value, nodes, onChange }: { value?: number | null; nodes: Array<{ id: number; name: string }>; onChange: (value: number | null) => void }) {
  return (
    <Select value={value ? String(value) : 'none'} onValueChange={next => onChange(next === 'none' ? null : Number(next))}>
      <SelectTrigger><SelectValue placeholder="Select node" /></SelectTrigger>
      <SelectContent><SelectItem value="none">No node</SelectItem>{nodes.map(node => <SelectItem key={node.id} value={String(node.id)}>{node.name}</SelectItem>)}</SelectContent>
    </Select>
  )
}

function CertSelect({ value, onChange }: { value: ManagedDomain['certificate_method']; onChange: (value: ManagedDomain['certificate_method']) => void }) {
  return (
    <Select value={value} onValueChange={value => onChange(value as ManagedDomain['certificate_method'])}>
      <SelectTrigger><SelectValue /></SelectTrigger>
      <SelectContent>
        <SelectItem value="letsencrypt">Auto with Let's Encrypt</SelectItem>
        <SelectItem value="cloudflare">Auto with Cloudflare DNS</SelectItem>
        <SelectItem value="existing">Use existing certificate</SelectItem>
      </SelectContent>
    </Select>
  )
}

function StatusBadge({ status }: { status: ManagedDomain['status'] }) {
  const label = status === 'active' ? 'Active' : status === 'expiring' ? 'Expiring' : status === 'failed' ? 'Failed' : 'Pending'
  const cls = status === 'active' ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400' : status === 'failed' ? 'border-red-500/30 bg-red-500/10 text-red-400' : 'border-amber-500/30 bg-amber-500/10 text-amber-400'
  return <span className={`rounded-full border px-2 py-1 ${cls}`}>{label}</span>
}
