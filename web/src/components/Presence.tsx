import { useTranslation } from 'react-i18next'

import { Time } from './Time'

/** Whether an Assistant's session runs: a green dot while it does, a grey one otherwise (decision 0029). */
export function PresenceDot({ online }: { online: boolean }) {
  const { t } = useTranslation()
  return (
    <span
      role="img"
      aria-label={online ? t('presence.online') : t('presence.offline')}
      className={`inline-block size-2 shrink-0 rounded-full ${
        online
          ? 'bg-emerald-500 shadow-[0_0_6px_1px] shadow-emerald-400/70 dark:bg-emerald-400 dark:shadow-emerald-400/50'
          : 'bg-stone-300 dark:bg-stone-600'
      }`}
    />
  )
}

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
