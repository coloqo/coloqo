import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router'

import { api, call, planPath, topicPath, type PlanDetail, type PlanRow } from '../api/client'
import { usePlan, usePlans, useTeam } from '../api/queries'
import { Page } from '../components/Layout'
import { TeamPageFrame } from '../components/TeamBar'
import { Badge, Button, Card, CardHeader, Empty, ErrorNote, Input, Loading } from '../components/ui'
import { errorText } from '../lib/format'

type Tone = 'stone' | 'amber' | 'green' | 'red'

const STATE_TONE: Record<string, Tone> = { draft: 'stone', approved: 'green', closed: 'amber' }
const MARK_TONE: Record<string, Tone> = { planned: 'stone', found: 'amber', off_plan: 'red' }

/** The numbers written as T-12, 15, t-3 in a line. */
function numbers(text: string): number[] {
  return [...text.matchAll(/\d+/g)].map((match) => Number(match[0]))
}

/** A Team's plans and a form for a new draft (decision 0037). */
export function PlansPage() {
  const { t } = useTranslation()
  const slug = useParams().team ?? ''
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const team = useTeam(slug)
  const plans = usePlans(slug)
  const [name, setName] = useState('')
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')
  const create = useMutation({
    mutationFn: () =>
      call(
        api.POST('/api/team/{team}/plan', {
          params: { path: { team: slug } },
          body: { name, period_start: start, period_end: end },
        }),
      ),
    onSuccess: (plan) => {
      void queryClient.invalidateQueries({ queryKey: ['plans', slug] })
      void navigate(planPath(slug, plan.number))
    },
  })
  if (team.isPending) return <Page><Loading /></Page>
  if (team.error || !team.data) {
    return (
      <Page title={t('plans.title')}>
        <ErrorNote>{errorText(team.error, t)}</ErrorNote>
      </Page>
    )
  }
  return (
    <TeamPageFrame team={team.data} current="plans" title={t('plans.title')}>
      <div className="flex flex-col gap-5">
        <Card>
          <CardHeader title={t('plans.list')} />
          {plans.isPending && <Loading />}
          <ErrorNote>{plans.error ? errorText(plans.error, t) : null}</ErrorNote>
          {plans.data && plans.data.length === 0 && <Empty>{t('plans.none')}</Empty>}
          <ul className="divide-y divide-stone-200 dark:divide-stone-800">
            {(plans.data ?? []).map((plan) => (
              <li key={plan.number} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-4 py-3 text-sm">
                <Link to={planPath(slug, plan.number)} className="font-medium hover:underline">
                  {plan.name}
                </Link>
                <span className="text-stone-500 dark:text-stone-400">
                  {plan.period_start} — {plan.period_end}
                </span>
                <Badge tone={STATE_TONE[plan.state]}>{t(`plans.state.${plan.state}`)}</Badge>
                <span className="text-xs text-stone-500 dark:text-stone-400">{t('plans.rows', { count: plan.rows })}</span>
              </li>
            ))}
          </ul>
        </Card>
        <Card>
          <CardHeader title={t('plans.new')} />
          <form
            className="flex flex-wrap items-end gap-3 px-4 py-3"
            onSubmit={(event) => {
              event.preventDefault()
              create.mutate()
            }}
          >
            <label className="flex flex-col gap-1 text-sm">
              {t('plans.name')}
              <Input value={name} onChange={(event) => setName(event.target.value)} placeholder={t('plans.namePlaceholder')} required />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              {t('plans.start')}
              <Input type="date" value={start} onChange={(event) => setStart(event.target.value)} required />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              {t('plans.end')}
              <Input type="date" value={end} onChange={(event) => setEnd(event.target.value)} required />
            </label>
            <Button type="submit" variant="primary" disabled={create.isPending}>
              {t('plans.create')}
            </Button>
            <ErrorNote>{create.error ? errorText(create.error, t) : null}</ErrorNote>
          </form>
        </Card>
      </div>
    </TeamPageFrame>
  )
}

