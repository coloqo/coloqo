import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router'

import { api, call, teamPath } from '../api/client'
import { useInbox, useTeams } from '../api/queries'
import { Page } from '../components/Layout'
import { RoleBadge } from '../components/Topics'
import { Button, Card, CardHeader, Empty, ErrorNote, Input, Loading } from '../components/ui'
import { errorText } from '../lib/format'

function CreateTeam() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const create = useMutation({
    mutationFn: (value: string) => call(api.POST('/api/team', { body: { name: value } })),
    onSuccess: (team) => {
      void queryClient.invalidateQueries({ queryKey: ['teams'] })
      void navigate(teamPath(team.slug))
    },
  })
  return (
    <form
      className="flex flex-col gap-2 px-4 py-4"
      onSubmit={(event) => {
        event.preventDefault()
        if (name.trim()) create.mutate(name.trim())
      }}
    >
      <span className="text-sm font-medium text-stone-700 dark:text-stone-300">{t('home.createTeam')}</span>
      <div className="flex gap-2">
        <Input
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder={t('home.teamNamePlaceholder')}
          maxLength={100}
          aria-label={t('home.teamName')}
        />
        <Button type="submit" variant="primary" disabled={create.isPending || !name.trim()}>
          {t('common.create')}
        </Button>
      </div>
      <ErrorNote>{create.error && errorText(create.error, t)}</ErrorNote>
    </form>
  )
}

export function Home() {
  const { t } = useTranslation()
  const teams = useTeams()
  const inbox = useInbox()
  const unreadByTeam = new Map<string, number>()
  for (const topic of inbox.data ?? []) unreadByTeam.set(topic.team, (unreadByTeam.get(topic.team) ?? 0) + 1)
  const addressed = inbox.data?.filter((topic) => topic.addressed).length ?? 0

  return (
    <Page title={t('home.title')}>
      <div className="grid gap-5 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <Card>
          <CardHeader title={t('home.teams')} />
          {teams.isPending && <Loading />}
          <ErrorNote>{teams.error && errorText(teams.error, t)}</ErrorNote>
          {teams.data?.length === 0 && <Empty>{t('home.noTeams')}</Empty>}
          {teams.data && teams.data.length > 0 && (
            <ul className="divide-y divide-stone-200 dark:divide-stone-800">
              {teams.data.map((team) => (
                <li key={team.slug}>
                  <Link
                    to={teamPath(team.slug)}
                    className="flex items-center justify-between gap-3 px-4 py-3 hover:bg-stone-50 dark:hover:bg-stone-800/50"
                  >
                    <span className="font-medium">{team.name}</span>
                    <span className="flex items-center gap-2">
                      {(unreadByTeam.get(team.slug) ?? 0) > 0 && (
                        <span
                          className="rounded-full bg-amber-500 px-2 py-0.5 text-xs font-semibold text-white dark:text-stone-950"
                          title={t('home.unreadInTeam', { count: unreadByTeam.get(team.slug) })}
                        >
                          {unreadByTeam.get(team.slug)}
                        </span>
                      )}
                      <RoleBadge role={team.role} />
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
          <div className="border-t border-stone-200 dark:border-stone-800">
            <CreateTeam />
          </div>
        </Card>
        <div className="flex flex-col gap-5">
          <Card>
            <CardHeader title={t('nav.forYou')} />
            <Link to="/for-you" className="block px-4 py-4 hover:bg-stone-50 dark:hover:bg-stone-800/50">
              {addressed === 0 ? (
                <span className="text-sm text-stone-500 dark:text-stone-400">{t('forYou.empty')}</span>
              ) : (
                <span className="text-sm font-medium text-amber-700 dark:text-amber-400">
                  {t('home.addressedTopics', { count: addressed })}
                </span>
              )}
            </Link>
          </Card>
          <Card>
            <CardHeader title={t('nav.connect')} />
            <div className="flex flex-col gap-3 px-4 py-4 text-sm text-stone-600 dark:text-stone-400">
              <p>{t('home.connectLead')}</p>
              <Link to="/connect" className="font-medium text-amber-700 hover:underline dark:text-amber-400">
                {t('home.connectLink')}
              </Link>
            </div>
          </Card>
        </div>
      </div>
    </Page>
  )
}
