import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react'
import { useTranslation } from 'react-i18next'

import { api, call } from '../api/client'
import { errorText } from '../lib/format'
import { type Span } from '../lib/spans'
import { Hourglass } from './Hourglass'
import { Button, ErrorNote, Input } from './ui'

/** Pastel tones to tell columns apart in the editor; the board itself keeps its own look. */
const TONES = [
  'bg-amber-100 border-amber-300 dark:bg-amber-900/30 dark:border-amber-700/60',
  'bg-sky-100 border-sky-300 dark:bg-sky-900/30 dark:border-sky-700/60',
  'bg-emerald-100 border-emerald-300 dark:bg-emerald-900/30 dark:border-emerald-700/60',
  'bg-violet-100 border-violet-300 dark:bg-violet-900/30 dark:border-violet-700/60',
  'bg-rose-100 border-rose-300 dark:bg-rose-900/30 dark:border-rose-700/60',
  'bg-lime-100 border-lime-300 dark:bg-lime-900/30 dark:border-lime-700/60',
  'bg-cyan-100 border-cyan-300 dark:bg-cyan-900/30 dark:border-cyan-700/60',
  'bg-orange-100 border-orange-300 dark:bg-orange-900/30 dark:border-orange-700/60',
]

/** Where each column starts, by the index of its first stage. */
function starts(spans: Span[]): number[] {
  const result: number[] = []
  let at = 0
  for (const span of spans) {
    result.push(at)
    at += span.size
  }
  return result
}

/**
 * A drag in progress: what is pulled, the columns before it, the name and colour a new column
 * gets, the borders between stages as they stood when it began, and the border it is on.
 */
type Drag = {
  kind: 'left' | 'right' | 'move'
  index: number
  from: Span[]
  name: string
  tone: number
  lines: number[]
  at: number | null
  top: number
  bottom: number
}

/** How far above or below the stages an empty column is pulled to be removed, in pixels. */
const AWAY = 40

/** The border reached by pulling an empty column away from the stages: it is removed. */
const GONE = -1

/** How far past the halfway point the pointer goes before the border changes, in pixels. */
const STICK = 12

/**
 * The columns editor for a workflow whose stages follow one another (the author, 2026-11-09).
 * Stages are vertical strips; a column is a coloured frame over a run of them. Pulling a frame's
 * edge in frees stages into a new column; pulling it out takes them from the neighbour. A frame
 * pulled to a line is an empty column between two stages, which can be moved to any border
 * between columns and made the waiting one.
 */
