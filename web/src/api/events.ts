import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'

/** What an event names: the Team by slug and the Topic by its number (decision 0025). */
type EventData = { team?: string; topic?: number }

/**
 * Keep the cached data fresh from the server's event stream (`/api/events`).
 *
 * Each event marks the queries it affects stale; the browser reconnects by itself
 * with `Last-Event-ID`. When the stream is closed for good (the session ended, the
 * server is away), it is opened again a few seconds later after checking who is
 * logged in.
 */
export function useEventStream(enabled: boolean) {
  const queryClient = useQueryClient()
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    if (!enabled) return
    const source = new EventSource('/api/events')
    let connected = false
    let retry: number | undefined

    const parse = (event: MessageEvent<string>): EventData => {
      try {
        return JSON.parse(event.data) as EventData
      } catch {
        return {}
      }
    }
    const refreshLists = (data: EventData) => {
      if (data.team !== undefined) {
        void queryClient.invalidateQueries({ queryKey: ['topics', data.team] })
        void queryClient.invalidateQueries({ queryKey: ['team', data.team] })
      }
      void queryClient.invalidateQueries({ queryKey: ['inbox'] })
    }
    const onTopicChange = (event: MessageEvent<string>) => {
      const data = parse(event)
      if (data.team !== undefined && data.topic !== undefined) {
        void queryClient.invalidateQueries({ queryKey: ['topic', data.team, data.topic] })
      }
      refreshLists(data)
    }
    const onReady = () => {
      // After a reconnect something may have been missed while away.
      if (connected) void queryClient.invalidateQueries()
      connected = true
    }
    source.addEventListener('ready', onReady)
    source.addEventListener('message', onTopicChange)
    source.addEventListener('topic', onTopicChange)
    source.addEventListener('topic_status', onTopicChange)
    source.onerror = () => {
      if (source.readyState === EventSource.CLOSED) {
        retry = window.setTimeout(() => {
          void queryClient.invalidateQueries({ queryKey: ['me'] })
          setAttempt((n) => n + 1)
        }, 5000)
      }
    }
    return () => {
      window.clearTimeout(retry)
      source.close()
    }
  }, [enabled, attempt, queryClient])
}
