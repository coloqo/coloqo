import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams, useSearchParams } from 'react-router'

import { api, boardPath, call, topicPath, type Card as CardData } from '../api/client'
import { useBoard, useTasks, useTeam, type BoardFilter } from '../api/queries'
import { PersonAvatar } from '../components/Avatar'
import { Gear } from '../components/Gear'
import { Hourglass } from '../components/Hourglass'
import { Page } from '../components/Layout'
import { TeamPageFrame } from '../components/TeamBar'
import { BoardSettings } from '../components/TrackerSettings'
import { Badge, ErrorNote, Loading, Notice, Select } from '../components/ui'
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
  avatar,
  draggable,
  accepts,
  onDragStart,
  onDragEnd,
  onDrop,
  onAssignee,
}: {
  card: CardData
  avatar: string | null | undefined
  draggable: boolean
  /** A dragged card may be put above this one: it comes from the same column. */
  accepts: boolean
  onDragStart: () => void
  onDragEnd: () => void
  onDrop: () => void
  /** Show only this person's tasks; ``-`` for the unassigned. */
  onAssignee: (assignee: string) => void
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
      onDragEnd={onDragEnd}
      onDragOver={(event) => {
        // Not preventing the default leaves the browser's "no drop" cursor on another column.
        if (!draggable || !accepts) return
        event.preventDefault()
        setOver(true)
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(event) => {
        event.preventDefault()
        setOver(false)
        onDrop()
      }}
      className={`relative flex gap-2 rounded-md border p-3 shadow-sm ${
        // A waiting task reads apart at once: a cooler tone and an hourglass in its corner.
        card.waiting ? 'bg-sky-50 dark:bg-sky-950/40' : 'bg-white dark:bg-stone-900'
      } ${
        over ? 'border-amber-500' : card.waiting ? 'border-sky-200 dark:border-sky-800/70' : 'border-stone-200 dark:border-stone-800'
      } ${draggable ? 'cursor-grab' : ''}`}
    >
      {card.waiting && (
        <span className="absolute top-1.5 right-1.5 text-sky-600 dark:text-sky-400" title={t('board.move.external', { who: card.waiting })}>
          <Hourglass className="size-3.5" />
        </span>
      )}
      <Link to={topicPath(card.team, card.number, 'task')} className="flex min-w-0 flex-1 flex-col gap-1.5" draggable={false}>
        <div className="flex items-start gap-2">
          <span className="shrink-0 pt-px font-mono text-xs text-stone-500 dark:text-stone-400">{card.ref}</span>
          <span className="min-w-0 text-sm font-medium break-words">{card.title}</span>
        </div>
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-stone-500 dark:text-stone-400">
          <Badge tone="stone">{card.stage}</Badge>
          {card.parent && card.promise?.number !== card.parent && <span className="font-mono">⊂ T-{card.parent}</span>}
        </div>
        {card.promise && (
          <span className="truncate text-xs text-emerald-700 dark:text-emerald-400" title={card.promise.title}>
            ◇ {card.promise.title}
          </span>
        )}
        <Move card={card} />
      </Link>
      {/* Who works on it; a click shows only their tasks. */}
      <button
        type="button"
        onClick={() => onAssignee(card.assignee ?? '-')}
        className="shrink-0 self-center rounded-full p-0.5 transition-transform hover:scale-110 focus-visible:outline-2 focus-visible:outline-stone-400"
        title={card.assignee ? t('board.onlyOf', { who: card.assignee }) : t('board.onlyUnassigned')}
        aria-label={card.assignee ? t('board.onlyOf', { who: card.assignee }) : t('board.onlyUnassigned')}
      >
        {card.assignee ? (
          <PersonAvatar name={card.assignee} size={36} src={avatar} />
        ) : (
          <span
            className="flex size-9 items-center justify-center rounded-full border-2 border-dashed border-stone-300 text-base font-semibold text-stone-400 dark:border-stone-600 dark:text-stone-500"
            aria-hidden="true"
          >
            ?
          </span>
        )}
      </button>
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
  const avatars = new Map((team.data?.members ?? []).map((member) => [member.pseudonym ?? '', member.avatar]))

  if (team.isPending) return <Page><Loading /></Page>
  if (team.error || !team.data) {
    return (
      <Page title={t('board.title')}>
        <ErrorNote>{errorText(team.error, t)}</ErrorNote>
      </Page>
    )
  }
  return (
    <TeamPageFrame
      team={team.data}
      current="board"
      title={
        <span className="flex items-center gap-2">
          {t('board.title')}
          <Link
            to={`${boardPath(slug)}/settings`}
            className="inline-flex rounded-md p-1 text-stone-500 hover:bg-stone-200 hover:text-stone-800 dark:text-stone-400 dark:hover:bg-stone-800 dark:hover:text-stone-100"
            title={t('board.settings')}
            aria-label={t('board.settings')}
          >
            <Gear />
          </Link>
        </span>
      }
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
        // The columns use the screen's whole width, from its left edge, scrolling across; the
        // Team's line above stays where it is on every page.
        <div className="relative left-1/2 mb-3 w-screen -translate-x-1/2 overflow-x-auto border-y border-stone-200 bg-stone-100 py-4 dark:border-stone-800 dark:bg-stone-900/60">
          {/* Columns share the screen's width, from 12rem up to a readable 28rem each; what is
              left is shared at the sides, and only a screen too narrow for 12rem each scrolls. */}
          <div
            className="flex w-full justify-center gap-3 px-4 sm:px-6"
            style={{ minWidth: `calc(${board.data.columns.length} * 12rem + ${board.data.columns.length - 1} * 0.75rem + 3rem)` }}
          >
          {board.data.columns.map((column, index) => {
            const cards = board.data.cards.filter((card) => card.column === index)
            return (
              <section
                key={column.name}
                className={`relative flex max-w-md min-w-0 flex-1 basis-0 flex-col self-start rounded-lg bg-stone-200/70 dark:bg-stone-800/70 ${
                  dragged && dragged.column !== index ? 'opacity-50 outline-2 outline-stone-400 outline-dashed dark:outline-stone-500' : ''
                }`}
              >
                {dragged && dragged.column !== index && (
                  <p className="px-3 pt-3 text-xs text-stone-700 dark:text-stone-200">{t('board.noStageMove')}</p>
                )}
                <h2 className="flex items-baseline justify-between gap-2 px-3 pt-3 pb-2 text-xs font-semibold tracking-wide text-stone-600 uppercase dark:text-stone-300">
                  <span className="truncate">{column.name}</span>
                  <span className="rounded-full bg-stone-300/80 px-2 py-0.5 text-stone-700 dark:bg-stone-700 dark:text-stone-200">{cards.length}</span>
                </h2>
                {cards.length === 0 ? (
                  <p className="px-3 pb-4 text-sm text-stone-500 dark:text-stone-400">
                    {column.rule === 'waiting' ? t('board.noneWaiting') : t('board.empty')}
                  </p>
                ) : (
                  <ol className="flex flex-col gap-2 px-2 pb-2">
                    {cards.map((card) => (
                      <BoardCard
                        key={card.number}
                        card={card}
                        avatar={avatars.get(card.assignee ?? '')}
                        onAssignee={(assignee) => setFilter({ ...filter, assignee })}
                        draggable={canOrder}
                        accepts={!dragged || dragged.column === card.column}
                        onDragStart={() => setDragged(card)}
                        onDragEnd={() => setDragged(null)}
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
              </section>
            )
          })}
          </div>
        </div>
      )}
      {canOrder && <p className="text-xs text-stone-500 dark:text-stone-400">{t('board.hint')}</p>}
    </TeamPageFrame>
  )
}

/** A board's own settings: its columns (decision 0032). */
export function BoardSettingsPage() {
  const { t } = useTranslation()
  const slug = useParams().team ?? ''
  const team = useTeam(slug)
  if (team.isPending) return <Page><Loading /></Page>
  if (team.error || !team.data) {
    return (
      <Page title={t('board.settings')}>
        <ErrorNote>{errorText(team.error, t)}</ErrorNote>
      </Page>
    )
  }
  const owner = team.data.role === 'owner'
  return (
    <TeamPageFrame team={team.data} current="board" sub title={t('board.settings')}>
      {!owner && (
        <div className="mb-5">
          <Notice>{t('team.settingsReadOnly')}</Notice>
        </div>
      )}
      <div className="max-w-2xl">
        <BoardSettings team={team.data} readOnly={!owner} />
      </div>
    </TeamPageFrame>
  )
}
