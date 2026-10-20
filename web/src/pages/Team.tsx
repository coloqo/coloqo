import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams, useSearchParams } from 'react-router'

import {
  ApiError,
  api,
  areaPath,
  call,
  teamPath,
  topicPath,
  type Area,
  type Invite,
  type TeamDetail,
} from '../api/client'
import { useTeam, useTopics } from '../api/queries'
import { AddresseeSelect } from '../components/AddresseeSelect'
import { Page } from '../components/Layout'
import { Time } from '../components/Time'
import { RoleBadge, TopicList } from '../components/Topics'
import {
  Button,
  Card,
  CardHeader,
  CopyButton,
  Empty,
  ErrorNote,
  Field,
  Input,
  Loading,
  Select,
  Textarea,
} from '../components/ui'
import { errorText } from '../lib/format'

type StatusFilter = 'open' | 'closed' | 'all'

/** The Area is part of the address, `/team/acme/area/releases`; the status is a query (0025). */
function useTeamFilter(team: string) {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const area = useParams().area
  const statusParam = params.get('status')
  const status: StatusFilter = statusParam === 'closed' || statusParam === 'all' ? statusParam : 'open'
  const set = (next: { area?: string | null; status?: StatusFilter }) => {
    const updated = new URLSearchParams(params)
    if (next.status !== undefined) {
      if (next.status === 'open') updated.delete('status')
      else updated.set('status', next.status)
    }
    const chosen = next.area === undefined ? area : next.area
    const path = chosen ? areaPath(team, chosen) : teamPath(team)
    const query = updated.toString()
    void navigate(query ? `${path}?${query}` : path, { replace: true })
  }
  return { area, status, set }
}

