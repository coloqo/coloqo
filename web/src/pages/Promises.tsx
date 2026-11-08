import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router'

import { boardPath, topicPath, type Task } from '../api/client'
import { useTasks, useTeam } from '../api/queries'
import { Page } from '../components/Layout'
import { TeamPageFrame } from '../components/TeamBar'
import { Progress } from '../components/Task'
import { Badge, Card, CardHeader, Empty, ErrorNote, Loading } from '../components/ui'
import { errorText } from '../lib/format'

/** A task under a promise, with its subtasks. */
function TaskRow({ task, tree, depth }: { task: Task; tree: Map<number, Task[]>; depth: number }) {
  const { t } = useTranslation()
  const finished = task.category === 'finished'
  return (
    <>
      <li style={{ paddingLeft: `${depth * 1.25 + 1}rem` }} className={`flex flex-wrap items-center gap-x-3 gap-y-1 py-2 pr-4 text-sm ${finished ? 'opacity-60' : ''}`}>
        <Link to={topicPath(task.team, task.number, 'task')} className="font-mono text-xs text-stone-500 hover:underline dark:text-stone-400">
          {task.ref}
        </Link>
        <Link to={topicPath(task.team, task.number, 'task')} className="min-w-0 font-medium break-words hover:underline">
          {task.title}
        </Link>
        <Badge tone="stone">{task.stage}</Badge>
        <span className="text-xs text-stone-500 dark:text-stone-400">{task.assignee ?? t('task.unassigned')}</span>
      </li>
      {(tree.get(task.number) ?? []).map((child) => (
        <TaskRow key={child.number} task={child} tree={tree} depth={depth + 1} />
      ))}
    </>
  )
}

/** A promise, a goal when it holds promises (decision 0031), with what it holds. */
function PromiseNode({ promise, tree, depth }: { promise: Task; tree: Map<number, Task[]>; depth: number }) {
  const { t } = useTranslation()
  const held = tree.get(promise.number) ?? []
  const goal = held.some((child) => child.type === 'promise')
  const finished = promise.category === 'finished'
  return (
    <>
      <li style={{ paddingLeft: `${depth * 1.25 + 1}rem` }} className={`flex flex-col gap-1 border-t border-stone-200 py-3 pr-4 dark:border-stone-800 ${finished ? 'opacity-70' : ''}`}>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <Badge tone={goal ? 'amber' : 'green'}>{goal ? t('promises.goal') : t('task.promise')}</Badge>
          <Link to={topicPath(promise.team, promise.number, 'task')} className="font-mono text-xs text-stone-500 hover:underline dark:text-stone-400">
            {promise.ref}
          </Link>
          <Link to={topicPath(promise.team, promise.number, 'task')} className="min-w-0 font-semibold break-words hover:underline">
            {promise.title}
          </Link>
          <Badge tone="stone">{promise.stage}</Badge>
        </div>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-stone-500 dark:text-stone-400">
          {(promise.period_start || promise.period_end) && (
            <span>
              {promise.period_start ?? '…'} — {promise.period_end ?? '…'}
            </span>
          )}
          <span>{promise.assignee ?? t('task.unassigned')}</span>
          {promise.progress && promise.progress.total > 0 && <Progress done={promise.progress.done} total={promise.progress.total} />}
          <Link to={`${boardPath(promise.team)}?promise=${promise.number}`} className="text-amber-700 hover:underline dark:text-amber-400">
            {t('promises.onBoard')}
          </Link>
        </div>
      </li>
      {held.map((child) =>
        child.type === 'promise' ? (
          <PromiseNode key={child.number} promise={child} tree={tree} depth={depth + 1} />
        ) : (
          <TaskRow key={child.number} task={child} tree={tree} depth={depth + 1} />
        ),
      )}
    </>
  )
}

export function PromisesPage() {
  const { t } = useTranslation()
  const slug = useParams().team ?? ''
  const team = useTeam(slug)
  const tasks = useTasks(slug)
  const all = tasks.data ?? []
  const byNumber = new Map(all.map((task) => [task.number, task]))
  const tree = new Map<number, Task[]>()
  for (const task of all) {
    if (task.parent) tree.set(task.parent, [...(tree.get(task.parent) ?? []), task])
  }
  const roots = all.filter((task) => task.type === 'promise' && !(task.parent && byNumber.get(task.parent)?.type === 'promise'))
  if (team.isPending) return <Page><Loading /></Page>
  if (team.error || !team.data) {
    return (
      <Page title={t('promises.title')}>
        <ErrorNote>{errorText(team.error, t)}</ErrorNote>
      </Page>
    )
  }
  return (
    <TeamPageFrame team={team.data} current="promises" title={t('promises.title')}>
      <Card>
        <CardHeader title={t('promises.tree')} />
        {tasks.isPending && <Loading />}
        <ErrorNote>{tasks.error ? errorText(tasks.error, t) : null}</ErrorNote>
        {tasks.data && roots.length === 0 && <Empty>{t('promises.none')}</Empty>}
        <ul>
          {roots.map((promise) => (
            <PromiseNode key={promise.number} promise={promise} tree={tree} depth={0} />
          ))}
        </ul>
      </Card>
    </TeamPageFrame>
  )
}
