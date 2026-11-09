import { useTranslation } from 'react-i18next'

import { Time } from './Time'

/** "online", or when an offline session was last seen. */
export function PresenceText({ online, lastSeen }: { online: boolean; lastSeen: string | null }) {
  const { t } = useTranslation()
  if (online) {
    return <span className="text-xs text-emerald-700 dark:text-emerald-400">{t('presence.online')}</span>
  }
  if (!lastSeen) {
    return null
  }
  return (
    <span className="text-xs text-stone-500 dark:text-stone-400">
      {t('team.lastSeen')} <Time value={lastSeen} />
    </span>
  )
}
