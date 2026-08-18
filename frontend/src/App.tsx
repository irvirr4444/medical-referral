import type { ReactNode } from 'react'
import { FlowNav } from './components/FlowNav'
import { StageOperationsPage } from './components/StageOperationsPage'
import { OverviewPage } from './components/WorkflowModal'
import { canonicalOpsPageId } from './features/automation/combinedAssignment'
import { isFlowOpsPage } from './data/flowOps'
import {
  actionLabel,
  attentionSummary,
} from './features/automation/confirmationTimers'
import { PatientProfilePage } from './features/automation/PatientProfilePage'
import { usePatientPathKey } from './features/automation/patientRoute'
import { DemoProvider } from './state/DemoContext'
import { useDemo } from './state/useDemo'

/** Scoped to the open step on a stage; overview rolls the whole pipeline up. */
function OverdueConfirmationsBanner({ stageId }: { stageId: string | null }) {
  const { state, dispatch } = useDemo()
  const selectedStep = stageId
    ? state.opsSelectedStepByStage[stageId]
    : undefined
  const timers = stageId
    ? Object.fromEntries(
        Object.entries(state.actionTimers).filter(([, timer]) => {
          if (timer.stageId !== stageId) return false
          if (selectedStep) return timer.stepId === selectedStep
          return true
        }),
      )
    : state.actionTimers
  const { overdue, warning, oldest } = attentionSummary(timers)
  if (!oldest) return null

  const scope = stageId ? ' on this step' : ''
  const headline =
    overdue.length === 1
      ? `1 confirmation needs immediate attention${scope}`
      : `${overdue.length} confirmations need immediate attention${scope}`
  const stages = [...new Set(overdue.map((timer) => timer.stageId))]

  return (
    <button
      type="button"
      className="overdue-confirmations-banner"
      aria-label={`${headline}. Oldest is ${actionLabel(oldest.actionId)} for ${
        oldest.patientName
      }.`}
      onClick={() => {
        if (stageId) {
          dispatch({
            type: 'SCOPE_OPS_PATIENT',
            patientId: oldest.patientId,
            patientName: oldest.patientName,
          })
        } else {
          dispatch({ type: 'SET_ACTIVE_PAGE', page: oldest.stageId })
        }
        window.scrollTo({ top: 0, behavior: 'smooth' })
      }}
    >
      <span className="overdue-confirmations-banner__badge">Overdue</span>
      <span className="overdue-confirmations-banner__copy">
        <strong>{headline}</strong>
      </span>
      <span className="overdue-confirmations-banner__meta">
        {stageId
          ? `${overdue.length} overdue`
          : `${stages.length} ${stages.length === 1 ? 'stage' : 'stages'}`}
        {warning.length ? ` · ${warning.length} due soon` : ''}
      </span>
    </button>
  )
}

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
      {patientKey ? null : (
        <OverdueConfirmationsBanner stageId={opsPage} />
      )}
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
