import { buildPatientJourney } from '../data/patientJourney'
import type { FlowOpsPageId } from '../data/flowOps'
import { useDemo } from '../state/useDemo'
import './StageJourneyBanner.css'

/** Shows the active journey patient when their current step is on this stage. */
export function StageJourneyBanner({ pageId }: { pageId: FlowOpsPageId }) {
  const { state, dispatch } = useDemo()
  const journey = buildPatientJourney(state.workflowScenarios, state.selectedJourneyPatientId)
  const currentOnPage = journey.current?.stage === pageId
  const focusOnPage = journey.steps.some(
    (step) => step.caseId === state.journeyFocusCaseId && step.stage === pageId,
  )

  if (!currentOnPage && !focusOnPage) return null

  const step = journey.current ?? journey.steps.find((item) => item.caseId === state.journeyFocusCaseId)
  if (!step) return null

  const next = journey.steps.find((item) => !item.done && item.caseId !== step.caseId)
  const done = step.done || journey.complete

  return (
    <section className="stage-journey-banner panel" aria-label="Active patient walkthrough">
      <div>
        <p className="stage-journey-banner__eyebrow">Walking this patient</p>
        <h3>{journey.patientName}</h3>
        <p className="muted">
          {journey.scenarioLabel}
          <span aria-hidden="true"> · </span>
          {done ? step.resultLabel : step.actionLabel}
          {!done && next ? (
            <>
              <span aria-hidden="true"> · </span>
              then {next.stageLabel}
            </>
          ) : null}
        </p>
      </div>
      <button
        type="button"
        className="btn btn-primary"
        disabled={done || !journey.current}
        onClick={() => {
          dispatch({ type: 'ADVANCE_JOURNEY' })
          window.scrollTo({ top: 0, behavior: 'smooth' })
        }}
      >
        {done ? 'Stage complete' : `${step.actionLabel} →`}
      </button>
    </section>
  )
}
