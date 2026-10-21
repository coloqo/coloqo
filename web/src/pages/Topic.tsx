import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Fragment, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router'

import {
  ApiError,
  api,
  areaPath,
  call,
  downloadUrl,
  fileUrl,
  topicPath,
  uploadFile,
  type FileInfo,
  type Me,
  type Message,
  type TopicDetail,
} from '../api/client'
import { useTeam } from '../api/queries'
import { AddresseeSelect } from '../components/AddresseeSelect'
import { AuthorAvatar } from '../components/Avatar'
import { Bell } from '../components/Bell'
import { Page } from '../components/Layout'
import { Markdown } from '../components/Markdown'
import { Time } from '../components/Time'
import { StatusBadge } from '../components/Topics'
import { Badge, Button, Card, CardHeader, ErrorNote, Field, Loading, Notice, Textarea } from '../components/ui'
import { MessageImages } from '../components/Images'
import { absoluteTime, errorText, fileSize, issueLink } from '../lib/format'

/** Whether the page is in front of the person, so that reading can be recorded. */
function usePageVisible() {
  const [visible, setVisible] = useState(() => document.visibilityState === 'visible')
  useEffect(() => {
    const update = () => setVisible(document.visibilityState === 'visible')
    document.addEventListener('visibilitychange', update)
    return () => document.removeEventListener('visibilitychange', update)
  }, [])
  return visible
}

/** A draft kept per Topic for this browser tab, so that a reload does not lose it. */
function useDraft(team: string, number: number) {
  const key = `coloqo.draft.${team}.${number}`
  const [draft, setDraftState] = useState(() => {
    try {
      return sessionStorage.getItem(key) ?? ''
    } catch {
      return ''
    }
  })
  const setDraft = (value: string) => {
    setDraftState(value)
    try {
      if (value) sessionStorage.setItem(key, value)
      else sessionStorage.removeItem(key)
    } catch {
      // Storage may be unavailable; the draft then lives only in memory.
    }
  }
  return [draft, setDraft] as const
}

function FileLink({ file, team }: { file: FileInfo; team: string }) {
  const { i18n } = useTranslation()
  return (
    <a
      href={downloadUrl(team, file)}
      download={file.name}
      className="inline-flex max-w-full items-center gap-1.5 rounded-md border border-stone-200 px-2 py-1 text-sm hover:bg-stone-50 dark:border-stone-700 dark:hover:bg-stone-800"
    >
      <span className="truncate font-medium text-amber-700 dark:text-amber-400">{file.name}</span>
      <span className="shrink-0 text-xs text-stone-500 dark:text-stone-400">{fileSize(file.size, i18n.resolvedLanguage ?? 'ru')}</span>
    </a>
  )
}

/** Whether the screen is phone-sized; the feed's faces shrink there. */
function useNarrow() {
  const query = '(max-width: 639px)'
  const [narrow, setNarrow] = useState(() => window.matchMedia(query).matches)
  useEffect(() => {
    const list = window.matchMedia(query)
    const change = () => setNarrow(list.matches)
    list.addEventListener('change', change)
    return () => list.removeEventListener('change', change)
  }, [])
  return narrow
}

const GROUP_GAP_MS = 10 * 60 * 1000

/** A Message continues the previous one's group: same author, close in time, same addressee and holding. */
function continues(message: Message, previous: Message | undefined): boolean {
  return (
    previous !== undefined &&
    message.kind === 'message' &&
    previous.kind === 'message' &&
    previous.author === message.author &&
    previous.assistant_key === message.assistant_key &&
    previous.human_part === message.human_part &&
    previous.to === message.to &&
    previous.to_assistant === message.to_assistant &&
    previous.meant_for === message.meant_for &&
    previous.by_holder === message.by_holder &&
    new Date(message.created_at).getTime() - new Date(previous.created_at).getTime() < GROUP_GAP_MS
  )
}

function clock(value: string, lang: string): string {
  return new Intl.DateTimeFormat(lang, { hour: '2-digit', minute: '2-digit' }).format(new Date(value))
}

/** The first line of a Message's text, without Markdown marks: what a reply quotes. */
function snippet(body: string): string {
  const line = body
    .split('\n')
    .map((text) => text.trim())
    .find((text) => text && !text.startsWith('```'))
  return (line ?? '')
    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/[`*_>#|]/g, '')
    .trim()
}

/** Show the Message a reply answers: scroll to it and light it up for a moment. */
function jumpTo(number: number) {
  const element = document.getElementById(`m-${number}`)
  if (!element) return
  element.scrollIntoView({ behavior: 'smooth', block: 'center' })
  element.classList.remove('reply-flash')
  void element.offsetWidth
  element.classList.add('reply-flash')
}

function Quote({ message, number, onClick }: { message: Message | undefined; number: number; onClick?: () => void }) {
  const { t } = useTranslation()
  const content = (
    <>
      <span className="block truncate font-medium text-amber-800 dark:text-amber-300">
        {message ? (message.assistant ?? message.author ?? t('team.noName')) : `#${number}`}
      </span>
      <span className="block truncate text-stone-600 dark:text-stone-300">
        {message ? snippet(message.body) || t('message.attachment') : t('message.notLoaded')}
      </span>
    </>
  )
  const style = 'block w-full min-w-0 rounded-md border-l-[3px] border-amber-500 bg-stone-500/10 px-2 py-1 text-left text-[13px] leading-snug not-italic'
  return onClick ? (
    <button type="button" className={`${style} hover:bg-stone-500/15`} onClick={onClick} aria-label={t('message.showOriginal', { number })}>
      {content}
    </button>
  ) : (
    <div className={style}>{content}</div>
  )
}

