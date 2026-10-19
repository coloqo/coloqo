import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { ApiError, api, call } from '../api/client'
import { errorText } from '../lib/format'
import { Button, ErrorNote, Field, Input } from './ui'

const PSEUDONYM = /^[A-Za-z0-9][A-Za-z0-9_.-]{1,31}$/

/**
 * Choose or change the name the Team sees. On the first login through GitHub it also offers to
 * take the GitHub avatar once, checked by default (decision 0019).
 */
export function PseudonymForm({
  current,
  offerGithubAvatar = false,
  onDone,
}: {
  current?: string | null
  offerGithubAvatar?: boolean
  onDone?: () => void
}) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [value, setValue] = useState(current ?? '')
  const [touched, setTouched] = useState(false)
  const [githubAvatar, setGithubAvatar] = useState(true)
  const save = useMutation({
    mutationFn: async (pseudonym: string) => {
      const me = await call(api.PUT('/api/me/pseudonym', { body: { pseudonym } }))
      if (!offerGithubAvatar || !githubAvatar) return me
      try {
        // A GitHub that does not answer leaves the initials; the login goes on.
        await call(api.POST('/api/me/avatar/github'))
        return await call(api.GET('/api/me'))
      } catch {
        return me
      }
    },
    onSuccess: (me) => {
      queryClient.setQueryData(['me'], me)
      // Names shown in Teams and Topics change with it.
      void queryClient.invalidateQueries({ predicate: (q) => q.queryKey[0] !== 'me' })
      onDone?.()
    },
  })
  const trimmed = value.trim()
  const valid = PSEUDONYM.test(trimmed)
  const error = save.error
  let message: string | null = null
  if (touched && trimmed && !valid) message = t('pseudonym.malformed')
  else if (error instanceof ApiError && error.status === 409) message = t('pseudonym.taken')
  else if (error instanceof ApiError && error.status === 422) message = t('pseudonym.malformed')
  else if (error) message = errorText(error, t)

  return (
    <form
      className="flex flex-col gap-3"
      onSubmit={(event) => {
        event.preventDefault()
        setTouched(true)
        if (valid && trimmed !== current) save.mutate(trimmed)
      }}
    >
      <Field label={t('pseudonym.label')} hint={t('pseudonym.hint')}>
        <Input
          value={value}
          onChange={(event) => {
            setValue(event.target.value)
            save.reset()
          }}
          onBlur={() => setTouched(true)}
          autoComplete="username"
          autoCapitalize="none"
          spellCheck={false}
          maxLength={32}
          placeholder="alice"
          required
        />
      </Field>
      {offerGithubAvatar && (
        <label className="flex items-start gap-2 text-sm text-stone-700 dark:text-stone-300">
          <input
            type="checkbox"
            className="mt-0.5 size-4 accent-amber-600"
            checked={githubAvatar}
            onChange={(event) => setGithubAvatar(event.target.checked)}
          />
          <span>{t('pseudonym.githubAvatar')}</span>
        </label>
      )}
      <ErrorNote>{message}</ErrorNote>
      {save.isSuccess && current && <p className="text-sm text-emerald-700 dark:text-emerald-400">{t('common.saved')}</p>}
      <div>
        <Button type="submit" variant="primary" disabled={save.isPending || !trimmed || trimmed === current}>
          {current ? t('common.save') : t('pseudonym.submit')}
        </Button>
      </div>
    </form>
  )
}
