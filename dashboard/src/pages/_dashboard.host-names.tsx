import PageHeader from '@/components/layout/page-header'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { getPersonalHostNames, setPersonalHostName } from '@/service/api'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'

export default function HostNamesPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { data, isLoading, isError } = useQuery({
    queryKey: ['personalHostNames'],
    queryFn: () => getPersonalHostNames(),
  })
  const [drafts, setDrafts] = useState<Record<number, string>>({})
  const [savingId, setSavingId] = useState<number | null>(null)

  const saveName = async (hostId: number, currentName: string | null) => {
    const name = (drafts[hostId] ?? currentName ?? '').trim()
    if (!name) {
      toast.error(t('personalHostNameRequired', { defaultValue: 'Name cannot be empty' }))
      return
    }
    setSavingId(hostId)
    try {
      await setPersonalHostName(hostId, name)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['personalHostNames'] }),
        queryClient.invalidateQueries({ queryKey: ['getGetHostsQueryKey'] }),
      ])
      setDrafts(current => {
        const next = { ...current }
        delete next[hostId]
        return next
      })
      toast.success(t('personalHostNameSaved', { defaultValue: 'Private host name saved' }))
    } catch {
      toast.error(t('permissionDenied', { defaultValue: 'Permission denied' }))
    } finally {
      setSavingId(null)
    }
  }

  return (
    <div className="flex w-full flex-col items-start gap-2">
      <div className="w-full transform-gpu">
        <PageHeader title="personalHostNamesTab" description="personalHostNamePrompt" />
      </div>
      <div className="w-full space-y-3 p-4">
        {isLoading && <p className="text-muted-foreground text-sm">{t('loading', { defaultValue: 'Loading…' })}</p>}
        {isError && <p className="text-destructive text-sm">{t('loadHostIdentifiersError', { defaultValue: 'Could not load host identifiers' })}</p>}
        {data?.map(entry => {
          const value = drafts[entry.host_id] ?? entry.personal_name ?? ''
          return (
            <div key={entry.host_id} className="flex flex-col gap-3 rounded-lg border bg-card p-4 sm:flex-row sm:items-center">
              <div className="min-w-0 flex-1 space-y-1">
                <p className="break-words text-base font-semibold">{entry.host_name}</p>
                <p className="break-words text-xs text-muted-foreground">
                  {t('personalHostName', { defaultValue: 'Personal host name' })}: {entry.personal_name?.trim() || t('personalHostNameEmpty', { defaultValue: 'No personal name set yet' })}
                </p>
                <p className="font-mono text-xs text-muted-foreground">{t('hostIdentifier', { defaultValue: 'Host ID' })}: {entry.host_id}</p>
              </div>
              <div className="flex min-w-0 flex-1 flex-col gap-1">
                <label className="text-xs font-medium" htmlFor={`personal-host-name-${entry.host_id}`}>
                  {t('editPersonalHostName', { defaultValue: 'Change personal name' })}
                </label>
                <Input
                  id={`personal-host-name-${entry.host_id}`}
                  maxLength={256}
                  value={value}
                  onChange={event => setDrafts(current => ({ ...current, [entry.host_id]: event.target.value }))}
                  placeholder={t('personalHostNameEmpty', { defaultValue: 'No personal name set yet' })}
                />
              </div>
              <Button
                type="button"
                disabled={savingId === entry.host_id || !value.trim() || value.trim() === (entry.personal_name ?? '')}
                onClick={() => void saveName(entry.host_id, entry.personal_name)}
              >
                {savingId === entry.host_id ? t('savingHostName', { defaultValue: 'Saving…' }) : t('saveHostName', { defaultValue: 'Save' })}
              </Button>
            </div>
          )
        })}
        {data?.length === 0 && !isLoading && (
          <p className="text-muted-foreground text-sm">{t('noHostsAvailable', { defaultValue: 'No hosts are available.' })}</p>
        )}
      </div>
    </div>
  )
}
