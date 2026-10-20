import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import { topicPath, type Schemas, type Topic } from '../api/client'
import { Bell } from './Bell'
import { Time } from './Time'
import { Badge } from './ui'

export function RoleBadge({ role }: { role: Schemas['Role'] }) {
  const { t } = useTranslation()
  return <Badge tone={role === 'owner' ? 'amber' : 'stone'}>{t(`roles.${role}`)}</Badge>
}

export function StatusBadge({ status }: { status: Schemas['TopicStatus'] }) {
  const { t } = useTranslation()
  return <Badge tone={status === 'open' ? 'green' : 'stone'}>{t(`topic.status.${status}`)}</Badge>
}

/** One Topic in a list: reference, question, where it is and whether it waits for me. */
export function TopicRow({ topic, teamName }: { topic: Topic; teamName?: string }) {
  const { t } = useTranslation()
  const waiting = topic.status === 'open' && topic.turns_since_human >= topic.turn_limit
  return (
    <li>
      <Link
        to={topicPath(topic.team, topic.number)}
        className="flex gap-3 px-4 py-3 hover:bg-stone-50 dark:hover:bg-stone-800/50"
      >
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <div className="flex items-start gap-2">
            <span className="shrink-0 pt-px font-mono text-xs text-stone-500 dark:text-stone-400">{topic.ref}</span>
            <span className={`min-w-0 break-words ${topic.unread > 0 ? 'font-semibold' : 'font-medium'}`}>
              {topic.title}
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-stone-500 dark:text-stone-400">
            {teamName && <span>{teamName}</span>}
            <span>{topic.area_name}</span>
            {topic.holder && <span title={t('topic.holder')}>{topic.holder}</span>}
            {topic.status === 'closed' && <StatusBadge status="closed" />}
            {waiting && <Badge tone="amber">{t('topic.waitsForHuman')}</Badge>}
            <Time value={topic.updated_at} />
          </div>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1">
          {topic.addressed && (
            <span
              className="inline-flex items-center gap-1 text-xs font-medium text-amber-700 dark:text-amber-400"
              title={t('topic.addressedHint')}
            >
              <Bell className="size-3.5" />
              {t('topic.addressed')}
            </span>
          )}
          {topic.unread > 0 && (
            <span
              className="rounded-full bg-amber-500 px-2 py-0.5 text-xs font-semibold text-white dark:text-stone-950"
              title={t('topic.unreadHint', { count: topic.unread })}
            >
              {topic.unread}
            </span>
          )}
        </div>
      </Link>
    </li>
  )
}

export function TopicList({ topics, teamNames }: { topics: Topic[]; teamNames?: Map<string, string> }) {
  return (
    <ul className="divide-y divide-stone-200 dark:divide-stone-800">
      {topics.map((topic) => (
        <TopicRow key={`${topic.team}/${topic.number}`} topic={topic} teamName={teamNames?.get(topic.team)} />
      ))}
    </ul>
  )
}