function NewTopic({ team, defaultArea, onClose }: { team: TeamDetail; defaultArea?: string; onClose: () => void }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [area, setArea] = useState(defaultArea ?? team.areas[0]?.slug ?? '')
  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const [issue, setIssue] = useState('')
  const [to, setTo] = useState('')
  const create = useMutation({
    mutationFn: () =>
      call(
        api.POST('/api/team/{team}/topic', {
          params: { path: { team: team.slug } },
          body: { area, title: title.trim(), body, issue: issue.trim(), to: to || null },
        }),
      ),
    onSuccess: (topic) => {
      void queryClient.invalidateQueries({ queryKey: ['topics', team.slug] })
      void queryClient.invalidateQueries({ queryKey: ['team', team.slug] })
      void navigate(topicPath(topic.team, topic.number))
    },
  })
  return (
    <Card className="mb-5">
      <CardHeader title={t('team.newTopic')}>
        <Button variant="ghost" size="sm" onClick={onClose}>
          {t('common.cancel')}
        </Button>
      </CardHeader>
      <form
        className="flex flex-col gap-4 p-4"
        onSubmit={(event) => {
          event.preventDefault()
          if (area && title.trim() && body.trim()) create.mutate()
        }}
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={t('topic.area')}>
            <Select value={area} onChange={(event) => setArea(event.target.value)} required>
              {team.areas.map((option) => (
                <option key={option.slug} value={option.slug}>
                  {option.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t('topic.addressee')} hint={t('team.addresseeHint')}>
            <AddresseeSelect members={team.members} value={to} onChange={setTo} />
          </Field>
        </div>
        <Field label={t('topic.title')} hint={t('team.titleHint')}>
          <Input value={title} onChange={(event) => setTitle(event.target.value)} maxLength={200} required />
        </Field>
        <Field label={t('team.firstMessage')} hint={t('compose.markdownHint')}>
          <Textarea value={body} onChange={(event) => setBody(event.target.value)} rows={6} maxLength={50000} required />
        </Field>
        <Field label={t('topic.issue')} hint={t('team.issueHint')}>
          <Input value={issue} onChange={(event) => setIssue(event.target.value)} maxLength={300} placeholder="ACME-42" />
        </Field>
        <ErrorNote>{create.error && errorText(create.error, t)}</ErrorNote>
        <div>
          <Button type="submit" variant="primary" disabled={create.isPending || !title.trim() || !body.trim()}>
            {t('team.openTopic')}
          </Button>
        </div>
      </form>
    </Card>
  )
}

function Topics({ team }: { team: TeamDetail }) {
  const { t } = useTranslation()
  const filter = useTeamFilter(team.slug)
  const [creating, setCreating] = useState(false)
  const topics = useTopics(team.slug, {
    area: filter.area,
    status: filter.status === 'all' ? undefined : filter.status,
  })
  const statuses: StatusFilter[] = ['open', 'closed', 'all']
  return (
    <>
      {creating && (
        <NewTopic team={team} defaultArea={filter.area} onClose={() => setCreating(false)} />
      )}
      <Card>
        <CardHeader title={t('team.topics')}>
          {!creating && team.areas.length > 0 && (
            <Button size="sm" variant="primary" onClick={() => setCreating(true)}>
              {t('team.newTopic')}
            </Button>
          )}
        </CardHeader>
        <div className="flex flex-wrap items-center gap-2 border-b border-stone-200 px-4 py-2.5 dark:border-stone-800">
          <div className="w-full sm:w-64">
            <Select
              value={filter.area ?? ''}
              onChange={(event) => filter.set({ area: event.target.value || null })}
              aria-label={t('topic.area')}
            >
              <option value="">{t('team.allAreas')}</option>
              {team.areas.map((area) => (
                <option key={area.slug} value={area.slug}>
                  {area.name}
                </option>
              ))}
            </Select>
          </div>
          <div className="inline-flex rounded-md border border-stone-300 p-0.5 dark:border-stone-700" role="group">
            {statuses.map((status) => (
              <button
                key={status}
                type="button"
                aria-pressed={filter.status === status}
                onClick={() => filter.set({ status })}
                className={`rounded px-2.5 py-1 text-sm ${
                  filter.status === status
                    ? 'bg-stone-900 text-stone-50 dark:bg-stone-100 dark:text-stone-900'
                    : 'text-stone-600 hover:bg-stone-100 dark:text-stone-400 dark:hover:bg-stone-800'
                }`}
              >
                {t(`team.filter.${status}`)}
              </button>
            ))}
          </div>
        </div>
        {team.areas.length === 0 && (
          <Empty>{team.role === 'owner' ? t('team.noAreasOwner') : t('team.noAreasMember')}</Empty>
        )}
        {topics.isPending && <Loading />}
        <ErrorNote>{topics.error && errorText(topics.error, t)}</ErrorNote>
        {team.areas.length > 0 && topics.data?.length === 0 && <Empty>{t('team.noTopics')}</Empty>}
        {topics.data && topics.data.length > 0 && <TopicList topics={topics.data} />}
      </Card>
    </>
  )
}

function AreaForm({
  team,
  area,
  onDone,
}: {
  team: string
  area?: Area
  onDone: () => void
}) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const viewed = useParams().area
  const [name, setName] = useState(area?.name ?? '')
  const [description, setDescription] = useState(area?.description ?? '')
  const [slug, setSlug] = useState(area?.slug ?? '')
  const save = useMutation({
    mutationFn: () => {
      const body = { name: name.trim(), description: description.trim(), slug: slug.trim() || null }
      return area
        ? call(api.PATCH('/api/team/{team}/area/{area}', { params: { path: { team, area: area.slug } }, body }))
        : call(api.POST('/api/team/{team}/area', { params: { path: { team } }, body }))
    },
    onSuccess: (saved) => {
      void queryClient.invalidateQueries({ queryKey: ['team', team] })
      void queryClient.invalidateQueries({ queryKey: ['topics', team] })
      if (area && viewed === area.slug && saved.slug !== area.slug) {
        void navigate(areaPath(team, saved.slug), { replace: true })
      }
      onDone()
    },
  })
  const error = save.error
  return (
    <form
      className="flex flex-col gap-3 px-4 py-3"
      onSubmit={(event) => {
        event.preventDefault()
        if (name.trim()) save.mutate()
      }}
    >
      <Field label={t('area.name')}>
        <Input value={name} onChange={(event) => setName(event.target.value)} maxLength={100} required autoFocus />
      </Field>
      <Field label={t('area.description')} hint={t('area.descriptionHint')}>
        <Textarea value={description} onChange={(event) => setDescription(event.target.value)} rows={3} maxLength={2000} />
      </Field>
      <Field label={t('area.slug')} hint={area ? t('area.slugHint') : t('area.slugNewHint')}>
        <Input
          value={slug}
          onChange={(event) => setSlug(event.target.value.toLowerCase())}
          maxLength={40}
          pattern="[a-z0-9]([a-z0-9-]*[a-z0-9])?"
          className="font-mono"
        />
      </Field>
      <ErrorNote>
        {error && (error instanceof ApiError && error.status === 409 ? t('area.taken') : errorText(error, t))}
      </ErrorNote>
      <div className="flex gap-2">
        <Button type="submit" variant="primary" size="sm" disabled={save.isPending || !name.trim()}>
          {area ? t('common.save') : t('common.create')}
        </Button>
        <Button size="sm" variant="ghost" onClick={onDone}>
          {t('common.cancel')}
        </Button>
      </div>
    </form>
  )
}

function Areas({ team }: { team: TeamDetail }) {
  const { t } = useTranslation()
  const filter = useTeamFilter(team.slug)
  const [editing, setEditing] = useState<string | 'new' | null>(null)
  const owner = team.role === 'owner'
  return (
    <Card>
      <CardHeader title={t('team.areas')}>
        {owner && editing !== 'new' && (
          <Button size="sm" onClick={() => setEditing('new')}>
            {t('team.newArea')}
          </Button>
        )}
      </CardHeader>
      {editing === 'new' && <AreaForm team={team.slug} onDone={() => setEditing(null)} />}
      {team.areas.length === 0 && editing !== 'new' && (
        <Empty>{owner ? t('team.noAreasOwner') : t('team.noAreasMember')}</Empty>
      )}
      <ul className="divide-y divide-stone-200 dark:divide-stone-800">
        {team.areas.map((area) =>
          editing === area.slug ? (
            <li key={area.slug}>
              <AreaForm team={team.slug} area={area} onDone={() => setEditing(null)} />
            </li>
          ) : (
            <li key={area.slug} className={filter.area === area.slug ? 'bg-amber-50/60 dark:bg-amber-950/20' : undefined}>
              <div className="flex items-start gap-2 px-4 py-3">
                <button
                  type="button"
                  className="flex min-w-0 flex-1 flex-col items-start gap-0.5 text-left"
                  onClick={() => filter.set({ area: filter.area === area.slug ? null : area.slug })}
                  title={t('team.filterByArea')}
                >
                  <span className="font-medium">{area.name}</span>
                  {area.description && (
                    <span className="text-sm whitespace-pre-line text-stone-600 dark:text-stone-400">{area.description}</span>
                  )}
                  <span className="text-xs text-stone-500 dark:text-stone-400">
                    {t('area.openTopics', { count: area.open_topics })}
                  </span>
                </button>
                {owner && (
                  <Button size="sm" variant="ghost" onClick={() => setEditing(area.slug)}>
                    {t('common.edit')}
                  </Button>
                )}
              </div>
            </li>
          ),
        )}
      </ul>
    </Card>
  )
}

function Members({ team }: { team: TeamDetail }) {
  const { t } = useTranslation()
  return (
    <Card>
      <CardHeader title={t('team.members')} />
      <ul className="divide-y divide-stone-200 dark:divide-stone-800">
        {team.members.map((member) => (
          <li key={member.pseudonym} className="flex flex-col gap-1.5 px-4 py-3">
            <div className="flex items-center justify-between gap-2">
              <span className="font-medium">{member.pseudonym ?? t('team.noName')}</span>
              <RoleBadge role={member.role} />
            </div>
            {member.assistants.length === 0 ? (
              <span className="text-xs text-stone-500 dark:text-stone-400">{t('team.noAssistants')}</span>
            ) : (
              <ul className="flex flex-col gap-0.5">
                {member.assistants.map((assistant) => (
                  <li key={assistant.key} className="flex flex-wrap items-baseline justify-between gap-x-2 text-sm">
                    <span
                      className="text-stone-700 dark:text-stone-300"
                      title={assistant.session_id ? t('sessions.id', { id: assistant.session_id }) : undefined}
                    >
                      {assistant.name}
                    </span>
                    {assistant.last_seen_at && (
                      <span className="text-xs text-stone-500 dark:text-stone-400">
                        {t('team.lastSeen')} <Time value={assistant.last_seen_at} />
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>
    </Card>
  )
}

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

function TeamSettings({ team }: { team: TeamDetail }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [name, setName] = useState(team.name)
  const [slug, setSlug] = useState(team.slug)
  const [limit, setLimit] = useState(String(team.turn_limit))
  const save = useMutation({
    mutationFn: () =>
      call(
        api.PATCH('/api/team/{team}', {
          params: { path: { team: team.slug } },
          body: { name: name.trim(), slug: slug.trim(), turn_limit: Number(limit) },
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
  const valid = name.trim() && slug.trim() && Number.isInteger(limitNumber) && limitNumber >= 1 && limitNumber <= 100
  const changed = name.trim() !== team.name || slug.trim() !== team.slug || limitNumber !== team.turn_limit
  return (
    <Card>
      <CardHeader title={t('team.settings')} />
      <form
        className="flex flex-col gap-3 px-4 py-3"
        onSubmit={(event) => {
          event.preventDefault()
          if (valid) save.mutate()
        }}
      >
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
        <ErrorNote>
          {save.error && (save.error instanceof ApiError && save.error.status === 409 ? t('team.slugTaken') : errorText(save.error, t))}
        </ErrorNote>
        {save.isSuccess && !changed && <p className="text-sm text-emerald-700 dark:text-emerald-400">{t('common.saved')}</p>}
        <div>
          <Button type="submit" size="sm" variant="primary" disabled={save.isPending || !valid || !changed}>
            {t('common.save')}
          </Button>
        </div>
      </form>
    </Card>
  )
}

export function TeamPage() {
  const { t } = useTranslation()
  const { team: slug = '', area } = useParams()
  const team = useTeam(slug)
  const navigate = useNavigate()
  const current = team.data?.slug
  useEffect(() => {
    // A former slug answers with the current one: the address follows it (decision 0025).
    if (current && current !== slug) {
      const path = area ? areaPath(current, area) : teamPath(current)
      void navigate(`${path}${window.location.search}`, { replace: true })
    }
  }, [current, slug, area, navigate])

  if (team.isPending) return <Page><Loading /></Page>
  if (team.error || !team.data) {
    return (
      <Page title={t('team.title')}>
        <ErrorNote>{errorText(team.error, t)}</ErrorNote>
      </Page>
    )
  }
  const data = team.data
  return (
    <Page
      title={
        <span className="flex flex-wrap items-center gap-3">
          {data.name}
          <RoleBadge role={data.role} />
        </span>
      }
    >
      <div className="grid gap-5 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <div className="min-w-0">
          <Topics team={data} />
        </div>
        <div className="flex min-w-0 flex-col gap-5">
          <Areas team={data} />
          <Members team={data} />
          {data.role === 'owner' && (
            <>
              <InviteCard team={data} />
              <TeamSettings key={`${data.name}-${data.slug}-${data.turn_limit}`} team={data} />
            </>
          )}
        </div>
      </div>
    </Page>
  )
}
