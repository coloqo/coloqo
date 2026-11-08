import { QueryCache, QueryClient, MutationCache } from '@tanstack/react-query'
import createClient from 'openapi-fetch'

import type { components, paths } from './schema'

export type Schemas = components['schemas']
export type Me = Schemas['Me']
export type Team = Schemas['TeamOut']
export type TeamDetail = Schemas['TeamDetail']
export type Member = Schemas['MemberOut']
export type Area = Schemas['AreaOut']
export type Topic = Schemas['TopicOut']
export type TopicDetail = Schemas['TopicDetail']
export type Message = Schemas['MessageOut']
export type FileInfo = Schemas['FileOut']
export type Installation = Schemas['InstallationOut']
export type Project = Schemas['ProjectOut']
export type Assistant = Schemas['AssistantOut']
export type LinkPage = Schemas['LinkPage']
export type DeviceLogin = Schemas['DeviceLoginOut']
export type InvitePreview = Schemas['InvitePreview']
export type Invite = Schemas['InviteOut']

/** An API answer that is not a success, with the server's `detail`. */
export class ApiError extends Error {
  readonly status: number
  readonly detail: unknown

  constructor(status: number, detail: unknown) {
    super(typeof detail === 'string' ? detail : `HTTP ${status}`)
    this.status = status
    this.detail = detail
  }

  /** The machine-readable code of a structured detail, such as `number_taken`. */
  get code(): string | undefined {
    const detail = this.detail
    if (detail && typeof detail === 'object' && 'code' in detail && typeof detail.code === 'string') {
      return detail.code
    }
    return undefined
  }
}

/** Any 401 means the session is gone: the app drops back to the login screen. */
function onUnauthorized(error: unknown) {
  if (error instanceof ApiError && error.status === 401) {
    void queryClient.invalidateQueries({ queryKey: ['me'] })
  }
}

export const queryClient = new QueryClient({
  queryCache: new QueryCache({ onError: onUnauthorized }),
  mutationCache: new MutationCache({ onError: onUnauthorized }),
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      retry: (count, error) => !(error instanceof ApiError && error.status < 500) && count < 2,
    },
  },
})

// Same origin: the session cookie goes along, and the browser sets `Origin` on
// state-changing requests, which the server checks (decision 0013).
export const api = createClient<paths>({ baseUrl: '' })

/** Return the data of an API call, or throw `ApiError` for an error answer. */
export async function call<D>(
  request: Promise<{ data?: D; error?: unknown; response: Response }>,
): Promise<D> {
  const { data, error, response } = await request
  if (!response.ok) {
    const detail =
      error && typeof error === 'object' && 'detail' in error ? error.detail : (error ?? response.statusText)
    throw new ApiError(response.status, detail)
  }
  return data as D
}

/** Upload a file into a Topic; the body is the raw content. */
/** How a Topic is named: by its task, ``T-42``, or by its free number, ``F-5`` (decision 0031). */
export type TopicKind = 'task' | 'free'

export async function uploadFile(team: string, topic: number, file: File, kind: TopicKind = 'free'): Promise<FileInfo> {
  // The upload endpoint takes a raw body, which the OpenAPI document does not
  // describe, so it goes through plain fetch.
  const response = await fetch(`/api/team/${encodeURIComponent(team)}/${kind === 'task' ? 'task' : 'topic'}/${topic}/file`, {
    method: 'POST',
    headers: {
      'X-File-Name': encodeURIComponent(file.name),
      'Content-Type': file.type || 'application/octet-stream',
    },
    body: file,
  })
  const body: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = body && typeof body === 'object' && 'detail' in body ? body.detail : response.statusText
    const error = new ApiError(response.status, detail)
    onUnauthorized(error)
    throw error
  }
  return body as FileInfo
}

/** Set the person's avatar from a picture; the server re-encodes it (decision 0019). */
export async function uploadAvatar(file: File): Promise<void> {
  // The avatar endpoint takes a raw body, which the OpenAPI document does not describe.
  const response = await fetch('/api/me/avatar', {
    method: 'PUT',
    headers: { 'Content-Type': file.type || 'application/octet-stream' },
    body: file,
  })
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null)
    const detail = body && typeof body === 'object' && 'detail' in body ? body.detail : response.statusText
    const error = new ApiError(response.status, detail)
    onUnauthorized(error)
    throw error
  }
}

/** Where a file is served: an image inline, any other file as an attachment (decisions 0018, 0025). */
export const fileUrl = (team: string, file: FileInfo) => `/api/team/${encodeURIComponent(team)}/file/${file.number}`

/** Where a file is served as an attachment, an image too. */
export const downloadUrl = (team: string, file: FileInfo) => `${fileUrl(team, file)}?download=1`

/** The address of a Team's page (decision 0025). */
export const teamPath = (team: string) => `/team/${encodeURIComponent(team)}`

/** The address of an Area's page. */
export const areaPath = (team: string, area: string) => `${teamPath(team)}/area/${encodeURIComponent(area)}`

/** The address of a Topic's page: a task's at /task/N, a free one's at /topic/N (decision 0031). */
export const topicPath = (team: string, number: number, kind: TopicKind = 'free') =>
  `${teamPath(team)}/${kind === 'task' ? 'task' : 'topic'}/${number}`

type FeedQuery = { from_unread?: boolean; limit?: number; after?: number; before?: number }

/** Read a task's or a free Topic with some of its Messages. */
export const readTopic = (kind: TopicKind, team: string, number: number, query: FeedQuery) =>
  kind === 'task'
    ? api.GET('/api/team/{team}/task/{number}/topic', { params: { path: { team, number }, query } })
    : api.GET('/api/team/{team}/topic/{number}', { params: { path: { team, number }, query } })

/** Write a Message into a task's or a free Topic. */
export const postMessage = (
  kind: TopicKind,
  team: string,
  number: number,
  body: Schemas['MessageIn'],
) =>
  kind === 'task'
    ? api.POST('/api/team/{team}/task/{number}/message', { params: { path: { team, number } }, body })
    : api.POST('/api/team/{team}/topic/{number}/message', { params: { path: { team, number } }, body })

/** Record how far a task's or a free Topic is read. */
export const markRead = (kind: TopicKind, team: string, number: number, upTo: number) =>
  kind === 'task'
    ? api.POST('/api/team/{team}/task/{number}/read', { params: { path: { team, number } }, body: { number: upTo } })
    : api.POST('/api/team/{team}/topic/{number}/read', { params: { path: { team, number } }, body: { number: upTo } })

/** Where a logged-out person goes to log in with a provider and come back. */
export function loginUrl(provider: string, next: string): string {
  return `/api/auth/${encodeURIComponent(provider)}/start?next=${encodeURIComponent(next)}`
}
