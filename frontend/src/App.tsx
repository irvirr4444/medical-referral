import type { ReactNode } from 'react'
import { Breadcrumbs } from './components/Breadcrumbs'
import { FlowNav } from './components/FlowNav'
import { StageOperationsPage } from './components/StageOperationsPage'
import { OverviewPage } from './components/WorkflowModal'
import { isFlowOpsPage } from './data/flowOps'
import { DemoProvider } from './state/DemoContext'
import { useDemo } from './state/useDemo'

function Dashboard() {
  const { state } = useDemo()
  const page = state.activePage === 'operations' ? 'overview' : state.activePage

  let body: ReactNode
  if (page === 'overview') body = <OverviewPage />
  else if (isFlowOpsPage(page)) body = <StageOperationsPage pageId={page} />
  else body = <OverviewPage />

  return (
    <div className="app-shell">
      <FlowNav />
      <Breadcrumbs />
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