export function LinearColumnsEditor({
  team,
  stages,
  spans: initial,
  readOnly,
}: {
  team: string
  stages: string[]
  spans: Span[]
  readOnly: boolean
}) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [spans, setSpans] = useState<Span[]>(initial)
  // The columns as they stand, for the window's handlers, which outlive a render.
  const latest = useRef(spans)
  useEffect(() => {
    latest.current = spans
  }, [spans])
  const drag = useRef<Drag | null>(null)
  const strips = useRef<(HTMLDivElement | null)[]>([])
  const track = useRef<HTMLDivElement>(null)
  const counter = useRef(initial.length)

  /** The borders between stages on screen now: 0 before the first, n after the last. */
  const measure = (): number[] => {
    const rects = strips.current.slice(0, stages.length).map((strip) => strip?.getBoundingClientRect())
    const lines = [rects[0]?.left ?? 0]
    for (let i = 1; i < rects.length; i++) lines.push(((rects[i - 1]?.right ?? 0) + (rects[i]?.left ?? 0)) / 2)
    lines.push(rects[rects.length - 1]?.right ?? 0)
    return lines
  }

  /**
   * The border the pointer is on. The borders are those measured when the drag began: a column
   * appearing moves the strips, and measuring them anew would flip the border back and forth.
   * The border changes only when the pointer is clearly nearer another one.
   */
  const border = (current: Drag, x: number): number => {
    const { lines, at } = current
    let best = 0
    for (let i = 1; i < lines.length; i++) if (Math.abs(lines[i] - x) < Math.abs(lines[best] - x)) best = i
    if (at !== null && best !== at && Math.abs(lines[best] - x) + STICK > Math.abs(lines[at] - x)) return at
    return best
  }

  const moveEdge = (
    from: Span[],
    index: number,
    side: 'left' | 'right',
    to: number,
    name: string,
    tone: number,
  ): Span[] => {
    const fresh = (size: number): Span => ({ name, waiting: false, size, tone })
    const cols = from.map((span) => ({ ...span }))
    const start = starts(cols)[index]
    const end = start + cols[index].size
    if (side === 'right') {
      const g = Math.max(start, to)
      if (g < end) {
        cols[index].size = g - start
        cols.splice(index + 1, 0, fresh(end - g))
      } else if (g > end) {
        let need = g - end
        cols[index].size += need
        for (let j = index + 1; j < cols.length && need > 0; j++) {
          const take = Math.min(cols[j].size, need)
          cols[j].size -= take
          need -= take
        }
      }
    } else {
      const g = Math.min(end, to)
      if (g > start) {
        cols[index].size = end - g
        cols.splice(index, 0, fresh(g - start))
      } else if (g < start) {
        let need = start - g
        cols[index].size += need
        for (let j = index - 1; j >= 0 && need > 0; j--) {
          const take = Math.min(cols[j].size, need)
          cols[j].size -= take
          need -= take
        }
      }
    }
    // A column pulled to a line keeps its name and stands empty; it is no longer the waiting one
    // only if it holds stages again.
    return cols.map((span) => (span.size > 0 ? { ...span, waiting: false } : span))
  }

  const moveEmpty = (from: Span[], index: number, to: number): Span[] => {
    const cols = from.filter((_, i) => i !== index)
    const moved = from[index]
    // An empty column stands on a border between columns: after every column ending there.
    const at = starts(cols)
    let place = cols.length
    for (let i = 0; i < cols.length; i++) {
      if (at[i] >= to && cols[i].size > 0) {
        place = i
        break
      }
    }
    cols.splice(place, 0, moved)
    return cols
  }

  const begin = (event: ReactPointerEvent, kind: Drag['kind'], index: number) => {
    if (readOnly) return
    event.preventDefault()
    // The drag is followed on the whole window: the pulled column may leave the page, and the
    // element it was held by with it, while the button is still down.
    const move = (moved: PointerEvent) => follow(moved)
    const stop = () => {
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', stop)
      window.removeEventListener('pointercancel', stop)
      end()
    }
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', stop)
    window.addEventListener('pointercancel', stop)
    const used = new Set(spans.map((span) => span.tone))
    let tone = 0
    while (used.has(tone)) tone += 1
    drag.current = {
      kind,
      index,
      from: spans,
      name: t('tracker.columnN', { n: counter.current + 1 }),
      tone,
      lines: measure(),
      at: null,
      top: track.current?.getBoundingClientRect().top ?? 0,
      bottom: track.current?.getBoundingClientRect().bottom ?? 0,
    }
  }
  const follow = (event: PointerEvent) => {
    const current = drag.current
    if (!current) return
    // An empty column pulled up or down away from the stages is removed; brought back, it returns.
    const away = current.kind === 'move' && (event.clientY < current.top - AWAY || event.clientY > current.bottom + AWAY)
    const g = away ? GONE : border(current, event.clientX)
    if (g === current.at) return
    if (g === GONE) {
      current.at = g
      setSpans(current.from.filter((_, i) => i !== current.index))
      return
    }
    current.at = g
    setSpans(
      current.kind === 'move'
        ? moveEmpty(current.from, current.index, g)
        : moveEdge(current.from, current.index, current.kind, g, current.name, current.tone),
    )
  }
  const end = () => {
    // A new column took the next number: the next one gets the one after it.
    if (drag.current && latest.current.length > drag.current.from.length) counter.current += 1
    drag.current = null
  }

  const remove = (index: number) => {
    // A removed column gives its stages to the one before it, or to the next for the first.
    const cols = spans.map((span) => ({ ...span }))
    const size = cols[index].size
    cols.splice(index, 1)
    if (size > 0) {
      const heir = cols[index - 1] ?? cols[index]
      if (!heir) return
      heir.size += size
      heir.waiting = false
    }
    setSpans(cols)
  }

  const save = useMutation({
    mutationFn: () => {
      let at = 0
      const columns = spans.map((span) => {
        const held = stages.slice(at, at + span.size)
        at += span.size
        return { name: span.name.trim(), rule: span.waiting ? ('waiting' as const) : ('stages' as const), stages: held }
      })
      return call(api.PUT('/api/team/{team}/board', { params: { path: { team } }, body: { columns } }))
    },
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['board', team] }),
  })

  const at = starts(spans)
  return (
    <div className="flex flex-col gap-4 px-4 py-3">
      <p className="text-sm text-stone-600 dark:text-stone-400">{t('tracker.linearLead')}</p>
      <div className="overflow-x-auto pb-2">
        <div ref={track} className="flex w-max items-stretch gap-2 select-none">
          {spans.map((span, index) => {
            const tone = TONES[span.tone % TONES.length]
            const held = stages.slice(at[index], at[index] + span.size)
            return (
              <div key={span.tone} className={`relative flex flex-col rounded-lg border-2 ${tone} ${span.size === 0 ? 'w-7 border-dashed' : ''}`}>
                {span.size > 0 ? (
                  <span className="truncate px-2 pt-1 text-xs font-semibold" title={span.name}>
                    {span.name}
                  </span>
                ) : (
                  span.waiting && (
                    <span className="flex flex-1 flex-col items-center gap-2 pt-2 text-stone-600 dark:text-stone-300" title={span.name}>
                      <Hourglass />
                      <span style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)' }} className="text-xs whitespace-nowrap">
                        {t('tracker.byWaiting')}
                      </span>
                    </span>
                  )
                )}
                <div className="flex flex-1 gap-1.5 px-2 pt-1 pb-2">
                  {held.map((stage, i) => (
                    <div
                      key={stage}
                      ref={(element) => {
                        strips.current[at[index] + i] = element
                      }}
                      className="flex h-40 w-9 items-center justify-center rounded-md border border-stone-300 bg-white text-sm dark:border-stone-600 dark:bg-stone-900"
                    >
                      <span style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)' }} className="whitespace-nowrap">
                        {stage}
                      </span>
                    </div>
                  ))}
                </div>
                {!readOnly && span.size > 0 && (
                  <>
                    <div
                      role="separator"
                      aria-label={t('tracker.leftEdge', { name: span.name })}
                      onPointerDown={(event) => begin(event, 'left', index)}
                      className="absolute inset-y-0 -left-1.5 w-3 cursor-ew-resize rounded hover:bg-stone-400/40"
                    />
                    <div
                      role="separator"
                      aria-label={t('tracker.rightEdge', { name: span.name })}
                      onPointerDown={(event) => begin(event, 'right', index)}
                      className="absolute inset-y-0 -right-1.5 w-3 cursor-ew-resize rounded hover:bg-stone-400/40"
                    />
                  </>
                )}
                {!readOnly && span.size === 0 && (
                  <div
                    role="button"
                    aria-label={t('tracker.moveEmpty', { name: span.name })}
                    onPointerDown={(event) => begin(event, 'move', index)}
                    className="absolute inset-0 cursor-grab"
                  />
                )}
              </div>
            )
          })}
        </div>
      </div>
      <ol className="flex flex-col gap-1.5">
        {spans.map((span, index) => (
          <li key={span.tone} className="flex items-center gap-2">
            <span className={`size-4 shrink-0 rounded border-2 ${TONES[span.tone % TONES.length]}`} aria-hidden="true" />
            <Input
              value={span.name}
              onChange={(event) => setSpans(spans.map((s, i) => (i === index ? { ...s, name: event.target.value } : s)))}
              maxLength={60}
              disabled={readOnly}
              className="min-w-0 flex-1 py-1"
              aria-label={t('tracker.columnName')}
            />
            <label className={`inline-flex shrink-0 items-center gap-1 text-sm ${span.size > 0 ? 'opacity-40' : ''}`} title={span.size > 0 ? t('tracker.waitingOnlyEmpty') : undefined}>
              <input
                type="checkbox"
                checked={span.waiting}
                disabled={readOnly || span.size > 0}
                onChange={(event) => setSpans(spans.map((s, i) => (i === index ? { ...s, waiting: event.target.checked } : s)))}
              />
              {t('tracker.byWaiting')}
            </label>
            {!readOnly && (
              <Button size="sm" variant="ghost" onClick={() => remove(index)} disabled={spans.length === 1} aria-label={t('tracker.remove')}>
                ✕
              </Button>
            )}
          </li>
        ))}
      </ol>
      <ErrorNote>{save.error ? errorText(save.error, t) : null}</ErrorNote>
      {save.isSuccess && <p className="text-sm text-emerald-700 dark:text-emerald-400">{t('common.saved')}</p>}
      {!readOnly && (
        <div>
          <Button size="sm" variant="primary" onClick={() => save.mutate()} disabled={save.isPending || spans.some((s) => !s.name.trim())}>
            {t('common.save')}
          </Button>
        </div>
      )}
    </div>
  )
}
