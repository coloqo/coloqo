import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router'

import {
  ApiError,
  api,
  call,
  uploadFile,
  type FileInfo,
  type Me,
  type Message,
  type TopicDetail,
} from '../api/client'
import { useTeam, useTopic } from '../api/queries'
import { AddresseeSelect } from '../components/AddresseeSelect'
import { Bell } from '../components/Bell'
import { Page } from '../components/Layout'
import { Markdown } from '../components/Markdown'
import { Time } from '../components/Time'
import { StatusBadge } from '../components/Topics'
import { Badge, Button, Card, CardHeader, ErrorNote, Field, Loading, Notice, Textarea } from '../components/ui'
import { errorText, fileSize, issueLink } from '../lib/format'

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
function useDraft(topicId: number) {
  const key = `coloqo.draft.${topicId}`
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

function FileLink({ file }: { file: FileInfo }) {
  const { i18n } = useTranslation()
  return (
    <a
      href={`/api/files/${file.id}`}
      download={file.name}
      className="inline-flex max-w-full items-center gap-1.5 rounded-md border border-stone-200 px-2 py-1 text-sm hover:bg-stone-50 dark:border-stone-700 dark:hover:bg-stone-800"
    >
      <span className="truncate font-medium text-amber-700 dark:text-amber-400">{file.name}</span>
      <span className="shrink-0 text-xs text-stone-500 dark:text-stone-400">{fileSize(file.size, i18n.resolvedLanguage ?? 'ru')}</span>
    </a>
  )
}

function MessageItem({
  message,
  me,
  unread,
  onReply,
}: {
  message: Message
  me: Me
  unread: boolean
  onReply: (to: string) => void
}) {
  const { t } = useTranslation()
  const human = message.assistant === null
  const toMe = message.to !== null && message.to === me.pseudonym
  const addressee = message.to_assistant ?? message.to
  const replyTo = message.assistant ?? message.author
  return (
    <li
      id={`m-${message.number}`}
      className={`scroll-mt-4 border-l-2 px-4 py-3 ${
        toMe ? 'border-amber-500 bg-amber-50/50 dark:bg-amber-950/20' : 'border-transparent'
      }`}
    >
      <div className="mb-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
        <span className="font-mono text-xs text-stone-500 dark:text-stone-400">#{message.number}</span>
        {human ? (
          <>
            <span className="font-semibold">{message.author ?? t('team.noName')}</span>
            <Badge tone="blue">{t('message.human')}</Badge>
          </>
        ) : (
          <span className="font-semibold">{message.assistant}</span>
        )}
        {message.relayed && <Badge tone="blue">{t('message.relayed')}</Badge>}
        {message.kind === 'progress' && <Badge>{t('message.progress')}</Badge>}
        {addressee && (
          <span className={`inline-flex items-center gap-1 ${toMe ? 'font-medium text-amber-800 dark:text-amber-300' : 'text-stone-600 dark:text-stone-400'}`}>
            {toMe && <Bell className="size-3.5" />}→ {addressee}
          </span>
        )}
        {unread && <Badge tone="amber">{t('message.new')}</Badge>}
        <span className="ml-auto flex items-center gap-2 text-xs text-stone-500 dark:text-stone-400">
          <Time value={message.created_at} absolute />
          {replyTo && replyTo !== me.pseudonym && (
            <button
              type="button"
              className="rounded px-1.5 py-0.5 hover:bg-stone-200 hover:text-stone-800 dark:hover:bg-stone-800 dark:hover:text-stone-200"
              onClick={() => onReply(replyTo)}
            >
              {t('message.reply')}
            </button>
          )}
        </span>
      </div>
      <Markdown text={message.body} />
      {message.files.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-2">
          {message.files.map((file) => (
            <FileLink key={file.id} file={file} />
          ))}
        </div>
      )}
    </li>
  )
}

