import { useMutation, useQueryClient } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, NavLink, useNavigate } from 'react-router'

import { api, call, type Me } from '../api/client'
import { useInbox } from '../api/queries'
import { Bell } from './Bell'
import { Button } from './ui'

export function LanguageSwitch() {
  const { t, i18n } = useTranslation()
  const other = i18n.resolvedLanguage === 'en' ? 'ru' : 'en'
  return (
    <Button variant="ghost" size="sm" onClick={() => void i18n.changeLanguage(other)} lang={other}>
      {t('language')}
    </Button>
  )
}

const navClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-md px-2 py-1.5 text-sm whitespace-nowrap sm:px-2.5 ${
    isActive
      ? 'bg-stone-200 font-medium text-stone-900 dark:bg-stone-800 dark:text-stone-100'
      : 'text-stone-600 hover:bg-stone-200 dark:text-stone-400 dark:hover:bg-stone-800'
  }`

export function Header({ me }: { me: Me }) {
  const { t } = useTranslation()
  const inbox = useInbox()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  // The bell counts the Topics where someone calls me, not every unread Message (decision 0026).
  const calling = inbox.data?.filter((topic) => topic.addressed).length ?? 0
  const logout = useMutation({
    mutationFn: () => call(api.POST('/api/auth/logout')),
    onSuccess: () => {
      // Nobody is logged in now: the app shows the welcome page, and nothing of the
      // previous person stays in the cache.
      queryClient.setQueryData(['me'], null)
      queryClient.removeQueries({ predicate: (q) => q.queryKey[0] !== 'me' && q.queryKey[0] !== 'providers' })
      void navigate('/')
    },
  })

  return (
    <header className="border-b border-stone-200 bg-stone-50/90 dark:border-stone-800 dark:bg-stone-950/90">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-3 gap-y-1 px-4 py-2 sm:px-6">
        <Link to="/" className="flex items-center gap-2 py-1 font-semibold tracking-tight">
          <Bell className="size-6" />
          <span>Coloqo</span>
        </Link>
        <nav className="order-last -mx-2 flex w-[calc(100%+1rem)] gap-0.5 overflow-x-auto sm:order-none sm:mx-0 sm:w-auto">
          <NavLink to="/" end className={navClass}>
            {t('nav.teams')}
          </NavLink>
          <NavLink to="/for-you" className={navClass}>
            <span className="inline-flex items-center gap-1">
              <Bell className="size-4" />
              {t('nav.forYou')}
            </span>
            {calling > 0 && (
              <span className="ml-1.5 rounded-full bg-amber-500 px-1.5 text-xs font-semibold text-white dark:bg-amber-500 dark:text-stone-950">
                {calling}
              </span>
            )}
          </NavLink>
          <NavLink to="/connect" className={navClass}>
            <span className="sm:hidden">{t('nav.connectShort')}</span>
            <span className="hidden sm:inline">{t('nav.connect')}</span>
          </NavLink>
          <NavLink to="/settings" className={navClass}>
            {t('nav.settings')}
          </NavLink>
        </nav>
        <div className="ml-auto flex items-center gap-1">
          <span className="hidden px-2 text-sm text-stone-600 sm:inline dark:text-stone-400" title={t('nav.you')}>
            {me.pseudonym}
          </span>
          <LanguageSwitch />
          <Button variant="ghost" size="sm" onClick={() => logout.mutate()} disabled={logout.isPending}>
            {t('nav.logout')}
          </Button>
        </div>
      </div>
    </header>
  )
}

export function Page({ title, aside, children }: { title?: ReactNode; aside?: ReactNode; children: ReactNode }) {
  return (
    <main className="mx-auto max-w-6xl px-4 pt-6 pb-24 sm:px-6">
      {(title || aside) && (
        <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
          {title && <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>}
          {aside}
        </div>
      )}
      {children}
    </main>
  )
}
