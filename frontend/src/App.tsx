import { Route, Routes } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'
import { DashboardPage } from '@/pages/DashboardPage'
import { ProjectsPage } from '@/pages/ProjectsPage'
import { PipelinesPage } from '@/pages/PipelinesPage'
import { PipelineEditorPage } from '@/pages/PipelineEditorPage'
import { NodeLibraryPage } from '@/pages/NodeLibraryPage'
import { TechniquesPage } from '@/pages/TechniquesPage'
import { CustomNodePage } from '@/pages/CustomNodePage'
import { DatasetsPage } from '@/pages/DatasetsPage'
import { ModelsPage } from '@/pages/ModelsPage'
import { ExecutionPage } from '@/pages/ExecutionPage'
import { ResultsPage } from '@/pages/ResultsPage'
import { EvaluationPage } from '@/pages/EvaluationPage'
import { ExperimentsPage } from '@/pages/ExperimentsPage'
import { SettingsPage } from '@/pages/SettingsPage'
import { NotFoundPage } from '@/pages/NotFoundPage'

export function App() {
  return (
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
  )
}
