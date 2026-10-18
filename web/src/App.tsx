import { useTranslation } from 'react-i18next'
import { Link, Route, Routes } from 'react-router'

import type { Me } from './api/client'
import { useEventStream } from './api/events'
import { useMe } from './api/queries'
import { Header, Page } from './components/Layout'
import { Button, ErrorNote, Loading } from './components/ui'
import { errorText } from './lib/format'
import { ConnectPage } from './pages/Connect'
import { DevicePage } from './pages/Device'
import { Home } from './pages/Home'
import { InboxPage } from './pages/Inbox'
import { JoinPage } from './pages/Join'
import { SettingsPage } from './pages/Settings'
import { TeamPage } from './pages/Team'
import { TopicPage } from './pages/Topic'
import { ChoosePseudonym, Welcome } from './pages/Welcome'

function NotFound() {
  const { t } = useTranslation()
  return (
    <Page title={t('notFound.title')}>
      <Link to="/" className="text-amber-700 hover:underline dark:text-amber-400">
        {t('notFound.home')}
      </Link>
    </Page>
  )
}

function Shell({ me }: { me: Me }) {
  useEventStream(true)
  return (
    <div className="min-h-dvh">
      <Header me={me} />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/inbox" element={<InboxPage />} />
        <Route path="/teams/:teamId" element={<TeamPage />} />
        <Route path="/topics/:topicId" element={<TopicPage me={me} />} />
        <Route path="/device" element={<DevicePage />} />
        <Route path="/join/:token" element={<JoinPage />} />
        <Route path="/settings" element={<SettingsPage me={me} />} />
        <Route path="/connect" element={<ConnectPage me={me} />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </div>
  )
}

/**
 * Who is here decides the screen: nobody — the welcome page with login, staying on
 * the same address so that login comes back to it; no name yet — only the name form;
 * otherwise the app.
 */
export default function App() {
  const { t } = useTranslation()
  const me = useMe()
  if (me.isPending) {
    return (
      <div className="mx-auto max-w-2xl px-4 pt-24">
        <Loading />
      </div>
    )
  }
  if (me.isError) {
    return (
      <div className="mx-auto flex max-w-2xl flex-col gap-3 px-4 pt-24">
        <ErrorNote>{errorText(me.error, t)}</ErrorNote>
        <div>
          <Button onClick={() => void me.refetch()}>{t('common.retry')}</Button>
        </div>
      </div>
    )
  }
  if (!me.data) return <Welcome />
  if (!me.data.pseudonym) return <ChoosePseudonym />
  return <Shell me={me.data} />
}
