import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Trans, useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router'

import { ApiError, api, call, type DeviceLogin } from '../api/client'
import { Bell } from '../components/Bell'
import { Page } from '../components/Layout'
import { Button, Card, ErrorNote, Field, Input, Loading, Notice } from '../components/ui'
import { errorText } from '../lib/format'

/** Normalize a typed code to the `XXXX-XXXX` form the plugin prints. */
function normalize(code: string): string {
  const letters = code.toUpperCase().replace(/[^A-Z0-9]/g, '')
  return letters.length > 4 ? `${letters.slice(0, 4)}-${letters.slice(4, 8)}` : letters
}

function CodeForm({ onCode }: { onCode: (code: string) => void }) {
  const { t } = useTranslation()
  const [value, setValue] = useState('')
  const code = normalize(value)
  return (
    <form
      className="flex flex-col gap-3"
      onSubmit={(event) => {
        event.preventDefault()
        if (code.length === 9) onCode(code)
      }}
    >
      <Field label={t('device.codeLabel')} hint={t('device.codeHint')}>
        <Input
          value={value}
          onChange={(event) => setValue(normalize(event.target.value))}
          placeholder="BCDF-GHJK"
          autoCapitalize="characters"
          autoComplete="one-time-code"
          spellCheck={false}
          maxLength={9}
          className="max-w-48 font-mono tracking-widest"
          autoFocus
        />
      </Field>
      <div>
        <Button type="submit" variant="primary" disabled={code.length !== 9}>
          {t('device.continue')}
        </Button>
      </div>
    </form>
  )
}

function Confirm({ code, onOther }: { code: string; onOther: () => void }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const login = useQuery({
    queryKey: ['device', code],
    queryFn: () => call(api.GET('/api/device/{user_code}', { params: { path: { user_code: code } } })),
  })
  const decide = useMutation({
    mutationFn: (approve: boolean) =>
      call(
        approve
          ? api.POST('/api/device/{user_code}/approve', { params: { path: { user_code: code } } })
          : api.POST('/api/device/{user_code}/deny', { params: { path: { user_code: code } } }),
      ),
    onSuccess: (result: DeviceLogin) => {
      queryClient.setQueryData(['device', code], result)
      void queryClient.invalidateQueries({ queryKey: ['installations'] })
    },
    onError: () => void queryClient.invalidateQueries({ queryKey: ['device', code] }),
  })

  if (login.isPending) return <Loading />
  if (login.error) {
    return (
      <div className="flex flex-col gap-3">
        <ErrorNote>
          {login.error instanceof ApiError && login.error.status === 404 ? t('device.unknown') : errorText(login.error, t)}
        </ErrorNote>
        <div>
          <Button onClick={onOther}>{t('device.other')}</Button>
        </div>
      </div>
    )
  }
  const data = login.data
  return (
    <div className="flex flex-col gap-4">
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2">
        <dt className="text-sm text-stone-500 dark:text-stone-400">{t('device.code')}</dt>
        <dd className="font-mono text-lg tracking-widest">{data.user_code}</dd>
        <dt className="self-center text-sm text-stone-500 dark:text-stone-400">{t('device.name')}</dt>
        <dd className="text-lg font-semibold break-words">{data.name}</dd>
      </dl>
      {data.state === 'pending' && (
        <>
          <div
            role="note"
            className="flex gap-3 rounded-md border border-amber-300 bg-amber-50 px-3 py-2.5 text-sm leading-relaxed text-amber-950 dark:border-amber-800 dark:bg-amber-950/50 dark:text-amber-100"
          >
            <Bell className="mt-0.5 size-4 shrink-0" />
            <p>
              <Trans i18nKey="device.warning" components={{ code: <code className="font-mono text-[0.9em]" /> }} />
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="primary" onClick={() => decide.mutate(true)} disabled={decide.isPending}>
              {t('device.approve')}
            </Button>
            <Button variant="danger" onClick={() => decide.mutate(false)} disabled={decide.isPending}>
              {t('device.deny')}
            </Button>
          </div>
        </>
      )}
      {data.state === 'approved' && (
        <p className="rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-900 dark:bg-emerald-950/50 dark:text-emerald-200">
          {t('device.approved')}
        </p>
      )}
      {data.state === 'denied' && <Notice>{t('device.denied')}</Notice>}
      {data.state === 'expired' && <Notice>{t('device.expired')}</Notice>}
      <ErrorNote>{decide.error && errorText(decide.error, t)}</ErrorNote>
    </div>
  )
}

/** Confirming the plugin's login code (decision 0003); reached from `uvx coloqo login`. */
export function DevicePage() {
  const { t } = useTranslation()
  const [params, setParams] = useSearchParams()
  const code = normalize(params.get('code') ?? '')
  return (
    <Page title={t('device.title')}>
      <Card className="max-w-lg">
        <div className="flex flex-col gap-4 p-5">
          <p className="text-sm leading-relaxed text-stone-600 dark:text-stone-400">{t('device.lead')}</p>
          {code.length === 9 ? (
            <Confirm key={code} code={code} onOther={() => setParams({})} />
          ) : (
            <CodeForm onCode={(value) => setParams({ code: value })} />
          )}
        </div>
      </Card>
    </Page>
  )
}
