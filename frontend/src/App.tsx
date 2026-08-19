import type { ReactNode } from 'react'
import { FlowNav } from './components/FlowNav'
import { StageOperationsPage } from './components/StageOperationsPage'
import { OverviewPage } from './components/WorkflowModal'
import { isFlowOpsPage } from './data/flowOps'
import { canonicalOpsPageId } from './features/automation/combinedAssignment'
import { AttentionProvider } from './features/automation/AttentionProvider'
import { useAttention } from './features/automation/AttentionContext'
import { attentionBannerModel } from './features/automation/liveWorkflow/attentionDisplay'
import { LiveInboxProvider } from './features/automation/liveInbox/LiveInboxProvider'
import { LiveWorkflowProvider } from './features/automation/liveWorkflow/LiveWorkflowProvider'
import { PatientProfilePage } from './features/automation/PatientProfilePage'
import { usePatientPathKey } from './features/automation/patientRoute'
import { DemoProvider } from './state/DemoContext'
import { useDemo } from './state/useDemo'

/** Scoped to the open step on a stage; overview rolls the whole pipeline up. */
function OverdueConfirmationsBanner({ stageId }: { stageId: string | null }) {
  const { state, dispatch } = useDemo()
  const { timers, openSignal } = useAttention()
  const scopedStep = stageId ? state.opsSelectedStepByStage[stageId] : undefined
  const scopedTimers = stageId
    ? Object.fromEntries(
        Object.entries(timers).filter(([, timer]) => {
          if (timer.stageId !== stageId) return false
          if (scopedStep) return timer.stepId === scopedStep
          return true
        }),
      )
    : timers
  const banner = attentionBannerModel(Object.values(scopedTimers), {
    scopeSuffix: stageId ? ' on this step' : '',
    stageScoped: Boolean(stageId),
  })
  if (!banner) return null

  return (
    <button
      type="button"
      className="overdue-confirmations-banner"
      aria-label={banner.ariaLabel}
      onClick={() => {
        openSignal(banner.target, dispatch)
        window.scrollTo({ top: 0, behavior: 'smooth' })
      }}
    >
      <span className="overdue-confirmations-banner__badge">{banner.badge}</span>
      <span className="overdue-confirmations-banner__copy">
        <strong>{banner.headline}</strong>
      </span>
      {banner.meta ? (
        <span className="overdue-confirmations-banner__meta">{banner.meta}</span>
      ) : null}
    </button>
  )
}

function Dashboard() {
  const { state } = useDemo()
  const patientKey = usePatientPathKey()
  const rawPage = state.activePage === 'operations' ? 'overview' : state.activePage
  const page = canonicalOpsPageId(rawPage)

  let body: ReactNode
  if (patientKey) body = <PatientProfilePage patientKey={patientKey} />
  else if (page === 'overview') body = <OverviewPage />
  else if (isFlowOpsPage(page)) body = <StageOperationsPage pageId={page} />
  else body = <OverviewPage />

  return (
    <div className="app-shell">
      {patientKey ? null : <FlowNav />}
      {patientKey ? null : (
        <OverdueConfirmationsBanner
          stageId={isFlowOpsPage(page) ? page : null}
        />
      )}
      {body}
    </div>
  )
}

export default function App() {
  return (
    <DemoProvider>
      <LiveInboxProvider>
        <LiveWorkflowProvider>
          <AttentionProvider>
            <Dashboard />
          </AttentionProvider>
        </LiveWorkflowProvider>
      </LiveInboxProvider>
    </DemoProvider>
  )
}
