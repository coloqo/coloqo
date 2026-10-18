import { useTranslation } from 'react-i18next'

import { absoluteTime, relativeTime } from '../lib/format'

/** A time shown relative to now ("5 min ago") or absolute, with the exact time on hover. */
export function Time({ value, absolute = false }: { value: string; absolute?: boolean }) {
  const { i18n } = useTranslation()
  const lang = i18n.resolvedLanguage ?? 'ru'
  const exact = absoluteTime(value, lang, true)
  return (
    <time dateTime={value} title={exact} className="whitespace-nowrap">
      {absolute ? absoluteTime(value, lang) : relativeTime(value, lang)}
    </time>
  )
}
