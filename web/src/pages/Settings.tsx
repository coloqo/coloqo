import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import { api, call, uploadAvatar, type Installation, type Me, type OwnAssistant, type Team } from '../api/client'
import { useInstallations, useOwnAssistants, useTeams } from '../api/queries'
import { PersonAvatar } from '../components/Avatar'
import { Page } from '../components/Layout'
import { PseudonymForm } from '../components/PseudonymForm'
import { Time } from '../components/Time'
import { Badge, Button, Card, CardHeader, Empty, ErrorNote, Loading, Select } from '../components/ui'
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

function AvatarCard({ me }: { me: Me }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const fileInput = useRef<HTMLInputElement>(null)
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ['me'] })
    void queryClient.invalidateQueries({ queryKey: ['team'] })
  }
  const upload = useMutation({ mutationFn: uploadAvatar, onSuccess: refresh })
  const github = useMutation({ mutationFn: () => call(api.POST('/api/me/avatar/github')), onSuccess: refresh })
  const remove = useMutation({ mutationFn: () => call(api.DELETE('/api/me/avatar')), onSuccess: refresh })
  const busy = upload.isPending || github.isPending || remove.isPending
  const error = upload.error ?? github.error ?? remove.error
  return (
    <Card>
      <CardHeader title={t('avatar.title')} />
      <div className="flex flex-wrap items-center gap-4 px-4 py-4">
        <PersonAvatar name={me.pseudonym ?? '?'} size={64} src={me.avatar} />
        <div className="flex min-w-0 flex-1 flex-col gap-2">
          <p className="text-sm text-stone-600 dark:text-stone-400">{t('avatar.lead')}</p>
          <div className="flex flex-wrap gap-2">
            <input
              ref={fileInput}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={(event) => {
                const file = event.target.files?.[0]
                if (file) upload.mutate(file)
                event.target.value = ''
              }}
            />
            <Button size="sm" onClick={() => fileInput.current?.click()} disabled={busy}>
              {t('avatar.upload')}
            </Button>
            {me.github && (
              <Button size="sm" onClick={() => github.mutate()} disabled={busy}>
                {t('avatar.github')}
              </Button>
            )}
            {me.avatar && (
              <Button size="sm" variant="ghost" onClick={() => remove.mutate()} disabled={busy}>
                {t('avatar.remove')}
              </Button>
            )}
          </div>
          <ErrorNote>{error && errorText(error, t)}</ErrorNote>
        </div>
      </div>
    </Card>
  )
}

function AssistantRow({ assistant, teams }: { assistant: OwnAssistant; teams: Team[] }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const link = useMutation({
    mutationFn: (teamId: number | null) =>
      call(
        api.PUT('/api/assistants/{assistant_id}/team', {
          params: { path: { assistant_id: assistant.id } },
          body: { team_id: teamId },
        }),
      ),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['assistants'] }),
  })
  return (
    <li className="flex flex-wrap items-center gap-3 px-4 py-3">
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="font-medium break-words">{assistant.name}</span>
        <span className="text-xs text-stone-500 dark:text-stone-400">
          {assistant.installation}
          {assistant.last_seen_at && (
            <>
              {' · '}
              {t('installations.lastSeen')} <Time value={assistant.last_seen_at} />
            </>
          )}
        </span>
        <ErrorNote>{link.error && errorText(link.error, t)}</ErrorNote>
      </div>
      <div className="w-full sm:w-56">
        <Select
          aria-label={t('assistants.team', { name: assistant.name })}
          value={assistant.team_id ?? ''}
          disabled={link.isPending}
          onChange={(event) => link.mutate(event.target.value ? Number(event.target.value) : null)}
        >
          <option value="">{t('assistants.unlinked')}</option>
          {teams.map((team) => (
            <option key={team.id} value={team.id}>
              {team.name}
            </option>
          ))}
        </Select>
      </div>
    </li>
  )
}

function AssistantsCard() {
  const { t } = useTranslation()
  const assistants = useOwnAssistants()
  const teams = useTeams()
  return (
    <Card>
      <CardHeader title={t('assistants.title')} />
      <p className="px-4 pt-3 text-sm text-stone-600 dark:text-stone-400">{t('assistants.lead')}</p>
      {(assistants.isPending || teams.isPending) && <Loading />}
      <ErrorNote>{assistants.error && errorText(assistants.error, t)}</ErrorNote>
      {assistants.data?.length === 0 && <Empty>{t('assistants.empty')}</Empty>}
      {assistants.data && assistants.data.length > 0 && teams.data && (
        <ul className="mt-2 divide-y divide-stone-200 border-t border-stone-200 dark:divide-stone-800 dark:border-stone-800">
          {assistants.data.map((assistant) => (
            <AssistantRow key={assistant.id} assistant={assistant} teams={teams.data} />
          ))}
        </ul>
      )}
    </Card>
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
        <AvatarCard me={me} />
        <AssistantsCard />
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
