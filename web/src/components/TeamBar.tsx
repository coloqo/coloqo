import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import { boardPath, promisesPath, teamPath, type TeamDetail } from '../api/client'
import { Gear } from './Gear'
import { Page } from './Layout'
import { RoleBadge } from './Topics'

export type TeamSection = 'topics' | 'board' | 'promises' | 'settings'

/**
 * The line every page of a Team starts with, the same on each: the Team, the caller's role, its
 * settings, and its pages. The current page is underlined and not a link.
 */
export function TeamBar({ team, current, sub = false }: { team: TeamDetail; current: TeamSection; sub?: boolean }) {
  const { t } = useTranslation()
  const pages: { section: TeamSection; label: string; to: string }[] = [
    { section: 'topics', label: t('team.topicsPage'), to: teamPath(team.slug) },
    ...(team.tracker
      ? [
          { section: 'board' as const, label: t('board.title'), to: boardPath(team.slug) },
          { section: 'promises' as const, label: t('promises.title'), to: promisesPath(team.slug) },
        ]
      : []),
  ]
  const gear = 'inline-flex rounded-md p-1'
  return (
    <div className="mb-5 flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-stone-200 pb-3 dark:border-stone-800">
      <span className="text-lg font-semibold tracking-tight">{team.name}</span>
      <RoleBadge role={team.role} />
      {current === 'settings' ? (
        <span className={`${gear} bg-stone-200 text-stone-900 dark:bg-stone-800 dark:text-stone-100`} aria-current="page" title={t('team.settings')}>
          <Gear />
        </span>
      ) : (
        <Link
          to={`${teamPath(team.slug)}/settings`}
          className={`${gear} text-stone-500 hover:bg-stone-200 hover:text-stone-800 dark:text-stone-400 dark:hover:bg-stone-800 dark:hover:text-stone-100`}
          title={t('team.settings')}
          aria-label={t('team.settings')}
        >
          <Gear />
        </Link>
      )}
      <span className="h-5 border-l border-stone-300 dark:border-stone-700" aria-hidden="true" />
      <nav className="flex flex-wrap gap-x-4 gap-y-1 text-sm" aria-label={t('team.pages')}>
        {pages.map((page) =>
          page.section === current && !sub ? (
            <span key={page.section} aria-current="page" className="font-medium underline decoration-2 underline-offset-[6px]">
              {page.label}
            </span>
          ) : page.section === current ? (
            // A page within this one, such as a board's settings: underlined, and a way back.
            <Link key={page.section} to={page.to} className="font-medium underline decoration-2 underline-offset-[6px]">
              {page.label}
            </Link>
          ) : (
            <Link key={page.section} to={page.to} className="text-stone-600 hover:text-stone-900 dark:text-stone-400 dark:hover:text-stone-100">
              {page.label}
            </Link>
          ),
        )}
      </nav>
    </div>
  )
}

/** A page of a Team: its line, the page's title, and what the page shows. */
export function TeamPageFrame({
  team,
  current,
  title,
  aside,
  sub,
  children,
}: {
  team: TeamDetail
  current: TeamSection
  title: ReactNode
  /** A page within the current one: its menu item stays a link back. */
  sub?: boolean
  aside?: ReactNode
  children: ReactNode
}) {
  return (
    <Page>
      <TeamBar team={team} current={current} sub={sub} />
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {aside}
      </div>
      {children}
    </Page>
  )
}
