import { http } from './client'
import type { CustomNode, CustomNodeDependency, CustomNodeTestOutput, CustomNodeVersion, TestRun } from '@/types'

export interface CustomNodeTemplate {
  id: string
  name: string
  description: string
}

export const customNodesApi = {
  get: (id: string): Promise<CustomNode> => http.get(`/custom-nodes/${id}`),
  update: (id: string, input: Partial<CustomNode>): Promise<CustomNode> => http.patch(`/custom-nodes/${id}`, input),
  test: (id: string): Promise<CustomNodeTestOutput> => http.post(`/custom-nodes/${id}/test`),
  runTests: (id: string): Promise<TestRun> => http.post(`/custom-nodes/${id}/tests`),
  testResults: (id: string): Promise<TestRun> => http.get(`/custom-nodes/${id}/test-results`),
  addDependency: (id: string, dependency: { name: string; version: string }): Promise<CustomNodeDependency> =>
    http.post(`/custom-nodes/${id}/dependencies`, dependency),
  publish: (id: string): Promise<{ id: string; version: string; status: string }> => http.post(`/custom-nodes/${id}/publish`),
  versions: (id: string): Promise<CustomNodeVersion[]> => http.get(`/custom-nodes/${id}/versions`),
  restoreVersion: (id: string, version: string): Promise<CustomNode> => http.post(`/custom-nodes/${id}/versions/${version}/restore`),
  templates: (): Promise<CustomNodeTemplate[]> => http.get('/custom-nodes/templates'),
}
