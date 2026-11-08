import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import { api, call, topicPath, type TaskDetail, type TeamDetail, type TimelineEntry } from '../api/client'
import { issueLink } from '../lib/format'
import { Markdown } from './Markdown'
import { Time } from './Time'
import { Badge, Button, Card, CardHeader, ErrorNote, Notice, Select, Textarea } from './ui'

/** The text of a timeline entry, for the feed and for a task without a Topic. */
export function TimelineText({ entry }: { entry: TimelineEntry }) {
  const { t } = useTranslation()
  const data = entry.data as Record<string, string | number | boolean | null>
  switch (entry.kind) {
    case 'created':
      return <>{data.source ? t('timeline.createdFrom', { source: `T-${data.source}` }) : t('timeline.created')}</>
    case 'assigned':
      return <>{data.to ? t('timeline.assigned', { to: data.to }) : t('timeline.unassigned')}</>
    case 'described':
      return <>{t('timeline.described')}</>
    case 'linked':
      return <>{t('timeline.linked', { key: data.key })}</>
    case 'retitled':
      return <>{t('timeline.retitled', { to: data.to })}</>
    case 'area':
      return <>{t('timeline.area', { to: data.to })}</>
    case 'period':
      return <>{t('timeline.period')}</>
    case 'stage':
      if (data.migrated) return <>{t('timeline.migrated', { to: data.to })}</>
      if (data.workflow) return <>{t('timeline.workflow', { from: data.from, to: data.to })}</>
      return <>{t('timeline.stage', { to: data.to })}</>
    case 'skipped':
      return <>{t('timeline.skipped', { stage: data.stage, reason: data.reason })}</>
    case 'waiting':
      return <>{t('timeline.waiting', { what: data.what })}</>
    case 'resumed':
      return <>{t('timeline.resumed')}</>
    case 'closed':
      return <>{t('timeline.closed', { to: data.to })}</>
    default:
      return <>{entry.kind}</>
  }
}

/** A timeline entry as a service line in the feed, apart from the conversation. */
export function TimelineLine({ entry }: { entry: TimelineEntry }) {
  return (
    <li className="my-2 flex items-center justify-center gap-2 text-center text-xs text-stone-500 dark:text-stone-400">
      <span>⚙</span>
      <span>
        {entry.assistant ?? entry.author ?? 'Coloqo'} · <TimelineText entry={entry} />
      </span>
      <Time value={entry.created_at} />
    </li>
  )
}

/** The task's fields: type, stage, assignee, wait, links, its promise, period, progress, outcome. */
export function TaskPanel({ task, team }: { task: TaskDetail; team?: TeamDetail }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const finished = task.category === 'finished'
  const assign = useMutation({
    mutationFn: (assignee: string) =>
      call(
        api.POST('/api/team/{team}/task/{number}/assign', {
          params: { path: { team: task.team, number: task.number } },
          body: { assignee: assignee || null },
        }),
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['task', task.team] })
      void queryClient.invalidateQueries({ queryKey: ['topic', task.team] })
      void queryClient.invalidateQueries({ queryKey: ['board', task.team] })
    },
  })
  const row = (label: string, value: React.ReactNode) => (
    <div className="flex gap-2 text-sm">
      <dt className="w-32 shrink-0 text-stone-500 dark:text-stone-400">{label}</dt>
      <dd className="min-w-0 break-words">{value}</dd>
    </div>
  )
  return (
    <Card>
      <CardHeader title={task.type === 'promise' ? t('task.promise') : t('task.task')} />
      <dl className="flex flex-col gap-2 px-4 py-3">
        {row(t('task.stage'), <Badge tone={finished ? 'stone' : 'amber'}>{task.stage}</Badge>)}
        {row(
          t('task.assignee'),
          team?.tracker && !finished ? (
            <Select
              value={task.assignee ?? ''}
              onChange={(event) => assign.mutate(event.target.value)}
              disabled={assign.isPending}
              aria-label={t('task.assignee')}
              className="py-1"
            >
              <option value="">{t('task.unassigned')}</option>
              {team.members
                .filter((member) => member.pseudonym)
                .map((member) => (
                  <option key={member.pseudonym} value={member.pseudonym ?? ''}>
                    {member.pseudonym}
                  </option>
                ))}
            </Select>
          ) : (
            (task.assignee ?? t('task.unassigned'))
          ),
        )}
        {task.waiting && row(t('task.waiting'), task.waiting)}
        {task.links.length > 0 &&
          row(
            t('task.links'),
            <span className="flex flex-wrap gap-x-2">
              {task.links.map((link) => {
                const href = link.url || issueLink(link.key)
                return href ? (
                  <a key={link.key} href={href} target="_blank" rel="noreferrer noopener" className="text-amber-700 hover:underline dark:text-amber-400">
                    {link.key}
                  </a>
                ) : (
                  <span key={link.key}>{link.key}</span>
                )
              })}
            </span>,
          )}
        {task.parent &&
          row(
            t('task.parent'),
            <Link to={topicPath(task.team, task.parent, 'task')} className="font-mono text-amber-700 hover:underline dark:text-amber-400">
              T-{task.parent}
            </Link>,
          )}
        {task.source &&
          row(
            t('task.source'),
            <Link to={topicPath(task.team, task.source, 'task')} className="font-mono text-amber-700 hover:underline dark:text-amber-400">
              T-{task.source}
            </Link>,
          )}
        {(task.period_start || task.period_end) &&
          row(t('task.period'), `${task.period_start ?? '…'} — ${task.period_end ?? '…'}`)}
        {task.progress && row(t('task.progress'), <Progress done={task.progress.done} total={task.progress.total} />)}
        {task.outcome && row(t('task.outcome'), <Markdown text={task.outcome} />)}
      </dl>
      <ErrorNote>{assign.error ? String(assign.error) : null}</ErrorNote>
      <div className="px-4 pb-3">
        <Notice>{t('settle.task')}</Notice>
      </div>
    </Card>
  )
}