/** One row of a plan: the task, its mark, and what a human does with it (decision 0037). */
function Row({ plan, row, depth }: { plan: PlanDetail; row: PlanRow; depth: number }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState<'dropped' | 'postpone' | null>(null)
  const [text, setText] = useState('')
  const task = row.task
  const path = { team: task.team, number: plan.number, task_number: task.number }
  const done = (fresh: PlanDetail) => {
    setEditing(null)
    queryClient.setQueryData(['plan', task.team, plan.number], fresh)
  }
  const change = useMutation({
    mutationFn: (body: { mark?: 'found' | 'off_plan'; dropped?: string; postponed?: boolean; reason?: string }) =>
      call(api.PATCH('/api/team/{team}/plan/{number}/item/{task_number}', { params: { path }, body })),
    onSuccess: done,
  })
  const remove = useMutation({
    mutationFn: () => call(api.DELETE('/api/team/{team}/plan/{number}/item/{task_number}', { params: { path } })),
    onSuccess: done,
  })
  const open = plan.state !== 'closed'
  const work = task.type !== 'promise'
  const offPlan = row.mark === 'off_plan'
  return (
    <li
      style={{ paddingLeft: `${depth * 1.25 + 1}rem` }}
      className={`flex flex-col gap-1.5 border-t border-stone-200 py-2.5 pr-4 text-sm dark:border-stone-800 ${task.category === 'finished' ? 'opacity-70' : ''}`}
    >
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        {task.type === 'promise' && <Badge tone="green">{t('task.promise')}</Badge>}
        <Link to={topicPath(task.team, task.number, 'task')} className="font-mono text-xs text-stone-500 hover:underline dark:text-stone-400">
          {task.ref}
        </Link>
        <Link to={topicPath(task.team, task.number, 'task')} className={`min-w-0 break-words hover:underline ${task.type === 'promise' ? 'font-semibold' : 'font-medium'}`}>
          {task.title}
        </Link>
        <Badge tone="stone">{task.stage}</Badge>
        {work && <span className="text-xs text-stone-500 dark:text-stone-400">{task.assignee ?? t('task.unassigned')}</span>}
        {work && <Badge tone={MARK_TONE[row.mark]}>{t(`plans.mark.${row.mark}`)}</Badge>}
        {row.carried_from && <span className="text-xs text-stone-500 dark:text-stone-400">{t('plans.carried', { name: row.carried_from })}</span>}
        {row.postponed && <Badge tone="amber">{t('plans.postponed')}</Badge>}
        {row.result && <Badge tone={row.result === 'done' ? 'green' : 'stone'}>{t(`plans.result.${row.result}`)}</Badge>}
      </div>
      {row.postponed && <p className="text-xs text-stone-600 dark:text-stone-400">{t('plans.postponedBecause', { reason: row.postponed_reason, who: row.postponed_by ?? '' })}</p>}
      {work && offPlan && (
        <p className={`text-xs ${row.dropped ? 'text-stone-600 dark:text-stone-400' : 'font-medium text-red-700 dark:text-red-400'}`}>
          {row.dropped ? t('plans.drops', { text: row.dropped }) : t('plans.dropsUnnamed')}
        </p>
      )}
      {editing ? (
        <form
          className="flex flex-wrap items-center gap-2"
          onSubmit={(event) => {
            event.preventDefault()
            change.mutate(editing === 'dropped' ? { dropped: text } : { postponed: true, reason: text })
          }}
        >
          <Input
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder={editing === 'dropped' ? t('plans.dropsPlaceholder') : t('plans.reasonPlaceholder')}
            className="min-w-64 flex-1 py-1"
            autoFocus
            required={editing === 'postpone'}
          />
          <Button size="sm" variant="primary" type="submit" disabled={change.isPending}>
            {t('common.save')}
          </Button>
          <Button size="sm" variant="ghost" type="button" onClick={() => setEditing(null)}>
            {t('common.cancel')}
          </Button>
        </form>
      ) : (
        open &&
        work && (
          <div className="flex flex-wrap items-center gap-2">
            {plan.state === 'draft' && (
              <Button size="sm" variant="ghost" onClick={() => remove.mutate()} disabled={remove.isPending}>
                {t('plans.remove')}
              </Button>
            )}
            {plan.state === 'approved' && row.mark !== 'planned' && (
              <Button size="sm" variant="ghost" onClick={() => change.mutate({ mark: offPlan ? 'found' : 'off_plan' })}>
                {offPlan ? t('plans.makeFound') : t('plans.makeOffPlan')}
              </Button>
            )}
            {offPlan && (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => {
                  setText(row.dropped)
                  setEditing('dropped')
                }}
              >
                {t('plans.nameDrops')}
              </Button>
            )}
            {task.category !== 'finished' &&
              (row.postponed ? (
                <Button size="sm" variant="ghost" onClick={() => change.mutate({ postponed: false })}>
                  {t('plans.resume')}
                </Button>
              ) : (
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => {
                    setText('')
                    setEditing('postpone')
                  }}
                >
                  {t('plans.postpone')}
                </Button>
              ))}
          </div>
        )
      )}
      <ErrorNote>{change.error ? errorText(change.error, t) : remove.error ? errorText(remove.error, t) : null}</ErrorNote>
    </li>
  )
}

