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
  type TeamDetail,
} from '../api/client'
import { useTeam, useTopics } from '../api/queries'
import { AddresseeSelect } from '../components/AddresseeSelect'
import { AgentIcon } from '../components/AgentIcon'
import { Page } from '../components/Layout'
import { PresenceText } from '../components/Presence'
import { TeamPageFrame } from '../components/TeamBar'
import { RoleBadge, TopicList } from '../components/Topics'
import {
  Button,
  Card,
  CardHeader,
  Empty,
  ErrorNote,
  Field,
  Input,
  Loading,
  Select,
  Textarea,
} from '../components/ui'
import { sessionHint } from '../lib/agents'
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
  // A person in the web opens a free Topic: a task is opened by an Assistant taking work (0031).
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
          body: { area, title: title.trim(), body, issue: issue.trim(), to: to || null, free: true },
        }),
      ),
    onSuccess: (topic) => {
      void queryClient.invalidateQueries({ queryKey: ['topics', team.slug] })
      void queryClient.invalidateQueries({ queryKey: ['team', team.slug] })
      void navigate(topicPath(topic.team, topic.number, topic.kind))
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

/** Planning in the web: a task in the backlog, maybe assigned (decision 0032). */
function NewTask({ team, defaultArea, onClose }: { team: TeamDetail; defaultArea?: string; onClose: () => void }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [area, setArea] = useState(defaultArea ?? team.areas[0]?.slug ?? '')
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [assignee, setAssignee] = useState('')
  const [promise, setPromise] = useState(false)
  const create = useMutation({
    mutationFn: () =>
      call(
        api.POST('/api/team/{team}/task', {
          params: { path: { team: team.slug } },
          body: {
            area,
            title: title.trim(),
            description,
            assignee: assignee || null,
            type: promise ? 'promise' : 'task',
          },
        }),
      ),
    onSuccess: (task) => {
      void queryClient.invalidateQueries({ queryKey: ['tasks', team.slug] })
      void queryClient.invalidateQueries({ queryKey: ['board', team.slug] })
      void navigate(topicPath(task.team, task.number, 'task'))
    },
  })
  return (
    <Card className="mb-5">
      <CardHeader title={t('team.newTask')}>
        <Button variant="ghost" size="sm" onClick={onClose}>
          {t('common.cancel')}
        </Button>
      </CardHeader>
      <form
        className="flex flex-col gap-4 p-4"
        onSubmit={(event) => {
          event.preventDefault()
          if (area && title.trim()) create.mutate()
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
          <Field label={t('task.assignee')}>
            <Select value={assignee} onChange={(event) => setAssignee(event.target.value)}>
              <option value="">{t('task.unassigned')}</option>
              {team.members
                .filter((member) => member.pseudonym)
                .map((member) => (
                  <option key={member.pseudonym} value={member.pseudonym ?? ''}>
                    {member.pseudonym}
                  </option>
                ))}
            </Select>
          </Field>
        </div>
        <Field label={t('topic.title')}>
          <Input value={title} onChange={(event) => setTitle(event.target.value)} maxLength={200} required />
        </Field>
        <Field label={t('task.description')} hint={t('compose.markdownHint')}>
          <Textarea value={description} onChange={(event) => setDescription(event.target.value)} rows={5} maxLength={50000} />
        </Field>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={promise} onChange={(event) => setPromise(event.target.checked)} />
          {t('team.isPromise')}
        </label>
        <ErrorNote>{create.error && errorText(create.error, t)}</ErrorNote>
        <div>
          <Button type="submit" variant="primary" disabled={create.isPending || !title.trim()}>
            {t('team.createTask')}
          </Button>
        </div>
      </form>
    </Card>
  )
}

function Topics({ team, kind }: { team: TeamDetail; kind: 'task' | 'free' }) {
  const { t } = useTranslation()
  const filter = useTeamFilter(team.slug)
  const [creating, setCreating] = useState(false)
  const topics = useTopics(team.slug, {
    area: filter.area,
    status: filter.status === 'all' ? undefined : filter.status,
    kind,
  })
  const canCreate = kind === 'free' || team.tracker
  const statuses: StatusFilter[] = ['open', 'closed', 'all']
  return (
    <>
      {creating &&
        (kind === 'free' ? (
          <NewTopic team={team} defaultArea={filter.area} onClose={() => setCreating(false)} />
        ) : (
          <NewTask team={team} defaultArea={filter.area} onClose={() => setCreating(false)} />
        ))}
      <Card className={kind === 'free' ? 'mt-5' : undefined}>
        <CardHeader title={kind === 'task' ? t('team.tasks') : t('team.freeTopics')}>
          {!creating && canCreate && team.areas.length > 0 && (
            <Button size="sm" variant={kind === 'task' ? 'primary' : 'secondary'} onClick={() => setCreating(true)}>
              {kind === 'task' ? t('team.newTask') : t('team.newTopic')}
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
        {team.areas.length > 0 && topics.data?.length === 0 && (
          <Empty>{kind === 'task' ? t('team.noTasks') : t('team.noFreeTopics')}</Empty>
        )}
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
                  <li
                    key={assistant.key}
                    className={`flex flex-wrap items-center justify-between gap-x-2 text-sm ${assistant.online ? '' : 'opacity-60'}`}
                  >
                    <span
                      className="inline-flex items-center gap-1.5 text-stone-700 dark:text-stone-300"
                      title={assistant.session_id ? sessionHint(t, assistant.agent ?? 'claude', assistant.session_id) : undefined}
                    >
                      <AgentIcon agent={assistant.agent ?? 'claude'} />
                      {assistant.name}
                    </span>
                    <PresenceText online={assistant.online ?? false} lastSeen={assistant.last_seen_at} />
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
    <TeamPageFrame team={data} current="topics" title={t('team.topicsPage')}>
      <div className="grid gap-5 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <div className="min-w-0">
          <Topics team={data} kind="task" />
          <Topics team={data} kind="free" />
        </div>
        <div className="flex min-w-0 flex-col gap-5">
          <Areas team={data} />
          <Members team={data} />
        </div>
      </div>
    </TeamPageFrame>
  )
}
