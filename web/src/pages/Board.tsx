import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams, useSearchParams } from 'react-router'

import { api, call, promisesPath, teamPath, topicPath, type Card as CardData } from '../api/client'
import { useBoard, useTasks, useTeam, type BoardFilter } from '../api/queries'
import { Page } from '../components/Layout'
import { Badge, Card, CardHeader, Empty, ErrorNote, Loading, Select } from '../components/ui'
import { errorText } from '../lib/format'

/** The board's filters live in the address, so a link keeps them (decision 0032). */
function useBoardFilter(): [BoardFilter, (next: BoardFilter) => void] {
  const [params, setParams] = useSearchParams()
  const promise = Number(params.get('promise'))
  const filter: BoardFilter = {
    area: params.get('area') ?? undefined,
    assignee: params.get('assignee') ?? undefined,
    promise: promise > 0 ? promise : undefined,
  }
  const set = (next: BoardFilter) => {
    const updated = new URLSearchParams()
    if (next.area) updated.set('area', next.area)
    if (next.assignee) updated.set('assignee', next.assignee)
    if (next.promise) updated.set('promise', String(next.promise))
    setParams(updated, { replace: true })
  }
  return [filter, set]
}

/** Whose move it is, in a line (decision 0033). */
function Move({ card }: { card: CardData }) {
  const { t } = useTranslation()
  if (!card.move) return null
  const tone = card.move === 'external' ? 'text-sky-700 dark:text-sky-400' : card.move === 'assistant' ? 'text-stone-500 dark:text-stone-400' : 'text-amber-700 dark:text-amber-400'
  return <span className={`text-xs ${tone}`}>{t(`board.move.${card.move}`, { who: card.move_who ?? '' })}</span>
}

