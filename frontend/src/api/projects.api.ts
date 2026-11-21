import { http } from './client'
import type { ActivityItem, DashboardData, Project, SearchResult, SystemStatus, Workspace } from '@/types'

export const projectsApi = {
  list: (): Promise<Project[]> => http.get('/projects'),
  get: (id: string): Promise<Project> => http.get(`/projects/${id}`),
  create: (input: { name: string; description?: string }): Promise<Project> => http.post('/projects', input),
  update: (id: string, input: Partial<Project>): Promise<Project> => http.patch(`/projects/${id}`, input),
  remove: (id: string): Promise<{ ok: boolean }> => http.delete(`/projects/${id}`),
  dashboard: (): Promise<DashboardData> => http.get('/dashboard'),
  activity: (): Promise<ActivityItem[]> => http.get('/activity'),
  workspace: (): Promise<Workspace> => http.get('/workspace'),
  systemStatus: (): Promise<SystemStatus> => http.get('/system/status'),
  search: (query: string): Promise<SearchResult[]> => http.get(`/search?q=${encodeURIComponent(query)}`),
}
