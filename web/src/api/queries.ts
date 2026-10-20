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

export function useTeam(team: string) {
  return useQuery({
    queryKey: ['team', team],
    queryFn: () => call(api.GET('/api/team/{team}', { params: { path: { team } } })),
    enabled: team !== '',
  })
}

export type TopicFilter = { area?: string; status?: 'open' | 'closed' }

export function useTopics(team: string, filter: TopicFilter) {
  return useQuery({
    queryKey: ['topics', team, filter],
    queryFn: () =>
      call(
        api.GET('/api/team/{team}/topic', {
          params: { path: { team }, query: { area: filter.area, status: filter.status, limit: 200 } },
        }),
      ),
    enabled: team !== '',
  })
}

export function useInbox() {
  return useQuery({ queryKey: ['inbox'], queryFn: () => call(api.GET('/api/inbox')) })
}

export function useProjects() {
  return useQuery({ queryKey: ['projects'], queryFn: () => call(api.GET('/api/project')) })
}

export function useInstallations() {
  return useQuery({ queryKey: ['installations'], queryFn: () => call(api.GET('/api/installation')) })
}