function Compose({
  topic,
  to,
  setTo,
}: {
  topic: TopicDetail
  to: string
  setTo: (value: string) => void
}) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const team = useTeam(topic.team_id)
  const [body, setBody] = useDraft(topic.id)
  const [attached, setAttached] = useState<FileInfo[]>([])
  const [uploading, setUploading] = useState(0)
  const [uploadError, setUploadError] = useState<unknown>(null)
  const [conflict, setConflict] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ['topic', topic.id] })
    void queryClient.invalidateQueries({ queryKey: ['topics', topic.team_id] })
    void queryClient.invalidateQueries({ queryKey: ['team', topic.team_id] })
    void queryClient.invalidateQueries({ queryKey: ['inbox'] })
  }
  const send = useMutation({
    mutationFn: () =>
      call(
        api.POST('/api/topics/{topic_id}/messages', {
          params: { path: { topic_id: topic.id } },
          body: {
            number: topic.last_number + 1,
            body,
            to: to || null,
            file_ids: attached.map((file) => file.id),
          },
        }),
      ),
    onSuccess: () => {
      setBody('')
      setAttached([])
      setConflict(false)
      setTo('')
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
        const info = await uploadFile(topic.id, file)
        setAttached((list) => [...list, info])
        void queryClient.invalidateQueries({ queryKey: ['topic', topic.id] })
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
                key={file.id}
                className="inline-flex items-center gap-1 rounded-md bg-stone-100 py-0.5 pr-0.5 pl-2 text-sm dark:bg-stone-800"
              >
                <span className="max-w-48 truncate">{file.name}</span>
                <button
                  type="button"
                  className="rounded px-1.5 text-stone-500 hover:bg-stone-200 hover:text-stone-900 dark:hover:bg-stone-700 dark:hover:text-stone-100"
                  onClick={() => setAttached((list) => list.filter((item) => item.id !== file.id))}
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
        api.PATCH('/api/topics/{topic_id}', {
          params: { path: { topic_id: topic.id } },
          body: { status, outcome: status === 'closed' ? outcome.trim() : '' },
        }),
      ),
    onSuccess: () => {
      setClosing(false)
      setOutcome('')
      void queryClient.invalidateQueries({ queryKey: ['topic', topic.id] })
      void queryClient.invalidateQueries({ queryKey: ['topics', topic.team_id] })
      void queryClient.invalidateQueries({ queryKey: ['team', topic.team_id] })
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

function Files({ files }: { files: FileInfo[] }) {
  const { t } = useTranslation()
  if (files.length === 0) return null
  return (
    <Card>
      <CardHeader title={t('files.title')} />
      <ul className="divide-y divide-stone-200 dark:divide-stone-800">
        {files.map((file) => (
          <li key={file.id} className="flex flex-col gap-1 px-4 py-2.5">
            <FileLink file={file} />
            <span className="text-xs text-stone-500 dark:text-stone-400">
              {file.uploaded_by ?? t('team.noName')} · <Time value={file.created_at} />
              {' · '}
              {file.message_number !== null ? (
                <a href={`#m-${file.message_number}`} className="hover:underline">
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
  const { t } = useTranslation()
  const link = topic.issue ? issueLink(topic.issue) : null
  const waiting = topic.status === 'open' && topic.turns_since_human >= topic.turn_limit
  return (
    <div className="mb-5 flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-stone-500 dark:text-stone-400">
        <span className="font-mono">{topic.ref}</span>
        <Link to={`/teams/${topic.team_id}?area=${topic.area_id}`} className="hover:underline">
          {topic.area}
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

export function TopicPage({ me }: { me: Me }) {
  const { t } = useTranslation()
  const topicId = Number(useParams().topicId)
  const topic = useTopic(topicId)
  const queryClient = useQueryClient()
  const visible = usePageVisible()
  const [to, setTo] = useState('')
  // Messages unread when the page opened, and those arriving while it is open, stay marked "new".
  const [newFrom, setNewFrom] = useState<number | null>(null)
  const scrolled = useRef(false)
  const marking = useRef(0)

  const data = topic.data
  const lastNumber = data?.last_number ?? 0
  const unread = data?.unread ?? 0

  useEffect(() => {
    if (!data || scrolled.current) return
    scrolled.current = true
    const first = data.last_number - data.unread + 1
    setNewFrom(first)
    if (data.unread > 0) {
      window.requestAnimationFrame(() => document.getElementById(`m-${first}`)?.scrollIntoView({ block: 'start' }))
    }
  }, [data])

  // Reading is recorded while the page is in front, up to the newest Message.
  useEffect(() => {
    if (!visible || unread === 0 || lastNumber <= marking.current) return
    marking.current = lastNumber
    void call(api.POST('/api/topics/{topic_id}/read', { params: { path: { topic_id: topicId } }, body: { number: lastNumber } }))
      .then((out) => {
        queryClient.setQueryData<TopicDetail>(['topic', topicId], (old) => (old ? { ...old, unread: out.unread, addressed: out.addressed } : old))
        void queryClient.invalidateQueries({ queryKey: ['inbox'] })
        void queryClient.invalidateQueries({ queryKey: ['topics', out.team_id] })
      })
      .catch(() => {
        marking.current = 0
      })
  }, [visible, unread, lastNumber, topicId, queryClient])

  if (topic.isPending) return <Page><Loading /></Page>
  if (topic.error || !data) {
    return (
      <Page title={t('topic.notFoundTitle')}>
        <ErrorNote>{errorText(topic.error, t)}</ErrorNote>
      </Page>
    )
  }

  const reply = (name: string) => {
    setTo(name)
    const box = document.getElementById('compose-body')
    box?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    box?.focus({ preventScroll: true })
  }

  return (
    <Page>
      <TopicHeader topic={data} />
      <div className="grid gap-5 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <div className="flex min-w-0 flex-col gap-5">
          <Card>
            <CardHeader title={t('topic.messages', { count: data.last_number })} />
            {data.messages.length < data.last_number && (
              <Notice>{t('topic.truncated', { count: data.messages.length })}</Notice>
            )}
            <ol className="divide-y divide-stone-200 dark:divide-stone-800">
              {data.messages.map((message) => (
                <MessageItem
                  key={message.number}
                  message={message}
                  me={me}
                  unread={
                    newFrom !== null &&
                    message.number >= newFrom &&
                    !(message.assistant === null && message.author === me.pseudonym)
                  }
                  onReply={reply}
                />
              ))}
            </ol>
          </Card>
          <Compose topic={data} to={to} setTo={setTo} />
        </div>
        <div className="flex min-w-0 flex-col gap-5">
          <Settle topic={data} />
          <Files files={data.files} />
        </div>
      </div>
    </Page>
  )
}
