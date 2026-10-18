import type { TFunction } from 'i18next'

import { ApiError } from '../api/client'

/** Return a message to show for a failed request; the server's text when nothing better is known. */
export function errorText(error: unknown, t: TFunction): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return t('errors.unauthorized')
    if (error.status === 403) return t('errors.forbidden')
    if (error.status === 404) return t('errors.notFound')
    if (error.status === 413) return t('errors.tooLarge')
    const detail = error.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      const first: unknown = detail[0]
      if (first && typeof first === 'object' && 'msg' in first && typeof first.msg === 'string') {
        return first.msg
      }
    }
    if (detail && typeof detail === 'object' && 'message' in detail && typeof detail.message === 'string') {
      return detail.message
    }
    if (error.status >= 500) return t('errors.server')
    return t('errors.generic', { status: error.status })
  }
  if (error instanceof TypeError) return t('errors.network')
  return t('errors.unknown')
}

/** Format a time as "5 minutes ago"-style text in the given language. */
export function relativeTime(value: string | Date, lang: string, now = Date.now()): string {
  const date = typeof value === 'string' ? new Date(value) : value
  const seconds = Math.round((date.getTime() - now) / 1000)
  const format = new Intl.RelativeTimeFormat(lang, { numeric: 'auto' })
  const abs = Math.abs(seconds)
  if (abs < 45) return format.format(0, 'second')
  if (abs < 45 * 60) return format.format(Math.round(seconds / 60), 'minute')
  if (abs < 22 * 3600) return format.format(Math.round(seconds / 3600), 'hour')
  if (abs < 6 * 86400) return format.format(Math.round(seconds / 86400), 'day')
  return absoluteTime(date, lang, abs > 300 * 86400)
}

/** Format a time as a short date and clock time. */
export function absoluteTime(value: string | Date, lang: string, withYear = false): string {
  const date = typeof value === 'string' ? new Date(value) : value
  return new Intl.DateTimeFormat(lang, {
    day: 'numeric',
    month: 'short',
    year: withYear ? 'numeric' : undefined,
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

/** Format a byte count for people. */
export function fileSize(bytes: number, lang: string): string {
  const units = ['byte', 'kilobyte', 'megabyte', 'gigabyte'] as const
  let value = bytes
  let unit = 0
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024
    unit += 1
  }
  return new Intl.NumberFormat(lang, {
    style: 'unit',
    unit: units[unit],
    unitDisplay: 'short',
    maximumFractionDigits: unit === 0 ? 0 : 1,
  }).format(value)
}

/** An issue field holds a key like `ACME-42` or a link; only http(s) links become links. */
export function issueLink(issue: string): string | null {
  try {
    const url = new URL(issue)
    return url.protocol === 'https:' || url.protocol === 'http:' ? url.href : null
  } catch {
    return null
  }
}

/** The path and query of the current page, to come back to after logging in. */
export function currentPath(): string {
  return window.location.pathname + window.location.search
}
