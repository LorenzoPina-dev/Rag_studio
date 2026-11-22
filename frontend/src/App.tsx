import * as React from 'react'
import { Route, Routes } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'

// Route-level code splitting keeps the editor, charts and Monaco out of the
// initial bundle: each page is fetched only when its route is visited.
const DashboardPage = React.lazy(() => import('@/pages/DashboardPage').then((m) => ({ default: m.DashboardPage })))
const ProjectsPage = React.lazy(() => import('@/pages/ProjectsPage').then((m) => ({ default: m.ProjectsPage })))
const PipelinesPage = React.lazy(() => import('@/pages/PipelinesPage').then((m) => ({ default: m.PipelinesPage })))
const PipelineEditorPage = React.lazy(() => import('@/pages/PipelineEditorPage').then((m) => ({ default: m.PipelineEditorPage })))
const NodeLibraryPage = React.lazy(() => import('@/pages/NodeLibraryPage').then((m) => ({ default: m.NodeLibraryPage })))
const TechniquesPage = React.lazy(() => import('@/pages/TechniquesPage').then((m) => ({ default: m.TechniquesPage })))
const CustomNodePage = React.lazy(() => import('@/pages/CustomNodePage').then((m) => ({ default: m.CustomNodePage })))
const DatasetsPage = React.lazy(() => import('@/pages/DatasetsPage').then((m) => ({ default: m.DatasetsPage })))
const ModelsPage = React.lazy(() => import('@/pages/ModelsPage').then((m) => ({ default: m.ModelsPage })))
const ExecutionPage = React.lazy(() => import('@/pages/ExecutionPage').then((m) => ({ default: m.ExecutionPage })))
const ResultsPage = React.lazy(() => import('@/pages/ResultsPage').then((m) => ({ default: m.ResultsPage })))
const EvaluationPage = React.lazy(() => import('@/pages/EvaluationPage').then((m) => ({ default: m.EvaluationPage })))
const ExperimentsPage = React.lazy(() => import('@/pages/ExperimentsPage').then((m) => ({ default: m.ExperimentsPage })))
const SettingsPage = React.lazy(() => import('@/pages/SettingsPage').then((m) => ({ default: m.SettingsPage })))
const NotFoundPage = React.lazy(() => import('@/pages/NotFoundPage').then((m) => ({ default: m.NotFoundPage })))

function RouteFallback() {
  return (
    <div className="flex min-h-[40vh] items-center justify-center">
      <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-dim">Loading view…</span>
    </div>
  )
}

export function App() {
  return (
    <React.Suspense fallback={<RouteFallback />}>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/projects" element={<ProjectsPage />} />
          <Route path="/pipelines" element={<PipelinesPage />} />
          <Route path="/pipelines/:pipelineId" element={<PipelineEditorPage />} />
          <Route path="/nodes" element={<NodeLibraryPage />} />
          <Route path="/techniques" element={<TechniquesPage />} />
          <Route path="/custom-nodes" element={<CustomNodePage />} />
          <Route path="/datasets" element={<DatasetsPage />} />
          <Route path="/models" element={<ModelsPage />} />
          <Route path="/runs/:runId" element={<ExecutionPage />} />
          <Route path="/runs/:runId/results" element={<ResultsPage />} />
          <Route path="/evaluation" element={<EvaluationPage />} />
          <Route path="/experiments" element={<ExperimentsPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </React.Suspense>
  )
}
