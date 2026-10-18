import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { ApiError, api, call } from '../api/client'
import { errorText } from '../lib/format'
import { Button, ErrorNote, Field, Input } from './ui'

const PSEUDONYM = /^[A-Za-z0-9][A-Za-z0-9_.-]{1,31}$/

/** Choose or change the name the Team sees. */
export function PseudonymForm({ current, onDone }: { current?: string | null; onDone?: () => void }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [value, setValue] = useState(current ?? '')
  const [touched, setTouched] = useState(false)
  const save = useMutation({
    mutationFn: (pseudonym: string) => call(api.PUT('/api/me/pseudonym', { body: { pseudonym } })),
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
