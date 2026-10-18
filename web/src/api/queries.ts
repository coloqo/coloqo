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
  return useQuery({ queryKey: ['teams'], queryFn: () => call(api.GET('/api/teams')) })
}

export function useTeam(teamId: number) {
  return useQuery({
    queryKey: ['team', teamId],
    queryFn: () => call(api.GET('/api/teams/{team_id}', { params: { path: { team_id: teamId } } })),
  })
}

export type TopicFilter = { areaId?: number; status?: 'open' | 'closed' }

export function useTopics(teamId: number, filter: TopicFilter) {
  return useQuery({
    queryKey: ['topics', teamId, filter],
    queryFn: () =>
      call(
        api.GET('/api/teams/{team_id}/topics', {
          params: {
            path: { team_id: teamId },
            query: { area_id: filter.areaId, status: filter.status, limit: 200 },
          },
        }),
      ),
  })
}

export function useTopic(topicId: number) {
  return useQuery({
    queryKey: ['topic', topicId],
    queryFn: () =>
      call(
        api.GET('/api/topics/{topic_id}', {
          params: { path: { topic_id: topicId }, query: { after: 0, limit: 500 } },
        }),
      ),
  })
}

export function useInbox() {
  return useQuery({ queryKey: ['inbox'], queryFn: () => call(api.GET('/api/inbox')) })
}

export function useInstallations() {
  return useQuery({ queryKey: ['installations'], queryFn: () => call(api.GET('/api/installations')) })
}