function ReplyArrow() {
  return (
    <svg viewBox="0 0 16 16" aria-hidden="true" className="size-3.5 fill-none stroke-current" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M6.5 3.5 2.5 7.5l4 4" />
      <path d="M2.5 7.5h6.5a4.5 4.5 0 0 1 4.5 4.5v.5" />
    </svg>
  )
}

/** How much the Assistant's person took part in a reply: without, with, or their words (0026). */
function HumanPart({ message }: { message: Message }) {
  const { t } = useTranslation()
  if (!message.human_part || !message.author) return null
  const tone = message.human_part === 'without' ? 'stone' : 'blue'
  return (
    <Badge tone={tone} title={t(`message.humanPartHint.${message.human_part}`, { name: message.author })}>
      {t(`message.humanPart.${message.human_part}`, { name: message.author })}
    </Badge>
  )
}

function MessageItem({
  message,
  original,
  me,
  team,
  holder,
  grouped,
  narrow,
  onReply,
  onJump,
  avatars,
}: {
  message: Message
  original: Message | undefined
  me: Me
  team: string
  holder: string | null
  grouped: boolean
  narrow: boolean
  onReply: (message: Message) => void
  onJump: (number: number) => void
  avatars: Map<string, string | null | undefined>
}) {
  const { t, i18n } = useTranslation()
  const lang = i18n.resolvedLanguage ?? 'ru'
  const mine = message.author === me.pseudonym
  const toMe = message.to !== null && message.to === me.pseudonym
  const addressee = message.to_assistant ?? message.to
  const progress = message.kind === 'progress'
  const images = message.files.filter((file) => file.preview)
  const others = message.files.filter((file) => !file.preview)
  const size = narrow ? 32 : 40
  const name = message.assistant ?? message.author ?? t('team.noName')
  const held = message.by_holder ? (message.assistant_key !== null && message.assistant_key === holder ? 'now' : 'then') : null
  const bubble = progress
    ? 'border border-dashed border-stone-300 text-stone-500 italic dark:border-stone-700 dark:text-stone-400'
    : mine
      ? 'bg-emerald-50 shadow-sm dark:bg-emerald-950/40'
      : 'bg-white shadow-sm dark:bg-stone-800/80'
  return (
    <li id={`m-${message.number}`} className={`group relative flex scroll-mt-16 gap-2.5 ${grouped ? 'mt-1' : 'mt-3'}`}>
      <div className="shrink-0" style={{ width: size }}>
        {!grouped && (
          <AuthorAvatar
            person={message.author}
            assistant={message.assistant !== null}
            size={size}
            src={message.author ? avatars.get(message.author) : null}
          />
        )}
      </div>
      <div
        className={`relative max-w-[min(100%,46rem)] min-w-0 rounded-2xl px-3.5 pt-2 pb-1.5 ${grouped ? '' : 'rounded-tl-md'} ${bubble} ${
          toMe ? 'ring-2 ring-amber-400 dark:ring-amber-500/70' : ''
        }`}
      >
        {!grouped && (
          <div className="mb-0.5 flex flex-wrap items-baseline gap-x-2 gap-y-0.5 text-sm not-italic">
            <span className="font-semibold text-stone-900 dark:text-stone-100">{name}</span>
            <HumanPart message={message} />
            {addressee && (
              <span className={`inline-flex items-center gap-1 ${toMe ? 'font-medium text-amber-800 dark:text-amber-300' : 'text-stone-500 dark:text-stone-400'}`}>
                {toMe && <Bell className="size-3.5 self-center" />}→ {toMe ? t('message.toYou') : addressee}
              </span>
            )}
            {message.meant_for && (
              <span className="text-xs text-stone-500 dark:text-stone-400" title={message.meant_for}>
                {t('message.meantFor', { name: message.meant_for.split(' · ').pop() })}
              </span>
            )}
            {held && (
              <span
                className={`ml-auto inline-flex items-center gap-1 self-center pl-2 text-xs font-medium ${
                  held === 'now' ? 'text-amber-700 dark:text-amber-400' : 'text-stone-400 dark:text-stone-500'
                }`}
                title={held === 'now' ? t('message.holdsNow') : t('message.heldThen')}
              >
                <svg viewBox="0 0 12 12" aria-hidden="true" className="size-3">
                  <path d="M3 1.5v9" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
                  <path d="M3.6 2h5.6L7.8 4.1l1.4 2.1H3.6z" fill="currentColor" />
                </svg>
                {held === 'now' ? t('message.holds') : t('message.held')}
              </span>
            )}
          </div>
        )}
        {message.reply_to !== null && (
          <div className="mt-0.5 mb-1.5">
            <Quote message={original} number={message.reply_to} onClick={() => onJump(message.reply_to!)} />
          </div>
        )}
        <div className={progress ? 'text-sm' : undefined}>
          <Markdown text={message.body} />
        </div>
        {images.length > 0 && <MessageImages images={images} team={team} />}
        {others.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-2">
            {others.map((file) => (
              <FileLink key={file.number} file={file} team={team} />
            ))}
          </div>
        )}
        <div className="-mr-1 flex items-center justify-end gap-2 text-[11px] text-stone-400 not-italic tabular-nums dark:text-stone-500">
          {/* On a pointer that hovers, Reply waits for the hover; on touch it is always there. */}
          <button
            type="button"
            className="-my-1 inline-flex items-center gap-1 rounded px-1.5 py-1 text-stone-500 group-focus-within:opacity-100 group-hover:opacity-100 hover:bg-stone-500/10 hover:text-stone-800 dark:text-stone-400 dark:hover:text-stone-100 [@media(hover:hover)]:opacity-0"
            onClick={() => onReply(message)}
          >
            <ReplyArrow />
            {t('message.reply')}
          </button>
          <span className="font-mono">#{message.number}</span>
          <time dateTime={message.created_at} title={absoluteTime(message.created_at, lang, true)}>
            {clock(message.created_at, lang)}
          </time>
        </div>
      </div>
    </li>
  )
}

