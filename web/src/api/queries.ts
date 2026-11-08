import { useQuery } from '@tanstack/react-query'

import { ApiError, api, call, type Me } from './client'

/** Who is logged in; `null` when nobody is (the server answers 401). */
export function useMe() {
  return useQuery({
    queryKey: ['me'],
    queryFn: async (): Promise<Me | null> => {
      try {
        return await call(api.GET('/api/me'))
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) return null
        throw error
      }
    },
    staleTime: 60_000,
  })
}

export function useProviders() {
  return useQuery({
    queryKey: ['providers'],
    queryFn: () => call(api.GET('/api/auth/providers')),
    staleTime: Infinity,
  })
}

export function useTeams() {
  return useQuery({ queryKey: ['teams'], queryFn: () => call(api.GET('/api/team')) })
}

/** Which sessions are online changes with no event (decision 0029): pages that show it ask again this often. */
const PRESENCE_MS = 30_000

export function useTeam(team: string) {
  return useQuery({
    queryKey: ['team', team],
    queryFn: () => call(api.GET('/api/team/{team}', { params: { path: { team } } })),
    enabled: team !== '',
    refetchInterval: PRESENCE_MS,
  })
}

export type TopicFilter = { area?: string; status?: 'open' | 'closed'; kind?: 'task' | 'free' }

export function useTopics(team: string, filter: TopicFilter) {
  return useQuery({
    queryKey: ['topics', team, filter],
    queryFn: () =>
      call(
        api.GET('/api/team/{team}/topic', {
          params: { path: { team }, query: { area: filter.area, status: filter.status, kind: filter.kind, limit: 200 } },
        }),
      ),
    enabled: team !== '',
  })
}

/** A task with its description, timeline and Topic (decision 0031). */
export function useTask(team: string, number: number) {
  return useQuery({
    queryKey: ['task', team, number],
    queryFn: () => call(api.GET('/api/team/{team}/task/{number}', { params: { path: { team, number } } })),
    enabled: team !== '' && number > 0,
  })
}

export type TaskFilter = { type?: 'task' | 'promise'; category?: 'to_do' | 'in_progress' | 'finished' }

export function useTasks(team: string, filter: TaskFilter = {}) {
  return useQuery({
    queryKey: ['tasks', team, filter],
    queryFn: () =>
      call(api.GET('/api/team/{team}/task', { params: { path: { team }, query: { ...filter, limit: 500 } } })),
    enabled: team !== '',
  })
}

export type BoardFilter = { area?: string; assignee?: string; promise?: number }

/** The board with its cards; whose move changes with no event, so it is asked again (0033). */
export function useBoard(team: string, filter: BoardFilter) {
  return useQuery({
    queryKey: ['board', team, filter],
    queryFn: () => call(api.GET('/api/team/{team}/board', { params: { path: { team }, query: filter } })),
    enabled: team !== '',
    refetchInterval: PRESENCE_MS,
  })
}

export function useWorkflows(team: string) {
  return useQuery({
    queryKey: ['workflows', team],
    queryFn: () => call(api.GET('/api/team/{team}/workflow', { params: { path: { team } } })),
    enabled: team !== '',
  })
}

export function useInbox() {
  return useQuery({ queryKey: ['inbox'], queryFn: () => call(api.GET('/api/inbox')) })
}

export function useProjects() {
  return useQuery({ queryKey: ['projects'], queryFn: () => call(api.GET('/api/project')), refetchInterval: PRESENCE_MS })
}

export function useInstallations() {
  return useQuery({ queryKey: ['installations'], queryFn: () => call(api.GET('/api/installation')) })
}
