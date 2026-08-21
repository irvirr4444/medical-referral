import type { ReactNode } from 'react'
import { Breadcrumbs } from './components/Breadcrumbs'
import { FlowNav } from './components/FlowNav'
import { StageOperationsPage } from './components/StageOperationsPage'
import { OverviewPage } from './components/WorkflowModal'
import { canonicalOpsPageId } from './features/automation/combinedAssignment'
import { isFlowOpsPage } from './data/flowOps'
import { PatientProfilePage } from './features/automation/PatientProfilePage'
import { usePatientPathKey } from './features/automation/patientRoute'
import { DemoProvider } from './state/DemoContext'
import { useDemo } from './state/useDemo'

function Dashboard() {
  const { state } = useDemo()
  const patientKey = usePatientPathKey()
  const page = state.activePage === 'operations' ? 'overview' : state.activePage
  const opsPage = isFlowOpsPage(page) ? canonicalOpsPageId(page) : null

  let body: ReactNode
  if (patientKey) body = <PatientProfilePage patientKey={patientKey} />
  else if (page === 'overview') body = <OverviewPage />
  else if (opsPage) body = <StageOperationsPage pageId={opsPage} />
  else body = <OverviewPage />

  return (
    <div className="app-shell">
      {patientKey ? null : <FlowNav />}
      {patientKey ? null : <Breadcrumbs />}
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