function DayDivider({ value }: { value: string }) {
  const { i18n } = useTranslation()
  const day = new Intl.DateTimeFormat(i18n.resolvedLanguage ?? 'ru', { day: 'numeric', month: 'long', year: 'numeric' }).format(new Date(value))
  return (
    <li className="mt-3 flex justify-center">
      <span className="rounded-full bg-stone-200/80 px-3 py-0.5 text-xs font-medium text-stone-600 dark:bg-stone-800 dark:text-stone-300">{day}</span>
    </li>
  )
}

/** A stage, a closing or a takeover: a service line in the feed, apart from the bubbles (0021, 0024). */
function ServiceLine({ message }: { message: Message }) {
  const { t, i18n } = useTranslation()
  const lang = i18n.resolvedLanguage ?? 'ru'
  const who = message.system ? 'Coloqo' : (message.assistant ?? message.author ?? t('team.noName'))
  const closed = message.kind === 'closed'
  const taken = message.kind === 'taken'
  return (
    <li id={`m-${message.number}`} className="mt-3 flex scroll-mt-16 justify-center">
      <span
        className={`inline-flex max-w-full flex-wrap items-baseline justify-center gap-x-1.5 rounded-full px-3 py-1 text-center text-xs ${
          closed
            ? 'bg-emerald-100 text-emerald-900 dark:bg-emerald-950/60 dark:text-emerald-200'
            : 'bg-stone-200/80 text-stone-700 dark:bg-stone-800 dark:text-stone-300'
        }`}
        title={absoluteTime(message.created_at, lang, true)}
      >
        <span aria-hidden="true">{closed ? '✓' : '⚙'}</span>
        <span className="font-medium">{who}</span>
        {taken ? (
          <span className="min-w-0 break-words">
            {message.body ? t('message.tookFrom', { from: message.body }) : t('message.took')}
          </span>
        ) : (
          <>
            <span>{closed ? t('message.closedTopic') : '—'}</span>
            {message.body && <span className="min-w-0 break-words">{message.body}</span>}
          </>
        )}
        <span className="text-stone-500 tabular-nums dark:text-stone-400">{clock(message.created_at, lang)}</span>
      </span>
    </li>
  )
}

function NewDivider() {
  const { t } = useTranslation()
  return (
    <li className="mt-3 flex items-center gap-3 py-1 text-xs font-medium tracking-wide text-amber-700 uppercase dark:text-amber-400" aria-label={t('message.newDivider')}>
      <span className="h-px flex-1 bg-amber-300 dark:bg-amber-800" />
      {t('message.newDivider')}
      <span className="h-px flex-1 bg-amber-300 dark:bg-amber-800" />
    </li>
  )
}

