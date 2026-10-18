import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { api, call, loginUrl } from '../api/client'
import { useProviders } from '../api/queries'
import { Bell } from '../components/Bell'
import { LanguageSwitch } from '../components/Layout'
import { PseudonymForm } from '../components/PseudonymForm'
import { Button, ErrorNote, Input } from '../components/ui'
import { currentPath, errorText } from '../lib/format'

const PROVIDER_NAMES: Record<string, string> = { github: 'GitHub', google: 'Google' }

function DevLogin() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [pseudonym, setPseudonym] = useState('')
  const login = useMutation({
    mutationFn: (name: string) => call(api.POST('/api/auth/dev', { body: { pseudonym: name } })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['me'] }),
  })
  return (
    <form
      className="flex flex-col gap-2 rounded-lg border border-dashed border-stone-300 p-4 dark:border-stone-700"
      onSubmit={(event) => {
        event.preventDefault()
        if (pseudonym.trim()) login.mutate(pseudonym.trim())
      }}
    >
      <p className="text-sm text-stone-600 dark:text-stone-400">{t('welcome.devLogin')}</p>
      <div className="flex gap-2">
        <Input
          value={pseudonym}
          onChange={(event) => setPseudonym(event.target.value)}
          placeholder="alice"
          autoCapitalize="none"
          spellCheck={false}
          aria-label={t('pseudonym.label')}
          className="max-w-56"
        />
        <Button type="submit" disabled={login.isPending || !pseudonym.trim()}>
          {t('welcome.devLoginSubmit')}
        </Button>
      </div>
      <ErrorNote>{login.error && errorText(login.error, t)}</ErrorNote>
    </form>
  )
}

function Frame({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-dvh">
      <header className="flex justify-end px-4 py-4 sm:px-8">
        <LanguageSwitch />
      </header>
      <main className="mx-auto flex max-w-2xl flex-col gap-6 px-4 pt-10 pb-24 sm:px-8 sm:pt-20">{children}</main>
    </div>
  )
}

/** The logged-out screen: what Coloqo is and how to log in, coming back to the same page. */
export function Welcome() {
  const { t } = useTranslation()
  const providers = useProviders()
  const next = currentPath()
  const real = (providers.data ?? []).filter((name) => name !== 'dev')
  return (
    <Frame>
      <Bell />
      <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">{t('welcome.title')}</h1>
      <p className="text-lg leading-relaxed text-stone-700 dark:text-stone-300">{t('welcome.lead')}</p>
      <div className="flex flex-wrap gap-3">
        {real.map((name) => (
          <a
            key={name}
            href={loginUrl(name, next)}
            className="inline-flex items-center rounded-md bg-stone-900 px-4 py-2.5 text-sm font-medium text-stone-50 hover:bg-stone-700 dark:bg-stone-100 dark:text-stone-900 dark:hover:bg-stone-300"
          >
            {t('welcome.loginWith', { provider: PROVIDER_NAMES[name] ?? name })}
          </a>
        ))}
      </div>
      {providers.isSuccess && real.length === 0 && !providers.data.includes('dev') && (
        <p className="text-sm text-stone-500 dark:text-stone-400">{t('welcome.noProviders')}</p>
      )}
      <ErrorNote>{providers.error && errorText(providers.error, t)}</ErrorNote>
      {providers.data?.includes('dev') && <DevLogin />}
    </Frame>
  )
}

/** The only screen until the person has chosen how the Team sees them. */
export function ChoosePseudonym() {
  const { t } = useTranslation()
  return (
    <Frame>
      <Bell className="size-10" />
      <h1 className="text-3xl font-semibold tracking-tight">{t('pseudonym.title')}</h1>
      <p className="leading-relaxed text-stone-700 dark:text-stone-300">{t('pseudonym.lead')}</p>
      <div className="max-w-sm">
        <PseudonymForm />
      </div>
    </Frame>
  )
}
