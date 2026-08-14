import type { ReactNode } from 'react'
import { FlowNav } from './components/FlowNav'
import { StageOperationsPage } from './components/StageOperationsPage'
import { OverviewPage } from './components/WorkflowModal'
import { isFlowOpsPage } from './data/flowOps'
import { PatientProfilePage } from './features/automation/PatientProfilePage'
import { usePatientPathKey } from './features/automation/patientRoute'
import { DemoProvider } from './state/DemoContext'
import { useDemo } from './state/useDemo'

function Dashboard() {
  const { state } = useDemo()
  const patientKey = usePatientPathKey()
  const page = state.activePage === 'operations' ? 'overview' : state.activePage

  let body: ReactNode
  if (patientKey) body = <PatientProfilePage patientKey={patientKey} />
  else if (page === 'overview') body = <OverviewPage />
  else if (isFlowOpsPage(page)) body = <StageOperationsPage pageId={page} />
  else body = <OverviewPage />

  return (
    <div className="app-shell">
      {patientKey ? null : <FlowNav />}
      {body}
    </div>
  )
}

export default function App() {
  return (
    <DemoProvider>
      <Dashboard />
    </DemoProvider>
  )
}