function BoardCard({
  card,
  draggable,
  onDragStart,
  onDrop,
}: {
  card: CardData
  draggable: boolean
  onDragStart: () => void
  onDrop: () => void
}) {
  const { t } = useTranslation()
  const [over, setOver] = useState(false)
  return (
    <li
      draggable={draggable}
      onDragStart={(event) => {
        event.dataTransfer.effectAllowed = 'move'
        onDragStart()
      }}
      onDragOver={(event) => {
        if (!draggable) return
        event.preventDefault()
        setOver(true)
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(event) => {
        event.preventDefault()
        setOver(false)
        onDrop()
      }}
      className={`rounded-md border bg-white shadow-sm dark:bg-stone-900 ${over ? 'border-amber-500' : 'border-stone-200 dark:border-stone-800'} ${draggable ? 'cursor-grab' : ''}`}
    >
      <Link to={topicPath(card.team, card.number, 'task')} className="flex flex-col gap-1.5 p-3" draggable={false}>
        <div className="flex items-start gap-2">
          <span className="shrink-0 pt-px font-mono text-xs text-stone-500 dark:text-stone-400">{card.ref}</span>
          <span className="min-w-0 text-sm font-medium break-words">{card.title}</span>
        </div>
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-stone-500 dark:text-stone-400">
          <Badge tone="stone">{card.stage}</Badge>
          <span>{card.assignee ?? t('task.unassigned')}</span>
          {card.parent && card.promise?.number !== card.parent && <span className="font-mono">⊂ T-{card.parent}</span>}
        </div>
        {card.promise && (
          <span className="truncate text-xs text-emerald-700 dark:text-emerald-400" title={card.promise.title}>
            ◇ {card.promise.title}
          </span>
        )}
        <Move card={card} />
      </Link>
    </li>
  )
}

export function BoardPage() {
  const { t } = useTranslation()
  const slug = useParams().team ?? ''
  const [filter, setFilter] = useBoardFilter()
  const team = useTeam(slug)
  const board = useBoard(slug, filter)
  const promises = useTasks(slug, { type: 'promise' })
  const queryClient = useQueryClient()
  const [dragged, setDragged] = useState<CardData | null>(null)
  const order = useMutation({
    mutationFn: ({ number, before }: { number: number; before: number }) =>
      call(
        api.POST('/api/team/{team}/task/{number}/order', {
          params: { path: { team: slug, number } },
          body: { before },
        }),
      ),
    onSettled: () => void queryClient.invalidateQueries({ queryKey: ['board', slug] }),
  })
  const canOrder = Boolean(team.data?.tracker)

  return (
    <Page
      title={t('board.title')}
      aside={
        team.data && (
          <span className="flex flex-wrap gap-x-3 text-sm">
            <Link to={teamPath(slug)} className="text-amber-700 hover:underline dark:text-amber-400">
              {team.data.name}
            </Link>
            <Link to={promisesPath(slug)} className="text-amber-700 hover:underline dark:text-amber-400">
              {t('promises.title')}
            </Link>
          </span>
        )
      }
      wide
    >
      <div className="mb-4 flex flex-wrap gap-2">
        <div className="w-full sm:w-52">
          <Select value={filter.area ?? ''} onChange={(event) => setFilter({ ...filter, area: event.target.value || undefined })} aria-label={t('topic.area')}>
            <option value="">{t('team.allAreas')}</option>
            {team.data?.areas.map((area) => (
              <option key={area.slug} value={area.slug}>
                {area.name}
              </option>
            ))}
          </Select>
        </div>
        <div className="w-full sm:w-44">
          <Select value={filter.assignee ?? ''} onChange={(event) => setFilter({ ...filter, assignee: event.target.value || undefined })} aria-label={t('task.assignee')}>
            <option value="">{t('board.anyone')}</option>
            <option value="-">{t('task.unassigned')}</option>
            {team.data?.members
              .filter((member) => member.pseudonym)
              .map((member) => (
                <option key={member.pseudonym} value={member.pseudonym ?? ''}>
                  {member.pseudonym}
                </option>
              ))}
          </Select>
        </div>
        <div className="w-full sm:w-64">
          <Select
            value={filter.promise ? String(filter.promise) : ''}
            onChange={(event) => setFilter({ ...filter, promise: Number(event.target.value) || undefined })}
            aria-label={t('task.promise')}
          >
            <option value="">{t('board.anyPromise')}</option>
            {promises.data?.map((promise) => (
              <option key={promise.number} value={promise.number}>
                {promise.ref} {promise.title}
              </option>
            ))}
          </Select>
        </div>
      </div>
      {board.isPending && <Loading />}
      <ErrorNote>{board.error ? errorText(board.error, t) : order.error ? errorText(order.error, t) : null}</ErrorNote>
      {board.data && (
        <div className="flex gap-3 overflow-x-auto pb-4">
          {board.data.columns.map((column, index) => {
            const cards = board.data.cards.filter((card) => card.column === index)
            return (
              <Card key={column.name} className="flex w-72 shrink-0 flex-col self-start">
                <CardHeader title={`${column.name} · ${cards.length}`} />
                {cards.length === 0 ? (
                  <Empty>{column.rule === 'waiting' ? t('board.noneWaiting') : t('board.empty')}</Empty>
                ) : (
                  <ol className="flex flex-col gap-2 p-2">
                    {cards.map((card) => (
                      <BoardCard
                        key={card.number}
                        card={card}
                        draggable={canOrder}
                        onDragStart={() => setDragged(card)}
                        onDrop={() => {
                          // Order within a status only: a stage is moved by the assignee's Assistant.
                          if (dragged && dragged.number !== card.number && dragged.column === card.column) {
                            order.mutate({ number: dragged.number, before: card.number })
                          }
                          setDragged(null)
                        }}
                      />
                    ))}
                  </ol>
                )}
              </Card>
            )
          })}
        </div>
      )}
      {canOrder && <p className="text-xs text-stone-500 dark:text-stone-400">{t('board.hint')}</p>}
    </Page>
  )
}
