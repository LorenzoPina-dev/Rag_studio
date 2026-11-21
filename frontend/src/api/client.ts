/**
 * Centralized HTTP client.
 *
 * The app can run against a typed in-memory mock adapter or the FastAPI
 * backend through the same interface. This repo's `.env` sets
 * VITE_USE_MOCKS=false for local development against the real backend;
 * VITE_USE_MOCKS=true re-enables the mock adapter. UI code never talks to the
 * network directly — always through the domain API modules.
 */
import { mockRequest } from './mock/adapter'

const API_BASE = import.meta.env.VITE_API_URL ?? '/api/v1'
const USE_MOCKS = (import.meta.env.VITE_USE_MOCKS ?? 'true') !== 'false'

export const isMockMode = USE_MOCKS

export class ApiError extends Error {
  status: number
  detail?: unknown

  constructor(status: number, message: string, detail?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

type Method = 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'

async function request<T>(method: Method, path: string, body?: unknown): Promise<T> {
  if (USE_MOCKS) {
    return mockRequest<T>(method, path, body)
  }

  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  })

  if (!response.ok) {
    let detail: unknown
    try {
      detail = await response.json()
    } catch {
      detail = await response.text()
    }
    const message =
      typeof detail === 'object' && detail && 'detail' in detail
        ? String((detail as { detail: unknown }).detail)
        : `Request failed with ${response.status}`
    throw new ApiError(response.status, message, detail)
  }

  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export const http = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body),
  patch: <T>(path: string, body?: unknown) => request<T>('PATCH', path, body),
  put: <T>(path: string, body?: unknown) => request<T>('PUT', path, body),
  delete: <T>(path: string) => request<T>('DELETE', path),
}

export const apiBaseUrl = API_BASE