/** The rows grouped as a plan reads: each promise with its work, then the work outside promises. */
function grouped(plan: PlanDetail): { promise: PlanRow | null; rows: { row: PlanRow; depth: number }[] }[] {
  const byNumber = new Map(plan.items.map((row) => [row.task.number, row]))
  const promiseOf = (row: PlanRow): PlanRow | null => {
    let parent = row.task.parent
    const seen = new Set<number>()
    while (parent && !seen.has(parent)) {
      seen.add(parent)
      const above = byNumber.get(parent)
      if (!above) return null
      if (above.task.type === 'promise') return above
      parent = above.task.parent
    }
    return null
  }
  const depthOf = (row: PlanRow): number => (row.task.parent && byNumber.get(row.task.parent)?.task.type === 'task' ? 2 : 1)
  const promises = plan.items.filter((row) => row.task.type === 'promise')
  const groups = promises.map((promise) => ({
    promise,
    rows: plan.items
      .filter((row) => row.task.type !== 'promise' && promiseOf(row)?.task.number === promise.task.number)
      .map((row) => ({ row, depth: depthOf(row) })),
  }))
  const outside = plan.items
    .filter((row) => row.task.type !== 'promise' && promiseOf(row) === null)
    .map((row) => ({ row, depth: row.task.parent && byNumber.has(row.task.parent) ? 1 : 0 }))
  return [...groups, { promise: null, rows: outside }]
}