function Compose({
  topic,
  to,
  setTo,
  replying,
  setReplying,
}: {
  topic: TopicDetail
  to: string
  setTo: (value: string) => void
  replying: Message | null
  setReplying: (message: Message | null) => void
}) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const team = useTeam(topic.team)
  const [body, setBody] = useDraft(topic.team, topic.number)
  const [attached, setAttached] = useState<FileInfo[]>([])
  const [uploading, setUploading] = useState(0)
  const [uploadError, setUploadError] = useState<unknown>(null)
  const [conflict, setConflict] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ['topic', topic.team, topic.number] })
    void queryClient.invalidateQueries({ queryKey: ['topics', topic.team] })
    void queryClient.invalidateQueries({ queryKey: ['team', topic.team] })
    void queryClient.invalidateQueries({ queryKey: ['inbox'] })
  }
  const send = useMutation({
    mutationFn: () =>
      call(
        api.POST('/api/team/{team}/topic/{number}/message', {
          params: { path: { team: topic.team, number: topic.number } },
          body: {
            number: topic.last_number + 1,
            body,
            to: to || null,
            files: attached.map((file) => file.number),
            reply_to: replying?.number ?? null,
          },
        }),
      ),
    onSuccess: () => {
      setBody('')
      setAttached([])
      setConflict(false)
      setTo('')
      setReplying(null)
      refresh()
    },
    onError: (error) => {
      // Someone wrote first: read the new Messages, the draft stays (decision 0007).
      if (error instanceof ApiError && error.code === 'number_taken') {
        setConflict(true)
        refresh()
      }
    },
  })

  const upload = async (files: FileList) => {
    setUploadError(null)
    for (const file of Array.from(files)) {
      setUploading((n) => n + 1)
      try {
        const info = await uploadFile(topic.team, topic.number, file)
        setAttached((list) => [...list, info])
        void queryClient.invalidateQueries({ queryKey: ['topic', topic.team, topic.number] })
      } catch (error) {
        setUploadError(error)
      } finally {
        setUploading((n) => n - 1)
      }
    }
  }

  const busy = send.isPending || uploading > 0
  const sendError = send.error && !(send.error instanceof ApiError && send.error.code === 'number_taken') ? send.error : null

  return (
    <Card id="compose">
      <CardHeader title={t('compose.title')} />
      <form
        className="flex flex-col gap-3 p-4"
        onSubmit={(event) => {
          event.preventDefault()
          if (body.trim() && !busy) send.mutate()
        }}
      >
        {conflict && <Notice>{t('compose.numberTaken')}</Notice>}
        {topic.status === 'closed' && <Notice>{t('compose.reopens')}</Notice>}
        {replying && (
          <div className="-mb-1 flex items-center gap-2">
            <span className="shrink-0 text-stone-500 dark:text-stone-400"><ReplyArrow /></span>
            <div className="min-w-0 flex-1">
              <Quote message={replying} number={replying.number} onClick={() => jumpTo(replying.number)} />
            </div>
            <button
              type="button"
              className="shrink-0 rounded px-2 py-1 text-stone-500 hover:bg-stone-200 hover:text-stone-900 dark:hover:bg-stone-700 dark:hover:text-stone-100"
              onClick={() => setReplying(null)}
              aria-label={t('compose.cancelReply')}
            >
              ×
            </button>
          </div>
        )}
        <Textarea
          id="compose-body"
          value={body}
          onChange={(event) => setBody(event.target.value)}
          rows={5}
          maxLength={50000}
          placeholder={t('compose.placeholder')}
          aria-label={t('compose.title')}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
              event.preventDefault()
              if (body.trim() && !busy) send.mutate()
            }
          }}
        />
        <p className="-mt-1 text-xs text-stone-500 dark:text-stone-400">{t('compose.markdownHint')}</p>
        {attached.length > 0 && (
          <ul className="flex flex-wrap gap-2">
            {attached.map((file) => (
              <li
                key={file.number}
                className={`inline-flex items-center gap-1 rounded-md bg-stone-100 py-0.5 pr-0.5 text-sm dark:bg-stone-800 ${file.preview ? 'pl-0.5' : 'pl-2'}`}
              >
                {file.preview && <img src={fileUrl(topic.team, file)} alt="" className="size-10 rounded object-cover" />}
                <span className="max-w-48 truncate">{file.name}</span>
                <button
                  type="button"
                  className="rounded px-1.5 text-stone-500 hover:bg-stone-200 hover:text-stone-900 dark:hover:bg-stone-700 dark:hover:text-stone-100"
                  onClick={() => setAttached((list) => list.filter((item) => item.number !== file.number))}
                  aria-label={t('compose.detach', { name: file.name })}
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        )}
        <ErrorNote>{uploadError ? errorText(uploadError, t) : null}</ErrorNote>
        <ErrorNote>{sendError && errorText(sendError, t)}</ErrorNote>
        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-48 flex-1">
            <Field label={t('topic.addressee')}>
              <AddresseeSelect members={team.data?.members ?? []} value={to} onChange={setTo} />
            </Field>
          </div>
          <input
            ref={fileInput}
            type="file"
            multiple
            className="hidden"
            onChange={(event) => {
              if (event.target.files?.length) void upload(event.target.files)
              event.target.value = ''
            }}
          />
          <Button onClick={() => fileInput.current?.click()} disabled={uploading > 0}>
            {uploading > 0 ? t('compose.uploading') : t('compose.attach')}
          </Button>
          <Button type="submit" variant="primary" disabled={busy || !body.trim()}>
            {t('compose.send')}
          </Button>
        </div>
      </form>
    </Card>
  )
}

function Settle({ topic }: { topic: TopicDetail }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [closing, setClosing] = useState(false)
  const [outcome, setOutcome] = useState('')
  const settle = useMutation({
    mutationFn: (status: 'open' | 'closed') =>
      call(
        api.PATCH('/api/team/{team}/topic/{number}', {
          params: { path: { team: topic.team, number: topic.number } },
          body: { status, outcome: status === 'closed' ? outcome.trim() : '' },
        }),
      ),
    onSuccess: () => {
      setClosing(false)
      setOutcome('')
      void queryClient.invalidateQueries({ queryKey: ['topic', topic.team, topic.number] })
      void queryClient.invalidateQueries({ queryKey: ['topics', topic.team] })
      void queryClient.invalidateQueries({ queryKey: ['team', topic.team] })
      void queryClient.invalidateQueries({ queryKey: ['inbox'] })
    },
  })
  return (
    <Card>
      <CardHeader title={t('settle.title')} />
      <div className="flex flex-col gap-3 p-4">
        {topic.status === 'open' && !closing && (
          <>
            <p className="text-sm text-stone-600 dark:text-stone-400">{t('settle.lead')}</p>
            <div>
              <Button onClick={() => setClosing(true)}>{t('settle.close')}</Button>
            </div>
          </>
        )}
        {topic.status === 'open' && closing && (
          <form
            className="flex flex-col gap-3"
            onSubmit={(event) => {
              event.preventDefault()
              settle.mutate('closed')
            }}
          >
            <Field label={t('settle.outcome')} hint={t('settle.outcomeHint')}>
              <Textarea value={outcome} onChange={(event) => setOutcome(event.target.value)} rows={3} maxLength={5000} autoFocus />
            </Field>
            <div className="flex gap-2">
              <Button type="submit" variant="primary" disabled={settle.isPending}>
                {t('settle.confirmClose')}
              </Button>
              <Button variant="ghost" onClick={() => setClosing(false)}>
                {t('common.cancel')}
              </Button>
            </div>
          </form>
        )}
        {topic.status === 'closed' && (
          <>
            <p className="text-sm text-stone-600 dark:text-stone-400">{t('settle.closedLead')}</p>
            <div>
              <Button onClick={() => settle.mutate('open')} disabled={settle.isPending}>
                {t('settle.reopen')}
              </Button>
            </div>
          </>
        )}
        <ErrorNote>{settle.error && errorText(settle.error, t)}</ErrorNote>
      </div>
    </Card>
  )
}

function Files({ files, team, onJump }: { files: FileInfo[]; team: string; onJump: (number: number) => void }) {
  const { t } = useTranslation()
  if (files.length === 0) return null
  return (
    <Card>
      <CardHeader title={t('files.title')} />
      <ul className="divide-y divide-stone-200 dark:divide-stone-800">
        {files.map((file) => (
          <li key={file.number} className="flex flex-col gap-1 px-4 py-2.5">
            <FileLink file={file} team={team} />
            <span className="text-xs text-stone-500 dark:text-stone-400">
              {file.uploaded_by ?? t('team.noName')} · <Time value={file.created_at} />
              {' · '}
              {file.message_number !== null ? (
                <a
                  href={`#m-${file.message_number}`}
                  className="hover:underline"
                  onClick={(event) => {
                    event.preventDefault()
                    onJump(file.message_number!)
                  }}
                >
                  {t('files.inMessage', { number: file.message_number })}
                </a>
              ) : (
                t('files.notAttached')
              )}
            </span>
          </li>
        ))}
      </ul>
    </Card>
  )
}

function TopicHeader({ topic }: { topic: TopicDetail }) {
  const { t, i18n } = useTranslation()
  const link = topic.issue ? issueLink(topic.issue) : null
  const waiting = topic.status === 'open' && topic.turns_since_human >= topic.turn_limit
  return (
    <div className="mb-5 flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-stone-500 dark:text-stone-400">
        <span className="font-mono">{topic.ref}</span>
        <Link to={areaPath(topic.team, topic.area)} className="hover:underline">
          {topic.area_name}
        </Link>
        <StatusBadge status={topic.status} />
      </div>
      <h1 className="text-2xl font-semibold tracking-tight break-words">{topic.title}</h1>
      <dl className="flex flex-wrap gap-x-6 gap-y-1.5 text-sm">
        <div className="flex gap-1.5">
          <dt className="text-stone-500 dark:text-stone-400">{t('topic.holder')}:</dt>
          <dd>{topic.holder ?? t('topic.noHolder')}</dd>
        </div>
        {topic.created_by && (
          <div className="flex gap-1.5">
            <dt className="text-stone-500 dark:text-stone-400">{t('topic.openedBy')}:</dt>
            <dd>
              {topic.created_by}, <Time value={topic.created_at} />
            </dd>
          </div>
        )}
        {topic.issue && (
          <div className="flex min-w-0 gap-1.5">
            <dt className="text-stone-500 dark:text-stone-400">{t('topic.issue')}:</dt>
            <dd className="min-w-0 break-all">
              {link ? (
                <a href={link} target="_blank" rel="noreferrer noopener" className="text-amber-700 hover:underline dark:text-amber-400">
                  {topic.issue}
                </a>
              ) : (
                topic.issue
              )}
            </dd>
          </div>
        )}
        <div className="flex gap-1.5">
          <dt className="text-stone-500 dark:text-stone-400">{t('topic.turns')}:</dt>
          <dd className={waiting ? 'font-medium text-amber-700 dark:text-amber-400' : undefined}>
            {t('topic.turnsValue', { count: topic.turns_since_human, limit: topic.turn_limit })}
          </dd>
        </div>
      </dl>
      {waiting && <Notice>{t('topic.waitsForHumanLong')}</Notice>}
      {topic.deleted_at ? (
        <Notice>{t('topic.deleted', { date: absoluteTime(topic.deleted_at, i18n.resolvedLanguage ?? 'ru') })}</Notice>
      ) : (
        topic.deletes_at && (
          <Notice>{t('topic.archived', { date: absoluteTime(topic.deletes_at, i18n.resolvedLanguage ?? 'ru') })}</Notice>
        )
      )}
      {topic.status === 'closed' && (
        <div className="rounded-md border border-stone-200 bg-white px-4 py-3 dark:border-stone-800 dark:bg-stone-900/60">
          <p className="mb-1 text-xs font-semibold tracking-wide text-stone-500 uppercase dark:text-stone-400">
            {t('topic.outcome')}
          </p>
          {topic.outcome ? <Markdown text={topic.outcome} /> : <p className="text-sm text-stone-500">{t('topic.noOutcome')}</p>}
        </div>
      )}
    </div>
  )
}

/** How many Messages a Topic opens with and each "Show earlier" adds (decision 0026). */
const PAGE = 50

/** Messages by number, oldest first, with later copies of a number winning. */
function joined(...lists: Message[][]): Message[] {
  const byNumber = new Map<number, Message>()
  for (const list of lists) for (const message of list) byNumber.set(message.number, message)
  return [...byNumber.values()].sort((a, b) => a.number - b.number)
}

/**
 * A Topic with the Messages the reader has loaded: its latest window, kept fresh, and the
 * earlier ones loaded by hand (decision 0026). Each refresh joins the new window to what is
 * cached, and fetches what lies between when more arrived than the window holds.
 */
function useTopicFeed(team: string, number: number) {
  const queryClient = useQueryClient()
  const key = ['topic', team, number]
  const query = useQuery({
    queryKey: key,
    queryFn: async () => {
      const fresh = await call(
        api.GET('/api/team/{team}/topic/{number}', {
          params: { path: { team, number }, query: { from_unread: true, limit: PAGE } },
        }),
      )
      const cached = queryClient.getQueryData<TopicDetail>(key)?.messages ?? []
      let gap: Message[] = []
      const last = cached.length > 0 ? cached[cached.length - 1].number : null
      if (last !== null && fresh.messages.length > 0 && fresh.messages[0].number > last + 1) {
        const between = await call(
          api.GET('/api/team/{team}/topic/{number}', {
            params: { path: { team, number }, query: { after: last, limit: 500 } },
          }),
        )
        gap = between.messages
      }
      return { ...fresh, messages: joined(cached, gap, fresh.messages) }
    },
    enabled: team !== '' && number > 0,
  })
  /** Load earlier Messages: a page of them, or as many as reach the given number. */
  const loadEarlier = async (until?: number) => {
    let first = queryClient.getQueryData<TopicDetail>(key)?.messages[0]?.number
    while (first !== undefined && first > 1 && (until === undefined || first > until)) {
      const limit = until === undefined ? PAGE : Math.min(first - until, 500)
      const earlier = await call(
        api.GET('/api/team/{team}/topic/{number}', {
          params: { path: { team, number }, query: { before: first, limit } },
        }),
      )
      queryClient.setQueryData<TopicDetail>(key, (old) =>
        old ? { ...old, messages: joined(earlier.messages, old.messages) } : old,
      )
      if (until === undefined || earlier.messages.length === 0) break
      first = earlier.messages[0].number
    }
  }
  return { query, messages: query.data?.messages ?? [], loadEarlier }
}

/** Whether an element is on screen; the floating buttons show only when there is somewhere to go. */
function useOnScreen(element: HTMLElement | null) {
  const [on, setOn] = useState(true)
  useEffect(() => {
    if (!element) return
    const observer = new IntersectionObserver(([entry]) => setOn(entry.isIntersecting))
    observer.observe(element)
    return () => observer.disconnect()
  }, [element])
  return on
}

function Arrow({ up }: { up?: boolean }) {
  return (
    <svg viewBox="0 0 16 16" aria-hidden="true" className={`size-4 fill-none stroke-current ${up ? 'rotate-180' : ''}`} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M8 3v10M3.5 8.5 8 13l4.5-4.5" />
    </svg>
  )
}

export function TopicPage({ me }: { me: Me }) {
  const { t } = useTranslation()
  const params = useParams()
  const slug = params.team ?? ''
  const number = Number(params.number)
  const feed = useTopicFeed(slug, number)
  const topic = feed.query
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const visible = usePageVisible()
  const [to, setTo] = useState('')
  const [replying, setReplying] = useState<Message | null>(null)
  // Messages unread when the page opened, and those arriving while it is open, stay marked "new".
  const [newFrom, setNewFrom] = useState<number | null>(null)
  const [loadingEarlier, setLoadingEarlier] = useState(false)
  const [earlierError, setEarlierError] = useState<unknown>(null)
  const scrolled = useRef(false)
  const marking = useRef(0)
  const anchor = useRef<{ number: number; top: number } | null>(null)
  const [top, setTop] = useState<HTMLElement | null>(null)
  const [bottom, setBottom] = useState<HTMLElement | null>(null)
  const topOnScreen = useOnScreen(top)
  const bottomOnScreen = useOnScreen(bottom)
  const narrow = useNarrow()
  const data = topic.data
  const team = useTeam(data?.team ?? '')
  const messages = feed.messages
  const lastNumber = data?.last_number ?? 0
  const unread = data?.unread ?? 0

  useEffect(() => {
    // A former slug answers with the current one: the address follows it (decision 0025).
    if (data && data.team !== slug) void navigate(topicPath(data.team, data.number), { replace: true })
  }, [data, slug, navigate])

  useEffect(() => {
    // Open where the reading is: at the first unread Message, or at the latest (decision 0026).
    if (!data || scrolled.current || messages.length === 0) return
    scrolled.current = true
    const first = data.last_number - data.unread + 1
    setNewFrom(first)
    // More unread than a window holds starts at the first loaded Message instead.
    const unreadTarget = document.getElementById(`m-${first}`) ? `m-${first}` : `m-${messages[0].number}`
    const target = data.unread > 0 ? unreadTarget : `m-${messages[messages.length - 1].number}`
    window.requestAnimationFrame(() =>
      document.getElementById(target)?.scrollIntoView({ block: data.unread > 0 ? 'start' : 'end' }),
    )
  }, [data, messages])

  const firstLoaded = messages[0]?.number
  useLayoutEffect(() => {
    // After earlier Messages are inserted, the one above the button stays where it was. Only
    // an insertion above it moves it: a Message arriving below meanwhile leaves the anchor waiting.
    const kept = anchor.current
    if (!kept || firstLoaded === undefined || firstLoaded >= kept.number) return
    const element = document.getElementById(`m-${kept.number}`)
    if (element) window.scrollBy(0, element.getBoundingClientRect().top - kept.top)
    anchor.current = null
  }, [firstLoaded])

  // Reading is recorded while the page is in front and the latest Messages are on screen.
  useEffect(() => {
    if (!data || !visible || !bottomOnScreen || unread === 0 || lastNumber <= marking.current) return
    marking.current = lastNumber
    void call(
      api.POST('/api/team/{team}/topic/{number}/read', {
        params: { path: { team: data.team, number: data.number } },
        body: { number: lastNumber },
      }),
    )
      .then((out) => {
        queryClient.setQueryData<TopicDetail>(['topic', slug, number], (old) =>
          old ? { ...old, unread: out.unread, addressed: out.addressed } : old,
        )
        void queryClient.invalidateQueries({ queryKey: ['inbox'] })
        void queryClient.invalidateQueries({ queryKey: ['topics', out.team] })
      })
      .catch(() => {
        marking.current = 0
      })
  }, [data, visible, bottomOnScreen, unread, lastNumber, slug, number, queryClient])

  if (topic.isPending) return <Page><Loading /></Page>
  if (topic.error || !data) {
    return (
      <Page title={t('topic.notFoundTitle')}>
        <ErrorNote>{errorText(topic.error, t)}</ErrorNote>
      </Page>
    )
  }

  const byNumber = new Map(messages.map((m) => [m.number, m]))
  const avatars = new Map((team.data?.members ?? []).map((m) => [m.pseudonym ?? '', m.avatar]))
  // The line "New messages" stands before the first one someone else wrote since the page opened.
  const firstNew =
    newFrom === null
      ? -1
      : messages.findIndex((m) => m.number >= newFrom && !(m.assistant === null && m.author === me.pseudonym))
  const hasEarlier = messages.length > 0 && messages[0].number > 1
  const newBelow = bottomOnScreen ? 0 : unread

  const loadEarlier = () => {
    const first = messages[0]
    const element = first ? document.getElementById(`m-${first.number}`) : null
    anchor.current = first && element ? { number: first.number, top: element.getBoundingClientRect().top } : null
    setLoadingEarlier(true)
    setEarlierError(null)
    feed
      .loadEarlier()
      .catch(setEarlierError)
      .finally(() => setLoadingEarlier(false))
  }

  /** Show a Message, loading the earlier ones it is among when it is not loaded yet. */
  const reveal = (target: number) => {
    if (document.getElementById(`m-${target}`)) {
      jumpTo(target)
      return
    }
    setLoadingEarlier(true)
    setEarlierError(null)
    feed
      .loadEarlier(target)
      .then(() => window.requestAnimationFrame(() => jumpTo(target)))
      .catch(setEarlierError)
      .finally(() => setLoadingEarlier(false))
  }

  const reply = (message: Message) => {
    setReplying(message)
    const author = message.assistant ?? message.author
    if (author && author !== me.pseudonym) setTo(author)
    const box = document.getElementById('compose-body')
    box?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    box?.focus({ preventScroll: true })
  }

  const stickyBar = (
    <div className="sticky top-0 z-20 -mx-4 mb-4 flex min-w-0 items-center gap-2 border-b border-stone-200 bg-stone-50/95 px-4 py-2 text-sm backdrop-blur sm:-mx-6 sm:px-6 dark:border-stone-800 dark:bg-stone-950/90">
      <span className="shrink-0 font-mono text-stone-500 dark:text-stone-400">{data.ref}</span>
      <span className="shrink-0 text-stone-400">·</span>
      <Link to={areaPath(data.team, data.area)} className="shrink-0 text-amber-700 hover:underline dark:text-amber-400">
        {data.area_name}
      </Link>
      <span className="shrink-0 text-stone-400">·</span>
      <span className="min-w-0 truncate font-medium">{data.title}</span>
    </div>
  )

  if (data.deleted_at) {
    // Only the card is left: the conversation and its files were deleted (decision 0021).
    return (
      <Page>
        {stickyBar}
        <TopicHeader topic={data} />
      </Page>
    )
  }

  const floating =
    'pointer-events-auto inline-flex size-11 items-center justify-center rounded-full border border-stone-300 bg-white text-stone-700 shadow-md hover:bg-stone-100 dark:border-stone-700 dark:bg-stone-900 dark:text-stone-200 dark:hover:bg-stone-800'

  return (
    <Page>
      {stickyBar}
      <TopicHeader topic={data} />
      <div className="grid gap-5 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <div className="flex min-w-0 flex-col gap-5">
          <Card>
            <CardHeader title={t('topic.messages', { count: data.last_number })} />
            <div ref={setTop} className="scroll-mt-16">
              {hasEarlier && (
                <div className="flex flex-col items-center gap-2 border-b border-stone-200 bg-stone-100 px-3 py-2 dark:border-stone-800 dark:bg-stone-950/70">
                  <Button size="sm" onClick={loadEarlier} disabled={loadingEarlier}>
                    {loadingEarlier ? t('common.loading') : t('topic.showEarlier')}
                  </Button>
                  <ErrorNote>{earlierError ? errorText(earlierError, t) : null}</ErrorNote>
                </div>
              )}
            </div>
            <ol className="flex flex-col rounded-b-lg bg-stone-100 px-3 pt-1 pb-4 [--feed-ring:#f5f5f4] sm:px-4 dark:bg-stone-950/70 dark:[--feed-ring:#0f0d0c]">
              {messages.map((message, index) => {
                const previous = messages[index - 1]
                const newDay = previous === undefined || new Date(previous.created_at).toDateString() !== new Date(message.created_at).toDateString()
                const divider = index === firstNew
                return (
                  <Fragment key={message.number}>
                    {newDay && <DayDivider value={message.created_at} />}
                    {divider && <NewDivider />}
                    {message.kind === 'stage' || message.kind === 'closed' || message.kind === 'taken' ? (
                      <ServiceLine message={message} />
                    ) : (
                      <MessageItem
                        message={message}
                        me={me}
                        team={data.team}
                        holder={data.holder_key}
                        grouped={!divider && !newDay && continues(message, previous)}
                        narrow={narrow}
                        original={message.reply_to !== null ? byNumber.get(message.reply_to) : undefined}
                        onReply={reply}
                        onJump={reveal}
                        avatars={avatars}
                      />
                    )}
                  </Fragment>
                )
              })}
            </ol>
            <div ref={setBottom} />
          </Card>
          <Compose topic={data} to={to} setTo={setTo} replying={replying} setReplying={setReplying} />
        </div>
        <div className="flex min-w-0 flex-col gap-5">
          <Settle topic={data} />
          <Files files={data.files} team={data.team} onJump={reveal} />
        </div>
      </div>
      <div className="pointer-events-none fixed right-4 bottom-4 z-30 flex flex-col gap-2 sm:right-6 sm:bottom-6">
        {!topOnScreen && (
          <button
            type="button"
            className={floating}
            onClick={() => top?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
            aria-label={t('topic.toTop')}
            title={t('topic.toTop')}
          >
            <Arrow up />
          </button>
        )}
        {!bottomOnScreen && (
          <button
            type="button"
            className={`${floating} relative`}
            onClick={() => bottom?.scrollIntoView({ behavior: 'smooth', block: 'end' })}
            aria-label={t('topic.toLatest')}
            title={t('topic.toLatest')}
          >
            <Arrow />
            {newBelow > 0 && (
              <span className="absolute -top-1.5 -right-1.5 min-w-5 rounded-full bg-amber-500 px-1 text-center text-xs font-semibold text-white dark:text-stone-950">
                {newBelow}
              </span>
            )}
          </button>
        )}
      </div>
    </Page>
  )
}
