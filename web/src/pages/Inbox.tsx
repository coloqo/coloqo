import { useTranslation } from 'react-i18next'

import { useInbox, useTeams } from '../api/queries'
import { Page } from '../components/Layout'
import { TopicList } from '../components/Topics'
import { Card, CardHeader, Empty, ErrorNote, Loading } from '../components/ui'
import { errorText } from '../lib/format'

/** Topics with Messages I have not read; those addressed to me first (the server orders them). */
export function InboxPage() {
  const { t } = useTranslation()
  const inbox = useInbox()
  const teams = useTeams()
  const names = new Map((teams.data ?? []).map((team) => [team.id, team.name]))
  const multipleTeams = names.size > 1
  const addressed = inbox.data?.filter((topic) => topic.addressed) ?? []
  const other = inbox.data?.filter((topic) => !topic.addressed) ?? []
  return (
    <Page title={t('inbox.title')}>
      <div className="flex max-w-3xl flex-col gap-5">
        {inbox.isPending && <Loading />}
        <ErrorNote>{inbox.error && errorText(inbox.error, t)}</ErrorNote>
        {inbox.data?.length === 0 && (
          <Card>
            <Empty>{t('inbox.empty')}</Empty>
          </Card>
        )}
        {addressed.length > 0 && (
          <Card>
            <CardHeader title={t('inbox.addressed')} />
            <TopicList topics={addressed} teamNames={multipleTeams ? names : undefined} />
          </Card>
        )}
        {other.length > 0 && (
          <Card>
            <CardHeader title={t('inbox.other')} />
            <TopicList topics={other} teamNames={multipleTeams ? names : undefined} />
          </Card>
        )}
      </div>
    </Page>
  )
}
