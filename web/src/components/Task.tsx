import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Suspense, lazy, useLayoutEffect, useRef, useState } from 'react'
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
    // A delivery and the delivery a task works for (decision 0036).
    case 'delivery':
      return <>{t('timeline.delivery')}</>
    case 'works_for':
      return <>{data.to ? t('timeline.worksFor', { to: `T-${data.to}` }) : t('timeline.worksForNone')}</>
    // A move to another parent, in the task and in both parents' timelines (decision 0034).
    case 'parent':
      return <>{data.to ? t('timeline.parent', { to: `T-${data.to}` }) : t('timeline.parentNone')}</>
    case 'child_in':
      return (
        <>
          {data.from
            ? t('timeline.childInFrom', { task: `T-${data.task}`, from: `T-${data.from}` })
            : t('timeline.childIn', { task: `T-${data.task}` })}
        </>
      )
    case 'child_out':
      return (
        <>
          {data.to
            ? t('timeline.childOutTo', { task: `T-${data.task}`, to: `T-${data.to}` })
            : t('timeline.childOut', { task: `T-${data.task}` })}
        </>
      )
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
              onChange={(event) => {
                const to = event.target.value
                // Handing over a task in work: its assignee's Assistant stops moving it (0031).
                if (
                  task.category === 'in_progress' &&
                  task.assignee &&
                  to !== task.assignee &&
                  !window.confirm(t('task.handOver', { ref: task.ref, from: task.assignee, to: to || t('task.unassigned') }))
                ) {
                  event.target.value = task.assignee
                  return
                }
                assign.mutate(to)
              }}
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

/** The editor and CodeMirror come only when a description is edited: a chunk of their own. */
const MarkdownEditor = lazy(() => import('./MarkdownEditor').then((module) => ({ default: module.MarkdownEditor })))

/** How many lines a long text shows before "Show it all": it keeps what follows within reach. */
const FOLDED_LINES = 4

/** A long text shown in part, fading out, with a button to show it all and to fold it again. */
function Folded({ children }: { children: React.ReactNode }) {
  const { t } = useTranslation()
  const box = useRef<HTMLDivElement>(null)
  const [long, setLong] = useState(false)
  const [open, setOpen] = useState(false)
  const [height, setHeight] = useState(0)
  const [fade, setFade] = useState(0)
  useLayoutEffect(() => {
    if (!box.current) return
    // Four lines of the text's own line height in full, then two more fading out, so it shows
    // that the text goes on; a text barely longer is shown whole.
    const line = parseFloat(getComputedStyle(box.current).lineHeight) || 24
    const folded = Math.round(line * (FOLDED_LINES + 2))
    setHeight(folded)
    setFade(Math.round(line * 2))
    setLong(box.current.scrollHeight > folded + line)
  }, [children])
  return (
    <div>
      <div
        ref={box}
        className="relative overflow-hidden"
        // The fade is a mask, so it suits the card's background in both themes.
        style={
          long && !open
            ? {
                maxHeight: height,
                maskImage: `linear-gradient(to bottom, black calc(100% - ${fade}px), transparent)`,
                WebkitMaskImage: `linear-gradient(to bottom, black calc(100% - ${fade}px), transparent)`,
              }
            : undefined
        }
      >
        {children}
      </div>
      {long && (
        <Button size="sm" variant="ghost" onClick={() => setOpen(!open)} className="mt-1">
          {open ? t('task.fold') : t('task.unfold')}
        </Button>
      )}
    </div>
  )
}

/**
 * The task's delivery: its meaning in the business's language (decision 0036). A task states its
 * own, edited here, or works for another's, shown as a link; the tasks working for its delivery
 * are listed. Links are set by an Assistant for now.
 */
