import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router'

import { ApiError, api, call, teamPath, type Invite, type TeamDetail } from '../api/client'
import { useTeam } from '../api/queries'
import { Page } from '../components/Layout'
import { TeamPageFrame } from '../components/TeamBar'
import { Time } from '../components/Time'
import { TrackerSettings } from '../components/TrackerSettings'
import { Button, Card, CardHeader, CopyButton, ErrorNote, Field, Input, Loading, Notice } from '../components/ui'
import { errorText } from '../lib/format'

function InviteCard({ team }: { team: TeamDetail }) {
  const { t } = useTranslation()
  const [invite, setInvite] = useState<Invite | null>(null)
  const create = useMutation({
    mutationFn: () => call(api.POST('/api/team/{team}/invite', { params: { path: { team: team.slug } } })),
    onSuccess: setInvite,
  })
  return (
    <Card>
      <CardHeader title={t('team.invite')} />
      <div className="flex flex-col gap-3 px-4 py-3">
        <p className="text-sm text-stone-600 dark:text-stone-400">{t('team.inviteLead')}</p>
        {invite && (
          <div className="flex flex-col gap-2">
            <div className="flex items-start gap-2 rounded-md bg-stone-100 p-2 pl-3 dark:bg-stone-800/70">
              <code className="min-w-0 flex-1 py-1 font-mono text-xs break-all">{invite.url}</code>
              <CopyButton text={invite.url} />
            </div>
            <p className="text-xs text-stone-500 dark:text-stone-400">
              {t('team.inviteNote')} <Time value={invite.expires_at} absolute />.
            </p>
          </div>
        )}
        <ErrorNote>{create.error && errorText(create.error, t)}</ErrorNote>
        <div>
          <Button size="sm" onClick={() => create.mutate()} disabled={create.isPending}>
            {invite ? t('team.inviteAnother') : t('team.inviteCreate')}
          </Button>
        </div>
      </div>
    </Card>
  )
}

