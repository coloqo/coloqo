import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useParams } from 'react-router'

import { ApiError, api, call } from '../api/client'
import { useTeams } from '../api/queries'
import { Page } from '../components/Layout'
import { Button, Card, ErrorNote, Field, Loading, Notice, Select } from '../components/ui'
import { errorText } from '../lib/format'

/**
 * Choose the Team a project is linked to, by the one-time link `coloqo link` hands out
 * (decisions 0020, 0025).
 */
export function LinkPage() {
  const { t } = useTranslation()
  const token = useParams().token ?? ''
  const teams = useTeams()
  const queryClient = useQueryClient()
  const page = useQuery({
    queryKey: ['link', token],
    queryFn: () => call(api.GET('/api/link/{token}', { params: { path: { token } } })),
  })
  const [team, setTeam] = useState<string | null>(null)
  const link = useMutation({
    mutationFn: (slug: string) =>
      call(api.PUT('/api/link/{token}', { params: { path: { token } }, body: { team: slug } })),
    onSuccess: (updated) => {
      queryClient.setQueryData(['link', token], updated)
      void queryClient.invalidateQueries({ queryKey: ['projects'] })
    },
  })

  if (page.isPending || teams.isPending) return <Page><Loading /></Page>
  if (page.error || !page.data) {
    return (
      <Page title={t('link.title')}>
        <ErrorNote>
          {page.error instanceof ApiError && page.error.status === 404 ? t('link.unknown') : errorText(page.error, t)}
        </ErrorNote>
      </Page>
    )
  }
  const current = page.data
  const chosen = team ?? current.team ?? teams.data?.[0]?.slug ?? null
  return (
    <Page title={t('link.title')}>
      <Card className="flex max-w-xl flex-col gap-4 p-5">
        <p className="text-sm leading-relaxed text-stone-700 dark:text-stone-300">
          {t('link.lead', { name: current.project, computer: current.installation })}
        </p>
        {link.isSuccess ? (
          <Notice>{t('link.done', { team: current.team_name })}</Notice>
        ) : !current.valid ? (
          <ErrorNote>{t('link.expired')}</ErrorNote>
        ) : (
          <>
            {current.team_name && <p className="text-sm">{t('link.current', { team: current.team_name })}</p>}
            {teams.data && teams.data.length > 0 ? (
              <Field label={t('link.team')}>
                <Select value={chosen ?? ''} onChange={(event) => setTeam(event.target.value)}>
                  {teams.data.map((option) => (
                    <option key={option.slug} value={option.slug}>
                      {option.name}
                    </option>
                  ))}
                </Select>
              </Field>
            ) : (
              <Notice>{t('link.noTeams')}</Notice>
            )}
            <ErrorNote>{link.error && errorText(link.error, t)}</ErrorNote>
            <div>
              <Button
                variant="primary"
                disabled={chosen === null || link.isPending}
                onClick={() => chosen !== null && link.mutate(chosen)}
              >
                {t('link.confirm')}
              </Button>
            </div>
          </>
        )}
      </Card>
    </Page>
  )
}

/** The page plugins older than 0.5.0 open to link a project; it lives no more (decision 0025). */
export function OldLinkPage() {
  const { t } = useTranslation()
  return (
    <Page title={t('link.title')}>
      <Card className="flex max-w-xl flex-col gap-3 p-5">
        <p className="text-sm leading-relaxed text-stone-700 dark:text-stone-300">{t('link.oldPlugin')}</p>
      </Card>
    </Page>
  )
}
