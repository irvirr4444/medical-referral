import type { ReactNode } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { FlowNav } from './components/FlowNav'
import { PatientProfilePage } from './components/PatientProfilePage'
import { StageOperationsPage } from './components/StageOperationsPage'
import { OverviewPage } from './components/WorkflowModal'
import { isFlowOpsPage } from './data/flowOps'
import { DemoProvider } from './state/DemoContext'
import { useDemo } from './state/useDemo'

function ConsoleShell() {
  const { state } = useDemo()
  const page = state.activePage === 'operations' ? 'overview' : state.activePage

  let body: ReactNode
  if (page === 'overview') body = <OverviewPage />
  else if (isFlowOpsPage(page)) body = <StageOperationsPage pageId={page} />
  else body = <OverviewPage />

  return (
    <div className="app-shell">
      <FlowNav />
      {body}
    </div>
  )
}

function PatientProfileShell() {
  return (
    <div className="app-shell patient-profile-shell">
      <PatientProfilePage />
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <DemoProvider>
        <Routes>
          <Route path="/" element={<ConsoleShell />} />
          <Route path="/patients/:profileId" element={<PatientProfileShell />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </DemoProvider>
    </BrowserRouter>
  )
}