/** The Team's own settings: the owner edits them, a member sees them. */
function GeneralSettings({ team, readOnly }: { team: TeamDetail; readOnly: boolean }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [name, setName] = useState(team.name)
  const [slug, setSlug] = useState(team.slug)
  const [limit, setLimit] = useState(String(team.turn_limit))
  const [tracker, setTracker] = useState(team.tracker ?? false)
  const [idle, setIdle] = useState(String(team.task_idle_days ?? 7))
  const [repeat, setRepeat] = useState(String(team.task_idle_repeat_days ?? 1))
  const save = useMutation({
    mutationFn: () =>
      call(
        api.PATCH('/api/team/{team}', {
          params: { path: { team: team.slug } },
          body: {
            name: name.trim(),
            slug: slug.trim(),
            turn_limit: Number(limit),
            tracker,
            task_idle_days: Number(idle),
            task_idle_repeat_days: Number(repeat),
          },
        }),
      ),
    onSuccess: (saved) => {
      void queryClient.invalidateQueries({ queryKey: ['team'] })
      void queryClient.invalidateQueries({ queryKey: ['teams'] })
      void queryClient.invalidateQueries({ queryKey: ['topics'] })
      if (saved.slug !== team.slug) void navigate(teamPath(saved.slug), { replace: true })
    },
  })
  const limitNumber = Number(limit)
  const days = (value: string) => Number.isInteger(Number(value)) && Number(value) >= 1 && Number(value) <= 365
  const valid =
    name.trim() && slug.trim() && Number.isInteger(limitNumber) && limitNumber >= 1 && limitNumber <= 100 && days(idle) && days(repeat)
  const changed =
    name.trim() !== team.name ||
    slug.trim() !== team.slug ||
    limitNumber !== team.turn_limit ||
    tracker !== (team.tracker ?? false) ||
    Number(idle) !== (team.task_idle_days ?? 7) ||
    Number(repeat) !== (team.task_idle_repeat_days ?? 1)
  return (
    <Card>
      <CardHeader title={t('team.settings')} />
      <form
        className="flex flex-col gap-3 px-4 py-3"
        onSubmit={(event) => {
          event.preventDefault()
          if (valid && !readOnly) save.mutate()
        }}
      >
        <fieldset disabled={readOnly} className="flex flex-col gap-3">
        <Field label={t('team.name')}>
          <Input value={name} onChange={(event) => setName(event.target.value)} maxLength={100} required />
        </Field>
        <Field label={t('team.slug')} hint={t('team.slugHint')}>
          <Input
            value={slug}
            onChange={(event) => setSlug(event.target.value.toLowerCase())}
            maxLength={40}
            pattern="[a-z0-9]([a-z0-9-]*[a-z0-9])?"
            className="font-mono"
            required
          />
        </Field>
        <Field label={t('team.turnLimit')} hint={t('team.turnLimitHint')}>
          <Input
            type="number"
            min={1}
            max={100}
            value={limit}
            onChange={(event) => setLimit(event.target.value)}
            className="w-28"
            required
          />
        </Field>
        <label className="flex items-start gap-2 text-sm">
          <input type="checkbox" checked={tracker} onChange={(event) => setTracker(event.target.checked)} className="mt-0.5" />
          <span>
            <span className="font-medium">{t('team.tracker')}</span>
            <span className="block text-stone-500 dark:text-stone-400">{t('team.trackerHint')}</span>
          </span>
        </label>
        <Field label={t('team.taskIdleDays')} hint={t('team.taskIdleDaysHint')}>
          <Input type="number" min={1} max={365} value={idle} onChange={(event) => setIdle(event.target.value)} className="w-28" required />
        </Field>
        <Field label={t('team.taskIdleRepeatDays')} hint={t('team.taskIdleRepeatDaysHint')}>
          <Input type="number" min={1} max={365} value={repeat} onChange={(event) => setRepeat(event.target.value)} className="w-28" required />
        </Field>
        </fieldset>
        <ErrorNote>
          {save.error && (save.error instanceof ApiError && save.error.status === 409 ? t('team.slugTaken') : errorText(save.error, t))}
        </ErrorNote>
        {save.isSuccess && !changed && <p className="text-sm text-emerald-700 dark:text-emerald-400">{t('common.saved')}</p>}
        {!readOnly && (
          <div>
            <Button type="submit" size="sm" variant="primary" disabled={save.isPending || !valid || !changed}>
              {t('common.save')}
            </Button>
          </div>
        )}
      </form>
    </Card>
  )
}

/** The Team's settings page: general, the tracker, its stages and board, invitations. */
export function TeamSettingsPage() {
  const { t } = useTranslation()
  const slug = useParams().team ?? ''
  const team = useTeam(slug)
  if (team.isPending) return <Page><Loading /></Page>
  if (team.error || !team.data) {
    return (
      <Page title={t('team.settings')}>
        <ErrorNote>{errorText(team.error, t)}</ErrorNote>
      </Page>
    )
  }
  const data = team.data
  const owner = data.role === 'owner'
  return (
    <TeamPageFrame team={data} current="settings" title={t('team.settings')}>
      {!owner && (
        <div className="mb-5">
          <Notice>{t('team.settingsReadOnly')}</Notice>
        </div>
      )}
      <div className="grid gap-5 lg:grid-cols-2">
        <div className="flex min-w-0 flex-col gap-5">
          <GeneralSettings
            key={`${data.name}-${data.slug}-${data.turn_limit}-${data.tracker}-${data.task_idle_days}-${data.task_idle_repeat_days}`}
            team={data}
            readOnly={!owner}
          />
          {owner && <InviteCard team={data} />}
        </div>
        <div className="flex min-w-0 flex-col gap-5">
          {data.tracker ? <TrackerSettings team={data} readOnly={!owner} /> : <Notice>{t('team.trackerOff')}</Notice>}
        </div>
      </div>
    </TeamPageFrame>
  )
}
