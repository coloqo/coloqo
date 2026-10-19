import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useParams } from 'react-router'

import { api, call } from '../api/client'
import { useOwnAssistant, useTeams } from '../api/queries'
import { Page } from '../components/Layout'
import { Button, Card, ErrorNote, Field, Loading, Notice, Select } from '../components/ui'
import { errorText } from '../lib/format'

/** Link an Assistant's project to one of the person's Teams; `coloqo link` sends people here (0020). */
export function LinkPage() {
  const { t } = useTranslation()
  const assistantId = Number(useParams().assistantId)
  const assistant = useOwnAssistant(assistantId)
  const teams = useTeams()
  const queryClient = useQueryClient()
  const [teamId, setTeamId] = useState<number | null>(null)
  const link = useMutation({
    mutationFn: (team: number) =>
      call(
        api.PUT('/api/assistants/{assistant_id}/team', {
          params: { path: { assistant_id: assistantId } },
          body: { team_id: team },
        }),
      ),
    onSuccess: (updated) => {
      queryClient.setQueryData(['assistant', assistantId], updated)
      void queryClient.invalidateQueries({ queryKey: ['assistants'] })
    },
  })

  if (assistant.isPending || teams.isPending) return <Page><Loading /></Page>
  if (assistant.error || !assistant.data) {
    return (
      <Page title={t('link.title')}>
        <ErrorNote>{errorText(assistant.error, t)}</ErrorNote>
      </Page>
    )
  }
  const current = assistant.data
  const chosen = teamId ?? current.team_id ?? teams.data?.[0]?.id ?? null
  return (
    <Page title={t('link.title')}>
      <Card className="flex max-w-xl flex-col gap-4 p-5">
        <p className="text-sm leading-relaxed text-stone-700 dark:text-stone-300">
          {t('link.lead', { name: current.name, computer: current.installation })}
        </p>
        {link.isSuccess ? (
          <Notice>{t('link.done', { team: current.team })}</Notice>
        ) : (
          <>
            {current.team && <p className="text-sm">{t('link.current', { team: current.team })}</p>}
            {teams.data && teams.data.length > 0 ? (
              <Field label={t('link.team')}>
                <Select value={chosen ?? ''} onChange={(event) => setTeamId(Number(event.target.value))}>
                  {teams.data.map((team) => (
                    <option key={team.id} value={team.id}>
                      {team.name}
                    </option>
                  ))}
                </Select>
              </Field>
            ) : (
              <Notice>{t('link.noTeams')}</Notice>
            )}
            <ErrorNote>{link.error && errorText(link.error, t)}</ErrorNote>
            <div>
              <Button variant="primary" disabled={chosen === null || link.isPending} onClick={() => chosen !== null && link.mutate(chosen)}>
                {t('link.confirm')}
              </Button>
            </div>
          </>
        )}
      </Card>
    </Page>
  )
}
