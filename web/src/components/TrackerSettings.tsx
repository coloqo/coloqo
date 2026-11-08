import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { api, call, type Schemas, type TeamDetail, type Workflow } from '../api/client'
import { useBoard, useWorkflows } from '../api/queries'
import { errorText } from '../lib/format'
import { Button, Card, CardHeader, ErrorNote, Input, Loading, Select } from './ui'

type Kind = Schemas['StageKind']

/** The kinds a task's stages may take, in the order of the built-in workflow (decision 0032). */
const TASK_KINDS: Kind[] = ['backlog', 'analysis', 'design', 'documentation', 'agreement', 'code', 'review', 'delivery', 'done', 'cancelled']

type Row = { name: string; kind: Kind; was: string | null }

/** The owner renames, reorders, adds and removes the stages of the Team's task workflow. */
function WorkflowEditor({ team, workflow }: { team: string; workflow: Workflow }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const initial: Row[] = workflow.stages.map((stage) => ({ name: stage.name, kind: stage.kind, was: stage.name }))
  const [rows, setRows] = useState<Row[]>(initial)
  const [moves, setMoves] = useState<Record<string, string>>({})
  const [kind, setKind] = useState<Kind>('review')
  const removed = initial.filter((row) => !rows.some((kept) => kept.was === row.was))
  const save = useMutation({
    mutationFn: () =>
      call(
        api.PUT('/api/team/{team}/workflow/{type_}', {
          params: { path: { team, type_: 'task' } },
          body: { stages: rows.map((row) => ({ name: row.name.trim(), kind: row.kind, was: row.was })), moves },
        }),
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['workflows', team] })
      void queryClient.invalidateQueries({ queryKey: ['board', team] })
      void queryClient.invalidateQueries({ queryKey: ['task', team] })
    },
  })
  const swap = (index: number, other: number) => {
    const next = [...rows]
    ;[next[index], next[other]] = [next[other], next[index]]
    setRows(next)
  }
  return (
    <form
      className="flex flex-col gap-2 px-4 py-3"
      onSubmit={(event) => {
        event.preventDefault()
        save.mutate()
      }}
    >
      <p className="text-sm text-stone-600 dark:text-stone-400">{t('tracker.workflowLead')}</p>
      <ol className="flex flex-col gap-1.5">
        {rows.map((row, index) => (
          <li key={`${row.was ?? 'new'}-${index}`} className="flex items-center gap-1.5">
            <Input
              value={row.name}
              onChange={(event) => setRows(rows.map((r, i) => (i === index ? { ...r, name: event.target.value } : r)))}
              maxLength={60}
              className="min-w-0 flex-1 py-1"
              aria-label={t('tracker.stageName')}
            />
            <span className="w-24 shrink-0 truncate text-xs text-stone-500 dark:text-stone-400" title={t(`tracker.kind.${row.kind}`)}>
              {t(`tracker.kind.${row.kind}`)}
            </span>
            <Button size="sm" variant="ghost" onClick={() => swap(index, index - 1)} disabled={index === 0} aria-label={t('tracker.up')}>
              ↑
            </Button>
            <Button size="sm" variant="ghost" onClick={() => swap(index, index + 1)} disabled={index === rows.length - 1} aria-label={t('tracker.down')}>
              ↓
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setRows(rows.filter((_, i) => i !== index))} aria-label={t('tracker.remove')}>
              ✕
            </Button>
          </li>
        ))}
      </ol>
      <div className="flex items-center gap-2">
        <Select value={kind} onChange={(event) => setKind(event.target.value as Kind)} className="py-1" aria-label={t('tracker.newKind')}>
          {TASK_KINDS.map((option) => (
            <option key={option} value={option}>
              {t(`tracker.kind.${option}`)}
            </option>
          ))}
        </Select>
        <Button size="sm" onClick={() => setRows([...rows, { name: t(`tracker.kind.${kind}`), kind, was: null }])}>
          {t('tracker.addStage')}
        </Button>
      </div>
      {removed.length > 0 && (
        <div className="flex flex-col gap-1.5 rounded-md bg-amber-50 p-2 text-sm dark:bg-amber-950/30">
          <span>{t('tracker.movesLead')}</span>
          {removed.map((row) => (
            <label key={row.was} className="flex items-center gap-2">
              <span className="w-32 shrink-0 truncate">{row.was}</span>
              <span>→</span>
              <Select value={moves[row.was ?? ''] ?? ''} onChange={(event) => setMoves({ ...moves, [row.was ?? '']: event.target.value })} className="py-1">
                <option value="">{t('tracker.noMove')}</option>
                {rows.map((target) => (
                  <option key={target.name} value={target.name}>
                    {target.name}
                  </option>
                ))}
              </Select>
            </label>
          ))}
        </div>
      )}
      <ErrorNote>{save.error ? errorText(save.error, t) : null}</ErrorNote>
      {save.isSuccess && <p className="text-sm text-emerald-700 dark:text-emerald-400">{t('common.saved')}</p>}
      <div>
        <Button type="submit" size="sm" variant="primary" disabled={save.isPending}>
          {t('common.save')}
        </Button>
      </div>
    </form>
  )
}

