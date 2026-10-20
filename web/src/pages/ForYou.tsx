import { useTranslation } from 'react-i18next'

import { useInbox, useTeams } from '../api/queries'
import { Page } from '../components/Layout'
import { TopicList } from '../components/Topics'
import { Card, Empty, ErrorNote, Loading } from '../components/ui'
import { errorText } from '../lib/format'

/**
 * "For you": the Topics where someone addresses me and I have not read it (decision 0026).
 * Other unread Messages show as counters in the lists of Topics, where they live.
 */
export function ForYouPage() {
  const { t } = useTranslation()
  const inbox = useInbox()
  const teams = useTeams()
  const names = new Map((teams.data ?? []).map((team) => [team.slug, team.name]))
  const addressed = inbox.data?.filter((topic) => topic.addressed) ?? []
  return (
    <Page title={t('forYou.title')}>
      <div className="flex max-w-3xl flex-col gap-5">
        <p className="text-sm text-stone-600 dark:text-stone-400">{t('forYou.lead')}</p>
        {inbox.isPending && <Loading />}
        <ErrorNote>{inbox.error && errorText(inbox.error, t)}</ErrorNote>
        {inbox.data && (
          <Card>
            {addressed.length === 0 ? (
              <Empty>{t('forYou.empty')}</Empty>
            ) : (
              <TopicList topics={addressed} teamNames={names.size > 1 ? names : undefined} />
            )}
          </Card>
        )}
      </div>
    </Page>
  )
}
