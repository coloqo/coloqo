import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import { api, call, type Installation, type Me } from '../api/client'
import { useInstallations } from '../api/queries'
import { Page } from '../components/Layout'
import { PseudonymForm } from '../components/PseudonymForm'
import { Time } from '../components/Time'
import { Badge, Button, Card, CardHeader, Empty, ErrorNote, Loading } from '../components/ui'
import { errorText } from '../lib/format'

function InstallationRow({ installation }: { installation: Installation }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [confirming, setConfirming] = useState(false)
  const revoke = useMutation({
    mutationFn: () =>
      call(api.DELETE('/api/installations/{installation_id}', { params: { path: { installation_id: installation.id } } })),
    onSuccess: () => {
      setConfirming(false)
      void queryClient.invalidateQueries({ queryKey: ['installations'] })
    },
  })
  return (
    <li className="flex flex-wrap items-center gap-3 px-4 py-3">
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="flex flex-wrap items-center gap-2 font-medium">
          <span className="break-words">{installation.name}</span>
          {installation.revoked && <Badge tone="red">{t('installations.revoked')}</Badge>}
        </span>
        <span className="text-xs text-stone-500 dark:text-stone-400">
          {t('installations.created')} <Time value={installation.created_at} />
          {' · '}
          {installation.last_seen_at ? (
            <>
              {t('installations.lastSeen')} <Time value={installation.last_seen_at} />
            </>
          ) : (
            t('installations.neverSeen')
          )}
        </span>
        <ErrorNote>{revoke.error && errorText(revoke.error, t)}</ErrorNote>
      </div>
      {!installation.revoked &&
        (confirming ? (
          <div className="flex gap-2">
            <Button size="sm" variant="danger" onClick={() => revoke.mutate()} disabled={revoke.isPending}>
              {t('installations.confirmRevoke')}
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setConfirming(false)}>
              {t('common.cancel')}
            </Button>
          </div>
        ) : (
          <Button size="sm" variant="danger" onClick={() => setConfirming(true)}>
            {t('installations.revoke')}
          </Button>
        ))}
    </li>
  )
}

export function SettingsPage({ me }: { me: Me }) {
  const { t } = useTranslation()
  const installations = useInstallations()
  return (
    <Page title={t('settings.title')}>
      <div className="flex max-w-3xl flex-col gap-5">
        <Card>
          <CardHeader title={t('settings.pseudonym')} />
          <div className="flex flex-col gap-3 px-4 py-4">
            <p className="text-sm text-stone-600 dark:text-stone-400">{t('settings.pseudonymLead')}</p>
            <div className="max-w-sm">
              <PseudonymForm current={me.pseudonym} />
            </div>
          </div>
        </Card>
        <Card>
          <CardHeader title={t('installations.title')} />
          <p className="px-4 pt-3 text-sm text-stone-600 dark:text-stone-400">
            {t('installations.lead')}{' '}
            <Link to="/connect" className="text-amber-700 hover:underline dark:text-amber-400">
              {t('installations.connectLink')}
            </Link>
          </p>
          {installations.isPending && <Loading />}
          <ErrorNote>{installations.error && errorText(installations.error, t)}</ErrorNote>
          {installations.data?.length === 0 && <Empty>{t('installations.empty')}</Empty>}
          {installations.data && installations.data.length > 0 && (
            <ul className="mt-2 divide-y divide-stone-200 border-t border-stone-200 dark:divide-stone-800 dark:border-stone-800">
              {installations.data.map((installation) => (
                <InstallationRow key={installation.id} installation={installation} />
              ))}
            </ul>
          )}
        </Card>
      </div>
    </Page>
  )
}