type ColumnRow = { name: string; rule: 'stages' | 'waiting'; stages: string[] }

/** The owner groups the stages into the board's columns, the statuses (decision 0032). */
function ColumnsEditor({ team, stages, columns }: { team: string; stages: string[]; columns: ColumnRow[] }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [rows, setRows] = useState<ColumnRow[]>(columns)
  const save = useMutation({
    mutationFn: () =>
      call(api.PUT('/api/team/{team}/board', { params: { path: { team } }, body: { columns: rows } })),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['board', team] }),
  })
  const update = (index: number, change: Partial<ColumnRow>) => setRows(rows.map((row, i) => (i === index ? { ...row, ...change } : row)))
  const toggle = (index: number, stage: string) => {
    // A stage stands in one column: picking it here takes it out of the others.
    setRows(
      rows.map((row, i) =>
        i === index
          ? { ...row, stages: row.stages.includes(stage) ? row.stages.filter((s) => s !== stage) : [...row.stages, stage] }
          : { ...row, stages: row.stages.filter((s) => s !== stage) },
      ),
    )
  }
  const swap = (index: number, other: number) => {
    const next = [...rows]
    ;[next[index], next[other]] = [next[other], next[index]]
    setRows(next)
  }
  return (
    <form
      className="flex flex-col gap-3 px-4 py-3"
      onSubmit={(event) => {
        event.preventDefault()
        save.mutate()
      }}
    >
      <p className="text-sm text-stone-600 dark:text-stone-400">{t('tracker.columnsLead')}</p>
      {rows.map((row, index) => (
        <div key={index} className="flex flex-col gap-1.5 rounded-md border border-stone-200 p-2 dark:border-stone-800">
          <div className="flex items-center gap-1.5">
            <Input value={row.name} onChange={(event) => update(index, { name: event.target.value })} maxLength={60} className="min-w-0 flex-1 py-1" aria-label={t('tracker.columnName')} />
            <Select
              value={row.rule}
              onChange={(event) => update(index, { rule: event.target.value as ColumnRow['rule'], stages: [] })}
              className="w-36 py-1"
              aria-label={t('tracker.columnRule')}
            >
              <option value="stages">{t('tracker.byStages')}</option>
              <option value="waiting">{t('tracker.byWaiting')}</option>
            </Select>
            <Button size="sm" variant="ghost" onClick={() => swap(index, index - 1)} disabled={index === 0} aria-label={t('tracker.up')}>
              ↑
            </Button>
            <Button size="sm" variant="ghost" onClick={() => swap(index, index + 1)} disabled={index === rows.length - 1} aria-label={t('tracker.down')}>
              ↓
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setRows(rows.filter((_, i) => i !== index))} aria-label={t('tracker.remove')}>
              ✕
            </Button>
          </div>
          {row.rule === 'stages' ? (
            <div className="flex flex-wrap gap-x-3 gap-y-1">
              {stages.map((stage) => (
                <label key={stage} className="inline-flex items-center gap-1 text-sm">
                  <input type="checkbox" checked={row.stages.includes(stage)} onChange={() => toggle(index, stage)} />
                  {stage}
                </label>
              ))}
            </div>
          ) : (
            <span className="text-xs text-stone-500 dark:text-stone-400">{t('tracker.waitingHint')}</span>
          )}
        </div>
      ))}
      <div>
        <Button size="sm" onClick={() => setRows([...rows, { name: t('tracker.newColumn'), rule: 'stages', stages: [] }])}>
          {t('tracker.addColumn')}
        </Button>
      </div>
      <ErrorNote>{save.error ? errorText(save.error, t) : null}</ErrorNote>
      {save.isSuccess && <p className="text-sm text-emerald-700 dark:text-emerald-400">{t('common.saved')}</p>}
      <div>
        <Button type="submit" size="sm" variant="primary" disabled={save.isPending}>
          {t('common.save')}
        </Button>
      </div>
    </form>
  )
}

/** The tracker's settings for the Team's owner: its workflow and its board's columns. */
export function TrackerSettings({ team }: { team: TeamDetail }) {
  const { t } = useTranslation()
  const workflows = useWorkflows(team.slug)
  const board = useBoard(team.slug, {})
  const workflow = workflows.data?.find((w) => w.type === 'task')
  return (
    <>
      <Card>
        <CardHeader title={t('tracker.workflow')} />
        {workflows.isPending && <Loading />}
        {workflow && <WorkflowEditor key={workflow.stages.map((s) => s.name).join('|')} team={team.slug} workflow={workflow} />}
      </Card>
      <Card>
        <CardHeader title={t('tracker.columns')} />
        {board.isPending && <Loading />}
        {board.data && workflow && (
          <ColumnsEditor
            key={board.data.columns.map((c) => `${c.name}:${c.stages.join(',')}`).join('|')}
            team={team.slug}
            stages={workflow.stages.map((s) => s.name)}
            columns={board.data.columns.map((c) => ({ name: c.name, rule: c.rule, stages: c.stages }))}
          />
        )}
      </Card>
    </>
  )
}
