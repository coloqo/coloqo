import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router'

import { ApiError, api, call } from '../api/client'
import { Page } from '../components/Layout'
import { Button, Card, ErrorNote, Loading } from '../components/ui'
import { errorText } from '../lib/format'

/** Joining a Team by a one-time invitation link. */
export function JoinPage() {
  const { t } = useTranslation()
  const token = useParams().token ?? ''
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const preview = useQuery({
    queryKey: ['invite', token],
    queryFn: () => call(api.GET('/api/invites/{token}', { params: { path: { token } } })),
  })
  const accept = useMutation({
    mutationFn: () => call(api.POST('/api/invites/{token}/accept', { params: { path: { token } } })),
    onSuccess: (team) => {
      void queryClient.invalidateQueries({ queryKey: ['teams'] })
      void navigate(`/teams/${team.id}`, { replace: true })
    },
  })
  const data = preview.data
  const gone = accept.error instanceof ApiError && accept.error.status === 410
  return (
    <Page title={t('join.title')}>
      <Card className="max-w-lg">
        <div className="flex flex-col gap-4 p-5">
          {preview.isPending && <Loading />}
          {preview.error && (
            <ErrorNote>
              {preview.error instanceof ApiError && preview.error.status === 404 ? t('join.unknown') : errorText(preview.error, t)}
            </ErrorNote>
          )}
          {data && (
            <>
              <p className="text-lg">
                {t('join.lead')} <strong className="font-semibold">{data.team_name}</strong>
              </p>
              {data.already_member ? (
                <>
                  <p className="text-sm text-stone-600 dark:text-stone-400">{t('join.already')}</p>
                  <div>
                    <Button variant="primary" onClick={() => navigate(`/teams/${data.team_id}`)}>
                      {t('join.open')}
                    </Button>
                  </div>
                </>
              ) : data.valid && !gone ? (
                <div>
                  <Button variant="primary" onClick={() => accept.mutate()} disabled={accept.isPending}>
                    {t('join.accept')}
                  </Button>
                </div>
              ) : (
                <ErrorNote>{t('join.invalid')}</ErrorNote>
              )}
              {accept.error && !gone && <ErrorNote>{errorText(accept.error, t)}</ErrorNote>}
            </>
          )}
        </div>
      </Card>
    </Page>
  )
}