/** Done against all, as a bar and a count. */
export function Progress({ done, total }: { done: number; total: number }) {
  const share = total > 0 ? Math.round((done / total) * 100) : 0
  return (
    <span className="inline-flex items-center gap-2">
      <span className="inline-block h-1.5 w-24 overflow-hidden rounded-full bg-stone-200 dark:bg-stone-800">
        <span className="block h-full bg-emerald-500" style={{ width: `${share}%` }} />
      </span>
      <span className="text-xs text-stone-500 dark:text-stone-400">
        {done}/{total}
      </span>
    </span>
  )
}

/** The task's description, editable, with every former text kept in its history (0033). */
export function Description({ task }: { task: TaskDetail }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [text, setText] = useState(task.description)
  const [history, setHistory] = useState(false)
  const versions = task.timeline.filter((entry) => entry.kind === 'described')
  const save = useMutation({
    mutationFn: () =>
      call(
        api.PATCH('/api/team/{team}/task/{number}', {
          params: { path: { team: task.team, number: task.number } },
          body: { description: text },
        }),
      ),
    onSuccess: () => {
      setEditing(false)
      void queryClient.invalidateQueries({ queryKey: ['task', task.team] })
    },
  })
  return (
    <Card>
      <CardHeader title={t('task.description')}>
        {!editing && (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              setText(task.description)
              setEditing(true)
            }}
          >
            {t('common.edit')}
          </Button>
        )}
      </CardHeader>
      <div className="flex flex-col gap-3 px-4 py-3">
        {editing ? (
          <form
            className="flex flex-col gap-2"
            onSubmit={(event) => {
              event.preventDefault()
              save.mutate()
            }}
          >
            <Textarea value={text} onChange={(event) => setText(event.target.value)} rows={8} maxLength={50000} autoFocus />
            <ErrorNote>{save.error ? String(save.error) : null}</ErrorNote>
            <div className="flex gap-2">
              <Button type="submit" size="sm" variant="primary" disabled={save.isPending}>
                {t('common.save')}
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
                {t('common.cancel')}
              </Button>
            </div>
          </form>
        ) : task.description ? (
          <Markdown text={task.description} />
        ) : (
          <p className="text-sm text-stone-500 dark:text-stone-400">{t('task.noDescription')}</p>
        )}
        {versions.length > 1 && (
          <div>
            <Button size="sm" variant="ghost" onClick={() => setHistory(!history)}>
              {t('task.history', { count: versions.length })}
            </Button>
            {history && (
              <ol className="mt-2 flex flex-col gap-3 border-l-2 border-stone-200 pl-3 dark:border-stone-800">
                {[...versions].reverse().map((version, index) => (
                  <li key={index} className="flex flex-col gap-1">
                    <span className="text-xs text-stone-500 dark:text-stone-400">
                      {version.assistant ?? version.author} · <Time value={version.created_at} />
                    </span>
                    <Markdown text={String(version.data.text ?? '')} />
                  </li>
                ))}
              </ol>
            )}
          </div>
        )}
      </div>
    </Card>
  )
}