/** A plan: its state, what it came to, its promises with their work, and the work outside them. */
export function PlanPage() {
  const { t } = useTranslation()
  const params = useParams()
  const slug = params.team ?? ''
  const number = Number(params.number)
  const queryClient = useQueryClient()
  const team = useTeam(slug)
  const plan = usePlan(slug, number)
  const [adding, setAdding] = useState('')
  // Today in the Team's time zone, as the server compares it with a plan's last day (0037).
  const [now] = useState(() => new Date())
  const refresh = (fresh: PlanDetail) => {
    queryClient.setQueryData(['plan', slug, number], fresh)
    void queryClient.invalidateQueries({ queryKey: ['plans', slug] })
  }
  const add = useMutation({
    mutationFn: (tasks: number[]) =>
      call(api.POST('/api/team/{team}/plan/{number}/item', { params: { path: { team: slug, number } }, body: { tasks } })),
    onSuccess: (fresh) => {
      setAdding('')
      refresh(fresh)
    },
  })
  const approve = useMutation({
    mutationFn: () => call(api.POST('/api/team/{team}/plan/{number}/approve', { params: { path: { team: slug, number } } })),
    onSuccess: refresh,
  })
  const close = useMutation({
    mutationFn: () => call(api.POST('/api/team/{team}/plan/{number}/close', { params: { path: { team: slug, number } } })),
    onSuccess: refresh,
  })
  if (team.isPending || plan.isPending) return <Page><Loading /></Page>
  if (team.error || !team.data || plan.error || !plan.data) {
    return (
      <Page title={t('plans.title')}>
        <ErrorNote>{errorText(team.error ?? plan.error, t)}</ErrorNote>
      </Page>
    )
  }
  const data = plan.data
  const summary = data.summary
  const today = new Intl.DateTimeFormat('en-CA', { timeZone: team.data.time_zone ?? 'UTC' }).format(now)
  return (
    <TeamPageFrame team={team.data} current="plans" title={data.name} sub>
      <div className="flex flex-col gap-5">
        <Card>
          <div className="flex flex-col gap-3 px-4 py-4">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
              <span className="text-sm text-stone-600 dark:text-stone-300">
                {data.period_start} — {data.period_end}
              </span>
              <Badge tone={STATE_TONE[data.state]}>{t(`plans.state.${data.state}`)}</Badge>
              {data.approved_by && <span className="text-xs text-stone-500 dark:text-stone-400">{t('plans.approvedBy', { who: data.approved_by })}</span>}
              {data.state === 'draft' && (
                <Button size="sm" variant="primary" onClick={() => approve.mutate()} disabled={approve.isPending}>
                  {t('plans.approve')}
                </Button>
              )}
              {data.state === 'approved' && today > data.period_end && (
                <Button size="sm" variant="primary" onClick={() => close.mutate()} disabled={close.isPending}>
                  {t('plans.close')}
                </Button>
              )}
            </div>
            <p className="text-sm text-stone-600 dark:text-stone-400">
              {t('plans.summary', {
                planned: summary.planned,
                done: summary.planned_done,
                postponed: summary.postponed,
                found: summary.found,
                offPlan: summary.off_plan,
              })}
              {summary.dropped_unnamed > 0 && <span className="ml-2 font-medium text-red-700 dark:text-red-400">{t('plans.unnamed', { count: summary.dropped_unnamed })}</span>}
            </p>
            {data.state !== 'closed' && (
              <form
                className="flex flex-wrap items-center gap-2"
                onSubmit={(event) => {
                  event.preventDefault()
                  add.mutate(numbers(adding))
                }}
              >
                <Input value={adding} onChange={(event) => setAdding(event.target.value)} placeholder={t('plans.addPlaceholder')} className="min-w-64 flex-1 py-1" />
                <Button size="sm" type="submit" disabled={add.isPending || numbers(adding).length === 0}>
                  {t('plans.add')}
                </Button>
                {data.previous_unfinished.length > 0 && (
                  <Button size="sm" variant="ghost" type="button" onClick={() => add.mutate(data.previous_unfinished)} disabled={add.isPending}>
                    {t('plans.takePrevious', { tasks: data.previous_unfinished.map((n) => `T-${n}`).join(', ') })}
                  </Button>
                )}
              </form>
            )}
            <ErrorNote>{[add.error, approve.error, close.error].find(Boolean) ? errorText([add.error, approve.error, close.error].find(Boolean), t) : null}</ErrorNote>
          </div>
        </Card>
        {data.items.length === 0 && (
          <Card>
            <Empty>{t('plans.empty')}</Empty>
          </Card>
        )}
        {grouped(data)
          .filter((group) => group.promise || group.rows.length > 0)
          .map((group) => (
            <Card key={group.promise?.task.number ?? 'outside'}>
              <CardHeader title={group.promise ? group.promise.task.title : t('plans.outside')} />
              <ul>
                {group.promise && <Row plan={data} row={group.promise} depth={0} />}
                {group.rows.map(({ row, depth }) => (
                  <Row key={row.task.number} plan={data} row={row} depth={depth} />
                ))}
              </ul>
            </Card>
          ))}
      </div>
    </TeamPageFrame>
  )
}