export function Delivery({ task }: { task: TaskDetail }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [text, setText] = useState<string | null>(null)
  const save = useMutation({
    mutationFn: (value: string) =>
      call(
        api.PATCH('/api/team/{team}/task/{number}', {
          params: { path: { team: task.team, number: task.number } },
          body: { delivery: value },
        }),
      ),
    onSuccess: () => {
      setText(null)
      void queryClient.invalidateQueries({ queryKey: ['task', task.team] })
    },
  })
  const taskLink = (number: number) => (
    <Link key={number} to={topicPath(task.team, number, 'task')} className="font-mono text-amber-700 hover:underline dark:text-amber-400">
      T-{number}
    </Link>
  )
  return (
    <Card>
      <CardHeader title={t('task.delivery')} />
      <div className="flex flex-col gap-3 px-4 py-3 text-sm">
        {task.subtask && task.parent ? (
          <p className="text-stone-600 dark:text-stone-400">
            {t('task.subtaskWorksFor')} {taskLink(task.parent)}
          </p>
        ) : task.works_for ? (
          <p className="text-stone-600 dark:text-stone-400">
            {t('task.worksFor')} {taskLink(task.works_for)}
          </p>
        ) : text === null ? (
          <button type="button" onClick={() => setText(task.delivery ?? '')} className="cursor-text text-left">
            {task.delivery ? (
              <span className="whitespace-pre-wrap">{task.delivery}</span>
            ) : (
              <span className="text-stone-400 dark:text-stone-500">{t('task.deliveryPlaceholder')}</span>
            )}
          </button>
        ) : (
          <>
            <Textarea
              value={text}
              onChange={(event) => setText(event.target.value)}
              placeholder={t('task.deliveryPlaceholder')}
              rows={3}
              autoFocus
              aria-label={t('task.delivery')}
            />
            <div className="flex items-center gap-2">
              <Button size="sm" variant="primary" onClick={() => save.mutate(text)} disabled={save.isPending}>
                {t('common.save')}
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setText(null)}>
                {t('common.cancel')}
              </Button>
            </div>
            <ErrorNote>{save.error ? String(save.error) : null}</ErrorNote>
          </>
        )}
        {(task.working_for_it ?? []).length > 0 && (
          <p className="flex flex-wrap gap-x-2 text-stone-600 dark:text-stone-400">
            <span>{t('task.workingForIt')}</span>
            {(task.working_for_it ?? []).map(taskLink)}
          </p>
        )}
      </div>
    </Card>
  )
}

/**
 * The task's description, edited in place like Obsidian edits Markdown: the line under the
 * cursor shows its Markdown, the rest reads as rendered (the author, 2026-11-09). Save and cancel
 * appear once it changed; each saved text is kept in its history (decision 0033).
 */
export function Description({ task }: { task: TaskDetail }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [text, setText] = useState(task.description)
  const [base, setBase] = useState(task.description)
  const [history, setHistory] = useState(false)
  const [open, setOpen] = useState(false)
  const versions = task.timeline.filter((entry) => entry.kind === 'described')
  // A description changed elsewhere comes in unless this one has unsaved changes.
  if (task.description !== base && text === base) {
    setBase(task.description)
    setText(task.description)
  }
  const dirty = text !== base
  const save = useMutation({
    mutationFn: () =>
      call(
        api.PATCH('/api/team/{team}/task/{number}', {
          params: { path: { team: task.team, number: task.number } },
          body: { description: text },
        }),
      ),
    onSuccess: () => {
      setBase(text)
      void queryClient.invalidateQueries({ queryKey: ['task', task.team] })
    },
  })
  return (
    <Card>
      <CardHeader title={t('task.description')} />
      <div className="flex flex-col gap-3 px-4 py-3">
        {/* Folded until opened or edited: a long text keeps the conversation within reach. */}
        {open || dirty ? (
          <Suspense fallback={<Markdown text={text} />}>
            <MarkdownEditor value={text} onChange={setText} placeholder={t('task.descriptionPlaceholder')} />
          </Suspense>
        ) : (
          <div onClick={() => setOpen(true)} className="cursor-text">
            {task.description ? (
              <Folded>
                <Markdown text={task.description} />
              </Folded>
            ) : (
              <p className="text-sm text-stone-400 dark:text-stone-500">{t('task.descriptionPlaceholder')}</p>
            )}
          </div>
        )}
        {dirty && (
          <div className="flex items-center gap-2">
            <Button size="sm" variant="primary" onClick={() => save.mutate()} disabled={save.isPending}>
              {t('common.save')}
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setText(base)}>
              {t('common.cancel')}
            </Button>
            <ErrorNote>{save.error ? String(save.error) : null}</ErrorNote>
          </div>
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
