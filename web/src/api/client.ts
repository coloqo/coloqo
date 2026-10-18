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
export async function uploadFile(topicId: number, file: File): Promise<FileInfo> {
  // The upload endpoint takes a raw body, which the OpenAPI document does not
  // describe, so it goes through plain fetch.
  const response = await fetch(`/api/topics/${topicId}/files`, {
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

/** Where a logged-out person goes to log in with a provider and come back. */
export function loginUrl(provider: string, next: string): string {
  return `/api/auth/${encodeURIComponent(provider)}/start?next=${encodeURIComponent(next)}`
}
